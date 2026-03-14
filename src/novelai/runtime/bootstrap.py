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
    from novelai.providers.gemini_provider import GeminiProvider
    from novelai.providers.openai_provider import OpenAIProvider
    from novelai.providers.registry import register_provider

    register_provider("dummy", lambda: DummyProvider())
    register_provider("openai", lambda: OpenAIProvider())
    register_provider("gemini", lambda: GeminiProvider())


def bootstrap_sources() -> None:
    """Register all known novel sources."""
    from novelai.sources.generic import GenericSource
    from novelai.sources.kakuyomu import KakuyomuSource
    from novelai.sources.novel18_syosetu import Novel18SyosetuSource
    from novelai.sources.registry import register_source
    from novelai.sources.syosetu_ncode import SyosetuNcodeSource

    register_source("syosetu_ncode", lambda: SyosetuNcodeSource())
    register_source("novel18_syosetu", lambda: Novel18SyosetuSource())
    register_source("kakuyomu", lambda: KakuyomuSource())
    register_source("generic", lambda: GenericSource())


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
    """Register all known export formats."""
    from novelai.export.epub_exporter import EPUBExporter
    from novelai.export.html_exporter import HTMLExporter
    from novelai.export.markdown_exporter import MarkdownExporter
    from novelai.export.registry import register_exporter

    register_exporter("epub", lambda: EPUBExporter())
    register_exporter("html", lambda: HTMLExporter())
    register_exporter("md", lambda: MarkdownExporter())
    # PDF exporter is not yet implemented (requires reportlab or weasyprint).


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
    _BOOTSTRAPPED = True
