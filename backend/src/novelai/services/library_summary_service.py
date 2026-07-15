"""Live admin Library summary service.

Counts are derived from canonical R2/S3 storage, not from SQL catalog
projections.  Uses a single recursive listing pass per uncached refresh,
an in-process 30-second TTL cache, and true single-flight concurrency
for cold, expired, and forced refreshes.

State model:

* ``_cache`` / ``_expires_at`` — currently valid cache for one catalog identity
* ``_active_generation`` / ``_active_identity`` — the in-flight build, if any
* ``_completed`` — mapping from completed generation → outcome
* ``_next_generation`` — monotonic counter for generation allocation

Under the condition lock we always:

1. pick the generation we should run with,
2. allocate it atomically if needed,
3. release the lock for the build,
4. publish cache + outcome together, then notify.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from threading import Condition
from typing import Any

from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30

NOVELS_PREFIX = "novels/"


@dataclass(frozen=True)
class NovelSummaryCounts:
    novel_id: str
    total: int = 0
    scraped: int = 0
    translated: int = 0
    failed: int = 0
    pending: int = 0


@dataclass(frozen=True)
class _CachedSummary:
    """Immutable cached summary with catalog identity."""

    generated_at: str
    totals: NovelSummaryCounts
    items: tuple[NovelSummaryCounts, ...]
    catalog_identity: tuple[str, ...]


@dataclass(frozen=True)
class _CompletedBuild:
    """Outcome of a finished generation: either data or error, never both."""

    generation: int
    identity: tuple[str, ...]
    cache: _CachedSummary | None
    error: BaseException | None


@dataclass
class SummaryResponse:
    """Outward response with caller-specific cache metadata."""

    generated_at: str
    cache: dict[str, Any]
    totals: NovelSummaryCounts
    items: list[NovelSummaryCounts]


def _is_chapter_key(key: str) -> bool:
    return key.endswith(".json") and "/chapters/" in key


def _parse_novel_id_from_key(key: str, novels_prefix: str) -> str | None:
    rest = key[len(novels_prefix):]
    if "/" not in rest:
        return None
    folder = rest[: rest.index("/")]
    if not folder:
        return None
    return folder


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _get_failed_ids(
    novel_id: str,
    activity_log: Any | None,
) -> set[str]:
    if activity_log is None:
        return set()
    try:
        activities = activity_log.list_activity(
            novel_id=novel_id,
            activity_type="crawl",
            limit=5,
        )
    except Exception:
        logger.debug("Failed to list crawl activities for %s", novel_id, exc_info=True)
        return set()

    for act in activities:
        status = act.get("status")
        if status not in ("completed", "failed"):
            continue
        metadata = act.get("metadata") or {}
        crawl_result = metadata.get("crawl_result") or metadata.get("result") or {}
        failures = crawl_result.get("failures") or []
        if not isinstance(failures, list):
            continue
        ids: set[str] = set()
        for f in failures:
            if isinstance(f, dict):
                cid = f.get("chapter_id") or f.get("id")
            else:
                cid = f
            if cid is not None:
                ids.add(str(cid))
        if ids:
            return ids
    return set()


def _build_summary_from_storage(
    storage: StorageService,
    activity_log: Any | None,
    catalogued_novel_ids: list[str],
) -> _CachedSummary:
    """Single canonical build. Single recursive listing pass."""
    all_keys = storage.list_keys_under(NOVELS_PREFIX, recursive=True)

    inventory: dict[str, dict[str, set[str]]] = {}

    for key in all_keys:
        if not _is_chapter_key(key):
            continue
        folder = _parse_novel_id_from_key(key, NOVELS_PREFIX)
        if folder is None:
            continue
        stem = PurePosixPath(key).stem
        logical = StorageService.logical_id_from_stem(stem)
        bucket = inventory.setdefault(
            folder,
            {"chapter_ids": set(), "translated_ids": set(), "raw_ids": set()},
        )
        bucket["chapter_ids"].add(logical)

        payload = storage.read_payload(key)
        if payload is not None:
            if isinstance(payload.get("translated"), dict):
                bucket["translated_ids"].add(logical)
            if isinstance(payload.get("raw"), dict):
                bucket["raw_ids"].add(logical)

    all_novel_ids: set[str] = set(catalogued_novel_ids)
    all_novel_ids.update(inventory.keys())

    items: list[NovelSummaryCounts] = []
    total_total = total_scraped = total_translated = total_failed = total_pending = 0

    for novel_id in sorted(all_novel_ids):
        bucket = inventory.get(
            novel_id,
            {"chapter_ids": set(), "translated_ids": set(), "raw_ids": set()},
        )
        scraped = len(bucket["raw_ids"])
        translated = len(bucket["translated_ids"])

        try:
            meta = storage.load_metadata(novel_id)
        except Exception:
            meta = None
        chapter_list = (meta or {}).get("chapters")
        if isinstance(chapter_list, list):
            total = len(chapter_list)
        elif meta is not None and isinstance(meta.get("chapter_count"), int):
            total = meta["chapter_count"]
        else:
            total = max(scraped, translated, 0)
        total = max(total, scraped, translated)

        failed_ids = _get_failed_ids(novel_id, activity_log)
        failed = sum(1 for cid in failed_ids if cid not in bucket["raw_ids"])
        failed = min(failed, max(0, total - scraped))
        pending = max(0, total - scraped - failed)

        items.append(
            NovelSummaryCounts(
                novel_id=novel_id,
                total=total,
                scraped=scraped,
                translated=translated,
                failed=failed,
                pending=pending,
            )
        )
        total_total += total
        total_scraped += scraped
        total_translated += translated
        total_failed += failed
        total_pending += pending

    totals = NovelSummaryCounts(
        novel_id="__all__",
        total=total_total,
        scraped=total_scraped,
        translated=total_translated,
        failed=total_failed,
        pending=total_pending,
    )

    return _CachedSummary(
        generated_at=_utc_now_iso(),
        totals=totals,
        items=tuple(items),
        catalog_identity=tuple(sorted(set(catalogued_novel_ids))),
    )


def _response_from_cache(cached: _CachedSummary, *, hit: bool) -> SummaryResponse:
    """Build a fresh outward response (new dict, new list) for one caller."""
    return SummaryResponse(
        generated_at=cached.generated_at,
        # Always construct a fresh metadata dict — caller must never
        # influence cached state by mutating this.
        cache={"hit": hit, "ttl_seconds": CACHE_TTL_SECONDS},
        totals=cached.totals,
        # Items are reassembled into a fresh list (the underlying count
        # records are frozen, but the list itself is caller-private).
        items=list(cached.items),
    )


class LibrarySummaryService:
    """Live admin Library summary with in-process 30-second TTL cache.

    Single-flight semantics:

    * One storage listing per generation.
    * Concurrent callers (cold / expired / forced) share the same build.
    * Result and cache publication is atomic under one lock acquisition.
    * Failures wake every waiter and are propagated to all subscribers.
    * Catalog identity prevents cross-tenant cache reuse.
    """

    def __init__(
        self,
        storage: StorageService,
        activity_log: Any | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._storage = storage
        self._activity_log = activity_log
        self._clock = clock or time.monotonic

        # Currently valid cache for one identity.
        self._cache: _CachedSummary | None = None
        self._expires_at: float = 0.0

        # Active in-flight generation, if any.
        self._active_generation: int | None = None
        self._active_identity: tuple[str, ...] | None = None

        # Completed outcomes keyed by generation (kept briefly for
        # waiters that arrive just after notify()).
        self._completed: dict[int, _CompletedBuild] = {}

        # Monotonic counter for new generations.
        self._next_generation: int = 1

        self._cv = Condition()

    # -- public ---------------------------------------------------------

    def get_summary(
        self,
        *,
        refresh: bool = False,
        catalogued_novel_ids: list[str] | None = None,
    ) -> SummaryResponse:
        identity = tuple(sorted(set(catalogued_novel_ids or [])))

        with self._cv:
            # Cache hit fast path for non-refresh callers.
            if not refresh:
                cached = self._try_cache_hit(identity)
                if cached is not None:
                    return _response_from_cache(cached, hit=True)

            # Decide whether to attach to in-flight, wait for it, or build.
            generation, is_builder = self._enter_critical_section(refresh, identity)

        if is_builder:
            return self._run_builder(generation, identity)

        return self._wait_for_outcome(generation, refresh=refresh, identity=identity)

    def invalidate_cache(self) -> None:
        with self._cv:
            self._cache = None
            self._expires_at = 0.0
            self._cv.notify_all()

    # -- internals -------------------------------------------------------

    def _try_cache_hit(self, identity: tuple[str, ...]) -> _CachedSummary | None:
        """Return a matching live cache if present, else None."""
        if self._cache is None:
            return None
        if self._cache.catalog_identity != identity:
            return None
        if self._clock() >= self._expires_at:
            return None
        return self._cache

    def _enter_critical_section(
        self,
        refresh: bool,
        identity: tuple[str, ...],
    ) -> tuple[int, bool]:
        """Allocate a generation for this caller.

        Returns ``(generation, is_builder)``.

        * All callers seeing an *active* build for the same identity join it.
        * All callers seeing an *active* build for a different identity wait
          it out, then re-evaluate.
        * If no build is active, we become the builder.
        """
        while True:
            # Case 1: compatible active build — join it.
            if (
                self._active_generation is not None
                and self._active_identity == identity
            ):
                generation = self._active_generation
                return generation, False

            # Case 2: no active build — become the builder.
            if self._active_generation is None:
                self._next_generation += 1
                generation = self._next_generation
                self._active_generation = generation
                self._active_identity = identity
                return generation, True

            # Case 3: incompatible active build — wait for it out.
            incompatible_gen = self._active_generation
            self._cv.wait_for(
                lambda: self._active_generation != incompatible_gen
            )
            # Loop: re-evaluate from scratch.

    def _wait_for_outcome(
        self,
        generation: int,
        *,
        refresh: bool,
        identity: tuple[str, ...],
    ) -> SummaryResponse:
        """Wait for generation to finish, then return its outcome."""
        with self._cv:
            self._cv.wait_for(lambda: generation in self._completed)

            outcome = self._completed[generation]

        if outcome.error is not None:
            raise outcome.error

        # Transition: as a forced-refresh caller we already have a completed
        # generation that satisfies us, so no further work is needed.
        # For a normal caller, the published cache may already match our
        # identity — return it directly.
        assert outcome.cache is not None
        return _response_from_cache(outcome.cache, hit=not refresh)

    def _run_builder(
        self,
        generation: int,
        identity: tuple[str, ...],
    ) -> SummaryResponse:
        """Execute the actual build and publish the outcome atomically."""
        completed_at_completion: float
        cache: _CachedSummary | None = None
        error: BaseException | None = None

        try:
            cache = self._do_build(identity)
            completed_at_completion = self._clock()
        except BaseException as exc:
            error = exc
            completed_at_completion = self._clock()
            # Ensure filter-level exceptions like KeyboardInterrupt /
            # SystemExit propagate untouched while still publishing the
            # outcome so waiters don't deadlock.
        else:
            # Build succeeded.
            pass

        with self._cv:
            outcome = _CompletedBuild(
                generation=generation,
                identity=identity,
                cache=cache,
                error=error,
            )

            self._completed[generation] = outcome

            if cache is not None:
                self._cache = cache
                self._expires_at = completed_at_completion + CACHE_TTL_SECONDS

            # Only clear the active slot once the outcome is published.
            # This guarantees no waiter observes "no build in flight / no cache"
            # between notify and completion publication.
            if self._active_generation == generation:
                self._active_generation = None
                self._active_identity = None

            self._cv.notify_all()

            # Drop completed generations we're sure no waiter can still
            # care about — keep the last one as a courtesy for any
            # late-arriving forced caller comparing identities.
            retained: dict[int, _CompletedBuild] = {}
            if generation in self._completed:
                retained[generation] = self._completed[generation]
            self._completed = retained

        # Re-raise outside the lock to preserve traceback semantics.
        if error is not None:
            raise error

        assert cache is not None
        return _response_from_cache(cache, hit=False)

    def _do_build(self, identity: tuple[str, ...]) -> _CachedSummary:
        return _build_summary_from_storage(
            self._storage,
            self._activity_log,
            list(identity),
        )


def invalidate_library_summary_cache() -> None:
    from novelai.runtime.container import container

    if hasattr(container, "library_summary"):
        container.library_summary.invalidate_cache()
        logger.debug("Library summary cache invalidated")


def best_effort_invalidate(*, context: str | None = None) -> None:
    """Best-effort invalidation that never masks caller failures.

    Use after a successful storage mutation that may invalidate the
    Library summary (destructive deletion, metadata replacement,
    chapter save, translation save, glossary rewrite, version
    activation, novel deletion). Failures are logged at debug level and
    swallowed so the original operation result is preserved.
    """
    try:
        invalidate_library_summary_cache()
    except Exception:
        logger.debug(
            "Library summary cache invalidation failed (non-fatal)",
            exc_info=True,
            extra={"context": context} if context else None,
        )
