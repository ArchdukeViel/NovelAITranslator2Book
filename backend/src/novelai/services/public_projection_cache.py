"""Bounded process-local cache for safe public projection payloads."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any

from novelai.config.settings import settings

type PublicProjectionCacheKey = tuple[str, ...]


@dataclass(frozen=True)
class PublicProjectionCacheStats:
    hits: int
    misses: int
    entries: int
    invalidations: int


@dataclass(frozen=True)
class _CacheEntry:
    value: Any
    expires_at: float


class PublicProjectionCache:
    """Thread-safe TTL/LRU cache for non-personalized public projections.

    Values are copied on both sides of the cache boundary. Callers must only
    store JSON-safe public payloads; identity, progress, cookies, and raw
    query text are intentionally outside this cache.
    """

    def __init__(self) -> None:
        self._entries: OrderedDict[PublicProjectionCacheKey, _CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        self._lock = RLock()

    def get(self, key: PublicProjectionCacheKey) -> Any | None:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.expires_at <= now:
                if entry is not None:
                    self._entries.pop(key, None)
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return deepcopy(entry.value)

    def set(self, key: PublicProjectionCacheKey, value: Any) -> None:
        if not settings.PUBLIC_PROJECTION_CACHE_ENABLED:
            return
        ttl_seconds = settings.PUBLIC_PROJECTION_CACHE_TTL_SECONDS
        max_entries = settings.PUBLIC_PROJECTION_CACHE_MAX_ENTRIES
        if ttl_seconds <= 0 or max_entries <= 0:
            return
        entry = _CacheEntry(value=deepcopy(value), expires_at=monotonic() + ttl_seconds)
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > max_entries:
                self._entries.popitem(last=False)

    def clear(self, *, reset_stats: bool = False) -> None:
        with self._lock:
            self._entries.clear()
            if reset_stats:
                self._hits = 0
                self._misses = 0
                self._invalidations = 0
            else:
                self._invalidations += 1

    def stats(self) -> PublicProjectionCacheStats:
        with self._lock:
            now = monotonic()
            expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
            for key in expired:
                self._entries.pop(key, None)
            return PublicProjectionCacheStats(
                hits=self._hits,
                misses=self._misses,
                entries=len(self._entries),
                invalidations=self._invalidations,
            )


public_projection_cache = PublicProjectionCache()


def invalidate_public_projection_cache() -> None:
    """Invalidate catalog/chapter projection payloads after public writes."""
    public_projection_cache.clear()


def clear_public_projection_cache_for_tests(*, reset_stats: bool = False) -> None:
    public_projection_cache.clear(reset_stats=reset_stats)


def public_projection_cache_stats() -> PublicProjectionCacheStats:
    return public_projection_cache.stats()
