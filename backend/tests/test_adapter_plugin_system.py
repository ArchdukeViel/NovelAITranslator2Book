"""Contract tests for source adapter discovery and selection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from novelai.runtime.bootstrap import bootstrap_sources
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration.operations import OperationError
from novelai.sources.generic import GenericSource
from novelai.sources.kakuyomu import KakuyomuSource
from novelai.sources.novel18_syosetu import Novel18SyosetuSource
from novelai.sources.registry import AdapterRegistry, get_registry
from novelai.sources.syosetu_ncode import SyosetuNcodeSource


@pytest.fixture(autouse=True)
def _register_builtins() -> None:
    bootstrap_sources()


def test_builtin_adapters_are_registered() -> None:
    assert {"generic", "kakuyomu", "novel18_syosetu", "syosetu_ncode"} <= set(
        get_registry().list_adapters()
    )


def test_fresh_registry_discovers_builtin_adapters() -> None:
    registry = AdapterRegistry()

    assert registry.discover() >= 4
    assert {"generic", "kakuyomu", "novel18_syosetu", "syosetu_ncode"} <= set(registry.list_adapters())


def test_explicit_source_key_selection() -> None:
    adapter = get_registry().get_by_key("kakuyomu")
    assert isinstance(adapter, KakuyomuSource)
    assert adapter.source_key == "kakuyomu"
    assert get_registry().get_by_key("missing") is None


def test_url_auto_detection() -> None:
    adapter = get_registry().get_adapter("https://kakuyomu.jp/works/99999")
    assert isinstance(adapter, KakuyomuSource)
    assert get_registry().get_adapter("https://totally-unknown-site.example/novel/1") is None


@pytest.mark.parametrize(
    ("adapter", "url", "expected"),
    [
        (GenericSource(), "https://example.com/novel/1", False),
        (KakuyomuSource(), "https://kakuyomu.jp/works/123", True),
        (KakuyomuSource(), "https://example.com/novel/1", False),
        (SyosetuNcodeSource(), "https://ncode.syosetu.com/n1234abc/", True),
        (Novel18SyosetuSource(), "https://novel18.syosetu.com/n0813kx/", True),
    ],
)
def test_can_handle(adapter: object, url: str, expected: bool) -> None:
    assert isinstance(adapter, (GenericSource, KakuyomuSource, SyosetuNcodeSource, Novel18SyosetuSource))
    assert adapter.can_handle(url) is expected


def test_all_builtin_adapters_have_canonical_source_key() -> None:
    for adapter in (GenericSource(), KakuyomuSource(), SyosetuNcodeSource(), Novel18SyosetuSource()):
        assert adapter.source_key


def test_unknown_source_key_raises_operation_error() -> None:
    service = NovelOrchestrationService(storage=MagicMock(), translation=MagicMock())

    with pytest.raises(OperationError, match="No adapter found for source"):
        service._source_factory("totally_bogus_key")
