"""Crawl resilience contract tests.

Documents current crawl/update behavior to support SOURCE-PIPELINE-FIX-2 planning.
These tests prove what currently works and what currently doesn't, without
changing orchestration code.
"""

from __future__ import annotations

import shutil
from typing import Any
from uuid import uuid4

import pytest

from novelai.core.errors import SourceError
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.storage.service import StorageService
from novelai.translation.service import TranslationService
from tests.conftest import TESTS_TMP_ROOT


# ---------------------------------------------------------------------------
# Stub source adapters
# ---------------------------------------------------------------------------


class TwoChapterSource(SourceAdapter):
    """Minimal 2-chapter source with configurable chapter payloads."""

    def __init__(self) -> None:
        self.chapter_payloads: dict[str, dict[str, Any]] = {}
        self.fetch_errors: dict[str, Exception] = {}
        self.fetch_count = 0

    @property
    def key(self) -> str:
        return "test_source"

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {
            "source": self.key,
            "source_url": url,
            "title": "Test Novel",
            "author": "Test Author",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": f"{url}/ch1"},
                {"id": "2", "num": 2, "title": "Chapter 2", "url": f"{url}/ch2"},
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        payload = await self.fetch_chapter_payload(url)
        return str(payload.get("text", ""))

    async def fetch_chapter_payload(self, url: str, *, on_retry=None) -> dict[str, Any]:
        self.fetch_count += 1
        if url in self.fetch_errors:
            raise self.fetch_errors[url]
        if url in self.chapter_payloads:
            return self.chapter_payloads[url]
        return {"text": f"Content from {url}", "images": []}


class ChangingChapterSource(SourceAdapter):
    """Source where chapter content changes between scrapes."""

    def __init__(self) -> None:
        self.version = 1

    @property
    def key(self) -> str:
        return "changing_source"

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {
            "source": self.key,
            "source_url": url,
            "title": "Changing Novel",
            "author": "Changing Author",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": f"{url}/ch1"},
                {"id": "2", "num": 2, "title": "Chapter 2", "url": f"{url}/ch2"},
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return f"Version {self.version} content from {url}"

    async def fetch_chapter_payload(self, url: str, *, on_retry=None) -> dict[str, Any]:
        return {"text": f"Version {self.version} content from {url}", "images": []}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _NoopTranslationService:
    """Minimal translation service that does nothing."""

    async def translate_text(self, *args: Any, **kwargs: Any) -> str:
        return ""


@pytest.fixture
def crawl_env():
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"crawl_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    storage = StorageService(data_dir)
    prefs = PreferencesService(data_dir)
    prefs.set_provider_key("mock")
    prefs.set_provider_model("mock-1.0")
    cache = TranslationCache(data_dir)
    usage = UsageService(data_dir)

    yield {
        "data_dir": data_dir,
        "storage": storage,
        "settings": prefs,
        "cache": cache,
        "usage": usage,
    }

    shutil.rmtree(data_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Admin taxonomy preservation tests
# ---------------------------------------------------------------------------


class TestAdminTaxonomyPreservation:
    """Admin-assigned taxonomy rows should survive recrawl.

    Current behavior: taxonomy persistence in scraper deletes only
    assigned_by='scraper' rows. Admin rows (assigned_by='admin') survive.
    This is enforced in taxonomy_persistence.py and documented in
    admin_taxonomy.py docstring.

    These tests verify the filesystem-level metadata merge behavior,
    which is separate from the DB taxonomy layer.
    """

    @pytest.mark.asyncio
    async def test_metadata_save_preserves_extra_fields_not_in_new_data(self, crawl_env) -> None:
        """save_metadata merges shallow: keys only in existing survive."""
        storage = crawl_env["storage"]

        # Simulate existing metadata with admin-only fields
        existing = {
            "source": "test",
            "source_url": "https://example.com/novel",
            "title": "Original",
            "author": "Author",
            "chapters": [],
            "admin_notes": "Manual annotation by owner",
            "custom_field": "preserved",
        }
        storage.save_metadata("novel-1", existing)

        # Simulate recrawl: new metadata without admin_notes or custom_field
        new_data = {
            "source": "test",
            "source_url": "https://example.com/novel",
            "title": "Updated Title",
            "author": "Updated Author",
            "chapters": [{"id": "1", "num": 1, "title": "Ch 1", "url": "https://example.com/novel/1"}],
        }
        storage.save_metadata("novel-1", new_data)

        loaded = storage.load_metadata("novel-1")
        assert loaded is not None
        # New data overwrites
        assert loaded["title"] == "Updated Title"
        assert loaded["author"] == "Updated Author"
        # Old-only fields preserved (shallow merge)
        assert loaded.get("admin_notes") == "Manual annotation by owner"
        assert loaded.get("custom_field") == "preserved"

    @pytest.mark.asyncio
    async def test_metadata_save_replaces_chapters_list(self, crawl_env) -> None:
        """save_metadata replaces nested chapters list entirely (not element merge)."""
        storage = crawl_env["storage"]

        existing = {
            "source": "test",
            "source_url": "https://example.com/novel",
            "title": "Novel",
            "author": "Author",
            "chapters": [
                {"id": "1", "num": 1, "title": "Old Ch 1", "url": "https://example.com/novel/1"},
                {"id": "2", "num": 2, "title": "Old Ch 2", "url": "https://example.com/novel/2"},
                {"id": "3", "num": 3, "title": "Old Ch 3", "url": "https://example.com/novel/3"},
            ],
        }
        storage.save_metadata("novel-1", existing)

        # Recrawl returns only 2 chapters (chapter 3 was removed at source)
        new_data = {
            "source": "test",
            "source_url": "https://example.com/novel",
            "title": "Novel",
            "author": "Author",
            "chapters": [
                {"id": "1", "num": 1, "title": "New Ch 1", "url": "https://example.com/novel/1"},
                {"id": "2", "num": 2, "title": "New Ch 2", "url": "https://example.com/novel/2"},
            ],
        }
        storage.save_metadata("novel-1", new_data)

        loaded = storage.load_metadata("novel-1")
        assert loaded is not None
        # Chapters list fully replaced — chapter 3 gone
        assert len(loaded["chapters"]) == 2
        assert loaded["chapters"][0]["title"] == "New Ch 1"
        assert loaded["chapters"][1]["title"] == "New Ch 2"

    @pytest.mark.asyncio
    async def test_scraped_at_preserved_on_update(self, crawl_env) -> None:
        """save_metadata preserves original scraped_at timestamp on merge."""
        storage = crawl_env["storage"]

        existing = {
            "source": "test",
            "source_url": "https://example.com/novel",
            "title": "Novel",
            "author": "Author",
            "chapters": [],
            "scraped_at": "2025-01-01T00:00:00+00:00",
        }
        storage.save_metadata("novel-1", existing)

        new_data = {
            "source": "test",
            "source_url": "https://example.com/novel",
            "title": "Novel Updated",
            "author": "Author",
            "chapters": [],
        }
        storage.save_metadata("novel-1", new_data)

        loaded = storage.load_metadata("novel-1")
        assert loaded is not None
        # scraped_at should be the original first-scrape time
        assert loaded["scraped_at"] == "2025-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Changed chapter update tests
# ---------------------------------------------------------------------------


class TestChangedChapterUpdate:
    """Update mode should detect changed chapter content and replace it."""

    @pytest.mark.asyncio
    async def test_unchanged_chapter_skipped_in_update_mode(self, crawl_env) -> None:
        """In update mode, a chapter with identical content signature is skipped."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # First scrape (full mode) — populate chapters
        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )
        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Verify both chapters stored
        stored = storage.list_stored_chapters("novel-1")
        assert len(stored) == 2

        # Record fetch count before update
        count_before = source.fetch_count

        # Second scrape (update mode) — same content
        await service.scrape_chapters("test_source", "novel-1", "all", mode="update")

        # Chapters were fetched (the source was called)
        assert source.fetch_count > count_before

        # But content should be unchanged — verify storage still has 2 chapters
        stored_after = storage.list_stored_chapters("novel-1")
        assert len(stored_after) == 2

    @pytest.mark.asyncio
    async def test_changed_chapter_replaced_in_update_mode(self, crawl_env) -> None:
        """In update mode, a chapter with different content is replaced."""
        storage = crawl_env["storage"]
        source = ChangingChapterSource()

        # First scrape (full mode) — version 1
        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )
        await service.scrape_chapters("changing_source", "novel-1", "all", mode="full")

        # Verify version 1 content stored
        ch1 = storage.load_chapter("novel-1", "1")
        assert ch1 is not None
        assert "Version 1" in ch1["text"]

        # Change source content to version 2
        source.version = 2

        # Second scrape (update mode)
        await service.scrape_chapters("changing_source", "novel-1", "all", mode="update")

        # Verify version 2 content replaced version 1
        ch1_updated = storage.load_chapter("novel-1", "1")
        assert ch1_updated is not None
        assert "Version 2" in ch1_updated["text"]
        assert "Version 1" not in ch1_updated["text"]

    @pytest.mark.asyncio
    async def test_raw_text_available_after_update(self, crawl_env) -> None:
        """After update, raw text remains available for translation."""
        storage = crawl_env["storage"]
        source = ChangingChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )
        await service.scrape_chapters("changing_source", "novel-1", "all", mode="full")

        source.version = 2
        await service.scrape_chapters("changing_source", "novel-1", "all", mode="update")

        # Verify raw text is present and non-empty
        ch = storage.load_chapter("novel-1", "1")
        assert ch is not None
        assert ch["text"].strip()
        assert len(ch["text"]) > 10


# ---------------------------------------------------------------------------
# Single chapter failure behavior tests
# ---------------------------------------------------------------------------


class TestSingleChapterFailure:
    """Document what happens when one chapter fetch fails mid-scrape.

    After SOURCE-PIPELINE-FIX-2B: per-chapter failures are non-fatal.
    The scrape continues with remaining chapters and returns a summary.
    """

    @pytest.mark.asyncio
    async def test_chapter_fetch_error_does_not_abort_scrape(self, crawl_env) -> None:
        """A SourceError from fetch_chapter_payload is caught and recorded.

        Remaining chapters continue processing.
        """
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Make chapter 1 fail
        source.fetch_errors["novel-1/ch1"] = SourceError("Network timeout")

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # Scrape should NOT raise — it returns a summary
        result = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Chapter 1 failed, chapter 2 succeeded
        assert result["failed"] == 1
        assert result["succeeded"] == 1
        assert len(result["failures"]) == 1
        assert result["failures"][0]["chapter_id"] == "1"
        assert "Network timeout" in result["failures"][0]["error_message"]

    @pytest.mark.asyncio
    async def test_chapters_after_failure_still_processed(self, crawl_env) -> None:
        """When chapter 1 fails, chapter 2 is still fetched and saved."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Make chapter 1 fail
        source.fetch_errors["novel-1/ch1"] = SourceError("Server error")

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        result = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Chapter 2 was saved
        ch2 = storage.load_chapter("novel-1", "2")
        assert ch2 is not None
        assert ch2["text"].strip()
        assert result["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_failed_chapter_recorded_in_summary(self, crawl_env) -> None:
        """Failed chapter details are recorded in the failures list."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        source.fetch_errors["novel-1/ch1"] = SourceError("Connection refused")

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        result = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        assert len(result["failures"]) == 1
        failure = result["failures"][0]
        assert failure["chapter_id"] == "1"
        assert failure["chapter_number"] == 1
        assert failure["title"] == "Chapter 1"
        assert failure["source_url"] == "novel-1/ch1"
        assert failure["error_type"] == "SourceError"
        assert "Connection refused" in failure["error_message"]

    @pytest.mark.asyncio
    async def test_invalid_text_records_failure_and_continues(self, crawl_env) -> None:
        """Non-string text in chapter payload records failure, continues to next chapter."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Chapter 1 returns non-string text
        source.chapter_payloads["novel-1/ch1"] = {"text": 12345, "images": []}

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        result = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Chapter 1 failed (invalid text), chapter 2 succeeded
        assert result["failed"] == 1
        assert result["succeeded"] == 1
        assert result["failures"][0]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_failed_chapter_does_not_create_fake_content(self, crawl_env) -> None:
        """A failed chapter does not produce a saved chapter file."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        source.fetch_errors["novel-1/ch1"] = SourceError("Timeout")

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Chapter 1 was NOT saved
        ch1 = storage.load_chapter("novel-1", "1")
        assert ch1 is None

        # Chapter 2 WAS saved
        ch2 = storage.load_chapter("novel-1", "2")
        assert ch2 is not None

    @pytest.mark.asyncio
    async def test_progress_callback_receives_failure_events(self, crawl_env) -> None:
        """Progress callback receives warning messages for failed chapters."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        source.fetch_errors["novel-1/ch1"] = SourceError("Timeout")

        events: list[str] = []

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        result = await service.scrape_chapters(
            "test_source", "novel-1", "all", mode="full",
            progress_callback=events.append,
        )

        # Should contain failure message
        failure_events = [e for e in events if "failed" in e.lower()]
        assert len(failure_events) >= 1

        # Should contain partial success summary
        summary_events = [e for e in events if "partial success" in e.lower()]
        assert len(summary_events) == 1

    @pytest.mark.asyncio
    async def test_all_chapters_succeed_returns_zero_failures(self, crawl_env) -> None:
        """When all chapters succeed, failures list is empty."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        result = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        assert result["failed"] == 0
        assert result["succeeded"] == 2
        assert result["failures"] == []


# ---------------------------------------------------------------------------
# Concurrent crawl risk test (documented gap)
# ---------------------------------------------------------------------------


class TestConcurrentCrawlLocking:
    """Verify that concurrent scrapes of the same novel are protected by a lock.

    After SOURCE-PIPELINE-FIX-2C: in-process asyncio lock prevents two scrapes
    of the same source_key + novel_id from running simultaneously.
    """

    @pytest.mark.asyncio
    async def test_concurrent_same_novel_scrape_rejected(self, crawl_env) -> None:
        """Second concurrent scrape of same novel raises RuntimeError."""
        import asyncio

        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Add a delay to the source to ensure overlap
        original_fetch = source.fetch_chapter_payload

        async def slow_fetch(url: str) -> dict[str, Any]:
            await asyncio.sleep(0.1)  # Ensure second scrape starts while first is running
            return await original_fetch(url)

        source.fetch_chapter_payload = slow_fetch  # type: ignore[method-assign]

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # Run two scrapes concurrently
        results = await asyncio.gather(
            service.scrape_chapters("test_source", "novel-1", "all", mode="full"),
            service.scrape_chapters("test_source", "novel-1", "all", mode="full"),
            return_exceptions=True,
        )

        # One should succeed, one should be rejected
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, RuntimeError)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert "already in progress" in str(failures[0])

    @pytest.mark.asyncio
    async def test_lock_released_after_success(self, crawl_env) -> None:
        """Lock is released after successful scrape, allowing subsequent scrape."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # First scrape succeeds
        result1 = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        assert result1["succeeded"] == 2

        # Second scrape should also succeed (lock released)
        result2 = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        assert result2["succeeded"] == 2

    @pytest.mark.asyncio
    async def test_lock_released_after_partial_failure(self, crawl_env) -> None:
        """Lock is released after per-chapter partial failure."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()
        source.fetch_errors["novel-1/ch1"] = SourceError("Timeout")

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # First scrape has partial failure
        result1 = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        assert result1["failed"] == 1
        assert result1["succeeded"] == 1

        # Second scrape should work (lock released)
        source.fetch_errors.clear()  # Clear errors for second attempt
        result2 = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        assert result2["succeeded"] == 2

    @pytest.mark.asyncio
    async def test_lock_released_after_metadata_failure(self, crawl_env) -> None:
        """Lock is released after metadata/list-level failure."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # Update mode without prior metadata should fail
        with pytest.raises(RuntimeError, match="Metadata not found"):
            await service.scrape_chapters("test_source", "novel-1", "all", mode="update")

        # Lock should be released — full scrape should work
        result = await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        assert result["succeeded"] == 2

    @pytest.mark.asyncio
    async def test_different_novels_can_scrape_concurrently(self, crawl_env) -> None:
        """Concurrent scrapes of different novel IDs can proceed independently."""
        import asyncio

        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # Scrape two different novels concurrently
        results = await asyncio.gather(
            service.scrape_chapters("test_source", "novel-A", "all", mode="full"),
            service.scrape_chapters("test_source", "novel-B", "all", mode="full"),
            return_exceptions=True,
        )

        # Both should succeed (different lock keys)
        assert all(not isinstance(r, Exception) for r in results)
        assert results[0]["succeeded"] == 2
        assert results[1]["succeeded"] == 2

    @pytest.mark.asyncio
    async def test_update_mode_uses_same_lock(self, crawl_env) -> None:
        """Update mode scrape also uses the per-novel lock."""
        import asyncio

        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            translation=_NoopTranslationService(),
            source_factory=lambda k: source,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
        )

        # First do a full scrape to populate metadata
        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Add delay to update scrape
        original_fetch = source.fetch_chapter_payload

        async def slow_fetch(url: str) -> dict[str, Any]:
            await asyncio.sleep(0.1)
            return await original_fetch(url)

        source.fetch_chapter_payload = slow_fetch  # type: ignore[method-assign]

        # Run full + update concurrently — one should be rejected
        results = await asyncio.gather(
            service.scrape_chapters("test_source", "novel-1", "all", mode="full"),
            service.scrape_chapters("test_source", "novel-1", "all", mode="update"),
            return_exceptions=True,
        )

        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, RuntimeError)]
        assert len(successes) == 1
        assert len(failures) == 1


# ---------------------------------------------------------------------------
# Full mode destructive behavior test
# ---------------------------------------------------------------------------


class TestFullModeDestructive:
    """Document that mode='full' wipes existing novel data before scraping."""

    @pytest.mark.asyncio
    async def test_full_mode_replaces_all_chapters(self, crawl_env) -> None:
        """Full mode re-scrapes all chapters even if content is unchanged."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )

        # First scrape
        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        count_after_first = source.fetch_count

        # Second scrape (full mode again) — should re-fetch everything
        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        count_after_second = source.fetch_count

        # All chapters were re-fetched (not skipped)
        assert count_after_second > count_after_first

    @pytest.mark.asyncio
    async def test_full_mode_wipes_then_rescrapes(self, crawl_env) -> None:
        """Full mode calls delete_novel before scraping, removing old data."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )

        # First scrape
        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        assert len(storage.list_stored_chapters("novel-1")) == 2

        # Second full scrape — old chapters deleted, new ones scraped
        await service.scrape_chapters("test_source", "novel-1", "all", mode="full")
        stored = storage.list_stored_chapters("novel-1")
        assert len(stored) == 2

        # Verify content is from fresh scrape
        ch = storage.load_chapter("novel-1", "1")
        assert ch is not None
        assert "Content from" in ch["text"]
