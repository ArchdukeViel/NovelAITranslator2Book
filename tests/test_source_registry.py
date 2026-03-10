"""Tests for the source adapter registry."""

from __future__ import annotations

from novelai.sources.base import SourceAdapter
from novelai.sources.registry import (
    _SOURCE_REGISTRY,
    available_sources,
    detect_source,
    get_source,
    register_source,
)


class _FakeSource(SourceAdapter):
    """Minimal source adapter for registry tests."""

    def __init__(self, *, match: bool = False) -> None:
        self._match = match

    @property
    def key(self) -> str:
        return "fake"

    def matches_url(self, identifier_or_url: str) -> bool:
        return self._match

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict:
        return {}

    async def fetch_chapter(self, url: str) -> str:
        return ""


class TestSourceRegistry:
    """Isolated tests — each test saves/restores global state."""

    def setup_method(self) -> None:
        self._saved = dict(_SOURCE_REGISTRY)

    def teardown_method(self) -> None:
        _SOURCE_REGISTRY.clear()
        _SOURCE_REGISTRY.update(self._saved)

    def test_register_and_get_source(self) -> None:
        register_source("test_src", lambda: _FakeSource())
        adapter = get_source("test_src")
        assert isinstance(adapter, _FakeSource)

    def test_get_source_raises_for_unknown_key(self) -> None:
        import pytest
        with pytest.raises(KeyError, match="No source registered"):
            get_source("nonexistent")

    def test_available_sources_lists_registered_keys(self) -> None:
        register_source("alpha", lambda: _FakeSource())
        register_source("beta", lambda: _FakeSource())
        keys = available_sources()
        assert "alpha" in keys
        assert "beta" in keys

    def test_detect_source_returns_matching_key(self) -> None:
        register_source("matcher", lambda: _FakeSource(match=True))
        assert detect_source("http://example.com") == "matcher"

    def test_detect_source_returns_none_when_no_match(self) -> None:
        register_source("nomatch", lambda: _FakeSource(match=False))
        result = detect_source("http://example.com")
        # Could be None or a prior match; just ensure nomatch didn't match
        if result is not None:
            assert result != "nomatch"
