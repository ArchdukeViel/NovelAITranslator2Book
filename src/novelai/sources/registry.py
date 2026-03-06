from __future__ import annotations

from typing import Callable, Dict

from novelai.sources.base import SourceAdapter

_SOURCE_REGISTRY: Dict[str, Callable[[], SourceAdapter]] = {}


def register_source(key: str, factory: Callable[[], SourceAdapter]) -> None:
    """Register a source adapter factory by key."""
    _SOURCE_REGISTRY[key] = factory


def get_source(key: str) -> SourceAdapter:
    factory = _SOURCE_REGISTRY.get(key)
    if factory is None:
        raise KeyError(f"No source registered for key: {key}")
    return factory()


def available_sources() -> list[str]:
    return list(_SOURCE_REGISTRY.keys())
