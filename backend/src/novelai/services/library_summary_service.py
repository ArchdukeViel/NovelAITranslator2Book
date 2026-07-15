"""Live admin Library summary service.

Counts are derived from canonical R2/S3 storage, not from SQL catalog
projections.  Uses a single recursive listing pass per uncached refresh,
an in-process 30-second TTL cache, and true single-flight concurrency
for cold, expired, and forced refreshes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from threading import Condition, Lock
from typing import Any

from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30

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
) -> tuple[_CachedSummary, SummaryResponse]:
    """Build immutable cached summary and outward response."""
    all_keys = storage.list_keys_under(NOVELS_PREFIX, recursive=True)

    inventory: dict[str, dict[str, set[str]]] = {}

    for key in all_keys:
        if not _is_chapter_key(key):
            continue
        folder = _parse_novel_id_from_key(key, NOVELS_PREFIX)
        if folder is None:
            continue
        stem = PurePosixPath(key).stem
        logical = storage._logical_id_from_stem(stem)
        if folder not in inventory:
            inventory[folder] = {"chapter_ids": set(), "translated_ids": set(), "raw_ids": set()}
        inv = inventory[folder]
        inv["chapter_ids"].add(logical)

        payload = storage.read_payload(key)
        if payload is not None:
            if isinstance(payload.get("translated"), dict):
                inv["translated_ids"].add(logical)
            if isinstance(payload.get("raw"), dict):
                inv["raw_ids"].add(logical)

    all_novel_ids: set[str] = set(catalogued_novel_ids)
    all_novel_ids.update(inventory.keys())

    items: list[NovelSummaryCounts] = []
    agg_total = agg_scraped = agg_translated = agg_failed = agg_pending = 0

    for novel_id in sorted(all_novel_ids):
        inv = inventory.get(novel_id, {"chapter_ids": set(), "translated_ids": set(), "raw_ids": set()})
        scraped = len(inv["raw_ids"])
        translated = len(inv["translated_ids"])

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
        failed = sum(1 for cid in failed_ids if cid not in inv["raw_ids"])
        failed = min(failed, max(0, total - scraped))
        pending = max(0, total - scraped - failed)

        cnt = NovelSummaryCounts(
            novel_id=novel_id,
            total=total,
            scraped=scraped,
            translated=translated,
            failed=failed,
            pending=pending,
        )
        items.append(cnt)
        agg_total += total
        agg_scraped += scraped
        agg_translated += translated
        agg_failed += failed
        agg_pending += pending

    totals = NovelSummaryCounts(
        novel_id="__all__",
        total=agg_total,
        scraped=agg_scraped,
        translated=agg_translated,
        failed=agg_failed,
        pending=agg_pending,
    )
    generated_at = _utc_now_iso()

    catalog_identity = tuple(sorted(set(catalogued_novel_ids)))
    cached = _CachedSummary(
        generated_at=generated_at,
        totals=totals,
        items=tuple(items),
        catalog_identity=catalog_identity,
    )

    response = SummaryResponse(
        generated_at=generated_at,
        cache={"hit": False, "ttl_seconds": _CACHE_TTL_SECONDS},
        totals=totals,
        items=list(items),
    )
    return cached, response


class LibrarySummaryService:
    def __init__(
        self,
        storage: StorageService,
        activity_log: Any | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._storage = storage
        self._activity_log = activity_log
        self._clock = clock or time.monotonic
        self._cache: _CachedSummary | None = None
        self._expires_at: float = 0.0
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._build_gen = 0
        self._in_flight_gen: int | None = None
        self._in_flight_result: tuple[_CachedSummary, SummaryResponse] | None = None
        self._in_flight_error: BaseException | None = None

    def get_summary(
        self,
        *,
        refresh: bool = False,
        catalogued_novel_ids: list[str] | None = None,
    ) -> SummaryResponse:
        catalogued = tuple(sorted(set(catalogued_novel_ids or [])))
        now = self._clock()

        with self._cond:
            # Fast path: cache hit with matching identity
            if not refresh and self._cache is not None and self._expires_at > now:
                if self._cache.catalog_identity == catalogued:
                    cached = self._cache
                    return SummaryResponse(
                        generated_at=cached.generated_at,
                        cache={"hit": True, "ttl_seconds": _CACHE_TTL_SECONDS},
                        totals=cached.totals,
                        items=list(cached.items),
                    )

        # Need to build or refresh - use single-flight with generation tracking
        while True:
            with self._cond:
                # Re-check under lock after any wait
                if not refresh and self._cache is not None and self._expires_at > now:
                    if self._cache.catalog_identity == catalogued:
                        cached = self._cache
                        return SummaryResponse(
                            generated_at=cached.generated_at,
                            cache={"hit": True, "ttl_seconds": _CACHE_TTL_SECONDS},
                            totals=cached.totals,
                            items=list(cached.items),
                        )

                # Check if a build is in flight - keep lock held!
                if self._in_flight_gen is not None:
                    # Build in progress - decide our generation
                    if refresh:
                        # Forced refresh: wait for current generation, then start new one
                        my_gen = self._build_gen + 1
                        # Don't set _in_flight_gen yet - we'll do it after waiting
                        wait_for_gen = self._in_flight_gen
                    else:
                        # Normal miss: wait for current in-flight build
                        my_gen = self._in_flight_gen
                        wait_for_gen = self._in_flight_gen
                else:
                    # No build in flight - we become the builder ATOMICALLY
                    self._build_gen += 1
                    my_gen = self._build_gen
                    self._in_flight_gen = my_gen
                    self._in_flight_result = None
                    self._in_flight_error = None
                    wait_for_gen = None

            # If we're the builder, do the build outside the lock
            if wait_for_gen is None:
                try:
                    cached, response = _build_summary_from_storage(
                        self._storage,
                        self._activity_log,
                        list(catalogued),
                    )
                    with self._cond:
                        self._in_flight_result = (cached, response)
                        self._in_flight_error = None
                except BaseException as exc:
                    with self._cond:
                        self._in_flight_error = exc
                    raise
                finally:
                    with self._cond:
                        self._in_flight_gen = None
                        self._cond.notify_all()
                cached, data = cached, response
            else:
                # Wait for the in-flight build to complete
                with self._cond:
                    while self._in_flight_gen is not None and self._in_flight_gen != wait_for_gen:
                        self._cond.wait()
                    # Check if our waited-for generation completed
                    if (self._in_flight_gen == wait_for_gen
                            and self._in_flight_result is not None):
                        if self._in_flight_error is not None:
                            raise self._in_flight_error
                        cached, data = self._in_flight_result
                    else:
                        # Another generation started, or result not ready yet
                        now = self._clock()  # Update now for re-check
                        continue

            # Store in cache with expiry from completion time
            with self._cond:
                self._cache = cached
                self._expires_at = self._clock() + _CACHE_TTL_SECONDS
            return data

    def invalidate_cache(self) -> None:
        with self._cond:
            self._cache = None
            self._expires_at = 0.0


def invalidate_library_summary_cache() -> None:
    from novelai.runtime.container import container

    if hasattr(container, "library_summary"):
        container.library_summary.invalidate_cache()
        logger.debug("Library summary cache invalidated")
