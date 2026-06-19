"""Tests for storage service with state tracking."""

import json
import shutil
from uuid import uuid4

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.shared.pipeline import SchedulerModelState, SchedulerModelStatus
from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def storage():
    """Provide temporary storage."""
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"storage_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    store = StorageService(data_dir)
    yield store
    shutil.rmtree(data_dir, ignore_errors=True)


def test_save_and_load_chapter(storage):
    """Test saving and loading raw chapters."""

    # Save
    path = storage.save_chapter("novel1", "ch1", "Test chapter content", title="Chapter 1")
    assert path.exists()

    # Load
    loaded = storage.load_chapter("novel1", "ch1")
    assert loaded is not None
    assert loaded["text"] == "Test chapter content"
    assert loaded["title"] == "Chapter 1"


def test_save_and_load_chapter_preserves_multiline_formatting(storage):
    text = "Paragraph one.\nLine two.\n\nParagraph two."

    storage.save_chapter("novel1", "ch2", text, title="Chapter 2")

    loaded = storage.load_chapter("novel1", "ch2")
    assert loaded is not None
    assert loaded["text"] == text

    chapter_path = storage.base_dir / "novels" / "novel1" / "chapters" / "ch2.json"
    payload = json.loads(chapter_path.read_text(encoding="utf-8"))
    assert payload["raw"]["text"] == text
    assert payload["raw"]["paragraphs"] == ["Paragraph one.\nLine two.", "Paragraph two."]


def test_save_chapter_image_asset_and_load_export_images(storage):
    stored_asset = storage.save_chapter_image_asset(
        "novel1",
        "ch-images",
        image_index=0,
        content=b"fake-image-bytes",
        source_url="https://example.com/scene.jpg",
        content_type="image/jpeg",
    )

    storage.save_chapter(
        "novel1",
        "ch-images",
        "Before\n\n[Image: Scene]\n\nAfter",
        title="Illustrated Chapter",
        images=[
            {
                "index": 0,
                "placeholder": "[Image: Scene]",
                "original_url": "https://example.com/scene.jpg",
                "alt": "Scene",
                **stored_asset,
            }
        ],
    )

    chapter = storage.load_chapter("novel1", "ch-images")
    assert chapter is not None
    assert chapter["images"][0]["local_path"] == "assets/images/ch-images/0000.jpg"

    export_images = storage.load_chapter_export_images("novel1", "ch-images")
    assert export_images == [
        {
            "index": 0,
            "placeholder": "[Image: Scene]",
            "original_url": "https://example.com/scene.jpg",
            "alt": "Scene",
            "local_path": "assets/images/ch-images/0000.jpg",
            "content_type": "image/jpeg",
            "size_bytes": len(b"fake-image-bytes"),
            "sha256": stored_asset["sha256"],
            "asset_path": str(storage.base_dir / "novels" / "novel1" / "assets" / "images" / "ch-images" / "0000.jpg"),
        }
    ]


def test_save_and_load_translated_chapter(storage):
    """Test saving and loading translated chapters."""
    # Save
    path = storage.save_translated_chapter(
        "novel1", "ch1", "[TRANSLATED] Test content", provider="openai", model="gpt-4"
    )
    assert path.exists()

    # Load
    loaded = storage.load_translated_chapter("novel1", "ch1")
    assert loaded is not None
    assert "[TRANSLATED]" in loaded["text"]
    assert loaded["provider"] == "openai"


def test_translated_chapter_versions_keep_machine_history(storage):
    storage.save_translated_chapter("novel1", "ch1", "machine one", provider="openai", model="gpt-5.4")
    storage.save_translated_chapter("novel1", "ch1", "machine two", provider="gemini", model="gemini-3")

    versions = storage.list_translated_chapter_versions("novel1", "ch1")
    loaded = storage.load_translated_chapter("novel1", "ch1")

    assert len(versions) == 2
    assert versions[0]["text"] == "machine one"
    assert versions[0]["version_kind"] == "machine_translation"
    assert versions[1]["text"] == "machine two"
    assert versions[1]["active"] is True
    assert loaded is not None
    assert loaded["text"] == "machine two"
    assert loaded["version_id"] == versions[1]["version_id"]


def test_save_edited_translation_creates_manual_version_and_history(storage):
    storage.save_translated_chapter("novel1", "ch1", "machine translation", provider="openai", model="gpt-5.4")

    storage.save_edited_translation(
        "novel1",
        "ch1",
        "edited translation",
        editor="admin",
        note="fixed honorifics",
    )

    loaded = storage.load_translated_chapter("novel1", "ch1")
    versions = storage.list_translated_chapter_versions("novel1", "ch1")
    history = storage.load_translation_edit_history("novel1", "ch1")

    assert loaded is not None
    assert loaded["text"] == "edited translation"
    assert loaded["version_kind"] == "manual_edit"
    assert loaded["editor"] == "admin"
    assert len(versions) == 2
    assert versions[1]["base_version_id"] == versions[0]["version_id"]
    assert history == [
        {
            "id": "e1",
            "action": "manual_edit",
            "version_id": versions[1]["version_id"],
            "previous_version_id": versions[0]["version_id"],
            "created_at": history[0]["created_at"],
            "editor": "admin",
            "note": "fixed honorifics",
        }
    ]


def test_activate_translated_chapter_version_rolls_back_active_output(storage):
    storage.save_translated_chapter("novel1", "ch1", "machine translation", provider="openai", model="gpt-5.4")
    storage.save_edited_translation("novel1", "ch1", "edited translation", editor="admin")

    assert storage.activate_translated_chapter_version(
        "novel1",
        "ch1",
        "v1",
        editor="admin",
        note="restore machine output",
    ) is True

    loaded = storage.load_translated_chapter("novel1", "ch1")
    versions = storage.list_translated_chapter_versions("novel1", "ch1")
    history = storage.load_translation_edit_history("novel1", "ch1")

    assert loaded is not None
    assert loaded["text"] == "machine translation"
    assert loaded["version_id"] == "v1"
    assert versions[0]["active"] is True
    assert versions[1]["active"] is False
    assert history[-1]["action"] == "rollback"
    assert history[-1]["version_id"] == "v1"
    assert history[-1]["previous_version_id"] == "v2"


def test_list_stored_chapters_includes_raw_and_translated_entries(storage):
    storage.save_chapter("novel1", "1", "raw only", title="Chapter 1")
    storage.save_translated_chapter("novel1", "2", "translated only", provider="openai", model="gpt-5.4")

    assert storage.list_stored_chapters("novel1") == ["1", "2"]
    assert storage.count_stored_chapters("novel1") == 2


def test_chapter_storage_uses_single_merged_file(storage):
    storage.save_chapter("novel1", "ch1", "raw text", title="Chapter 1")
    storage.save_translated_chapter("novel1", "ch1", "translated text", provider="dummy", model="dummy")

    chapter_path = storage.base_dir / "novels" / "novel1" / "chapters" / "ch1.json"
    assert chapter_path.exists()

    payload = json.loads(chapter_path.read_text(encoding="utf-8"))
    assert payload["raw"]["text"] == "raw text"
    assert payload["translated"]["text"] == "translated text"


def test_chapter_storage_media_fields_default_for_existing_chapters(storage):
    storage.save_chapter("novel1", "ch-media-default", "raw text", title="Chapter 1")

    chapter_path = storage.base_dir / "novels" / "novel1" / "chapters" / "ch-media-default.json"
    payload = json.loads(chapter_path.read_text(encoding="utf-8"))

    assert payload["ocr_required"] is False
    assert payload["ocr_text"] is None
    assert payload["ocr_status"] == "skipped"
    assert payload["reembed_status"] == "skipped"

    loaded = storage.load_chapter("novel1", "ch-media-default")
    assert loaded is not None
    assert loaded["ocr_required"] is False
    assert loaded["ocr_text"] is None
    assert loaded["ocr_status"] == "skipped"
    assert loaded["reembed_status"] == "skipped"


def test_load_legacy_chapter_bundle_adds_media_defaults(storage):
    chapter_dir = storage.base_dir / "novels" / "novel1" / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = chapter_dir / "legacy.json"
    chapter_path.write_text(
        json.dumps(
            {
                "id": "legacy",
                "title": "Legacy Chapter",
                "raw": {"text": "legacy raw", "scraped_at": "2024-01-01T00:00:00Z"},
                "translated": {"text": "legacy translated", "translated_at": "2024-01-01T00:01:00Z"},
            }
        ),
        encoding="utf-8",
    )

    raw = storage.load_chapter("novel1", "legacy")
    translated = storage.load_translated_chapter("novel1", "legacy")

    assert raw is not None
    assert raw["ocr_required"] is False
    assert raw["ocr_text"] is None
    assert raw["ocr_status"] == "skipped"
    assert raw["reembed_status"] == "skipped"

    assert translated is not None
    assert translated["ocr_required"] is False
    assert translated["ocr_text"] is None
    assert translated["ocr_status"] == "skipped"
    assert translated["reembed_status"] == "skipped"


def test_save_translated_chapter_preserves_media_fields(storage):
    chapter_dir = storage.base_dir / "novels" / "novel1" / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = chapter_dir / "ch-media-roundtrip.json"
    chapter_path.write_text(
        json.dumps(
            {
                "id": "ch-media-roundtrip",
                "raw": {"text": "raw", "scraped_at": "2024-01-01T00:00:00Z"},
                "ocr_required": True,
                "ocr_text": "OCR corrected text",
                "ocr_status": "reviewed",
                "reembed_status": "pending",
            }
        ),
        encoding="utf-8",
    )

    storage.save_translated_chapter(
        "novel1",
        "ch-media-roundtrip",
        "translated",
        provider="openai",
        model="gpt-5.4",
    )

    payload = json.loads(chapter_path.read_text(encoding="utf-8"))
    assert payload["ocr_required"] is True
    assert payload["ocr_text"] == "OCR corrected text"
    assert payload["ocr_status"] == "reviewed"
    assert payload["reembed_status"] == "pending"


def test_save_and_load_chapter_media_state_helpers(storage):
    storage.save_chapter("novel1", "ch-media-helper", "raw text", title="Chapter 1")

    storage.save_chapter_media_state(
        "novel1",
        "ch-media-helper",
        ocr_required=True,
        ocr_text="Extracted OCR",
        ocr_status="reviewed",
        reembed_status="pending",
    )

    media = storage.load_chapter_media_state("novel1", "ch-media-helper")
    assert media is not None
    assert media["ocr_required"] is True
    assert media["ocr_text"] == "Extracted OCR"
    assert media["ocr_status"] == "reviewed"
    assert media["reembed_status"] == "pending"


def test_save_chapter_media_state_normalizes_invalid_status_values(storage):
    storage.save_chapter_media_state(
        "novel1",
        "ch-media-invalid",
        ocr_required=True,
        ocr_status="unknown",
        reembed_status="invalid",
    )

    media = storage.load_chapter_media_state("novel1", "ch-media-invalid")
    assert media is not None
    assert media["ocr_required"] is True
    assert media["ocr_status"] == "pending"
    assert media["reembed_status"] == "skipped"


def test_chapter_state_transitions(storage):
    """Test chapter state tracking."""
    # Create state
    storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)

    state1 = storage.load_chapter_state("novel1", "ch1")
    assert state1 is not None
    assert state1["current_state"] == ChapterState.SCRAPED
    assert len(state1["transitions"]) == 1

    # Transition to next state
    storage.update_chapter_state("novel1", "ch1", ChapterState.PARSED)

    state2 = storage.load_chapter_state("novel1", "ch1")
    assert state2["current_state"] == ChapterState.PARSED
    assert len(state2["transitions"]) == 2


def test_chapter_state_can_represent_partial_translation(storage):
    storage.update_chapter_state("novel1", "ch1", ChapterState.TRANSLATED_PARTIAL)

    state = storage.load_chapter_state("novel1", "ch1")

    assert state is not None
    assert state["current_state"] == ChapterState.TRANSLATED_PARTIAL


def test_chapter_state_with_error(storage):
    """Test chapter state transitions with errors."""
    storage.update_chapter_state(
        "novel1", "ch1", ChapterState.TRANSLATED, error="API timeout"
    )

    state = storage.load_chapter_state("novel1", "ch1")
    assert state["error_count"] == 1
    assert state["transitions"][-1].error == "API timeout"


def test_pipeline_event_storage_filters_by_job_and_chapter(storage):
    stored = storage.append_pipeline_event(
        {
            "job_id": "job_123",
            "activity_id": "job_123",
            "novel_id": "novel1",
            "chapter_id": "ch1",
            "source_key": "kakuyomu",
            "provider_key": "gemini",
            "provider_model": "gemini-3.1-flash-lite",
            "chunk_id": "c0002",
            "stage_name": "TranslateStage",
            "status_before": "translating",
            "status_after": "needs_retry",
            "error_code": "provider_rate_limited",
            "message": "Model cooling down for 21 seconds",
        }
    )

    assert stored["timestamp"]
    events = storage.list_pipeline_events(job_id="job_123", chapter_id="ch1")
    assert len(events) == 1
    assert events[0]["chunk_id"] == "c0002"
    assert events[0]["error_code"] == "provider_rate_limited"


def test_chunk_status_persistence_records_provider_model(storage):
    stored = storage.upsert_chunk_state(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["ch1"],
            "paragraph_ids": ["p0001"],
            "provider_key": "openai",
            "provider_model": "gpt-5.4",
            "attempt_number": 1,
            "status": "translated",
        }
    )

    assert stored["created_at"]
    assert stored["updated_at"]
    states = storage.load_chunk_states(novel_id="novel1", chapter_id="ch1")
    assert states == [stored]


def test_scheduler_state_can_represent_cooldown_and_exhaustion(storage):
    saved = storage.save_scheduler_state(
        "job_123",
        [
            SchedulerModelState(
                provider_key="gemini",
                provider_model="gemini-3.1-flash-lite",
                priority_order=1,
                cooldown_until="2026-06-04T12:01:00Z",
                last_error_code="provider_rate_limited",
                last_error_message="Rate limited",
                status=SchedulerModelStatus.COOLING_DOWN.value,
            ),
            {
                "provider_key": "openai",
                "provider_model": "gpt-5.4",
                "priority_order": 2,
                "exhausted_until": "2026-06-05T00:00:00Z",
                "last_error_code": "provider_quota_exhausted",
                "status": SchedulerModelStatus.DAILY_EXHAUSTED.value,
            },
        ],
    )

    loaded = storage.load_scheduler_state("job_123")
    assert loaded == saved
    statuses = {item["status"] for item in loaded["model_states"]}
    assert statuses == {"cooling_down", "daily_exhausted"}


def test_get_chapters_by_state(storage):
    """Test querying chapters by state."""
    # Create multiple chapters with different states
    storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    storage.update_chapter_state("novel1", "ch2", ChapterState.TRANSLATED)
    storage.update_chapter_state("novel1", "ch3", ChapterState.TRANSLATED)

    # Query
    translated = storage.get_chapters_by_state("novel1", ChapterState.TRANSLATED)
    scraped = storage.get_chapters_by_state("novel1", ChapterState.SCRAPED)

    assert len(translated) == 2
    assert len(scraped) == 1
    assert "ch1" in scraped


def test_chapter_progress(storage):
    """Test progress tracking."""
    storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    storage.update_chapter_state("novel1", "ch2", ChapterState.PARSED)
    storage.update_chapter_state("novel1", "ch3", ChapterState.TRANSLATED)
    storage.update_chapter_state("novel1", "ch4", ChapterState.EXPORTED)

    progress = storage.get_chapter_progress("novel1")

    assert progress["scraped"] == 1
    assert progress["parsed"] == 1
    assert progress["translated"] == 1
    assert progress["exported"] == 1


def test_get_chapters_ready_for_export(storage):
    """Test convenience method for export-ready chapters."""
    storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    storage.update_chapter_state("novel1", "ch2", ChapterState.TRANSLATED)
    storage.update_chapter_state("novel1", "ch3", ChapterState.EXPORTED)

    ready = storage.get_chapters_ready_for_export("novel1")

    assert len(ready) == 2
    assert "ch1" not in ready  # Scraped, not ready
    assert "ch2" in ready


def test_get_chapters_with_errors(storage):
    """Test querying chapters with errors."""
    storage.update_chapter_state("novel1", "ch1", ChapterState.TRANSLATED)
    storage.update_chapter_state("novel1", "ch2", ChapterState.TRANSLATED, error="Error 1")
    storage.update_chapter_state("novel1", "ch3", ChapterState.TRANSLATED, error="Error 2")

    errors = storage.get_chapters_with_errors("novel1")

    assert len(errors) == 2
    assert "ch2" in errors
    assert "ch3" in errors


def test_scraping_progress(storage):
    """Test detailed progress tracking."""
    storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    storage.update_chapter_state("novel1", "ch2", ChapterState.TRANSLATED)
    storage.update_chapter_state("novel1", "ch3", ChapterState.TRANSLATED, error="Error")

    progress = storage.get_scraping_progress("novel1")

    assert progress["total"] == 3
    assert progress["with_errors"] == 1
    assert progress["success_rate"] == pytest.approx(66.67, rel=0.01)


def test_metadata_operations(storage):
    """Test metadata save/load."""
    metadata = {
        "title": "Test Novel",
        "author": "Test Author",
        "chapters": ["ch1", "ch2"],
    }

    storage.save_metadata("novel1", metadata)
    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["title"] == "Test Novel"
    assert loaded["novel_id"] == "novel1"
    assert loaded["publication_status"] == "unknown"
    assert loaded["status"] == "unknown"


def test_metadata_normalizes_publication_status(storage):
    storage.save_metadata("novel1", {"title": "Test Novel", "publication_status": "Finished"})

    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["publication_status"] == "completed"
    assert loaded["status"] == "completed"


def test_metadata_rescrape_updates_publication_status(storage):
    storage.save_metadata("novel1", {"title": "Test Novel", "publication_status": "ongoing"})
    storage.save_metadata("novel1", {"publication_status": "completed"})

    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["publication_status"] == "completed"
    assert loaded["status"] == "completed"


def test_metadata_save_creates_bounded_backups_without_touching_chapters(storage):
    storage.save_chapter("novel1", "ch1", "Canonical chapter text", title="Chapter 1")
    storage.save_metadata("novel1", {"title": "Version 0"})
    for index in range(1, 8):
        storage.save_metadata("novel1", {"title": f"Version {index}"})

    backup_dir = storage.base_dir / "novels" / "novel1" / "metadata_backups"
    backups = sorted(backup_dir.glob("*.json"))
    loaded_chapter = storage.load_chapter("novel1", "ch1")

    assert len(backups) == 5
    assert any(json.loads(path.read_text(encoding="utf-8"))["title"] == "Version 6" for path in backups)
    assert loaded_chapter is not None
    assert loaded_chapter["text"] == "Canonical chapter text"


def test_metadata_save_merges_original_and_translated_fields(storage):
    storage.save_metadata("novel1", {"title": "Original Title", "author": "Original Author"})
    storage.save_metadata("novel1", {"translated_title": "Translated Title", "translated_author": "Translated Author"})

    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["title"] == "Original Title"
    assert loaded["translated_title"] == "Translated Title"
    assert loaded["translated_author"] == "Translated Author"
    assert loaded["titles"]["original"] == "Original Title"
    assert loaded["titles"]["translated"] == "Translated Title"
    assert loaded["authors"]["original"] == "Original Author"
    assert loaded["authors"]["translated"] == "Translated Author"


def test_list_novels(storage):
    """Test listing novels."""
    storage.save_metadata("novel1", {"title": "Novel 1"})
    storage.save_metadata("novel2", {"title": "Novel 2"})

    novels = storage.list_novels()

    assert len(novels) >= 2
    assert "novel1" in novels
    assert "novel2" in novels


def test_list_novels_discovers_unindexed_metadata_folder(storage):
    """Library listing should recover when storage folders exist but index.json is stale."""
    novel_dir = storage.novels_dir / "n0813kx"
    novel_dir.mkdir(parents=True)
    (novel_dir / "metadata.json").write_text(
        json.dumps({"novel_id": "n0813kx", "title": "Recovered Novel"}, ensure_ascii=False),
        encoding="utf-8",
    )

    novels = storage.list_novels()

    assert "n0813kx" in novels
    assert storage.load_metadata("n0813kx")["title"] == "Recovered Novel"


def test_list_novels_discovers_legacy_syosetu_folder_without_metadata(storage):
    """Legacy Syosetu folders like 0813kx should appear as canonical n0813kx."""
    novel_dir = storage.novels_dir / "0813kx"
    chapter_dir = novel_dir / "chapters"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / "1.json").write_text(
        json.dumps({"id": "1", "raw": {"text": "raw chapter"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    novels = storage.list_novels()

    assert "n0813kx" in novels
    assert "0813kx" not in novels
    assert storage._get_folder_name("n0813kx") == "0813kx"
    assert storage.count_stored_chapters("n0813kx") == 1
    assert storage.load_metadata("n0813kx") is None


def test_legacy_syosetu_folder_wins_when_index_points_to_missing_canonical_folder(storage):
    """A stale n0813kx index should not hide an existing 0813kx folder."""
    storage._persist_index({"n0813kx": {"folder_name": "n0813kx", "updated_at": "2026-06-03T00:00:00Z"}})
    novel_dir = storage.novels_dir / "0813kx"
    chapter_dir = novel_dir / "chapters"
    chapter_dir.mkdir(parents=True)
    (novel_dir / "metadata.json").write_text(
        json.dumps({"novel_id": "n0813kx", "title": "Legacy Folder Novel"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (chapter_dir / "1.json").write_text(
        json.dumps({"id": "1", "raw": {"text": "raw chapter"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert storage.list_novels() == ["n0813kx"]
    assert storage._get_folder_name("n0813kx") == "0813kx"
    assert storage.load_metadata("n0813kx")["title"] == "Legacy Folder Novel"
    assert storage.count_stored_chapters("n0813kx") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
