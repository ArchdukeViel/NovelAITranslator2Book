from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.engine import dispose_engines, session_scope
from novelai.db.model_registry import register_database_models
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration.crawler import _scrape_chapters_r2_impl
from novelai.storage.backends.r2 import R2Storage
from novelai.storage.service import StorageService

boto3 = pytest.importorskip("boto3")
pytest.importorskip("moto")


@pytest.fixture()
def r2_catalog(tmp_path, monkeypatch):
    from moto import mock_aws

    register_database_models()
    database_url = f"sqlite:///{tmp_path / 'r2-catalog.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    dispose_engines()
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="dokushodo")
        backend = R2Storage(bucket="dokushodo", endpoint_url=None, client=client)
        yield StorageService(backend=backend), client
    dispose_engines()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_r2_dispatch_stores_catalog_and_exact_artifacts(r2_catalog) -> None:
    storage, client = r2_catalog
    storage.save_metadata(
        "novel-r2",
        {
            "title": "Original title",
            "translated_title": "Translated title",
            "source_key": "stub",
            "chapters": [{"id": "c1", "num": 1, "title": "Chapter 1", "url": "https://example.test/c1"}],
        },
    )
    storage.save_chapter(
        "novel-r2",
        "c1",
        "source text",
        title="Chapter 1",
        source_key="stub",
        source_url="https://example.test/c1",
        source_blocks=[{"type": "line", "text": "source text"}],
    )
    storage.save_translated_chapter(
        "novel-r2",
        "c1",
        "translated text",
        provider_key="gemini",
        provider_model="gemini-test",
        source_hash=storage._hash_text("source text"),
    )

    raw = storage.load_chapter("novel-r2", "c1")
    translated = storage.load_translated_chapter("novel-r2", "c1")
    assert raw is not None and raw["text"] == "source text"
    assert translated is not None and translated["text"] == "translated text"
    storage.save_edited_translation(
        "novel-r2",
        "c1",
        "edited text",
        editor="owner",
        note="R2 editor test",
        glossary_revision=0,
    )
    versions = storage.list_translated_chapter_versions("novel-r2", "c1")
    assert len(versions) == 2
    assert versions[-1]["text"] == "edited text"
    assert versions[-1]["active"] is True
    assert storage.load_translation_edit_history("novel-r2", "c1")[0]["action"] == "manual_edit"
    assert storage.activate_translated_chapter_version("novel-r2", "c1", versions[0]["version_id"])
    assert storage.load_translated_chapter("novel-r2", "c1")["text"] == "translated text"
    assert storage.load_metadata("novel-r2")["chapters"][0]["id"] == "c1"

    keys = client.list_objects_v2(Bucket="dokushodo").get("Contents", [])
    object_keys = [item["Key"] for item in keys]
    assert object_keys
    storage_novel_id = storage.resolve_storage_novel_id("novel-r2")
    assert all(key.startswith(f"novels/{storage_novel_id}/") for key in object_keys)
    assert not any(key.endswith("metadata.json") or key.endswith("active_generation.json") for key in object_keys)


def test_r2_crawler_activates_db_generation_without_pointer_object(r2_catalog) -> None:
    storage, client = r2_catalog
    chapter_url = "https://example.test/novel-r2/c1"
    storage.save_metadata(
        "novel-r2",
        {
            "title": "Original title",
            "source_key": "stub",
            "chapters": [{"id": "c1", "num": 1, "title": "Chapter 1", "url": chapter_url}],
        },
    )

    class Source:
        async def fetch_chapter_payload(self, url, *, on_retry=None):
            assert url == chapter_url
            return {"text": "crawled source", "images": []}

    orchestrator = SimpleNamespace(
        storage=storage,
        _source_factory=lambda key: Source(),
        _chapter_content_signature=NovelOrchestrationService._chapter_content_signature,
        _infer_source_language=NovelOrchestrationService._infer_source_language,
    )
    result = asyncio.run(
        _scrape_chapters_r2_impl(
            orchestrator,
            "stub",
            "novel-r2",
            "all",
            "update",
            None,
            None,
            None,
            None,
        )
    )

    assert result["succeeded"] == 1
    assert result["failed"] == 0
    object_count_after_first = len(client.list_objects_v2(Bucket="dokushodo").get("Contents", []))
    with session_scope() as session:
        novel = session.query(Novel).filter_by(slug="novel-r2").one()
        chapter = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="c1").one()
        assert novel.active_generation_id == result["generation_id"]
        assert novel.active_generation_storage_key == f"novels/{novel.id}/generations/{result['generation_id']}.json.gz"
        assert chapter.raw_storage_key and chapter.raw_storage_key.startswith(f"novels/{novel.id}/chapters/c1/")

    second_result = asyncio.run(
        _scrape_chapters_r2_impl(
            orchestrator,
            "stub",
            "novel-r2",
            "all",
            "update",
            None,
            None,
            None,
            None,
        )
    )
    assert second_result["no_op"] is True
    assert second_result["generation_id"] == result["generation_id"]
    assert len(client.list_objects_v2(Bucket="dokushodo").get("Contents", [])) == object_count_after_first

    object_keys = [item["Key"] for item in client.list_objects_v2(Bucket="dokushodo").get("Contents", [])]
    assert any("/generations/" in key for key in object_keys)
    assert not any(key.endswith("active_generation.json") for key in object_keys)


def test_r2_document_import_activates_immutable_generation(r2_catalog) -> None:
    from novelai.inputs.models import ImportedDocument, ImportedUnit
    from novelai.services.orchestration.importer import _import_document_r2

    storage, client = r2_catalog

    class Adapter:
        key = "web"

        def list_units(self, document):
            return document.units

        async def load_assets(self, document, unit):
            return unit.images

    document = ImportedDocument(
        adapter_key="web",
        origin_type="url",
        origin_uri_or_path="https://example.com/story",
        document_type="web_novel",
        title="Imported story",
        source_language="English",
        units=(
            ImportedUnit(
                unit_id="part-1",
                import_order=1,
                title="Part 1",
                text="Imported source text",
                source_ref="https://example.com/story/1",
            ),
        ),
    )
    orchestrator = SimpleNamespace(storage=storage)
    result = asyncio.run(_import_document_r2(orchestrator, Adapter(), document, "novel-import"))

    assert result["title"] == "Imported story"
    with session_scope() as session:
        novel = session.query(Novel).filter_by(slug="novel-import").one()
        chapter = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="part-1").one()
        assert novel.active_generation_id
        assert chapter.raw_storage_key and chapter.raw_storage_key.startswith(f"novels/{novel.id}/chapters/part-1/")
        assert chapter.media_storage_key and chapter.media_storage_key.startswith(f"novels/{novel.id}/media/part-1/")

    object_keys = [item["Key"] for item in client.list_objects_v2(Bucket="dokushodo").get("Contents", [])]
    assert any("/generations/" in key for key in object_keys)
    assert not any(key.endswith("metadata.json") or key.endswith("active_generation.json") for key in object_keys)


def test_r2_runtime_state_stays_outside_the_application_bucket(r2_catalog, tmp_path, monkeypatch) -> None:
    storage, client = r2_catalog
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(settings, "RUNTIME_DIR", runtime_root)

    saved = storage.save_scheduler_state("job-1", [{"chapter_id": "c1", "status": "pending"}])

    assert saved["job_id"] == "job-1"
    assert (runtime_root / "traceability" / "scheduler_states.json").exists()
    object_keys = [item["Key"] for item in client.list_objects_v2(Bucket="dokushodo").get("Contents", [])]
    assert not any(key.startswith("runtime/") for key in object_keys)


def test_r2_glossary_api_uses_postgresql_not_an_object(r2_catalog) -> None:
    storage, client = r2_catalog
    storage.save_metadata("novel-glossary", {"title": "Glossary novel", "chapters": []})

    marker = storage.save_glossary(
        "novel-glossary",
        [{"source": "勇者", "target": "hero", "status": "approved", "confidence": 0.9}],
    )

    assert marker.as_posix() == "r2:glossary/novel-glossary"
    entries = storage.load_glossary("novel-glossary")
    assert entries[0]["source"] == "勇者"
    assert entries[0]["target"] == "hero"
    assert entries[0]["status"] == "approved"
    object_keys = [item["Key"] for item in client.list_objects_v2(Bucket="dokushodo").get("Contents", [])]
    assert not any("glossary" in key for key in object_keys)
