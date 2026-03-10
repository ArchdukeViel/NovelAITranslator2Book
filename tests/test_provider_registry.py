"""Tests for the provider registry."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from novelai.providers.base import TranslationProvider
from novelai.providers.registry import (
    _PROVIDER_REGISTRY,
    available_providers,
    get_provider,
    register_provider,
)


class _FakeProvider(TranslationProvider):
    """Minimal provider for registry tests."""

    @property
    def key(self) -> str:
        return "fake_prov"

    async def translate(self, prompt: str, model: str | None = None, max_tokens: int | None = None, **kwargs) -> dict:  # type: ignore[override]
        return {"text": prompt}

    def available_models(self) -> list[str]:
        return ["model-a", "model-b"]


class TestProviderRegistry:
    def setup_method(self) -> None:
        self._saved = dict(_PROVIDER_REGISTRY)

    def teardown_method(self) -> None:
        _PROVIDER_REGISTRY.clear()
        _PROVIDER_REGISTRY.update(self._saved)

    def test_register_and_get_provider(self) -> None:
        register_provider("test_prov", lambda: _FakeProvider())
        provider = get_provider("test_prov")
        assert isinstance(provider, _FakeProvider)

    def test_get_provider_raises_for_unknown(self) -> None:
        with pytest.raises(KeyError, match="No provider registered"):
            get_provider("nonexistent")

    def test_get_provider_uses_default_when_key_is_none(self) -> None:
        register_provider("dummy", lambda: _FakeProvider())
        with patch("novelai.providers.registry.settings") as mock_settings:
            mock_settings.PROVIDER_DEFAULT = "dummy"
            provider = get_provider(None)
            assert isinstance(provider, _FakeProvider)

    def test_available_providers(self) -> None:
        register_provider("prov_x", lambda: _FakeProvider())
        assert "prov_x" in available_providers()
