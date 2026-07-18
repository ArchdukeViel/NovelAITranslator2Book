"""Tests for the (Gemini-only) provider registry."""

from __future__ import annotations

import pytest

from novelai.providers.base import TranslationProvider
from novelai.providers.gemini_provider import GeminiProvider
from novelai.providers.registry import (
    _PROVIDER_REGISTRY,
    available_models,
    available_providers,
    get_provider,
    register_provider,
)
from novelai.runtime.bootstrap import bootstrap_providers


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
        register_provider("gemini", lambda: _FakeProvider())
        provider = get_provider("gemini")
        assert isinstance(provider, _FakeProvider)

    def test_get_provider_rejects_unknown_key(self) -> None:
        with pytest.raises(KeyError, match="nonexistent"):
            get_provider("nonexistent")

    def test_register_provider_rejects_unsupported_key(self) -> None:
        with pytest.raises(ValueError, match="Unsupported provider key: openai"):
            register_provider("openai", lambda: _FakeProvider())

    def test_available_providers(self) -> None:
        providers = set(available_providers())
        assert {"dummy", "gemini"}.issubset(providers)
        assert "nvidia" not in providers
        assert "openai" not in providers

    def test_bootstrap_registers_gemini_and_dummy_and_excludes_openai(self) -> None:
        _PROVIDER_REGISTRY.clear()
        bootstrap_providers()
        providers = set(available_providers())
        assert {"dummy", "gemini"}.issubset(providers)
        assert "openai" not in providers
        assert "nvidia" not in providers

    def test_available_models_returns_gemini_models(self) -> None:
        models = available_models("gemini")
        assert "gemini-3.1-flash-lite" in models
        assert "gemma-4-31b-it" in models

    def test_gemini_provider_lists_gemini_api_gemma_model_id(self) -> None:
        models = GeminiProvider().available_models()
        assert "gemma-4-31b-it" in models
        assert "google/gemma-4-31b-it" not in models
