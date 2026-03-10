from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Mapping, Protocol, TypeVar
from urllib.parse import urlparse

import httpx

from novelai.core.errors import SourceError

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


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

    _last_request_time: float = 0.0

    async def _rate_limit(self) -> None:
        """Wait if needed to respect the configured scrape delay."""
        from novelai.config.settings import settings

        delay = settings.SCRAPE_DELAY_SECONDS
        if delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_time = time.monotonic()

    _RETRYABLE_STATUS_CODES: set[int] = {429, 500, 502, 503, 504}

    async def _with_retry(self, fn: Callable[[], Awaitable[_T]]) -> _T:
        """Execute an async no-arg callable with retry on transient HTTP errors.

        Retries on connection errors, timeouts, and 429/5xx status codes.
        Uses exponential backoff with jitter via :class:`BackoffCalculator`.
        """
        from novelai.utils.retry_decorator import BackoffCalculator, RetryConfig, RetryStrategy

        config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=30.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=True,
        )
        backoff = BackoffCalculator(config)
        last_exc: Exception | None = None

        for attempt in range(config.max_attempts):
            try:
                return await fn()
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in self._RETRYABLE_STATUS_CODES:
                    raise
                last_exc = exc

            if attempt < config.max_attempts - 1:
                delay = backoff.calculate(attempt)
                logger.warning(
                    "Attempt %d/%d failed: %s — retrying in %.2fs",
                    attempt + 1,
                    config.max_attempts,
                    last_exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

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
        await self._rate_limit()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if isinstance(referer, str) and referer.strip():
            headers["Referer"] = referer.strip()

        async def _do_request() -> httpx.Response:
            async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp

        response = await self._with_retry(_do_request)

        return {
            "url": str(response.url),
            "content": response.content,
            "content_type": response.headers.get("content-type"),
        }


class SourceFactory(Protocol):
    """Factory signature for source adapter registrations."""

    def __call__(self, settings: Any) -> SourceAdapter:
        ...
