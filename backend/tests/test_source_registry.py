"""Tests for the canonical source adapter registry."""

from __future__ import annotations

from typing import Any

from novelai.sources.base import SourceAdapter
from novelai.sources.registry import AdapterRegistry


class _FakeSource(SourceAdapter):
    source_key = "fake"

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {}

    async def fetch_chapter(self, url: str) -> str:
        return ""


class _MatchingFakeSource(_FakeSource):
    source_key = "matching_fake"

    def can_handle(self, identifier_or_url: str) -> bool:
        return True


class _BlankKeySource(_FakeSource):
    source_key = "  "


def test_register_and_get_by_key() -> None:
    registry = AdapterRegistry()
    registry.register(_FakeSource)

    assert isinstance(registry.get_by_key("fake"), _FakeSource)
    assert registry.get_by_key("missing") is None


def test_list_adapters_is_sorted() -> None:
    registry = AdapterRegistry()
    class BetaSource(_FakeSource):
        source_key = "beta"

    class AlphaSource(_FakeSource):
        source_key = "alpha"

    registry.register(BetaSource)
    registry.register(AlphaSource)

    assert registry.list_adapters() == ["alpha", "beta"]


def test_get_adapter_returns_matching_instance() -> None:
    registry = AdapterRegistry()
    registry.register(_MatchingFakeSource)

    assert isinstance(registry.get_adapter("https://example.com"), _FakeSource)


def test_get_adapter_returns_none_without_match() -> None:
    registry = AdapterRegistry()
    registry.register(_FakeSource)

    assert registry.get_adapter("https://example.com") is None


def test_register_rejects_blank_source_key() -> None:
    registry = AdapterRegistry()

    try:
        registry.register(_BlankKeySource)
    except ValueError as exc:
        assert str(exc) == "source_key must not be blank"
    else:
        raise AssertionError("blank source_key was accepted")
