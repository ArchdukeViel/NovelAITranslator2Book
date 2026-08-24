from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


def _parse_utc_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp, tolerating 'Z' and +00:00."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError, AttributeError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class FetchCacheEntry:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str
    body: bytes
    source_key: str
    fetched_at: str
    # Content kind: "html" (pages) or "asset" (images/binaries). Each kind
    # has its own TTL and size budget so chapter pages expire fast while
    # assets stay cached longer without exhausting memory.
    kind: str = "html"
    # Request-profile variant (e.g. "regular" vs "r18"). Entries from
    # different profiles never collide, even for identical URLs, because
    # cookies/headers may differ per profile.
    profile: str | None = None

    @property
    def etag(self) -> str | None:
        return self.headers.get("etag")

    @property
    def last_modified(self) -> str | None:
        return self.headers.get("last-modified")


class FetchCache(Protocol):
    def get(self, source_key: str, url: str, *, profile: str | None = None) -> FetchCacheEntry | None: ...

    def set(self, entry: FetchCacheEntry) -> None: ...

    def conditional_headers(self, source_key: str, url: str, *, profile: str | None = None) -> dict[str, str]: ...


class LRUFetchCache:
    """Bounded, TTL-aware, profile-isolated LRU fetch cache.

    Entries are keyed by ``(source_key, profile, url)`` so identical URLs
    fetched under different request profiles never collide. Memory is
    bounded by ``max_entries`` and ``max_bytes`` (oldest entries are
    evicted first); individual entries larger than ``max_entry_bytes`` are
    not cached at all. TTLs are per content kind (html vs asset). All
    counters (hits/misses/insertions/evictions) are exposed through
    :meth:`stats` for observability.
    """

    def __init__(
        self,
        *,
        max_entries: int | None = 512,
        max_bytes: int | None = 64 * 1024 * 1024,
        max_entry_bytes: int | None = 8 * 1024 * 1024,
        html_ttl_seconds: int = 300,
        asset_ttl_seconds: int = 3600,
    ) -> None:
        if max_entries is not None and max_entries < 1:
            raise ValueError("max_entries must be >= 1 or None")
        if max_bytes is not None and max_bytes < 1:
            raise ValueError("max_bytes must be >= 1 or None")
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._max_entry_bytes = max_entry_bytes
        self._html_ttl_seconds = html_ttl_seconds
        self._asset_ttl_seconds = asset_ttl_seconds
        self._entries: OrderedDict[tuple[str, str | None, str], FetchCacheEntry] = OrderedDict()
        self._total_bytes = 0
        self.hits = 0
        self.misses = 0
        self.insertions = 0
        self.evictions = 0
        self.rejected_oversized = 0

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _key(source_key: str, url: str, profile: str | None) -> tuple[str, str | None, str]:
        return (source_key, profile, url)

    @classmethod
    def _entry_size(cls, entry: FetchCacheEntry) -> int:
        return len(entry.body) + len(entry.text.encode("utf-8", errors="replace")) + len(entry.requested_url)

    def _ttl_seconds(self, kind: str) -> int:
        return self._asset_ttl_seconds if kind == "asset" else self._html_ttl_seconds

    def _is_expired(self, entry: FetchCacheEntry) -> bool:
        ttl = self._ttl_seconds(entry.kind)
        if ttl <= 0:
            return False
        fetched_at = _parse_utc_iso(entry.fetched_at)
        if fetched_at is None:
            return False
        return (datetime.now(UTC) - fetched_at).total_seconds() > ttl

    # -- interface ----------------------------------------------------------

    def get(self, source_key: str, url: str, *, profile: str | None = None) -> FetchCacheEntry | None:
        key = self._key(source_key, url, profile)
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        if self._is_expired(entry):
            self._evict(key, entry)
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return entry

    def set(self, entry: FetchCacheEntry) -> None:
        key = self._key(entry.source_key, entry.requested_url, entry.profile)
        size = self._entry_size(entry)
        if self._max_entry_bytes is not None and size > self._max_entry_bytes:
            # Too large to cache: skip without polluting the budget.
            self.rejected_oversized += 1
            return
        if key in self._entries:
            self._evict(key, self._entries[key])
        self._entries[key] = entry
        self._total_bytes += size
        self.insertions += 1
        # Enforce budgets: evict the least-recently-used entries.
        while len(self._entries) > (self._max_entries or 0) and self._max_entries is not None:
            _oldest_key, oldest = self._entries.popitem(last=False)
            self._total_bytes -= self._entry_size(oldest)
            self.evictions += 1
        while self._max_bytes is not None and self._total_bytes > self._max_bytes:
            _oldest_key, oldest = self._entries.popitem(last=False)
            self._total_bytes -= self._entry_size(oldest)
            self.evictions += 1

    def conditional_headers(self, source_key: str, url: str, *, profile: str | None = None) -> dict[str, str]:
        entry = self.get(source_key, url, profile=profile)
        if entry is None:
            return {}
        headers: dict[str, str] = {}
        if entry.etag:
            headers["If-None-Match"] = entry.etag
        if entry.last_modified:
            headers["If-Modified-Since"] = entry.last_modified
        return headers

    def stats(self) -> dict[str, int | float | None]:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total else None
        return {
            "hits": self.hits,
            "misses": self.misses,
            "insertions": self.insertions,
            "evictions": self.evictions,
            "rejected_oversized": self.rejected_oversized,
            "size": len(self._entries),
            "byte_size": self._total_bytes,
            "max_entries": self._max_entries,
            "max_bytes": self._max_bytes,
            "hit_ratio": hit_ratio,
        }

    def _evict(self, key: tuple[str, str | None, str], entry: FetchCacheEntry) -> None:
        del self._entries[key]
        self._total_bytes -= self._entry_size(entry)
        self.evictions += 1

    def clear(self) -> None:
        self._entries.clear()
        self._total_bytes = 0


class InMemoryFetchCache(LRUFetchCache):
    """Unbounded, non-expiring fetch cache (legacy compatibility name).

    Kept for callers that explicitly construct the old class; new code
    should use :class:`LRUFetchCache` with explicit budgets.
    """

    def __init__(self) -> None:
        super().__init__(
            max_entries=None,
            max_bytes=None,
            max_entry_bytes=None,
            html_ttl_seconds=0,
            asset_ttl_seconds=0,
        )
