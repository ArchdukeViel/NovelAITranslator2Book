from __future__ import annotations

import logging
from collections.abc import Callable

from novelai.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

_SOURCE_REGISTRY: dict[str, Callable[[], SourceAdapter]] = {}


def register_source(key: str, factory: Callable[[], SourceAdapter]) -> None:
    """Register a source adapter factory by key."""
    _SOURCE_REGISTRY[key] = factory


def get_source(key: str) -> SourceAdapter:
    factory = _SOURCE_REGISTRY.get(key)
    if factory is None:
        raise KeyError(f"No source registered for key: {key}")
    return factory()


def detect_source(identifier_or_url: str) -> str | None:
    for key, factory in _SOURCE_REGISTRY.items():
        try:
            if factory().matches_url(identifier_or_url):
                return key
        except Exception:
            logger.debug("Source adapter %s failed during URL detection.", key)
            continue
    return None


def available_sources() -> list[str]:
    return list(_SOURCE_REGISTRY.keys())
