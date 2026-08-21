from __future__ import annotations

from novelai.config.settings import settings
from novelai.services.public_projection_cache import PublicProjectionCache


def test_projection_cache_copies_values_and_tracks_hits(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PUBLIC_PROJECTION_CACHE_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_PROJECTION_CACHE_TTL_SECONDS", 30)
    monkeypatch.setattr(settings, "PUBLIC_PROJECTION_CACHE_MAX_ENTRIES", 2)
    cache = PublicProjectionCache()
    value = {"novels": [{"slug": "a"}]}

    cache.set(("catalog-v1", "a"), value)
    value["novels"].append({"slug": "mutated"})
    cached = cache.get(("catalog-v1", "a"))

    assert cached == {"novels": [{"slug": "a"}]}
    assert cache.stats().hits == 1


def test_projection_cache_invalidation_removes_entries() -> None:
    cache = PublicProjectionCache()
    cache.set(("catalog-v1", "a"), {"value": 1})
    cache.clear()

    assert cache.get(("catalog-v1", "a")) is None
    stats = cache.stats()
    assert stats.invalidations == 1
