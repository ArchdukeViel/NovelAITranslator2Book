from __future__ import annotations

"""Explicit bootstrap for registering providers, sources, and input adapters.

The project uses registries for providers, sources, and input adapters (rather than hard imports).
This module provides a single bootstrap entrypoint that must run before any
code attempts to resolve providers, sources, or input adapters from registries.

This avoids import-time side-effects and makes it possible to control which
implementations are registered in a given runtime (e.g., tests).

bootstrap() is idempotent: it can be called multiple times safely.
"""

import logging  # noqa: E402

from novelai.logging_config import configure_logging  # noqa: E402

configure_logging()

_BOOTSTRAPPED = False
logger = logging.getLogger(__name__)


def bootstrap_providers() -> None:
    """Register all known translation providers."""
    from novelai.providers.dummy_provider import DummyProvider
    from novelai.providers.gemini_provider import GeminiProvider
    from novelai.providers.registry import register_provider

    register_provider("dummy", lambda: DummyProvider())
    register_provider("gemini", lambda: GeminiProvider())


def bootstrap_sources() -> None:
    """Register all known novel sources (built-in) then run pkgutil discovery."""
    from novelai.sources.generic import GenericSource
    from novelai.sources.kakuyomu import KakuyomuSource
    from novelai.sources.novel18_syosetu import Novel18SyosetuSource
    from novelai.sources.registry import get_registry
    from novelai.sources.syosetu_ncode import SyosetuNcodeSource

    registry = get_registry()
    registry.register(SyosetuNcodeSource)
    registry.register(Novel18SyosetuSource)
    registry.register(KakuyomuSource)
    registry.register(GenericSource)

    # Discover any extra adapter modules registered via pkgutil.
    registry.discover()
    logger.info("Adapter registry initialized: %d adapters registered", len(registry.list_adapters()))


def bootstrap_input_adapters() -> None:
    """Register the URL-based novel importer."""
    from novelai.inputs.registry import register_input_adapter
    from novelai.inputs.web import WebDocumentAdapter

    register_input_adapter("web", lambda: WebDocumentAdapter())


def bootstrap_provider_credentials() -> list[dict[str, object]]:
    """Hydrate active encrypted DB provider credentials into runtime settings."""
    from novelai.config.settings import settings

    if not settings.DATABASE_URL:
        logger.info("Provider credential hydration skipped: database_not_configured")
        return [{"hydrated": False, "reason": "database_not_configured"}]

    from novelai.db.engine import session_scope
    from novelai.runtime.container import container
    from novelai.services.provider_credentials import hydrate_active_provider_credentials

    try:
        with session_scope() as session:
            return hydrate_active_provider_credentials(db=session, preferences=container.preferences)
    except Exception as exc:
        if settings.ENV.strip().lower() not in {"development", "dev", "test", "testing", "local"}:
            raise
        logger.warning("Provider credential hydration skipped: %s", exc)
        return [{"hydrated": False, "reason": "hydration_failed"}]


def bootstrap() -> None:
    """Register all known providers, sources, and input adapters (idempotent).

    Safe to call multiple times; only registers once.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    bootstrap_providers()
    bootstrap_sources()
    bootstrap_input_adapters()
    bootstrap_provider_credentials()
    _BOOTSTRAPPED = True
