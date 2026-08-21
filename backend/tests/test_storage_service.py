"""StorageService contracts for the R2-only architecture."""

from __future__ import annotations

from uuid import uuid4

import pytest

from novelai.config.settings import settings
from novelai.storage.service import StorageService


@pytest.fixture
def storage(tmp_path) -> StorageService:
    return StorageService(tmp_path)


def _novel_id() -> str:
    return f"r2-service-{uuid4().hex}"


def test_metadata_and_raw_chapter_use_postgres_and_exact_r2_artifact(storage: StorageService) -> None:
    novel_id = _novel_id()
    storage.save_metadata(
        novel_id,
        {
            "title": "R2 novel",
            "source_key": "fixture",
            "chapters": [{"id": "c1", "num": 1, "title": "Chapter 1"}],
        },
    )
    marker = storage.save_chapter(novel_id, "c1", "source text", title="Chapter 1", source_key="fixture")

    assert marker.as_posix() == f"r2:chapter/{novel_id}/c1"
    loaded = storage.load_chapter(novel_id, "c1")
    assert loaded is not None and loaded["text"] == "source text"
    keys = storage.list_keys_under(f"novels/{novel_id}")
    assert any("/chapters/c1/" in key and key.endswith(".json.gz") for key in keys)
    assert not any(key.endswith("metadata.json") for key in keys)
    assert storage.list_novels() == [novel_id]


def test_translation_versions_and_manual_rollback_are_r2_plus_postgres(storage: StorageService) -> None:
    novel_id = _novel_id()
    storage.save_metadata(novel_id, {"title": "Translation novel", "chapters": []})
    storage.save_translated_chapter(novel_id, "c1", "machine", provider_key="gemini", provider_model="model")
    storage.save_edited_translation(
        novel_id,
        "c1",
        "edited",
        editor="owner",
        note="reviewed",
        glossary_revision=0,
    )

    versions = storage.list_translated_chapter_versions(novel_id, "c1")
    assert len(versions) == 2
    assert versions[-1]["active"] is True
    assert storage.load_translation_edit_history(novel_id, "c1")[0]["action"] == "manual_edit"
    assert storage.activate_translated_chapter_version(novel_id, "c1", versions[0]["version_id"])
    assert storage.load_translated_chapter(novel_id, "c1")["text"] == "machine"


def test_assets_are_content_addressed_and_do_not_expose_local_paths(storage: StorageService) -> None:
    novel_id = _novel_id()
    storage.save_metadata(novel_id, {"title": "Media novel", "chapters": []})
    manifest = storage.save_chapter_image_asset(
        novel_id,
        "c1",
        image_index=0,
        content=b"image-bytes",
        source_url="https://example.test/image.png",
        content_type="image/png",
    )

    assert manifest["storage_key"].startswith(f"novels/{novel_id}/assets/")
    assert manifest["sha256"]
    assert "local_path" not in manifest
    assert not any(key.startswith("runtime/") for key in storage.list_keys_under(f"novels/{novel_id}"))


def test_runtime_state_stays_local_and_is_not_required_as_catalog_content(storage: StorageService, monkeypatch) -> None:
    runtime_root = storage.runtime_path("test-runtime")
    monkeypatch.setattr(settings, "RUNTIME_DIR", runtime_root)

    result = storage.save_scheduler_state("job-1", [{"chapter_id": "c1", "status": "pending"}])

    assert result["job_id"] == "job-1"
    assert runtime_root.exists()
    assert storage.list_keys_under("runtime") == []


def test_chapter_processing_state_is_disposable_runtime_data(storage: StorageService) -> None:
    novel_id = _novel_id()
    from novelai.core.chapter_state import ChapterState

    storage.update_chapter_state(novel_id, "c1", ChapterState.SCRAPED)
    state = storage.load_chapter_state(novel_id, "c1")
    assert state is not None
    assert state["current_state"].value == "scraped"
    assert storage.list_keys_under(f"novels/{novel_id}") == []


def test_test_storage_does_not_create_canonical_local_novel_root(storage: StorageService) -> None:
    assert not (storage.base_dir / "novels").exists()
