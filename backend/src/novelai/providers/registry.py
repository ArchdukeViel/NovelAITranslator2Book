from __future__ import annotations

from collections.abc import Callable

from novelai.providers.base import TranslationProvider
from novelai.providers.dummy_provider import DummyProvider
from novelai.providers.gemini_provider import GeminiProvider

# Gemini is the production provider. Dummy remains available only for explicit
# local and test workflows.
_PROVIDER_REGISTRY: dict[str, Callable[[], TranslationProvider]] = {
    "gemini": lambda: GeminiProvider(),
    "dummy": lambda: DummyProvider(),
}


def register_provider(key: str, factory: Callable[[], TranslationProvider]) -> None:
    """Register a factory for an explicitly supported provider key."""
    if key not in {"gemini", "dummy"}:
        raise ValueError(f"Unsupported provider key: {key}")
    _PROVIDER_REGISTRY[key] = factory


def available_providers() -> list[str]:
    """Return the registered provider keys."""
    return sorted(_PROVIDER_REGISTRY)


def available_models(key: str) -> list[str]:
    """Return the supported model IDs for the provider identified by *key*."""
    provider = get_provider(key)
    try:
        return provider.available_models()
    except Exception:
        return [model for model in (getattr(provider, "DEFAULT_TEXT_MODEL", None),) if model]


def get_provider(key: str) -> TranslationProvider:
    """Return the provider registered for *key*."""
    factory = _PROVIDER_REGISTRY[key]
    return factory()
