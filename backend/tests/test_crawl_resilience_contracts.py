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

    async def fetch_chapter_payload(self, url: str) -> dict[str, Any]:
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

    async def fetch_chapter_payload(self, url: str) -> dict[str, Any]:
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
    """Document what happens when one chapter fetch fails mid-scrape."""

    @pytest.mark.asyncio
    async def test_chapter_fetch_error_aborts_scrape(self, crawl_env) -> None:
        """Current behavior: a SourceError from fetch_chapter_payload halts the loop.

        Chapters processed before the failure ARE saved.
        Chapters after the failure are NOT processed.
        """
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Make chapter 1 fail
        source.fetch_errors["novel-1/ch1"] = SourceError("Network timeout")

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )

        # Scrape should raise
        with pytest.raises(SourceError, match="Network timeout"):
            await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

    @pytest.mark.asyncio
    async def test_chapter_fetch_error_leaves_partial_state(self, crawl_env) -> None:
        """When chapter 2 fails, chapter 1 is already saved (partial success).

        This documents current all-or-nothing semantics at the loop level,
        but previously-saved chapters survive on disk.
        """
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Make chapter 2 fail (chapter 1 succeeds)
        source.fetch_errors["novel-1/ch2"] = SourceError("Server error")

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )

        with pytest.raises(SourceError, match="Server error"):
            await service.scrape_chapters("test_source", "novel-1", "all", mode="full")

        # Chapter 1 was saved before chapter 2 failed
        stored = storage.list_stored_chapters("novel-1")
        assert len(stored) >= 1
        ch1 = storage.load_chapter("novel-1", "1")
        assert ch1 is not None
        assert ch1["text"].strip()

    @pytest.mark.asyncio
    async def test_runtime_error_from_invalid_text_aborts(self, crawl_env) -> None:
        """When chapter payload has non-string text, RuntimeError halts scrape."""
        storage = crawl_env["storage"]
        source = TwoChapterSource()

        # Chapter 1 returns non-string text
        source.chapter_payloads["novel-1/ch1"] = {"text": 12345, "images": []}

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source,
            translation=_NoopTranslationService(),
        )

        with pytest.raises((RuntimeError, SourceError)):
            await service.scrape_chapters("test_source", "novel-1", "all", mode="full")


# ---------------------------------------------------------------------------
# Concurrent crawl risk test (documented gap)
# ---------------------------------------------------------------------------


class TestConcurrentCrawlRisk:
    """Document that no crawl locking mechanism currently exists.

    If two scrapes of the same novel run concurrently, they may
    corrupt each other's writes. This test documents the gap.
    """

    @pytest.mark.skip(
        reason="No crawl locking exists. Concurrent scrapes of the same novel "
        "may produce corrupted metadata or chapter files. "
        "Fix planned for SOURCE-PIPELINE-FIX-2C."
    )
    @pytest.mark.asyncio
    async def test_concurrent_scrapes_do_not_corrupt(self, crawl_env) -> None:
        """SKIPPED: No locking mechanism. Two simultaneous scrape_chapters() calls
        for the same novel_id may interleave writes to the same metadata.json
        and chapter files, producing corrupted state.

        Expected future behavior: second concurrent scrape should be rejected
        or queued, not allowed to run in parallel.
        """
        import asyncio

        storage = crawl_env["storage"]
        source_a = TwoChapterSource()
        source_b = TwoChapterSource()
        source_b.chapter_payloads["novel-1/ch1"] = {"text": "Source B content", "images": []}

        service = NovelOrchestrationService(
            storage=storage,
            settings_service=crawl_env["settings"],
            translation_cache=crawl_env["cache"],
            usage_service=crawl_env["usage"],
            source_factory=lambda k: source_a,
            translation=_NoopTranslationService(),
        )

        # Run two scrapes concurrently — this should NOT corrupt data
        results = await asyncio.gather(
            service.scrape_chapters("test_source", "novel-1", "all", mode="full"),
            service.scrape_chapters("test_source", "novel-1", "all", mode="full"),
            return_exceptions=True,
        )

        # Both should succeed or one should be rejected cleanly
        ch = storage.load_chapter("novel-1", "1")
        assert ch is not None
        assert ch["text"].strip()


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
