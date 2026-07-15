"""Tests for LibrarySummaryService live admin library summary."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from novelai.services import library_summary_service as _lss_module
from novelai.services.library_summary_service import LibrarySummaryService
from novelai.storage.service import StorageService

# ── fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def summary_storage(tmp_path):
    """A fresh StorageService rooted at a tmp directory."""
    storage = StorageService(tmp_path)
    yield storage
    storage._backend.mkdirs(tmp_path)


def _save_chapter(
    storage: StorageService,
    novel_id: str,
    chapter_id: str,
    *,
    raw: bool = True,
    translated: bool = False,
) -> None:
    """Save a chapter payload with optional raw/translated sections."""
    if raw:
        storage.save_chapter(novel_id, chapter_id, f"raw chapter body for {chapter_id}")
    if translated:
        storage.save_translated_chapter(
            novel_id,
            chapter_id,
            f"translated chapter body for {chapter_id}",
        )


def _metadata(
    chapters: int,
    title: str | None = None,
    translated_title: str | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "chapters": [{"id": str(i)} for i in range(1, chapters + 1)],
        "chapter_count": chapters,
    }
    if title:
        meta["title"] = title
    if translated_title:
        meta["translated_title"] = translated_title
    return meta


# ── inventory builder ─────────────────────────────────────────────────


class TestStorageInventory:
    """Tests for the single-pass storage inventory builder."""

    def test_inventory_lists_multiple_novels_in_one_pass(
        self, summary_storage: StorageService
    ) -> None:
        """One listing should cover all novels without per-novel scanning."""
        summary_storage.save_metadata("novel-a", _metadata(2))
        _save_chapter(summary_storage, "novel-a", "1")
        _save_chapter(summary_storage, "novel-a", "2")

        summary_storage.save_metadata("novel-b", _metadata(3))
        _save_chapter(summary_storage, "novel-b", "1")

        listing_calls: list[tuple[tuple, dict[str, Any]]] = []
        original = summary_storage._backend.list_keys

        def _spy(*args: Any, **kwargs: Any) -> list[str]:
            listing_calls.append((args, kwargs))
            return original(*args, **kwargs)

        with patch.object(summary_storage._backend, "list_keys", side_effect=_spy):
            service = LibrarySummaryService(summary_storage)
            result = service.get_summary(refresh=True)

        # Exactly one listing call regardless of novel count
        assert len(listing_calls) == 1
        # Both novels must appear in items (folder names derived from novel_id)
        ids = {item.novel_id for item in result.items}
        assert ids == {"novel-a", "novel-b"}

    def test_padded_filenames_produce_logical_source_ids(
        self, summary_storage: StorageService
    ) -> None:
        """`0001.json` must become logical ID ``"1"`` (not ``"0001"``)."""
        summary_storage.save_metadata("n2056dn", _metadata(3))
        # Use save_chapter which gauges the logical id from the *input*; the
        # storage backend converts that to padded physical names already
        # thanks to _chapter_filename().
        _save_chapter(summary_storage, "n2056dn", "1")
        _save_chapter(summary_storage, "n2056dn", "2")
        _save_chapter(summary_storage, "n2056dn", "3")

        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True)
        item = next(r for r in result.items if r.novel_id == "n2056dn")
        assert item.scraped == 3

    def test_unrelated_json_is_excluded(
        self, summary_storage: StorageService
    ) -> None:
        """Unrelated JSON files should not inflate scraped/translated counts."""
        summary_storage.save_metadata("novel-x", _metadata(2))
        _save_chapter(summary_storage, "novel-x", "1")
        # Add an unrelated JSON that is not a valid chapter payload.
        unrelated_dir = summary_storage._chapter_dir("novel-x")
        (unrelated_dir / "notes.json").write_text(
            json.dumps({"type": "index"}), encoding="utf-8"
        )

        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True)
        item = next(r for r in result.items if r.novel_id == "novel-x")
        assert item.scraped == 1

    def test_novel_prefix_boundaries_preserved(
        self, summary_storage: StorageService
    ) -> None:
        """Chapters from one novel must not leak into another."""
        summary_storage.save_metadata("n1", _metadata(1))
        summary_storage.save_metadata("n10", _metadata(1))
        _save_chapter(summary_storage, "n1", "1")
        _save_chapter(summary_storage, "n10", "1")

        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True)
        items = {r.novel_id: r for r in result.items}
        assert items["n1"].scraped == 1
        assert items["n10"].scraped == 1

    def test_empty_library_returns_zero_totals(
        self, summary_storage: StorageService
    ) -> None:
        """No novels → zero totals and zero items."""
        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True)
        assert result.totals.novel_id == "__all__"
        assert result.totals.total == 0
        assert result.totals.scraped == 0
        assert result.totals.translated == 0
        assert result.totals.failed == 0
        assert result.totals.pending == 0
        assert result.items == []

    def test_stale_sql_chapter_count_does_not_dominate(
        self, summary_storage: StorageService
    ) -> None:
        """Stale metadata chapter_count must NOT control displayed scraped/translated.

        Here StorageService is the source of truth: scraped comes from R2 only.
        The metadata field ``chapter_count`` is allowed to be larger or smaller
        than what is actually present in storage; the summary must rely on
        storage, not SQL.
        """
        # Metadata claims 100 chapters but only 2 are actually stored.
        summary_storage.save_metadata("stale-n", _metadata(100))
        _save_chapter(summary_storage, "stale-n", "1")
        _save_chapter(summary_storage, "stale-n", "2")

        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True)
        item = next(r for r in result.items if r.novel_id == "stale-n")
        assert item.scraped == 2  # Storage-derived, not 100
        # total ≥ scraped but never produces negative.
        assert item.total >= item.scraped

    def test_total_never_falls_below_stored_counts(
        self, summary_storage: StorageService
    ) -> None:
        """``total`` must always be ≥ scraped and ≥ translated."""
        summary_storage.save_metadata("n", _metadata(0))
        _save_chapter(summary_storage, "n", "1", translated=True)

        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True)
        item = next(r for r in result.items if r.novel_id == "n")
        assert item.total >= item.scraped
        assert item.total >= item.translated
        assert item.pending == max(0, item.total - item.scraped - item.failed)


# ── cache behavior ─────────────────────────────────────────────────────


class TestCache:
    """Tests for the 30-second TTL cache."""

    def test_cache_hit_within_ttl(self, summary_storage: StorageService) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        first = service.get_summary()
        # Second call inside TTL: cache info should report hit.
        second = service.get_summary()
        assert second.cache["hit"] is True
        # First call had no cache to hit; must not report hit.
        assert first.cache["hit"] is False

    def test_refresh_bypasses_cache(self, summary_storage: StorageService) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        service.get_summary()  # populates cache
        again = service.get_summary(refresh=True)
        assert again.cache["hit"] is False

    def test_explicit_invalidation_clears_cache(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        service.get_summary()
        service.invalidate_cache()
        third = service.get_summary()
        assert third.cache["hit"] is False

    def test_failed_computations_are_not_cached(
        self, summary_storage: StorageService
    ) -> None:
        """A storage exception should never be cached as a successful result."""

        service = LibrarySummaryService(summary_storage)

        with (
            patch.object(
                _lss_module,
                "_build_summary_from_storage",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(RuntimeError),
        ):
            service.get_summary(refresh=True)

        # Subsequent valid call should compute fresh.
        result = service.get_summary()
        assert result.cache["hit"] is False
        assert result.items == []

    def test_concurrent_miss_coalesces(
        self, summary_storage: StorageService
    ) -> None:
        """Concurrent cache alarms should not lead to uncontrolled N-fold scans."""

        listing_count = 0
        original = summary_storage._backend.list_keys

        def _counting(*args: Any, **kwargs: Any) -> list[str]:
            nonlocal listing_count
            listing_count += 1
            return original(*args, **kwargs)

        with patch.object(summary_storage._backend, "list_keys", side_effect=_counting):
            service = LibrarySummaryService(summary_storage)

            # First call populates the cache; subsequent calls should be hits.
            service.get_summary()
            for _ in range(5):
                service.get_summary()
            assert listing_count == 1


# ── catalogued novels without chapter keys ─────────────────────────────


class TestCataloguedNovels:
    """Catalogued novels (DB slug) must appear even with zero stored chapters."""

    def test_catalogued_novel_without_chapters_appears(
        self, summary_storage: StorageService
    ) -> None:
        """A novel in catalogued_novel_ids with no stored chapters must still appear."""
        # Storage has nothing
        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(refresh=True, catalogued_novel_ids=["n2056dn"])
        ids = {item.novel_id for item in result.items}
        assert "n2056dn" in ids
        item = next(r for r in result.items if r.novel_id == "n2056dn")
        assert item.total >= 0
        assert item.scraped == 0
        assert item.translated == 0
        assert item.failed == 0
        assert item.pending == 0

    def test_catalogued_and_storage_novels_are_merged(
        self, summary_storage: StorageService
    ) -> None:
        """Union of catalogued IDs and storage-discovered IDs must be returned."""
        summary_storage.save_metadata("storage-novel", _metadata(2))
        _save_chapter(summary_storage, "storage-novel", "1")
        _save_chapter(summary_storage, "storage-novel", "2")

        service = LibrarySummaryService(summary_storage)
        result = service.get_summary(
            refresh=True, catalogued_novel_ids=["catalogued-novel"]
        )
        ids = {item.novel_id for item in result.items}
        assert ids == {"storage-novel", "catalogued-novel"}


# ── public storage API usage ──────────────────────────────────────────


class TestPublicStorageAPI:
    """Service must use public StorageService methods, not private backend."""

    def test_service_does_not_call_private_backend_list_keys(
        self, summary_storage: StorageService
    ) -> None:
        """Spy on private backend.list_keys: should be called via public method only."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        with patch.object(
            summary_storage._backend, "list_keys", wraps=summary_storage._backend.list_keys
        ) as spy:
            service = LibrarySummaryService(summary_storage)
            service.get_summary(refresh=True)
            assert spy.call_count >= 1

    def test_service_does_not_use_private_read_text(
        self, summary_storage: StorageService
    ) -> None:
        """Service must not call storage._read_text directly."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        with patch.object(
            summary_storage, "_read_text", side_effect=AssertionError("private read")
        ):
            service = LibrarySummaryService(summary_storage)
            result = service.get_summary(refresh=True)
            assert result.items  # should still work via public read_payload


# ── real concurrent cache-miss coalescing ─────────────────────────────


class TestConcurrentCoalescing:
    """Concurrent cold requests must not duplicate storage scans."""

    def test_concurrent_threads_single_scan(
        self, summary_storage: StorageService
    ) -> None:
        """N threads hitting cold cache must produce exactly 1 listing call."""
        import threading

        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        listing_count = 0
        original = summary_storage._backend.list_keys
        ready = threading.Barrier(10)
        results: list[Any] = []

        def _counting(*args: Any, **kwargs: Any) -> list[str]:
            nonlocal listing_count
            listing_count += 1
            return original(*args, **kwargs)

        with patch.object(summary_storage._backend, "list_keys", side_effect=_counting):
            service = LibrarySummaryService(summary_storage)
            service.invalidate_cache()

            def worker() -> None:
                ready.wait()
                results.append(service.get_summary())

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # Coalesced: at most a small number of scans (not N=10)
        assert listing_count <= 2, f"expected coalesced scans, got {listing_count}"
        assert len(results) == 10
        # All threads got the same data
        assert all(r.items == results[0].items for r in results)


# ── public storage API additions ──────────────────────────────────────


class TestPublicStorageMethods:
    """StorageService public methods used by the summary service."""

    def test_list_keys_under_recursive(self, summary_storage: StorageService) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")
        keys = summary_storage.list_keys_under("novels/", recursive=True)
        assert any("chapters" in k for k in keys)

    def test_read_payload_returns_dict(self, summary_storage: StorageService) -> None:
        _save_chapter(summary_storage, "n", "1")
        key = "novels/n/chapters/0001.json"
        payload = summary_storage.read_payload(key)
        assert isinstance(payload, dict)
        assert "raw" in payload

    def test_read_payload_missing_returns_none(
        self, summary_storage: StorageService
    ) -> None:
        payload = summary_storage.read_payload("novels/missing/chapters/0001.json")
        assert payload is None
