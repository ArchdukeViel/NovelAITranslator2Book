from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Protocol

from novelai.infrastructure.http.client import validate_safe_url

logger = logging.getLogger(__name__)



def validate_url(url: str) -> str:
    """Validate URL scheme and reject private/internal targets (SSRF protection).

    Returns the validated URL unchanged, or raises ``SourceError``.
    """
    return validate_safe_url(url)


class SourceAdapter(ABC):
    """Base interface for a novel source / scraper adapter."""

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique key used to identify this source."""

    def matches_url(self, identifier_or_url: str) -> bool:
        """Return True if this adapter can handle the pasted novel URL."""
        return False

    def can_handle(self, identifier_or_url: str) -> bool:
        """Public alias for :meth:`matches_url`."""
        return self.matches_url(identifier_or_url)

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        """Convert a URL or loose identifier into the stable library key."""
        return identifier_or_url.strip()

    @abstractmethod
    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        """Fetch novel metadata (title/author, chapter list, etc.)."""

    @abstractmethod
    async def fetch_chapter(self, url: str) -> str:
        """Fetch raw chapter text from the source."""

    async def fetch_chapter_payload(self, url: str) -> Mapping[str, Any]:
        """Fetch chapter text plus optional structured assets."""
        validate_url(url)
        return {
            "text": await self.fetch_chapter(url),
            "images": [],
        }

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> Mapping[str, Any]:
        """Download an asset referenced by chapter content."""
        from novelai.infrastructure.http.fetch_service import get_default_fetch_service

        result = await get_default_fetch_service().get_bytes(url, source_key=self.key, referer=referer)
        return {
            "url": result.final_url,
            "content": result.body,
            "content_type": result.headers.get("content-type"),
        }


class SourceFactory(Protocol):
    """Factory signature for source adapter registrations."""

    def __call__(self, settings: Any) -> SourceAdapter:
        ...
