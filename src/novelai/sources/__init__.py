"""Content source adapters (web scraping/ingest)."""

from novelai.sources.base import SourceAdapter, SourceFactory, validate_url
from novelai.sources.registry import (
    available_sources,
    detect_source,
    get_source,
    register_source,
)

__all__ = [
    "SourceAdapter",
    "SourceFactory",
    "available_sources",
    "detect_source",
    "get_source",
    "register_source",
    "validate_url",
]
