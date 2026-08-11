from __future__ import annotations

from datetime import UTC, datetime, timedelta

from novelai.infrastructure.http.cache import FetchCacheEntry, InMemoryFetchCache, LRUFetchCache


def _entry(
    url: str = "https://example.test/page",
    *,
    source_key: str = "test_source",
    text: str = "body",
    kind: str = "html",
    profile: str | None = None,
    fetched_at: str | None = None,
) -> FetchCacheEntry:
    return FetchCacheEntry(
        requested_url=url,
        final_url=url,
        status_code=200,
        headers={"content-type": "text/html"},
        text=text,
        body=text.encode("utf-8"),
        source_key=source_key,
        fetched_at=fetched_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        kind=kind,
        profile=profile,
    )


def _past_iso(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class TestLRUFetchCacheBounding:
    def test_max_entries_evicts_oldest(self) -> None:
        cache = LRUFetchCache(max_entries=2, max_bytes=None, max_entry_bytes=None)
        cache.set(_entry("https://example.test/a"))
        cache.set(_entry("https://example.test/b"))
        cache.set(_entry("https://example.test/c"))

        stats = cache.stats()
        assert stats["size"] == 2
        assert stats["evictions"] == 1
        assert cache.get("test_source", "https://example.test/a") is None
        assert cache.get("test_source", "https://example.test/b") is not None

    def test_lru_order_refreshed_on_get(self) -> None:
        cache = LRUFetchCache(max_entries=2, max_bytes=None, max_entry_bytes=None)
        cache.set(_entry("https://example.test/a"))
        cache.set(_entry("https://example.test/b"))
        # Touching "a" makes "b" the least-recently-used.
        assert cache.get("test_source", "https://example.test/a") is not None
        cache.set(_entry("https://example.test/c"))

        assert cache.get("test_source", "https://example.test/a") is not None
        assert cache.get("test_source", "https://example.test/b") is None

    def test_max_bytes_budget_evicts_oldest(self) -> None:
        cache = LRUFetchCache(max_entries=None, max_bytes=500, max_entry_bytes=None)
        big = "x" * 150
        cache.set(_entry("https://example.test/big", text=big))
        assert cache.get("test_source", "https://example.test/big") is not None
        cache.set(_entry("https://example.test/other", text=big))
        # Two entries (~325 bytes each: body + text + url) exceed the
        # 500-byte budget → oldest evicted.
        assert cache.get("test_source", "https://example.test/big") is None
        assert cache.get("test_source", "https://example.test/other") is not None

    def test_oversized_entry_is_not_cached(self) -> None:
        cache = LRUFetchCache(max_entries=10, max_bytes=None, max_entry_bytes=100)
        cache.set(_entry("https://example.test/huge", text="x" * 200))

        assert cache.get("test_source", "https://example.test/huge") is None
        assert cache.stats()["rejected_oversized"] == 1
        assert cache.stats()["size"] == 0


class TestLRUFetchCacheTTL:
    def test_html_entry_expires_after_ttl(self) -> None:
        cache = LRUFetchCache(html_ttl_seconds=300, asset_ttl_seconds=3600, max_bytes=None)
        cache.set(_entry("https://example.test/page", fetched_at=_past_iso(400)))

        assert cache.get("test_source", "https://example.test/page") is None
        assert cache.stats()["evictions"] == 1

    def test_fresh_html_entry_is_returned(self) -> None:
        cache = LRUFetchCache(html_ttl_seconds=300, asset_ttl_seconds=3600, max_bytes=None)
        cache.set(_entry("https://example.test/page", fetched_at=_past_iso(10)))

        assert cache.get("test_source", "https://example.test/page") is not None

    def test_asset_ttl_differs_from_html_ttl(self) -> None:
        # Same timestamps: an old asset is still fresh while an old html page is not.
        cache = LRUFetchCache(html_ttl_seconds=300, asset_ttl_seconds=3600, max_bytes=None)
        cache.set(_entry("https://example.test/page", fetched_at=_past_iso(600)))
        cache.set(_entry("https://example.test/img.png", kind="asset", fetched_at=_past_iso(600)))

        assert cache.get("test_source", "https://example.test/page") is None
        assert cache.get("test_source", "https://example.test/img.png") is not None


class TestLRUFetchCacheProfileIsolation:
    def test_same_url_different_profiles_do_not_collide(self) -> None:
        cache = LRUFetchCache(max_bytes=None)
        cache.set(_entry("https://example.test/page", profile="regular"))
        cache.set(_entry("https://example.test/page", profile="r18"))

        assert cache.get("test_source", "https://example.test/page", profile="regular") is not None
        assert cache.get("test_source", "https://example.test/page", profile="r18") is not None
        assert cache.stats()["size"] == 2

    def test_conditional_headers_respect_profile(self) -> None:
        cache = LRUFetchCache(max_bytes=None)
        entry = _entry("https://example.test/page", profile="r18")
        entry = FetchCacheEntry(
            requested_url=entry.requested_url,
            final_url=entry.final_url,
            status_code=entry.status_code,
            headers={"etag": '"v2"', "content-type": "text/html"},
            text=entry.text,
            body=entry.body,
            source_key=entry.source_key,
            fetched_at=entry.fetched_at,
            kind=entry.kind,
            profile=entry.profile,
        )
        cache.set(entry)

        assert cache.conditional_headers("test_source", "https://example.test/page", profile="r18") == {
            "If-None-Match": '"v2"'
        }
        assert cache.conditional_headers("test_source", "https://example.test/page", profile="regular") == {}


class TestLRUFetchCacheMetrics:
    def test_hit_miss_ratio(self) -> None:
        cache = LRUFetchCache(max_bytes=None)
        cache.set(_entry("https://example.test/a"))

        assert cache.get("test_source", "https://example.test/a") is not None  # hit
        assert cache.get("test_source", "https://example.test/missing") is None  # miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_ratio"] == 0.5

    def test_conditional_headers_count_as_hit(self) -> None:
        cache = LRUFetchCache(max_bytes=None)
        cache.set(_entry("https://example.test/a"))

        assert cache.conditional_headers("test_source", "https://example.test/a") == {}
        assert cache.stats()["hits"] == 1


class TestInMemoryFetchCacheCompatibility:
    def test_unbounded_and_non_expiring(self) -> None:
        cache = InMemoryFetchCache()
        cache.set(_entry("https://example.test/a", fetched_at=_past_iso(100000)))
        cache.set(_entry("https://example.test/b", fetched_at=_past_iso(100000)))

        assert cache.get("test_source", "https://example.test/a") is not None
        assert cache.get("test_source", "https://example.test/b") is not None
        assert cache.stats()["size"] == 2
        assert cache.stats()["max_entries"] is None
