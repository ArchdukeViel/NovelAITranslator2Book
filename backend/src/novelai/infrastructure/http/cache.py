from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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

    @property
    def etag(self) -> str | None:
        return self.headers.get("etag")

    @property
    def last_modified(self) -> str | None:
        return self.headers.get("last-modified")


class FetchCache(Protocol):
    def get(self, source_key: str, url: str) -> FetchCacheEntry | None:
        ...

    def set(self, entry: FetchCacheEntry) -> None:
        ...

    def conditional_headers(self, source_key: str, url: str) -> dict[str, str]:
        ...


class InMemoryFetchCache:
    """Small process-local conditional fetch cache for source HTTP responses."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], FetchCacheEntry] = {}

    def get(self, source_key: str, url: str) -> FetchCacheEntry | None:
        return self._entries.get((source_key, url))

    def set(self, entry: FetchCacheEntry) -> None:
        self._entries[(entry.source_key, entry.requested_url)] = entry

    def conditional_headers(self, source_key: str, url: str) -> dict[str, str]:
        entry = self.get(source_key, url)
        if entry is None:
            return {}
        headers: dict[str, str] = {}
        if entry.etag:
            headers["If-None-Match"] = entry.etag
        if entry.last_modified:
            headers["If-Modified-Since"] = entry.last_modified
        return headers
