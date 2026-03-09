from __future__ import annotations

import ipaddress
import socket
from abc import ABC, abstractmethod
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

import httpx

from novelai.core.errors import SourceError


def validate_url(url: str) -> str:
    """Validate URL scheme and reject private/internal targets (SSRF protection).

    Returns the validated URL unchanged, or raises ``SourceError``.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SourceError(f"Unsupported URL scheme: {parsed.scheme!r}. Only http/https are allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise SourceError(f"Invalid URL (missing hostname): {url}")
    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        for _family, _type, _proto, _canonname, sockaddr in resolved:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
                raise SourceError(f"URL resolves to a private/reserved address: {hostname}")
    except socket.gaierror:
        pass  # DNS failure will be caught by httpx at request time
    return url


class SourceAdapter(ABC):
    """Base interface for a novel source / scraper adapter."""

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique key used to identify this source."""

    def matches_url(self, identifier_or_url: str) -> bool:
        """Return True if this adapter can handle the pasted novel URL."""
        return False

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
        validate_url(url)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if isinstance(referer, str) and referer.strip():
            headers["Referer"] = referer.strip()

        async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        return {
            "url": str(response.url),
            "content": response.content,
            "content_type": response.headers.get("content-type"),
        }


class SourceFactory(Protocol):
    """Factory signature for source adapter registrations."""

    def __call__(self, settings: Any) -> SourceAdapter:
        ...
