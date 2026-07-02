"""Tests for the adapter plugin system (registry, discover, can_handle, no-match error)."""

from __future__ import annotations

import pytest

from novelai.sources.generic import GenericSource
from novelai.sources.kakuyomu import KakuyomuSource
from novelai.sources.novel18_syosetu import Novel18SyosetuSource
from novelai.sources.registry import (
    _SOURCE_REGISTRY,
    available_sources,
    detect_source,
    get_adapter,
    get_by_key,
    get_source,
    list_adapters,
    register_source,
)
from novelai.sources.syosetu_ncode import SyosetuNcodeSource


@pytest.fixture(autouse=True)
def _register_builtins() -> None:
    """Ensure built-in adapters are registered for every test."""
    from novelai.runtime.bootstrap import bootstrap_sources
    bootstrap_sources()


# ---------------------------------------------------------------------------
# Task 6.1 -- discovery and registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_and_get(self) -> None:
        """register_source + get_source round-trips."""
        _SOURCE_REGISTRY.pop("_test_only", None)  # clean up
        register_source("_test_only", lambda: GenericSource())
        try:
            adapter = get_source("_test_only")
            assert isinstance(adapter, GenericSource)
            assert adapter.key == "generic"
        finally:
            _SOURCE_REGISTRY.pop("_test_only", None)

    def test_get_source_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="No source registered"):
            get_source("_nonexistent_key_xyz")

    def test_available_sources_includes_builtins(self) -> None:
        sources = available_sources()
        assert "generic" in sources
        assert "kakuyomu" in sources

    def test_list_adapters_sorted(self) -> None:
        result = list_adapters()
        assert result == sorted(result)
        assert "generic" in result

    def test_get_by_key_alias(self) -> None:
        adapter = get_by_key("generic")
        assert isinstance(adapter, GenericSource)


# ---------------------------------------------------------------------------
# Task 6.2 -- auto-detection via get_adapter
# ---------------------------------------------------------------------------

class TestAutoDetection:
    def test_detect_kakuyomu_url(self) -> None:
        key = detect_source("https://kakuyomu.jp/works/12345")
        assert key == "kakuyomu"

    def test_detect_unknown_returns_none(self) -> None:
        key = detect_source("https://totally-unknown-site.example/novel/1")
        assert key is None

    def test_get_adapter_kakuyomu(self) -> None:
        adapter = get_adapter("https://kakuyomu.jp/works/99999")
        assert isinstance(adapter, KakuyomuSource)

    def test_get_adapter_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="No adapter found"):
            get_adapter("https://totally-unknown-site.example/novel/1")


# ---------------------------------------------------------------------------
# Task 6.3 -- explicit key selection via get_by_key
# ---------------------------------------------------------------------------

class TestExplicitKeySelection:
    def test_get_by_key_kakuyomu(self) -> None:
        adapter = get_by_key("kakuyomu")
        assert isinstance(adapter, KakuyomuSource)
        assert adapter.key == "kakuyomu"

    def test_get_by_key_generic(self) -> None:
        adapter = get_by_key("generic")
        assert isinstance(adapter, GenericSource)

    def test_get_by_key_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="No source registered"):
            get_by_key("no_such_key")


# ---------------------------------------------------------------------------
# Task 1.2 / 1.3 -- can_handle and source_key (key property)
# ---------------------------------------------------------------------------

class TestCanHandle:
    def test_generic_can_handle_returns_false(self) -> None:
        """GenericSource is a fallback -- it never matches by URL."""
        src = GenericSource()
        assert src.can_handle("https://example.com/novel/1") is False

    def test_kakuyomu_can_handle(self) -> None:
        src = KakuyomuSource()
        assert src.can_handle("https://kakuyomu.jp/works/123") is True
        assert src.can_handle("https://example.com/novel/1") is False

    def test_syosetu_can_handle(self) -> None:
        src = SyosetuNcodeSource()
        assert src.can_handle("https://ncode.syosetu.com/n1234abc/") is True

    def test_can_handle_matches_url(self) -> None:
        """can_handle is an alias for matches_url."""
        src = KakuyomuSource()
        url = "https://kakuyomu.jp/works/123"
        assert src.can_handle(url) == src.matches_url(url)

    def test_all_builtin_adapters_have_key(self) -> None:
        """Every adapter returned by the registry has a string key property."""
        for adapter_cls in (GenericSource, KakuyomuSource, SyosetuNcodeSource, Novel18SyosetuSource):
            adapter = adapter_cls()
            assert isinstance(adapter.key, str)
            assert len(adapter.key) > 0


# ---------------------------------------------------------------------------
# Task 6.4 -- no-match error in orchestration
# ---------------------------------------------------------------------------

class TestOrchestrationNoMatchError:
    def test_unknown_source_key_raises_operation_error(self) -> None:
        from unittest.mock import MagicMock

        from novelai.services.novel_orchestration_service import NovelOrchestrationService
        from novelai.services.orchestration.operations import OperationError

        mock_storage = MagicMock()
        mock_translation = MagicMock()
        svc = NovelOrchestrationService(storage=mock_storage, translation=mock_translation)
        with pytest.raises(OperationError, match="No adapter found for source"):
            svc._source_factory("totally_bogus_key")
