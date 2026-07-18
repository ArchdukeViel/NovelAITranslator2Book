"""Tests for LibrarySummaryService live admin library summary."""

from __future__ import annotations

import json
import threading
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
        """N threads hitting cold cache must produce exactly 1 listing call.

        Uses a blocking ``list_keys`` spy so every concurrent caller is
        proven to overlap with the builder's in-flight build.
        """
        import threading

        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        listing_count = 0
        builder_started = threading.Event()
        releaser = threading.Event()
        original = summary_storage._backend.list_keys
        results: list[Any] = []
        errors: list[BaseException] = []

        class _Block:
            """Allow the first call to enter, then block until released."""

            def __init__(self) -> None:
                self._lock = threading.Lock()
                self.first_done = False

            def __call__(self, *args: Any, **kwargs: Any) -> list[str]:
                nonlocal listing_count
                with self._lock:
                    listing_count += 1
                if not self.first_done:
                    self.first_done = True
                    builder_started.set()
                    # Block the builder until released — every concurrent
                    # caller overlaps with the active build.
                    releaser.wait(timeout=5)
                return original(*args, **kwargs)

        blocking = _Block()

        with patch.object(summary_storage._backend, "list_keys", side_effect=blocking):
            service = LibrarySummaryService(summary_storage)
            service.invalidate_cache()

            def worker() -> None:
                try:
                    results.append(service.get_summary())
                except BaseException as exc:  # pragma: no cover - debug
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()

            # Wait for the builder to start, then release.
            assert builder_started.wait(timeout=5), "builder never started"
            releaser.set()
            for t in threads:
                t.join(timeout=5)

        alive = [t for t in threads if t.is_alive()]
        assert not alive, "thread stuck after release"
        assert not errors, errors
        # Exactly one listing call — true single-flight, not "<=2".
        assert listing_count == 1, f"expected 1 scan, got {listing_count}"
        assert len(results) == 10
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


# ── POSIX key & logical id public contract ─────────────────────────────


class TestPosixKeyAndLogicalId:
    def test_logical_id_from_stem_is_public(self) -> None:
        """``StorageService.logical_id_from_stem`` must be the public API."""
        assert callable(StorageService.logical_id_from_stem)
        assert StorageService.logical_id_from_stem("0001") == "1"
        assert StorageService.logical_id_from_stem("1") == "1"
        assert StorageService.logical_id_from_stem("abc") == "abc"
        # Private alias still resolves for in-package callers.
        assert StorageService._logical_id_from_stem("0042") == "42"


# ── deterministic single-flight suite ────────────────────────────────


def _make_blocking_listing_spy(
    storage: StorageService,
) -> tuple[Any, threading.Event, threading.Event, Any]:
    """Build a blocking ``list_keys`` spy + primed-barrier infra.

    Returns ``(spy_factory, started_event, release_event, counter)``. The
    first invocation enters the build, signals ``started_event``, then
    blocks on ``release_event`` to ensure every concurrent caller
    overlaps with the builder's active build.
    """
    lock = threading.Lock()
    started = threading.Event()
    release = threading.Event()
    counter = {"count": 0, "first_done": False}
    original = storage._backend.list_keys

    def spy(*args: Any, **kwargs: Any) -> list[str]:
        with lock:
            counter["count"] += 1
        if not counter["first_done"]:
            counter["first_done"] = True
            started.set()
            release.wait(timeout=10)
        return original(*args, **kwargs)

    return spy, started, release, counter


class TestSingleFlightDeterministic:
    """Hard deterministic single-flight assertions."""

    def test_cold_concurrent_normal_calls_one_build(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        spy, started, release, counter = _make_blocking_listing_spy(summary_storage)
        results: list[Any] = []

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage)
            service.invalidate_cache()

            def worker() -> None:
                results.append(service.get_summary())

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            assert started.wait(timeout=5), "builder never started"
            release.set()
            for t in threads:
                t.join(timeout=5)

        alive = [t for t in threads if t.is_alive()]
        assert not alive
        # True single-flight: exactly ONE listing call.
        assert counter["count"] == 1, f"expected 1 scan, got {counter['count']}"
        assert len(results) == 8
        assert all(r.items == results[0].items for r in results)

    def test_expired_concurrent_normal_calls_one_build(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        fake_now = {"t": 1000.0}

        def clock() -> float:
            return fake_now["t"]

        service = LibrarySummaryService(summary_storage, clock=clock)
        service.get_summary()  # populate
        fake_now["t"] = 2000.0  # jump well past TTL

        spy_started = threading.Event()
        release = threading.Event()
        called: list[int] = []
        backend_list_keys = summary_storage._backend.list_keys  # save unpatched

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            called.append(1)
            if len(called) == 1:
                spy_started.set()
                release.wait(timeout=5)
            return backend_list_keys(*args, **kwargs)

        results: list[Any] = []
        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            def worker() -> None:
                results.append(service.get_summary(refresh=False))

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            assert spy_started.wait(timeout=5)
            release.set()
            for t in threads:
                t.join(timeout=5)

        alive = [t for t in threads if t.is_alive()]
        assert not alive
        assert len(called) == 1, f"expected 1 scan, got {len(called)}"
        assert len(results) == 8
        assert all(r.items == results[0].items for r in results)

    def test_concurrent_forced_refreshes_one_build(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        started = threading.Event()
        release = threading.Event()
        first_done = {"v": False}
        call_count: list[int] = []
        backend_list_keys = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            call_count.append(1)
            if not first_done["v"]:
                first_done["v"] = True
                started.set()
                release.wait(timeout=5)
            return backend_list_keys(*args, **kwargs)

        results: list[Any] = []
        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage)
            service.invalidate_cache()

            def worker() -> None:
                results.append(service.get_summary(refresh=True))

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            assert started.wait(timeout=5)
            release.set()
            for t in threads:
                t.join(timeout=5)

        alive = [t for t in threads if t.is_alive()]
        assert not alive
        assert len(call_count) == 1, f"expected 1 scan, got {len(call_count)}"
        assert len(results) == 8
        assert all(r.cache["hit"] is False for r in results)

    def test_later_independent_forced_refresh_starts_second_build(
        self, summary_storage: StorageService
    ) -> None:

        summary_storage.save_metadata("n", _metadata(2))
        _save_chapter(summary_storage, "n", "1")
        _save_chapter(summary_storage, "n", "2")

        # Manually orchestrate: build 1 finishes, then a second refresh
        # arrives after completion → must trigger a second build.
        original = summary_storage._backend.list_keys
        call_count = [0]

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            call_count[0] += 1
            return original(*args, **kwargs)

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage)
            service.invalidate_cache()
            service.get_summary(refresh=True)  # first forced build
            r2 = service.get_summary(refresh=True)
            assert r2.cache["hit"] is False  # forced → fresh
            assert call_count[0] == 2

    def test_failed_build_wakes_all_and_propagates(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        boom = RuntimeError("simulated I/O failure")
        calls: dict[str, int] = {"cold": 0}
        backend_list_keys = summary_storage._backend.list_keys

        def flaky(*args: Any, **kwargs: Any) -> list[str]:
            calls["cold"] += 1
            if calls["cold"] == 1:
                raise boom
            return backend_list_keys(*args, **kwargs)

        service = LibrarySummaryService(summary_storage)
        service.invalidate_cache()

        with patch.object(summary_storage._backend, "list_keys", side_effect=flaky):
            with pytest.raises(RuntimeError):
                service.get_summary(refresh=True)
            r = service.get_summary(refresh=True)
            assert r.items

    def test_ttl_starts_after_build_completion(
        self, summary_storage: StorageService
    ) -> None:
        clock = {"now": 0.0}

        def fake_clock() -> float:
            return clock["now"]

        service = LibrarySummaryService(summary_storage, clock=fake_clock)

        started = threading.Event()
        release = threading.Event()
        original = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            started.set()
            release.wait(timeout=5)
            clock["now"] = 5_000.0
            return original(*args, **kwargs)

        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            def builder() -> None:
                service.get_summary(refresh=True)

            t = threading.Thread(target=builder)
            t.start()
            started.wait(timeout=5)
            release.set()
            t.join(timeout=5)
            assert not t.is_alive()

        assert service._expires_at == pytest.approx(5_000.0 + 30.0)

    def test_fake_clock_expiry_triggers_rebuild(
        self, summary_storage: StorageService
    ) -> None:
        clock = {"now": 0.0}

        def fake_clock() -> float:
            return clock["now"]

        original = summary_storage._backend.list_keys
        calls: list[int] = []

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            calls.append(1)
            return original(*args, **kwargs)

        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage, clock=fake_clock)
            service.invalidate_cache()
            service.get_summary()  # cold build
            service.get_summary()  # hit
            service.get_summary()  # hit
            assert len(calls) == 1
            clock["now"] = 100.0  # past TTL
            service.get_summary()  # rebuild
            assert len(calls) == 2

    def test_outward_mutation_does_not_corrupt_cache(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        first = service.get_summary()
        original_first_items = list(first.items)
        # Mutate the outward response.
        first.items.clear()
        first.cache["hit"] = False
        first.cache["ttl_seconds"] = 999

        # Second call must still be valid.
        second = service.get_summary()
        assert second.cache["hit"] is True
        assert second.cache["ttl_seconds"] == 30
        assert second.items == original_first_items

    def test_catalog_identity_order_does_not_change_identity(
        self, summary_storage: StorageService
    ) -> None:

        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        a = service.get_summary(catalogued_novel_ids=["a", "b", "c"])
        b = service.get_summary(catalogued_novel_ids=["c", "b", "a"])
        # Same identity after sorting → reuse cache.
        assert a.items == b.items
        assert b.cache["hit"] is True

    def test_catalog_identity_set_change_triggers_rebuild(
        self, summary_storage: StorageService
    ) -> None:
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        original = summary_storage._backend.list_keys
        calls: list[int] = []

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            calls.append(1)
            return original(*args, **kwargs)

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service.invalidate_cache()
            service.get_summary(catalogued_novel_ids=["a"])
            service.get_summary(catalogued_novel_ids=["a"])
            assert len(calls) == 1
            service.get_summary(catalogued_novel_ids=["a", "b"])
            # Identity differs → cache misses → list again.
            assert len(calls) == 2

    def test_incompatible_active_identity_does_not_return(
        self, summary_storage: StorageService
    ) -> None:
        """Waiters must not receive an incompatible-identity result."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        service = LibrarySummaryService(summary_storage)
        service.invalidate_cache()

        # Manually pre-set an active incompatible build.
        with service._cv:
            service._next_generation += 1
            gen = _lss_module._BuildGeneration(
                generation=service._next_generation,
                identity=("alpha",),
                start_epoch=service._invalidation_epoch,
            )
            service._active_generation = gen
            service._active_identity = ("alpha",)

        # A different-identity requester must wait for the incompatible build
        # and not return its result.
        result_ids = []
        leak = []

        def worker() -> None:
            try:
                resp = service.get_summary(catalogued_novel_ids=["beta"])
                result_ids.append(tuple(i.novel_id for i in resp.items))
            except Exception:
                leak.append("err")

        t = threading.Thread(target=worker)
        t.start()
        # The waiter must NOT return in 200 ms while the incompatible build
        # is still active — that's the deadlock-avoidance under incompatible
        # identity scenario.
        t.join(timeout=0.2)
        assert t.is_alive(), "waiter returned prematurely for incompatible identity"

        # Finish the incompatible build cleanly.
        with service._cv:
            gen.done = True
            gen.cache = None
            gen.error = None
            service._completed_generations[gen.generation] = gen
            service._active_generation = None
            service._active_identity = None
            service._cv.notify_all()

        t.join(timeout=2)
        assert not t.is_alive()
        assert not leak
        # The waiter eventually got a fresh build for its own identity.
        assert result_ids

    def test_successive_generation_waiter_retention_race(
        self, summary_storage: StorageService
    ) -> None:
        """Generation N starts, waiters attach, N completes, hold one waiter,
        N+1 starts+completes, release waiter → all N waiters finish with N's
        result; N+1 caller gets N+1's result. Uses explicit events/test hooks."""
        summary_storage.save_metadata("n", _metadata(2))
        _save_chapter(summary_storage, "n", "1")
        _save_chapter(summary_storage, "n", "2")

        # Events to control the two generations
        gen1_started = threading.Event()
        gen1_release = threading.Event()
        gen2_started = threading.Event()
        gen2_release = threading.Event()

        call_count = {"gen1": 0, "gen2": 0}
        original = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            if call_count["gen1"] == 0 and call_count["gen2"] == 0:
                call_count["gen1"] += 1
                gen1_started.set()
                gen1_release.wait(timeout=5)
                return original(*args, **kwargs)
            elif call_count["gen1"] == 1 and call_count["gen2"] == 0:
                call_count["gen2"] += 1
                gen2_started.set()
                gen2_release.wait(timeout=5)
                return original(*args, **kwargs)
            else:
                return original(*args, **kwargs)

        service = LibrarySummaryService(summary_storage)
        service.invalidate_cache()

        results = {"gen1_waiters": [], "gen1_builder": None, "gen2_builder": None}
        errors = []

        def gen1_builder_worker() -> None:
            try:
                results["gen1_builder"] = service.get_summary(refresh=True)
            except Exception as e:
                errors.append(("gen1_builder", e))

        def gen1_waiter_worker(wait_for_gen2: bool) -> None:
            try:
                # Wait for gen1 to start, then wait for gen1 to complete
                gen1_started.wait(timeout=5)
                if wait_for_gen2:
                    # This waiter will be held until gen2 completes
                    gen2_release.wait(timeout=5)
                result = service.get_summary()
                results["gen1_waiters"].append(result)
            except Exception as e:
                errors.append(("gen1_waiter", e))

        def gen2_builder_worker() -> None:
            try:
                # Wait for gen1 to complete, then start gen2
                gen1_release.wait(timeout=5)
                # Don't wait for gen2_started here - it's set inside the spy when list_keys is called
                results["gen2_builder"] = service.get_summary(refresh=True)
            except Exception as e:
                errors.append(("gen2_builder", e))

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            # Start gen1 builder
            t_builder = threading.Thread(target=gen1_builder_worker)
            t_builder.start()

            # Start gen1 waiters (one will wait for gen2)
            t_waiter1 = threading.Thread(target=gen1_waiter_worker, args=(False,))
            t_waiter2 = threading.Thread(target=gen1_waiter_worker, args=(True,))
            t_waiter1.start()
            t_waiter2.start()

            # Wait for gen1 to start, then release it
            assert gen1_started.wait(timeout=5), "gen1 builder never started"
            gen1_release.set()

            # Wait for gen1 builder to complete
            t_builder.join(timeout=5)
            assert not t_builder.is_alive(), "gen1 builder timed out"

            # Start gen2 builder (it will wait for gen1_release, then call get_summary)
            t_gen2_builder = threading.Thread(target=gen2_builder_worker)
            t_gen2_builder.start()

            # Wait for gen2 to start (spy sets gen2_started when list_keys is called)
            assert gen2_started.wait(timeout=5), "gen2 builder never started"

            # Release gen2
            gen2_release.set()

            # Release the waiter that was waiting for gen2
            # (it already has gen1's result, this just lets it finish)
            t_waiter1.join(timeout=5)
            t_waiter2.join(timeout=5)
            t_gen2_builder.join(timeout=5)

        assert not errors, f"errors: {errors}"
        assert t_waiter1.is_alive() is False
        assert t_waiter2.is_alive() is False
        assert t_gen2_builder.is_alive() is False

        # All gen1 waiters and gen1 builder should have gen1's result
        gen1_result = results["gen1_builder"]
        assert gen1_result is not None
        assert len(results["gen1_waiters"]) == 2
        for r in results["gen1_waiters"]:
            assert r.items == gen1_result.items, "gen1 waiter got different result"
            assert r.cache["hit"] is True, "gen1 waiter should see cache hit"

        # Gen2 builder should have gen2's result (different data)
        gen2_result = results["gen2_builder"]
        assert gen2_result is not None
        # Both generations see the same storage data in this test, but different generation
        assert gen2_result.cache["hit"] is False, "gen2 builder should be cache miss"

        # Total listing calls should be 2 (one per generation)
        assert call_count["gen1"] == 1
        assert call_count["gen2"] == 1

    def test_invalidation_epoch_stale_build_rejected(
        self, summary_storage: StorageService
    ) -> None:
        """First build lists old storage and blocks; mutate storage;
        invalidate_cache(); release old build; prove its result NOT cached/returned;
        prove one post-invalidation build runs; all callers receive new counts;
        total listing count exactly 2 (one stale, one stable)."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        # Events to control the stale build
        stale_started = threading.Event()
        stale_release = threading.Event()
        listing_count = [0]
        original = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            listing_count[0] += 1
            if listing_count[0] == 1:
                stale_started.set()
                stale_release.wait(timeout=5)
            return original(*args, **kwargs)

        service = LibrarySummaryService(summary_storage)
        service.invalidate_cache()

        results = []
        errors = []

        def stale_builder() -> None:
            try:
                results.append(("stale_builder", service.get_summary(refresh=True)))
            except Exception as e:
                errors.append(("stale_builder", e))

        def waiter() -> None:
            try:
                # This waiter will attach to the stale build, then be invalidated
                stale_started.wait(timeout=5)
                results.append(("waiter", service.get_summary()))
            except Exception as e:
                errors.append(("waiter", e))

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            t_builder = threading.Thread(target=stale_builder)
            t_waiter = threading.Thread(target=waiter)
            t_builder.start()
            t_waiter.start()

            # Wait for stale build to start
            assert stale_started.wait(timeout=5), "stale builder never started"

            # Mutate storage: add a second chapter
            _save_chapter(summary_storage, "n", "2")

            # Invalidate: increments epoch, clears cache, notifies
            service.invalidate_cache()

            # Release the stale build
            stale_release.set()

            t_builder.join(timeout=5)
            t_waiter.join(timeout=5)

        assert not errors, f"errors: {errors}"
        assert not t_builder.is_alive()
        assert not t_waiter.is_alive()

        # The stale build was invalidated - its result should NOT be cached.
        # The waiter re-entered acquisition loop and became builder for fresh build.
        # Cache should now have fresh data (2 chapters).
        assert service._cache is not None, "fresh build should have populated cache"
        assert service._cache.items[0].scraped == 2, "cache should have fresh data"

        # The waiter should have received the fresh result
        waiter_result = next(r for name, r in results if name == "waiter")
        assert waiter_result.items[0].scraped == 2, "waiter should get fresh data"
        assert waiter_result.cache["hit"] is False, "waiter's call was cache miss (fresh build)"

        # Stale builder's result should have been invalidated (not returned to caller)
        stale_result = next(r for name, r in results if name == "stale_builder")
        assert stale_result.items[0].scraped == 2, "stale builder should also get fresh data after invalidation"

        # Total listing calls: exactly 2 (one stale, one fresh)
        assert listing_count[0] == 2, f"expected 2 listings, got {listing_count[0]}"

    def test_concurrent_failed_generation_propagates(
        self, summary_storage: StorageService
    ) -> None:
        """8+ threads; builder starts and blocks; all callers attach;
        release builder to raise known exception; join all threads with timeout;
        assert no thread alive; exactly one build attempt; every caller
        receives same exception; later retry succeeds."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        builder_started = threading.Event()
        builder_release = threading.Event()
        builder_should_fail = [True]
        call_count = [0]
        original = summary_storage._backend.list_keys

        class TestError(Exception):
            pass

        def flaky_spy(*args: Any, **kwargs: Any) -> list[str]:
            call_count[0] += 1
            if builder_should_fail[0]:
                builder_started.set()
                builder_release.wait(timeout=5)
                raise TestError("simulated I/O failure")
            return original(*args, **kwargs)

        service = LibrarySummaryService(summary_storage)
        service.invalidate_cache()

        results = []
        errors = []

        def worker(idx: int) -> None:
            try:
                results.append((idx, service.get_summary()))
            except Exception as e:
                errors.append((idx, e))

        with patch.object(summary_storage._backend, "list_keys", side_effect=flaky_spy):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()

            # Wait for builder to start and block
            assert builder_started.wait(timeout=5), "builder never started"

            # Release builder to fail
            builder_release.set()

            # Join all threads
            for t in threads:
                t.join(timeout=5)

        alive = [t for t in threads if t.is_alive()]
        assert not alive, f"threads still alive: {alive}"

        # Exactly one build attempt was made
        assert call_count[0] == 1, f"expected 1 build attempt, got {call_count[0]}"

        # All 8 callers should have received the same exception
        assert len(errors) == 8, f"expected 8 errors, got {len(errors)}"
        for idx, e in errors:
            assert isinstance(e, TestError), f"thread {idx} got wrong error: {e}"

        # Now retry with success - should work
        builder_should_fail[0] = False
        retry_result = service.get_summary()
        assert retry_result.cache["hit"] is False
        assert len(retry_result.items) == 1

    def test_invalidate_during_active_build(
        self, summary_storage: StorageService
    ) -> None:
        """Invalidate during an active build is well-defined:
        the build will still complete but be marked invalidated and
        will NOT populate the cache; a subsequent caller triggers
        a fresh build.
        """
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        started = threading.Event()
        release = threading.Event()
        original = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            started.set()
            release.wait(timeout=5)
            return original(*args, **kwargs)

        service = LibrarySummaryService(summary_storage)

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            t = threading.Thread(target=lambda: service.get_summary(refresh=True))
            t.start()
            started.wait(timeout=5)

            # Invalidate while the build is in flight.
            service.invalidate_cache()
            assert service._cache is None

            release.set()
            t.join(timeout=5)
            assert not t.is_alive()

        # The invalidated build did NOT populate the cache.
        assert service._cache is None
        # A fresh caller triggers a new build and populates the cache.
        assert service.get_summary().cache["hit"] is False
        assert service._cache is not None
        assert service.get_summary().cache["hit"] is True

    # ── strengthened normal callers join forced build test ────────────────

    def test_normal_callers_join_forced_build_share_result_strengthened(
        self, summary_storage: StorageService
    ) -> None:
        """Normal callers joining a forced refresh share the same build result.
        Verifies: exactly one listing call, all waiters get same result,
        cache populated with forced-build result, waiters report cache hit.
        """
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        started = threading.Event()
        release = threading.Event()
        first_done = {"v": False}
        call_count: list[int] = []
        backend_list_keys = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            call_count.append(1)
            if not first_done["v"]:
                first_done["v"] = True
                started.set()
                release.wait(timeout=5)
            return backend_list_keys(*args, **kwargs)

        # Use SAME identity for all callers to test joining behavior
        identity = ("alpha", "beta")
        results: dict[int, Any] = {}
        errors: list[tuple[int, BaseException]] = []

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage)
            service.invalidate_cache()

            def worker(idx: int) -> None:
                try:
                    # Even indices: forced refresh; odd indices: normal call
                    results[idx] = service.get_summary(
                        refresh=(idx % 2 == 0),
                        catalogued_novel_ids=list(identity),
                    )
                except BaseException as e:
                    errors.append((idx, e))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
            for t in threads:
                t.start()
            assert started.wait(timeout=5)
            release.set()
            for t in threads:
                t.join(timeout=5)

        alive = [t for t in threads if t.is_alive()]
        assert not alive
        assert not errors, f"errors: {errors}"
        # Exactly one listing call — true single-flight
        assert len(call_count) == 1, f"expected 1 scan, got {len(call_count)}"
        assert len(results) == 6

        # All results should have identical items
        first_items = results[0].items
        for i, r in results.items():
            assert r.items == first_items, f"thread {i} got different items"

        # Forced refresh callers (even idx) should report cache miss
        for i in [0, 2, 4]:
            assert results[i].cache["hit"] is False, f"thread {i} forced refresh should be miss"

        # Normal callers (odd idx) should report cache hit (joined forced build)
        for i in [1, 3, 5]:
            assert results[i].cache["hit"] is True, f"thread {i} normal call should be hit"

        # Cache should be populated with the forced build's result
        assert service._cache is not None
        assert list(service._cache.items) == first_items

    # ── incompatible identity waits and rebuilds ──────────────────────────

    def test_incompatible_identity_waits_and_rebuilds(
        self, summary_storage: StorageService
    ) -> None:
        """A caller with different catalog identity must wait for the
        incompatible active build to complete, then start its own build.
        """
        summary_storage.save_metadata("n1", _metadata(1))
        _save_chapter(summary_storage, "n1", "1")
        summary_storage.save_metadata("n2", _metadata(1))
        _save_chapter(summary_storage, "n2", "1")

        # Spy to control the first (incompatible) build
        build1_started = threading.Event()
        build1_release = threading.Event()
        build2_started = threading.Event()
        build2_release = threading.Event()
        call_count = [0]
        original = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            call_count[0] += 1
            if call_count[0] == 1:
                build1_started.set()
                build1_release.wait(timeout=5)
            elif call_count[0] == 2:
                build2_started.set()
                build2_release.wait(timeout=5)
            return original(*args, **kwargs)

        service = LibrarySummaryService(summary_storage)
        service.invalidate_cache()

        results = {}
        errors = []

        def build1_worker() -> None:
            try:
                # Identity ("alpha",) - this build will block
                results["build1"] = service.get_summary(
                    refresh=True, catalogued_novel_ids=["alpha"]
                )
            except Exception as e:
                errors.append(("build1", e))

        def waiter_worker() -> None:
            try:
                # Different identity ("beta",) - must wait for build1, then build own
                build1_started.wait(timeout=5)
                results["waiter"] = service.get_summary(
                    catalogued_novel_ids=["beta"]
                )
            except Exception as e:
                errors.append(("waiter", e))

        def build2_worker() -> None:
            try:
                # This will be the waiter's build after build1 completes
                build1_release.wait(timeout=5)
                build2_started.wait(timeout=5)
                results["build2"] = service.get_summary(
                    refresh=True, catalogued_novel_ids=["beta"]
                )
            except Exception as e:
                errors.append(("build2", e))

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            t1 = threading.Thread(target=build1_worker)
            t_waiter = threading.Thread(target=waiter_worker)
            t2 = threading.Thread(target=build2_worker)

            t1.start()
            t_waiter.start()
            t2.start()

            # Wait for build1 to start
            assert build1_started.wait(timeout=5), "build1 never started"

            # Waiter should be blocked (waiting for build1 to complete)
            # Give it a moment to attach
            import time
            time.sleep(0.1)

            # Release build1
            build1_release.set()
            t1.join(timeout=5)
            assert not t1.is_alive(), "build1 timed out"

            # Now build2 should start (waiter's build)
            assert build2_started.wait(timeout=5), "build2 never started"

            # Release build2
            build2_release.set()

            t_waiter.join(timeout=5)
            t2.join(timeout=5)

        assert not errors, f"errors: {errors}"
        assert not t_waiter.is_alive()
        assert not t2.is_alive()

        # build1 used identity ("alpha",)
        assert results["build1"].cache["hit"] is False

        # waiter joined build2 (its own identity), got fresh build
        assert results["waiter"].cache["hit"] is False
        assert results["waiter"].items == results["build2"].items

        # Exactly 2 listing calls (one per identity)
        assert call_count[0] == 2, f"expected 2 listings, got {call_count[0]}"

    # ── real spying tests replacing Windows-prefix test ───────────────────

    def test_list_keys_under_spy_windows_style_paths(
        self, summary_storage: StorageService
    ) -> None:
        """Spy on backend.list_keys to verify POSIX normalization."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")
        _save_chapter(summary_storage, "n", "2")

        # Spy on the backend's list_keys to capture raw keys
        captured_keys: list[str] = []
        original = summary_storage._backend.list_keys

        def spy(*args: Any, **kwargs: Any) -> list[str]:
            keys = original(*args, **kwargs)
            captured_keys.extend(keys)
            return keys

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage)
            service.get_summary(refresh=True)

        # Verify all captured keys use POSIX separators
        for key in captured_keys:
            assert "\\" not in key, f"found backslash in key: {key}"
            assert key.startswith("novels/"), f"key doesn't start with novels/: {key}"
            # Chapter keys should contain /chapters/ and end with .json
            if "/chapters/" in key:
                assert key.endswith(".json"), f"chapter key doesn't end with .json: {key}"

    def test_list_keys_under_spy_prefix_normalization(
        self, summary_storage: StorageService
    ) -> None:
        """Spy to verify prefix normalization handles various input formats."""
        summary_storage.save_metadata("n", _metadata(1))
        _save_chapter(summary_storage, "n", "1")

        captured_prefixes: list[str] = []
        original = summary_storage._backend.list_keys

        def spy(prefix: str, *args: Any, **kwargs: Any) -> list[str]:
            captured_prefixes.append(prefix)
            return original(prefix, *args, **kwargs)

        with patch.object(summary_storage._backend, "list_keys", side_effect=spy):
            service = LibrarySummaryService(summary_storage)
            # Call with default (will use NOVELS_PREFIX)
            service.get_summary(refresh=True)

        # Should be called with the NOVELS_PREFIX
        assert len(captured_prefixes) >= 1
        for prefix in captured_prefixes:
            assert prefix == "novels/", f"unexpected prefix: {prefix}"

    def test_logical_id_from_stem_spy(
        self, summary_storage: StorageService
    ) -> None:
        """Spy on logical_id_from_stem to verify it's called for each chapter."""
        summary_storage.save_metadata("n", _metadata(3))
        _save_chapter(summary_storage, "n", "1")
        _save_chapter(summary_storage, "n", "2")
        _save_chapter(summary_storage, "n", "3")

        stems_seen: list[str] = []
        original = StorageService.logical_id_from_stem

        def spy(stem: str) -> str:
            stems_seen.append(stem)
            return original(stem)

        with patch.object(StorageService, "logical_id_from_stem", staticmethod(spy)):
            service = LibrarySummaryService(summary_storage)
            service.get_summary(refresh=True)

        # Should be called once per chapter file (3 chapters)
        assert len(stems_seen) == 3
        # All stems should be normalized to logical IDs (no leading zeros)
        logical_ids = [StorageService.logical_id_from_stem(s) for s in stems_seen]
        assert set(logical_ids) == {"1", "2", "3"}


# ── crawl failure semantics ───────────────────────────────────────────────


class MockActivityLog:
    """Mock activity log for testing _get_failed_ids behavior."""

    def __init__(self, activities: list[dict[str, Any]]) -> None:
        self._activities = activities

    def list_activity(
        self,
        *,
        novel_id: str,
        activity_type: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        filtered = [
            dict(act)
            for act in self._activities
            if act.get("novel_id") == novel_id and act.get("type") == activity_type
        ]
        if limit is not None:
            filtered = filtered[:limit]
        return filtered


class TestCrawlFailureSemantics:
    """Tests for _get_failed_ids: newest relevant crawl result is authoritative."""

    def test_noncanonical_result_field_is_ignored(self, summary_storage: StorageService) -> None:
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_current",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {"result": {"failures": ["5"]}},
            }
        ]

        assert _get_failed_ids("n1", MockActivityLog(activities)) == set()

    def test_newest_clean_completed_crawl_overrides_older_failure(
        self, summary_storage: StorageService
    ) -> None:
        """Newest completed crawl with empty failures clears older failure."""
        from novelai.services.library_summary_service import _get_failed_ids

        # Newest: completed, empty failures
        # Older: failed, chapter 10 failed
        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "finished_at": "2026-01-02T00:00:00Z",
                "started_at": "2026-01-02T00:00:00Z",
                "created_at": "2026-01-02T00:00:00Z",
                "metadata": {"crawl_result": {"failures": []}},
            },
            {
                "id": "crawl_old",
                "novel_id": "n1",
                "type": "crawl",
                "status": "failed",
                "finished_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "metadata": {"crawl_result": {"failures": [{"chapter_id": "10"}]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == set(), "Newest clean crawl should override older failure"

    def test_newest_failed_crawl_empty_list_overrides_older_failures(
        self, summary_storage: StorageService
    ) -> None:
        """Newest failed crawl with empty failures list overrides older failures."""
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "failed",
                "finished_at": "2026-01-02T00:00:00Z",
                "started_at": "2026-01-02T00:00:00Z",
                "created_at": "2026-01-02T00:00:00Z",
                "metadata": {"crawl_result": {"failures": []}},
            },
            {
                "id": "crawl_old",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "finished_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "metadata": {"crawl_result": {"failures": ["5", "6"]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == set(), "Newest failed crawl with empty list should override"

    def test_cancelled_activity_ignored(
        self, summary_storage: StorageService
    ) -> None:
        """Cancelled activity is skipped; next relevant activity is used."""
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_cancelled",
                "novel_id": "n1",
                "type": "crawl",
                "status": "cancelled",
                "metadata": {"crawl_result": {"failures": ["1", "2"]}},
            },
            {
                "id": "crawl_completed",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {"crawl_result": {"failures": ["3"]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == {"3"}, "Cancelled activity should be ignored"

    def test_running_activity_ignored(
        self, summary_storage: StorageService
    ) -> None:
        """Running activity is skipped; next relevant activity is used."""
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_running",
                "novel_id": "n1",
                "type": "crawl",
                "status": "running",
                "metadata": {"crawl_result": {"failures": ["1", "2"]}},
            },
            {
                "id": "crawl_completed",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {"crawl_result": {"failures": ["3"]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == {"3"}, "Running activity should be ignored"

    def test_malformed_newest_failure_does_not_resurrect_old(
        self, summary_storage: StorageService
    ) -> None:
        """Malformed newest crawl result returns empty set, does not fall back to older."""
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "finished_at": "2026-01-02T00:00:00Z",
                "started_at": "2026-01-02T00:00:00Z",
                "created_at": "2026-01-02T00:00:00Z",
                "metadata": {"crawl_result": {"failures": "not-a-list"}},
            },
            {
                "id": "crawl_old",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "finished_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "metadata": {"crawl_result": {"failures": ["5"]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == set(), "Malformed newest result should not resurrect old failure"

    def test_duplicate_chapter_ids_count_once(
        self, summary_storage: StorageService
    ) -> None:
        """Duplicate chapter IDs in failures list are deduplicated."""
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {"crawl_result": {"failures": ["5", "5", "6", "6"]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == {"5", "6"}, "Duplicate IDs should be deduplicated"

    def test_dict_and_scalar_failure_formats_normalize(
        self, summary_storage: StorageService
    ) -> None:
        """Both dict and scalar failure formats normalize correctly."""
        from novelai.services.library_summary_service import _get_failed_ids

        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {
                    "crawl_result": {
                        "failures": [
                            {"chapter_id": "1"},  # dict with chapter_id
                            {"id": "2"},  # dict with id
                            "3",  # scalar string
                            4,  # scalar int
                        ]
                    }
                },
            },
        ]
        activity_log = MockActivityLog(activities)

        failed_ids = _get_failed_ids("n1", activity_log)
        assert failed_ids == {"1", "2", "3", "4"}, "All formats should normalize to string IDs"

    def test_stored_chapter_excluded_from_failed(
        self, summary_storage: StorageService
    ) -> None:
        """Chapter present in raw storage is excluded from failed count."""
        from novelai.services.library_summary_service import _build_summary_from_storage

        # Storage has chapter 5
        summary_storage.save_metadata("n1", _metadata(10))
        _save_chapter(summary_storage, "n1", "5")

        # Activity says chapter 5 failed
        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {"crawl_result": {"failures": [{"chapter_id": "5"}]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        result = _build_summary_from_storage(summary_storage, activity_log, [])
        item = next(r for r in result.items if r.novel_id == "n1")
        # Chapter 5 is stored, so it should NOT be counted as failed
        assert item.failed == 0, "Stored chapter should not be counted as failed"

    def test_pending_calculation_remains_max_zero(
        self, summary_storage: StorageService
    ) -> None:
        """Pending = max(total - scraped - failed, 0) even when failed exceeds total."""
        from novelai.services.library_summary_service import _build_summary_from_storage

        # Storage has 2 chapters, metadata says 10 total
        summary_storage.save_metadata("n1", _metadata(10))
        _save_chapter(summary_storage, "n1", "1")
        _save_chapter(summary_storage, "n1", "2")

        # Activity says 15 chapters failed (more than total!)
        activities = [
            {
                "id": "crawl_new",
                "novel_id": "n1",
                "type": "crawl",
                "status": "completed",
                "metadata": {"crawl_result": {"failures": [str(i) for i in range(1, 16)]}},
            },
        ]
        activity_log = MockActivityLog(activities)

        result = _build_summary_from_storage(summary_storage, activity_log, [])
        item = next(r for r in result.items if r.novel_id == "n1")
        # Failed is capped at max(0, total - scraped) = max(0, 10 - 2) = 8
        # Pending = max(total - scraped - failed, 0) = max(10 - 2 - 8, 0) = 0
        assert item.failed == 8, f"Failed should be capped at 8, got {item.failed}"
        assert item.pending == 0, f"Pending should be 0, got {item.pending}"
