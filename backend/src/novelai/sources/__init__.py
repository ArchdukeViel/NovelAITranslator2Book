"""Content source adapters (web scraping/ingest)."""

from novelai.sources.base import SourceAdapter, SourceFactory, validate_url
from novelai.sources.registry import (
    available_sources,
    detect_source,
    discover,
    get_adapter,
    get_by_key,
    get_source,
    list_adapters,
    register_source,
)

__all__ = [
    "SourceAdapter",
    "SourceFactory",
    "available_sources",
    "detect_source",
    "discover",
    "get_adapter",
    "get_by_key",
    "get_source",
    "list_adapters",
    "register_source",
    "validate_url",
]
