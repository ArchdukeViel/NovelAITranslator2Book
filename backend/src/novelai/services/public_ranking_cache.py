"""Bounded cache for successful public ranking responses."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from time import monotonic

from novelai.config.settings import settings

type RankingCacheKey = tuple[str, str, int]


@dataclass(frozen=True)
class PublicRankingCacheStats:
    """Low-cardinality cache counters safe for the process metrics endpoint."""

    hits: int
    misses: int
    entries: int


@dataclass(frozen=True)
class _CacheEntry:
    value: dict[str, object]
    expires_at: float


class PublicRankingCache:
    """Thread-safe bounded TTL cache for successful ranking payloads.

    The cache is deliberately process-local. It is an optimization only: every
    miss recomputes from the database, and the short TTL bounds staleness. The
    key includes the published-projection version so a projection update does
    not reuse a result built from an older catalog state.
    """

    def __init__(self) -> None:
        self._entries: OrderedDict[RankingCacheKey, _CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._lock = RLock()

    def get(self, key: RankingCacheKey) -> dict[str, object] | None:
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

    def set(self, key: RankingCacheKey, value: dict[str, object]) -> None:
        if value.get("available") is not True or not value.get("items"):
            return
        ttl_seconds = settings.PUBLIC_RANKING_CACHE_TTL_SECONDS
        max_entries = settings.PUBLIC_RANKING_CACHE_MAX_ENTRIES
        if not settings.PUBLIC_RANKING_CACHE_ENABLED or ttl_seconds <= 0 or max_entries <= 0:
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

    def stats(self) -> PublicRankingCacheStats:
        with self._lock:
            now = monotonic()
            expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
            for key in expired:
                self._entries.pop(key, None)
            return PublicRankingCacheStats(
                hits=self._hits,
                misses=self._misses,
                entries=len(self._entries),
            )


public_ranking_cache = PublicRankingCache()


def clear_public_ranking_cache(*, reset_stats: bool = False) -> None:
    """Clear ranking cache state; intended for projection updates and tests."""

    public_ranking_cache.clear(reset_stats=reset_stats)


def public_ranking_cache_stats() -> PublicRankingCacheStats:
    """Return cache counters without exposing cache keys or response data."""

    return public_ranking_cache.stats()
