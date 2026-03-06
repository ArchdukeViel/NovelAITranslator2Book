from __future__ import annotations

from typing import Callable, Dict

from novelai.config.settings import settings
from novelai.providers.base import TranslationProvider


_PROVIDER_REGISTRY: Dict[str, Callable[[], TranslationProvider]] = {}


def register_provider(key: str, factory: Callable[[], TranslationProvider]) -> None:
    """Register a provider factory by key."""
    _PROVIDER_REGISTRY[key] = factory


def get_provider(key: str | None = None) -> TranslationProvider:
    """Retrieve a configured provider instance.

    Falls back to the default provider specified in settings.
    """

    effective_key = key or settings.PROVIDER_DEFAULT
    factory = _PROVIDER_REGISTRY.get(effective_key)
    if factory is None:
        raise KeyError(f"No provider registered for key: {effective_key}")

    return factory()


def available_providers() -> list[str]:
    return list(_PROVIDER_REGISTRY.keys())
