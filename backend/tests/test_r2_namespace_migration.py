from __future__ import annotations

import gzip
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.model_registry import register_database_models
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.storage.backends.r2 import InMemoryR2Storage
from novelai.storage.content_addressing import canonical_json_bytes, deterministic_gzip, sha256_hex
from novelai.storage.r2_namespace_migration import (
    R2NovelNamespaceMigrator,
    delete_migrated_source_namespace,
)


def _put_json(storage: InMemoryR2Storage, key: str, payload: dict) -> tuple[str, str]:
    logical = canonical_json_bytes(payload)
    digest = sha256_hex(logical)
    storage.put_immutable(key, deterministic_gzip(logical), logical_sha256=digest)
    return key, digest


def _load_json(storage: InMemoryR2Storage, key: str) -> dict:
    return json.loads(gzip.decompress(storage.load(key)).decode("utf-8"))


def test_namespace_migration_rekeys_nested_references_and_db_pointers() -> None:
    register_database_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    storage = InMemoryR2Storage()
    try:
        slug = "old-slug"
        prefix = f"novels/{slug}"
        asset_data = b"image-bytes"
        asset_key = f"{prefix}/assets/{sha256_hex(asset_data)}.png"
        storage.put_immutable(
            asset_key,
            asset_data,
            logical_sha256=sha256_hex(asset_data),
            content_type="image/png",
        )
        raw_payload = {
            "schema_version": 2,
            "chapter_id": "ch1",
            "raw": {"text": "source", "paragraphs": ["source"]},
            "images": [{"storage_key": asset_key}],
        }
        raw_key, raw_hash = _put_json(storage, f"{prefix}/chapters/ch1/placeholder.json.gz", raw_payload)
        translated_payload = {"chapter_id": "ch1", "text": "translation", "version_id": "v1"}
        translated_key, translated_hash = _put_json(
            storage,
            f"{prefix}/translations/ch1/placeholder.json.gz",
            translated_payload,
        )
        media_payload = {"chapter_id": "ch1", "state": {"images": [{"storage_key": asset_key}]}}
        media_key, media_hash = _put_json(storage, f"{prefix}/media/ch1/placeholder.json.gz", media_payload)
        manifest = {
            "schema_version": 1,
            "novel_id": slug,
            "generation_id": "g1",
            "chapters": [
                {
                    "chapter_id": "ch1",
                    "raw_storage_key": raw_key,
                    "raw_content_hash": raw_hash,
                    "translated_storage_key": translated_key,
                    "translated_content_hash": translated_hash,
                    "media_storage_key": media_key,
                    "media_content_hash": media_hash,
                    "assets": [asset_key],
                }
            ],
        }
        manifest_key, _ = _put_json(storage, f"{prefix}/generations/g1.json.gz", manifest)

        novel = Novel(
            slug=slug,
            title="Old slug novel",
            language="ja",
            publication_status="published",
            active_generation_id="g1",
            active_generation_storage_key=manifest_key,
            cover_storage_key=asset_key,
            metadata_json={"cover_storage_key": asset_key},
        )
        session.add(novel)
        session.flush()
        chapter = Chapter(
            novel_id=novel.id,
            logical_chapter_id="ch1",
            chapter_number=1,
            title="Chapter 1",
            raw_storage_key=raw_key,
            raw_content_hash=raw_hash,
            translated_storage_key=translated_key,
            translated_content_hash=translated_hash,
            media_storage_key=media_key,
            media_content_hash=media_hash,
            translation_versions_json=[
                {"version_id": "v1", "storage_key": translated_key, "content_hash": translated_hash}
            ],
        )
        session.add(chapter)
        session.commit()

        dry_run = R2NovelNamespaceMigrator(storage=storage, db_session=session).migrate_novel(slug, dry_run=True)
        assert dry_run.source_keys
        assert dry_run.destination_keys
        assert storage.list_keys("novels/1", recursive=True) == []
        assert session.query(Novel).one().active_generation_storage_key == manifest_key

        result = R2NovelNamespaceMigrator(storage=storage, db_session=session).migrate_novel(slug, dry_run=False)
        session.commit()
        assert result.storage_novel_id == "1"
        assert all(key.startswith("novels/1/") for key in result.destination_keys)
        migrated_novel = session.query(Novel).one()
        migrated_chapter = session.query(Chapter).one()
        active_generation_key = migrated_novel.active_generation_storage_key
        cover_key = migrated_novel.cover_storage_key
        raw_key = migrated_chapter.raw_storage_key
        versions = migrated_chapter.translation_versions_json
        assert isinstance(active_generation_key, str) and active_generation_key.startswith("novels/1/generations/")
        assert isinstance(cover_key, str) and cover_key.startswith("novels/1/assets/")
        assert isinstance(raw_key, str) and raw_key.startswith("novels/1/chapters/ch1/")
        assert isinstance(migrated_chapter.raw_content_hash, str)
        assert migrated_chapter.raw_content_hash == raw_key.rsplit("/", 1)[-1][:-8]
        assert isinstance(versions, list) and versions and isinstance(versions[0], dict)
        version_storage_key = versions[0].get("storage_key")
        assert isinstance(version_storage_key, str)
        assert version_storage_key.startswith("novels/1/translations/")
        assert versions[0]["content_hash"] == migrated_chapter.translated_content_hash

        assert isinstance(active_generation_key, str)
        migrated_manifest = _load_json(storage, active_generation_key)
        manifest_chapter = migrated_manifest["chapters"][0]
        assert migrated_manifest["novel_id"] == "1"
        assert migrated_manifest["public_slug"] == slug
        assert manifest_chapter["raw_storage_key"] == raw_key
        assert manifest_chapter["raw_content_hash"] == migrated_chapter.raw_content_hash
        assert isinstance(raw_key, str)
        migrated_raw = _load_json(storage, raw_key)
        assert migrated_raw["images"][0]["storage_key"].startswith("novels/1/assets/")

        assert delete_migrated_source_namespace(storage, result) == len(result.source_keys)
        assert storage.list_keys(prefix, recursive=True) == []
    finally:
        session.close()
        Base.metadata.drop_all(engine)
