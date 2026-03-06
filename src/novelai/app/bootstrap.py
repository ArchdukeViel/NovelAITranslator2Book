from __future__ import annotations

"""Explicit bootstrap for registering providers, sources, and exporters.

The project uses registries for providers, sources, and exporters (rather than hard imports).
This module provides a single bootstrap entrypoint that must run before any
code attempts to resolve providers/sources/exporters from registries.

This avoids import-time side-effects and makes it possible to control which
implementations are registered in a given runtime (e.g., tests).

bootstrap() is idempotent: it can be called multiple times safely.
"""

_BOOTSTRAPPED = False


def bootstrap_providers() -> None:
    """Register all known translation providers."""
    from novelai.providers.dummy_provider import DummyProvider
    from novelai.providers.openai_provider import OpenAIProvider
    from novelai.providers.registry import register_provider

    register_provider("dummy", lambda: DummyProvider())
    register_provider("openai", lambda: OpenAIProvider())


def bootstrap_sources() -> None:
    """Register all known novel sources."""
    from novelai.sources.example_source import ExampleSource
    from novelai.sources.registry import register_source
    from novelai.sources.syosetu_ncode import SyosetuNcodeSource

    register_source("example", lambda: ExampleSource())
    register_source("syosetu_ncode", lambda: SyosetuNcodeSource())


def bootstrap_exporters() -> None:
    """Register all known export formats."""
    from novelai.export.epub_exporter import EPUBExporter
    from novelai.export.pdf_exporter import PDFExporter
    from novelai.export.registry import register_exporter

    register_exporter("epub", lambda: EPUBExporter())
    register_exporter("pdf", lambda: PDFExporter())


def bootstrap() -> None:
    """Register all known providers, sources, and exporters (idempotent).
    
    Safe to call multiple times; only registers once.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    
    bootstrap_providers()
    bootstrap_sources()
    bootstrap_exporters()
    _BOOTSTRAPPED = True
