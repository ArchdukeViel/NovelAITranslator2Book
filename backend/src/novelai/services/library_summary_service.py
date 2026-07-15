"""Live admin Library summary service.

Counts are derived from canonical R2/S3 storage, not from SQL catalog
projections.  Uses a single recursive listing pass per uncached refresh,
an in-process 30-second TTL cache, and coalesced concurrent cache-miss
handling.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
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
class SummaryResponse:
    generated_at: str
    cache: dict[str, Any]
    totals: NovelSummaryCounts
    items: list[NovelSummaryCounts]


@dataclass
class _CacheEntry:
    data: SummaryResponse
    expires_at: float


def _is_chapter_key(key: str) -> bool:
    return key.endswith(".json") and "/chapters/" in key


def _logical_id(stem: str) -> str:
    try:
        return str(int(stem))
    except (ValueError, TypeError):
        return stem


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
) -> SummaryResponse:
    all_keys = storage.list_keys_under(NOVELS_PREFIX, recursive=True)

    inventory: dict[str, dict[str, set[str]]] = {}

    for key in all_keys:
        if not _is_chapter_key(key):
            continue
        folder = _parse_novel_id_from_key(key, NOVELS_PREFIX)
        if folder is None:
            continue
        stem = Path(key).stem
        logical = _logical_id(stem)
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
    return SummaryResponse(
        generated_at=_utc_now_iso(),
        cache={"hit": False, "ttl_seconds": _CACHE_TTL_SECONDS},
        totals=totals,
        items=items,
    )


class LibrarySummaryService:
    def __init__(
        self,
        storage: StorageService,
        activity_log: Any | None = None,
    ) -> None:
        self._storage = storage
        self._activity_log = activity_log
        self._cache: _CacheEntry | None = None
        self._lock = Lock()
        self._refresh_lock = Lock()
        self._building = False

    def get_summary(
        self,
        *,
        refresh: bool = False,
        catalogued_novel_ids: list[str] | None = None,
    ) -> SummaryResponse:
        now = time.monotonic()

        if not refresh:
            with self._lock:
                cached = self._cache
                if cached is not None and cached.expires_at > now:
                    resp = cached.data
                    return SummaryResponse(
                        generated_at=resp.generated_at,
                        cache={"hit": True, "ttl_seconds": _CACHE_TTL_SECONDS},
                        totals=resp.totals,
                        items=resp.items,
                    )

        with self._refresh_lock:
            with self._lock:
                cached = self._cache
                if cached is not None and cached.expires_at > now and not refresh:
                    resp = cached.data
                    return SummaryResponse(
                        generated_at=resp.generated_at,
                        cache={"hit": True, "ttl_seconds": _CACHE_TTL_SECONDS},
                        totals=resp.totals,
                        items=resp.items,
                    )

            try:
                data = _build_summary_from_storage(
                    self._storage,
                    self._activity_log,
                    catalogued_novel_ids or [],
                )
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
        with self._lock:
            self._cache = None


def invalidate_library_summary_cache() -> None:
    from novelai.runtime.container import container

    if hasattr(container, "library_summary"):
        container.library_summary.invalidate_cache()
        logger.debug("Library summary cache invalidated")
