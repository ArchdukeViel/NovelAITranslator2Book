from __future__ import annotations

"""Explicit bootstrap for registering providers, sources, and exporters.

The project uses registries for providers, sources, and exporters (rather than hard imports).
This module provides a single bootstrap entrypoint that must run before any
code attempts to resolve providers/sources/exporters from registries.

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
    """Register all known document/input adapters."""
    from novelai.inputs.cbz import CBZDocumentAdapter
    from novelai.inputs.epub import EPUBDocumentAdapter
    from novelai.inputs.image_folder import ImageFolderDocumentAdapter
    from novelai.inputs.pdf import PDFDocumentAdapter
    from novelai.inputs.registry import register_input_adapter
    from novelai.inputs.text import TextDocumentAdapter
    from novelai.inputs.web import WebDocumentAdapter

    register_input_adapter("web", lambda: WebDocumentAdapter())
    register_input_adapter("text", lambda: TextDocumentAdapter())
    register_input_adapter("epub", lambda: EPUBDocumentAdapter())
    register_input_adapter("pdf", lambda: PDFDocumentAdapter())
    register_input_adapter("image_folder", lambda: ImageFolderDocumentAdapter())
    register_input_adapter("cbz", lambda: CBZDocumentAdapter())


def bootstrap_exporters() -> None:
    """Register all known export formats.

    PDF export is deprecated (DEBT-007). The ``PDFExporter`` stub is not
    registered. ``ExportService.export("pdf", ...)`` returns a controlled
    ``OperationError`` instead of a raw ``KeyError`` or ``NotImplementedError``.
    Historical manifests with ``format: "pdf"`` are preserved but new PDF
    export requests are rejected.
    """
    from novelai.export.epub_exporter import EPUBExporter
    from novelai.export.html_exporter import HTMLExporter
    from novelai.export.markdown_exporter import MarkdownExporter
    from novelai.export.registry import register_exporter

    register_exporter("epub", lambda: EPUBExporter())
    register_exporter("html", lambda: HTMLExporter())
    register_exporter("md", lambda: MarkdownExporter())


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
    """Register all known providers, sources, and exporters (idempotent).

    Safe to call multiple times; only registers once.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    bootstrap_providers()
    bootstrap_sources()
    bootstrap_input_adapters()
    bootstrap_exporters()
    bootstrap_provider_credentials()
    _BOOTSTRAPPED = True
