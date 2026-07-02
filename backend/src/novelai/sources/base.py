from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, TypeVar

import httpx

from novelai.infrastructure.http.client import validate_safe_url

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def validate_url(url: str) -> str:
    """Validate URL scheme and reject private/internal targets (SSRF protection).

    Returns the validated URL unchanged, or raises ``SourceError``.
    """
    return validate_safe_url(url)


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
        Uses the project's :class:`Retrier` with a conservative config.
        """
        from novelai.utils.retry_decorator import RetryConfig, Retrier

        config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=30.0,
            jitter=True,
            # Only retry on network/calendar errors and HTTPStatusError
            retry_on=(httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError),
        )

        retrier = Retrier(config)

        class _NonRetryableError(Exception):
            pass

        async def _wrapped() -> _T:
            try:
                return await fn()
            except httpx.HTTPStatusError as exc:
                # If status code isn't considered retryable, surface as non-retryable
                if exc.response.status_code not in self._RETRYABLE_STATUS_CODES:
                    raise _NonRetryableError(exc)
                raise

        try:
            return await retrier.execute_async(_wrapped)
        except _NonRetryableError as exc:
            # Unwrap original HTTPStatusError passed as the first arg when
            # the sentinel _NonRetryableError was raised above. Guard against
            # missing/None values so we never attempt to raise a non-BaseException.
            original = exc.args[0] if exc.args else None
            if isinstance(original, BaseException):
                raise original from exc
            # Fall back to re-raising the wrapper if no valid inner exception.
            raise

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
