"""Tests for storage service with state tracking."""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.core.chapter_state import ChapterState, ChapterMetadata, ChapterStateTransition
from novelai.services.query_builder import ChapterQueryBuilder
from novelai.services.storage_service import StorageService
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
    chapter_data = {
        "id": "ch1",
        "title": "Chapter 1",
        "text": "Test chapter content",
    }

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


def test_chapter_storage_uses_single_merged_file(storage):
    storage.save_chapter("novel1", "ch1", "raw text", title="Chapter 1")
    storage.save_translated_chapter("novel1", "ch1", "translated text", provider="dummy", model="dummy")

    chapter_path = storage.base_dir / "novels" / "novel1" / "chapters" / "ch1.json"
    assert chapter_path.exists()

    payload = json.loads(chapter_path.read_text(encoding="utf-8"))
    assert payload["raw"]["text"] == "raw text"
    assert payload["translated"]["text"] == "translated text"


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


def test_chapter_state_with_error(storage):
    """Test chapter state transitions with errors."""
    storage.update_chapter_state(
        "novel1", "ch1", ChapterState.TRANSLATED, error="API timeout"
    )
    
    state = storage.load_chapter_state("novel1", "ch1")
    assert state["error_count"] == 1
    assert state["transitions"][-1].error == "API timeout"


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


def test_metadata_save_merges_original_and_translated_fields(storage):
    storage.save_metadata("novel1", {"title": "Original Title"})
    storage.save_metadata("novel1", {"translated_title": "Translated Title"})

    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["title"] == "Original Title"
    assert loaded["translated_title"] == "Translated Title"
    assert loaded["titles"]["original"] == "Original Title"
    assert loaded["titles"]["translated"] == "Translated Title"


def test_list_novels(storage):
    """Test listing novels."""
    storage.save_metadata("novel1", {"title": "Novel 1"})
    storage.save_metadata("novel2", {"title": "Novel 2"})

    novels = storage.list_novels()

    assert len(novels) >= 2
    assert "novel1" in novels
    assert "novel2" in novels


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
