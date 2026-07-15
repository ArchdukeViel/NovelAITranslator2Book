"""Live admin Library summary service.

Counts are derived from canonical R2/S3 storage, not from SQL catalog
projections.  Uses a single recursive listing pass per uncached refresh
and an in-process 30-second TTL cache.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30

# ── data types ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NovelSummaryCounts:
    """Live storage-derived counts for one novel."""
    novel_id: str
    total: int = 0
    scraped: int = 0
    translated: int = 0
    failed: int = 0
    pending: int = 0


@dataclass(frozen=True)
class SummaryResponse:
    """Complete summary response payload."""
    generated_at: str
    cache: dict[str, Any]
    totals: NovelSummaryCounts
    items: list[NovelSummaryCounts]


@dataclass
class _CacheEntry:
    """Internal cache entry with expiry."""
    data: SummaryResponse
    expires_at: float


# ── storage helpers ────────────────────────────────────────────────────

NOVELS_PREFIX = "novels/"


def _is_chapter_key(key: str) -> bool:
    """Return True when *key* looks like a novel chapter file."""
    return key.endswith(".json") and "/chapters/" in key


def _logical_id(stem: str) -> str:
    """Convert physical stem to logical chapter ID.

    ``0001`` (zero-padded) → ``1``, ``abc`` → ``abc``.
    """
    try:
        return str(int(stem))
    except (ValueError, TypeError):
        return stem


def _parse_novel_id_from_key(key: str, novels_prefix: str) -> str | None:
    """Extract the novel folder name (the first path segment after novels/).

    Returns ``None`` for keys directly under ``novels/`` with no subfolder.
    """
    rest = key[len(novels_prefix):]
    if "/" not in rest:
        return None
    folder = rest[: rest.index("/")]
    if not folder:
        return None
    return folder


def _is_translated_bundle(key: str, storage: StorageService) -> bool:
    """Return True when *key* contains a translated chapter payload.

    Reads the file to check for ``translated`` key.  This is called
    only for keys that already passed ``_is_chapter_key``.
    """
    try:
        payload = json.loads(storage._read_text(storage.base_dir / key))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(payload, dict) and isinstance(payload.get("translated"), dict)


def _has_raw_payload(key: str, storage: StorageService) -> bool:
    """Return True when *key* contains a source (raw) chapter payload."""
    try:
        payload = json.loads(storage._read_text(storage.base_dir / key))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(payload, dict) and isinstance(payload.get("raw"), dict)


# ── inventory builder ──────────────────────────────────────────────────


@dataclass
class _NovelInventory:
    """In-memory storage inventory for one novel."""
    chapter_ids: set[str] = field(default_factory=set)
    translated_ids: set[str] = field(default_factory=set)
    raw_ids: set[str] = field(default_factory=set)


def _build_inventory(storage: StorageService) -> dict[str, _NovelInventory]:
    """Single-pass storage inventory for all novels.

    Lists all keys under the ``novels/`` prefix recursively (one
    paginated remote call), groups by novel folder, and classifies each
    valid chapter key.
    """
    all_keys = storage._backend.list_keys(NOVELS_PREFIX, recursive=True)
    inventory: dict[str, _NovelInventory] = {}

    for key in all_keys:
        if not _is_chapter_key(key):
            continue
        folder = _parse_novel_id_from_key(key, NOVELS_PREFIX)
        if folder is None:
            continue
        stem = Path(key).stem
        logical = _logical_id(stem)
        entry = inventory.setdefault(folder, _NovelInventory())
        entry.chapter_ids.add(logical)

        if _is_translated_bundle(key, storage):
            entry.translated_ids.add(logical)
        if _has_raw_payload(key, storage):
            entry.raw_ids.add(logical)

    return inventory


# ── failure metadata resolver ──────────────────────────────────────────


def _get_failed_ids(
    novel_id: str,
    activity_log: Any | None,
) -> set[str]:
    """Return chapter IDs that are explicitly failed in the latest crawl.

    Returns an empty set when no activity log is available or when the
    latest crawl result has no failure records.
    """
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


# ── summary builder ────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_summary_from_inventory(
    storage: StorageService,
    activity_log: Any | None,
) -> SummaryResponse:
    """Build a complete summary from the canonical storage inventory."""
    inventory = _build_inventory(storage)

    # Union of inventory-discovered novel ids (single pass already done above)
    all_ids = sorted(inventory.keys())

    items: list[NovelSummaryCounts] = []
    agg_total = agg_scraped = agg_translated = agg_failed = agg_pending = 0

    for novel_id in all_ids:
        inv = inventory.get(novel_id, _NovelInventory())
        scraped = len(inv.raw_ids)
        translated = len(inv.translated_ids)

        # total: chapter_count from metadata if available, else max observed
        # We do NOT call an additional storage listing for this — load_metadata
        # is one read per novel, but if metadata is unavailable we fall back to
        # the in-memory inventory counts.
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

        # failed: explicit failures from latest crawl
        failed_ids = _get_failed_ids(novel_id, activity_log)
        failed = sum(1 for cid in failed_ids if cid not in inv.raw_ids)
        failed = min(failed, total - scraped)
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
    return SummaryResponse(
        generated_at=_utc_now_iso(),
        cache={"hit": False, "ttl_seconds": _CACHE_TTL_SECONDS},
        totals=totals,
        items=items,
    )


# ── service ────────────────────────────────────────────────────────────


class LibrarySummaryService:
    """Live admin Library summary with in-process 30-second TTL cache.

    The summary is rebuilt from canonical storage (R2) on cache miss or
    explicit refresh.  A single recursive listing pass covers all novels.
    """

    def __init__(
        self,
        storage: StorageService,
        activity_log: Any | None = None,
    ) -> None:
        self._storage = storage
        self._activity_log = activity_log
        self._cache: _CacheEntry | None = None
        self._lock = Lock()

    def get_summary(self, *, refresh: bool = False) -> SummaryResponse:
        """Return the library summary, using cache when possible.

        When *refresh* is True the cache is bypassed and replaced.
        """
        now = time.monotonic()

        # Fast path: cache hit (not expired, not refresh)
        if not refresh:
            with self._lock:
                cached = self._cache
                if cached is not None and cached.expires_at > now:
                    resp = cached.data
                    # Return a copy with cache.hit=True so callers see hit info
                    hit_resp = SummaryResponse(
                        generated_at=resp.generated_at,
                        cache={"hit": True, "ttl_seconds": _CACHE_TTL_SECONDS},
                        totals=resp.totals,
                        items=resp.items,
                    )
                    return hit_resp

        # Slow path: rebuild
        try:
            data = _build_summary_from_inventory(self._storage, self._activity_log)
        except Exception:
            logger.exception("Failed to build library summary")
            raise

        with self._lock:
            self._cache = _CacheEntry(
                data=data,
                expires_at=now + _CACHE_TTL_SECONDS,
            )
        return data

    def invalidate_cache(self) -> None:
        """Clear the in-process cache.

        Call after any storage-changing operation that would make the
        cached summary stale.
        """
        with self._lock:
            self._cache = None


def invalidate_library_summary_cache() -> None:
    """Module-level cache invalidation for external callers.

    Uses the runtime container singleton. Safe to call even if the
    service is not yet initialized (no-op in that case).
    """
    from novelai.runtime.container import container

    if hasattr(container, "library_summary"):
        container.library_summary.invalidate_cache()
        logger.debug("Library summary cache invalidated")
