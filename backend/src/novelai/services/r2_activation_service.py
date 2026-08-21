"""Immutable R2 generation publication with PostgreSQL activation truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.storage.artifacts import R2ArtifactRepository
from novelai.storage.service import StorageService


class GenerationConflictError(RuntimeError):
    """Raised when another writer changed the active generation first."""


class InvalidGenerationManifestError(ValueError):
    """Raised when a manifest is not safe to publish."""


@dataclass(frozen=True, slots=True)
class GenerationActivationResult:
    novel_id: str
    generation_id: str
    manifest_key: str
    chapter_count: int


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidGenerationManifestError(f"Manifest field {field} must be a non-empty string")
    return value.strip()


class R2GenerationActivationService:
    """Publish immutable objects, then atomically activate their DB references.

    The caller owns the surrounding SQLAlchemy transaction. The service never
    writes an active pointer into R2 and never lists an R2 prefix during a
    normal activation.
    """

    def __init__(self, *, storage: StorageService, db_session: Session) -> None:
        self.storage = storage
        self.db_session = db_session
        self.repository = R2ArtifactRepository(storage.r2_backend)

    def activate(
        self,
        *,
        novel_id: str,
        generation_id: str,
        manifest: dict[str, Any],
        expected_generation_id: str | None,
    ) -> GenerationActivationResult:
        if _required_string(manifest.get("novel_id"), "novel_id") != novel_id:
            raise InvalidGenerationManifestError("Manifest novel_id does not match the activation request")
        if _required_string(manifest.get("generation_id"), "generation_id") != generation_id:
            raise InvalidGenerationManifestError("Manifest generation_id does not match the activation request")
        chapters = manifest.get("chapters")
        if not isinstance(chapters, list):
            raise InvalidGenerationManifestError("Manifest chapters must be a list")

        references: list[tuple[str, str, dict[str, Any]]] = []
        required_prefix = f"novels/{novel_id}/"
        for item in chapters:
            if not isinstance(item, dict):
                raise InvalidGenerationManifestError("Manifest chapter entries must be objects")
            chapter_id = _required_string(item.get("chapter_id"), "chapters[].chapter_id")
            key_prefixes = {
                "raw_storage_key": f"{required_prefix}chapters/{chapter_id}/",
                "translated_storage_key": f"{required_prefix}translations/{chapter_id}/",
                "media_storage_key": f"{required_prefix}media/{chapter_id}/",
            }
            hash_fields = {
                "raw_storage_key": "raw_content_hash",
                "translated_storage_key": "translated_content_hash",
                "media_storage_key": "media_content_hash",
            }
            for field in ("raw_storage_key", "translated_storage_key", "media_storage_key"):
                key = item.get(field)
                if key is None:
                    continue
                key = _required_string(key, f"chapters[].{field}")
                if not key.startswith(key_prefixes[field]) or not key.endswith(".json.gz"):
                    raise InvalidGenerationManifestError(f"Manifest contains an invalid immutable key: {key}")
                try:
                    object_metadata = self.storage.r2_backend.head(key)
                except FileNotFoundError as exc:
                    raise InvalidGenerationManifestError(f"Manifest references a missing R2 object: {key}") from exc
                expected_hash = item.get(hash_fields[field])
                if expected_hash is not None and expected_hash != object_metadata.logical_sha256:
                    raise InvalidGenerationManifestError(f"Manifest checksum does not match R2 metadata: {key}")
            assets = item.get("assets")
            if assets is not None:
                if not isinstance(assets, list):
                    raise InvalidGenerationManifestError("Manifest chapter assets must be a list")
                for asset_key in assets:
                    asset_key = _required_string(asset_key, "chapters[].assets[]")
                    if not asset_key.startswith(f"{required_prefix}assets/"):
                        raise InvalidGenerationManifestError(f"Manifest contains an invalid asset key: {asset_key}")
                    filename = asset_key.rsplit("/", 1)[-1]
                    if "." not in filename:
                        raise InvalidGenerationManifestError(f"Manifest contains an invalid asset key: {asset_key}")
                    asset_hash, extension = filename.rsplit(".", 1)
                    if (
                        len(asset_hash) != 64
                        or any(character not in "0123456789abcdef" for character in asset_hash)
                        or not extension
                    ):
                        raise InvalidGenerationManifestError(f"Manifest contains an invalid asset key: {asset_key}")
                    try:
                        asset_metadata = self.storage.r2_backend.head(asset_key)
                    except FileNotFoundError as exc:
                        raise InvalidGenerationManifestError(
                            f"Manifest references a missing R2 asset: {asset_key}"
                        ) from exc
                    if asset_metadata.logical_sha256 and asset_metadata.logical_sha256 != asset_hash:
                        raise InvalidGenerationManifestError(
                            f"Manifest asset checksum does not match R2 metadata: {asset_key}"
                        )
            references.append((chapter_id, novel_id, item))

        stored = self.repository.put_generation_manifest(
            novel_id=novel_id,
            generation_id=generation_id,
            payload=manifest,
        )

        novel = self.db_session.query(Novel).filter(Novel.slug == novel_id).with_for_update().one_or_none()
        if novel is None:
            raise InvalidGenerationManifestError(f"Novel does not exist: {novel_id}")
        if novel.active_generation_id != expected_generation_id:
            raise GenerationConflictError(
                f"Active generation changed for {novel_id}: expected {expected_generation_id!r}, "
                f"found {novel.active_generation_id!r}"
            )

        chapter_rows = {
            chapter.logical_chapter_id: chapter
            for chapter in self.db_session.query(Chapter).filter(Chapter.novel_id == novel.id).all()
        }
        for chapter_id, _, item in references:
            chapter = chapter_rows.get(chapter_id)
            if chapter is None:
                raise InvalidGenerationManifestError(f"Manifest references an unknown chapter: {chapter_id}")
            for field in ("raw_storage_key", "translated_storage_key", "media_storage_key"):
                if field in item:
                    setattr(chapter, field, item.get(field))
            for field in ("raw_content_hash", "translated_content_hash", "media_content_hash"):
                if field in item:
                    setattr(chapter, field, item.get(field))
            if item.get("raw_storage_key"):
                chapter.raw_status = "fetched"
            if item.get("translated_storage_key"):
                chapter.translation_status = "translated"
            self.db_session.add(chapter)

        novel.active_generation_id = generation_id
        novel.active_generation_storage_key = stored.key
        self.db_session.add(novel)
        self.db_session.flush()
        return GenerationActivationResult(
            novel_id=novel_id,
            generation_id=generation_id,
            manifest_key=stored.key,
            chapter_count=len(references),
        )
