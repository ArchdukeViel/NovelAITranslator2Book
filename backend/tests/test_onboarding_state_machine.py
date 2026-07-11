"""Tests for novel onboarding state machine: storage helpers, inference, and integration."""

from __future__ import annotations

import shutil
from uuid import uuid4

import pytest

from novelai.storage.novels import VALID_ONBOARDING_STATUSES
from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def storage():
    """Provide temporary storage."""
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"onboarding_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    store = StorageService(data_dir)
    yield store
    shutil.rmtree(data_dir, ignore_errors=True)


class TestValidOnboardingStatuses:
    def test_contains_all_required_statuses(self):
        assert "not_started" in VALID_ONBOARDING_STATUSES
        assert "metadata_discovered" in VALID_ONBOARDING_STATUSES
        assert "glossary_pending" in VALID_ONBOARDING_STATUSES
        assert "chapters_pending" in VALID_ONBOARDING_STATUSES
        assert "scraping_chapters" in VALID_ONBOARDING_STATUSES
        assert "ready_for_translation" in VALID_ONBOARDING_STATUSES
        assert "failed" in VALID_ONBOARDING_STATUSES
        assert "cancelled" in VALID_ONBOARDING_STATUSES

    def test_is_frozenset(self):
        assert isinstance(VALID_ONBOARDING_STATUSES, frozenset)


class TestUpdateOnboardingStatus:
    def test_set_chapters_pending(self, storage):
        storage.save_metadata("n1", {"title": "Test Novel", "chapters": [{"id": "1"}]})
        result = storage.update_onboarding_status("n1", "chapters_pending")
        assert result["onboarding_status"] == "chapters_pending"
        assert result["onboarding_updated_at"] is not None

    def test_set_ready_for_translation(self, storage):
        storage.save_metadata("n1", {"title": "Test Novel", "chapters": [{"id": "1"}]})
        result = storage.update_onboarding_status("n1", "ready_for_translation")
        assert result["onboarding_status"] == "ready_for_translation"

    def test_set_failed_with_error(self, storage):
        storage.save_metadata("n1", {"title": "Test Novel", "chapters": [{"id": "1"}]})
        result = storage.update_onboarding_status(
            "n1",
            "failed",
            error_code="scrape_completed_without_chapters",
            error_message="Chapter scrape finished without saving any usable raw chapters.",
        )
        assert result["onboarding_status"] == "failed"
        assert result["onboarding_error_code"] == "scrape_completed_without_chapters"
        assert result["onboarding_error_message"] == "Chapter scrape finished without saving any usable raw chapters."
        assert result["onboarding_updated_at"] is not None

    def test_set_failed_and_clear_error(self, storage):
        storage.save_metadata("n1", {"title": "Test Novel", "chapters": [{"id": "1"}]})
        storage.update_onboarding_status(
            "n1",
            "failed",
            error_code="old_error",
            error_message="Old message",
        )
        result = storage.update_onboarding_status("n1", "chapters_pending", clear_error=True)
        assert result["onboarding_status"] == "chapters_pending"
        assert result.get("onboarding_error_code") is None
        assert result.get("onboarding_error_message") is None

    def test_invalid_status_raises(self, storage):
        storage.save_metadata("n1", {"title": "Test Novel"})
        with pytest.raises(ValueError, match="Invalid onboarding status"):
            storage.update_onboarding_status("n1", "invalid_status")

    def test_nonexistent_novel_raises(self, storage):
        with pytest.raises(ValueError, match="No metadata found"):
            storage.update_onboarding_status("nonexistent", "chapters_pending")

    def test_preserves_existing_metadata(self, storage):
        storage.save_metadata("n1", {"title": "My Novel", "author": "Test Author", "chapters": [{"id": "1"}]})
        result = storage.update_onboarding_status("n1", "chapters_pending")
        assert result["title"] == "My Novel"
        assert result["author"] == "Test Author"
        assert result["onboarding_status"] == "chapters_pending"

    def test_idempotent_update(self, storage):
        storage.save_metadata("n1", {"title": "Test", "chapters": [{"id": "1"}]})
        r1 = storage.update_onboarding_status("n1", "chapters_pending")
        r2 = storage.update_onboarding_status("n1", "ready_for_translation")
        assert r1["onboarding_status"] == "chapters_pending"
        assert r2["onboarding_status"] == "ready_for_translation"
        meta = storage.load_metadata("n1")
        assert meta["onboarding_status"] == "ready_for_translation"


class TestResolveOnboardingStatus:
    def test_explicit_status_returned(self, storage):
        storage.save_metadata("n1", {
            "title": "Test",
            "chapters": [{"id": "1"}],
            "onboarding_status": "chapters_pending",
        })
        assert storage.resolve_onboarding_status("n1") == "chapters_pending"

    def test_unknown_explicit_status_falls_back(self, storage):
        storage.save_metadata("n1", {
            "title": "Test",
            "onboarding_status": "invalid_state",
        })
        status = storage.resolve_onboarding_status("n1")
        assert status in VALID_ONBOARDING_STATUSES

    def test_infers_metadata_discovered_when_no_chapters(self, storage):
        storage.save_metadata("n1", {"title": "Test"})
        assert storage.resolve_onboarding_status("n1") == "metadata_discovered"

    def test_infers_chapters_pending_when_chapters_exist_but_no_raw(self, storage):
        storage.save_metadata("n1", {
            "title": "Test",
            "chapters": [{"id": "1"}, {"id": "2"}],
        })
        assert storage.resolve_onboarding_status("n1") == "chapters_pending"

    def test_infers_ready_for_translation_when_raw_chapters_exist(self, storage):
        storage.save_metadata("n1", {
            "title": "Test",
            "chapters": [{"id": "1"}],
        })
        storage.save_chapter("n1", "1", "Raw chapter content", title="Chapter 1")
        assert storage.resolve_onboarding_status("n1") == "ready_for_translation"

    def test_nonexistent_novel_returns_not_started(self, storage):
        assert storage.resolve_onboarding_status("nonexistent") == "not_started"

    def test_novel_with_empty_chapters_list_is_metadata_discovered(self, storage):
        storage.save_metadata("n1", {"title": "Test", "chapters": []})
        assert storage.resolve_onboarding_status("n1") == "metadata_discovered"

    def test_ready_takes_precedence_over_chapters_pending(self, storage):
        storage.save_metadata("n1", {
            "title": "Test",
            "chapters": [{"id": "1"}, {"id": "2"}],
        })
        storage.save_chapter("n1", "1", "Raw content 1", title="Ch1")
        storage.save_chapter("n1", "2", "Raw content 2", title="Ch2")
        assert storage.resolve_onboarding_status("n1") == "ready_for_translation"


class TestOnboardingStatusPersistence:
    def test_status_persisted_across_load(self, storage):
        storage.save_metadata("n1", {"title": "Test", "chapters": [{"id": "1"}]})
        storage.update_onboarding_status("n1", "failed", error_code="test", error_message="Test error")
        meta = storage.load_metadata("n1")
        assert meta["onboarding_status"] == "failed"
        assert meta["onboarding_error_code"] == "test"
        assert meta["onboarding_error_message"] == "Test error"

    def test_body_scrape_required_field_preserved(self, storage):
        storage.save_metadata("n1", {"title": "Test", "chapters": [{"id": "1"}]})
        storage.update_onboarding_status("n1", "chapters_pending")
        meta = storage.load_metadata("n1")
        assert "body_scrape_required" not in meta or meta.get("body_scrape_required") is None or meta.get("body_scrape_required") is True
