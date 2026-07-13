from __future__ import annotations

import logging
from collections.abc import Callable

from novelai.providers.base import TranslationProvider
from novelai.providers.dummy_provider import DummyProvider
from novelai.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

# Registry now has a single translation provider. The dict and the
# register_provider/available_providers helpers are kept as thin shims
# so legacy callers (admin service, tests, runtime bootstrap) keep working.
# All non-gemini keys fall back to the Gemini provider.
_PROVIDER_REGISTRY: dict[str, Callable[[], TranslationProvider]] = {
    "gemini": lambda: GeminiProvider(),
    "dummy": lambda: DummyProvider(),  # legacy alias for testing
}


def register_provider(key: str, factory: Callable[[], TranslationProvider]) -> None:
    """Register a provider factory. Only ``"gemini"`` (and the ``"dummy"`` alias) are honoured.

    Non-gemini registrations are accepted but ignored, with a warning. This
    preserves the old public API for bootstrap code and tests without
    re-introducing a multi-provider abstraction.
    """
    if key in {"gemini", "dummy"}:
        _PROVIDER_REGISTRY[key] = factory
        return
    logger.warning(
        "Provider key %r ignored: only Gemini is supported. NVIDIA provider has been removed.",
        key,
    )


def available_providers() -> list[str]:
    """Return the supported provider keys. Always includes ``"gemini"``."""
    return ["dummy", "gemini"]


def available_models(key: str | None = None) -> list[str]:
    """Return the supported model IDs for the provider identified by *key* (defaults to ``"gemini"``).

    Delegates to the provider instance so the result is always accurate per
    the registered factory.
    """
    provider = get_provider(key)
    try:
        return provider.available_models()
    except Exception:
        return [model for model in (getattr(provider, "DEFAULT_TEXT_MODEL", None),) if model]


def get_provider(key: str | None = None) -> TranslationProvider:
    """Return a provider by *key* (defaults to ``"gemini"``).

    The *key* argument is accepted for backward compatibility. Any value
    other than ``"gemini"``/``"dummy"`` triggers a warning and falls back
    to the Gemini provider.
    """
    if key is not None and key not in {"gemini", "dummy"}:
        logger.warning(
            "Provider key %r requested but only Gemini is available. Falling back to Gemini.",
            key,
        )

    factory = _PROVIDER_REGISTRY.get(key or "gemini") or _PROVIDER_REGISTRY["gemini"]
    return factory()
