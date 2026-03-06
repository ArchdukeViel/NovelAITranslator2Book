from __future__ import annotations

"""Explicit bootstrap for registering providers and sources.

The project uses registries for providers and sources (rather than hard imports).
This module provides a single bootstrap entrypoint that must run before any
code attempts to resolve providers or sources from the registry.

This avoids import-time side-effects and makes it possible to control which
providers/sources are registered in a given runtime (e.g., tests).
"""


def bootstrap_providers() -> None:
    from novelai.providers.dummy_provider import DummyProvider
    from novelai.providers.openai_provider import OpenAIProvider
    from novelai.providers.registry import register_provider

    register_provider("dummy", lambda: DummyProvider())
    register_provider("openai", lambda: OpenAIProvider())


def bootstrap_sources() -> None:
    from novelai.sources.example_source import ExampleSource
    from novelai.sources.registry import register_source
    from novelai.sources.syosetu_ncode import SyosetuNcodeSource

    register_source("example", lambda: ExampleSource())
    register_source("syosetu_ncode", lambda: SyosetuNcodeSource())


def bootstrap() -> None:
    """Register all known providers and sources."""
    bootstrap_providers()
    bootstrap_sources()
