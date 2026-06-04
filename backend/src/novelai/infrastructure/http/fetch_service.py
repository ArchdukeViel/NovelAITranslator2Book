from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from novelai.core.errors import SourceError
from novelai.infrastructure.http.cache import FetchCache, FetchCacheEntry, InMemoryFetchCache
from novelai.infrastructure.http.client import create_async_client, validate_safe_url
from novelai.infrastructure.http.throttle import DomainThrottle
from novelai.utils.retry_decorator import RetryConfig, Retrier


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str
    body: bytes
    source_key: str
    fetched_at: str
    from_cache: bool = False
    elapsed_seconds: float | None = None


ClientFactory = Callable[..., httpx.AsyncClient]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _headers_dict(headers: httpx.Headers | dict[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in dict(headers).items()}


class FetchService:
    """Central HTTP fetcher for source adapters."""

    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        client_factory: ClientFactory = create_async_client,
        throttle: DomainThrottle | None = None,
        cache: FetchCache | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._throttle = throttle or _GLOBAL_THROTTLE
        self._cache = cache or InMemoryFetchCache()

    async def get_text(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: Any = None,
    ) -> FetchResult:
        return await self._fetch(
            url,
            source_key=source_key,
            referer=referer,
            headers=headers,
            cookies=cookies,
        )

    async def get_bytes(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: Any = None,
    ) -> FetchResult:
        return await self._fetch(
            url,
            source_key=source_key,
            referer=referer,
            headers=headers,
            cookies=cookies,
        )

    async def _fetch(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None,
        headers: dict[str, str] | None,
        cookies: Any,
    ) -> FetchResult:
        requested_url = validate_safe_url(url)
        request_headers = dict(headers or {})
        if referer and referer.strip():
            request_headers["Referer"] = referer.strip()
        request_headers.update(self._cache.conditional_headers(source_key, requested_url))

        await self._throttle.before_request(requested_url)
        started = perf_counter()
        try:
            response = await self._with_retry(
                lambda: self._request(requested_url, headers=request_headers, cookies=cookies)
            )
        except httpx.HTTPStatusError as exc:
            await self._throttle.after_response(requested_url, exc.response.status_code)
            raise SourceError(
                f"Failed to fetch {source_key} page from {requested_url} "
                f"(status={exc.response.status_code})."
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"Failed to fetch {source_key} page from {requested_url}: {exc}") from exc

        elapsed = perf_counter() - started
        await self._throttle.after_response(str(response.url), response.status_code)

        if response.status_code == 304:
            cached = self._cache.get(source_key, requested_url)
            if cached is None:
                raise SourceError(f"{source_key} returned 304 for {requested_url}, but no cached response exists.")
            return FetchResult(
                requested_url=requested_url,
                final_url=str(response.url),
                status_code=304,
                headers=_headers_dict(response.headers),
                text=cached.text,
                body=cached.body,
                source_key=source_key,
                fetched_at=_utc_now_iso(),
                from_cache=True,
                elapsed_seconds=elapsed,
            )

        headers_payload = _headers_dict(response.headers)
        body = bytes(response.content)
        text = response.text
        result = FetchResult(
            requested_url=requested_url,
            final_url=str(response.url),
            status_code=response.status_code,
            headers=headers_payload,
            text=text,
            body=body,
            source_key=source_key,
            fetched_at=_utc_now_iso(),
            from_cache=False,
            elapsed_seconds=elapsed,
        )
        self._cache.set(
            FetchCacheEntry(
                requested_url=requested_url,
                final_url=result.final_url,
                status_code=result.status_code,
                headers=headers_payload,
                text=text,
                body=body,
                source_key=source_key,
                fetched_at=result.fetched_at,
            )
        )
        return result

    async def _request(self, url: str, *, headers: dict[str, str], cookies: Any) -> httpx.Response:
        async with self._client_factory(headers=headers, cookies=cookies) as client:
            response = await client.get(url)
            if response.status_code != 304:
                response.raise_for_status()
            return response

    async def _with_retry(self, fn: Callable[[], Any]) -> httpx.Response:
        config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=30.0,
            jitter=True,
            retry_on=(httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError),
        )
        retrier = Retrier(config)

        class _NonRetryableError(Exception):
            pass

        async def _wrapped() -> httpx.Response:
            try:
                return await fn()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in self._RETRYABLE_STATUS_CODES:
                    raise _NonRetryableError(exc)
                raise

        try:
            return await retrier.execute_async(_wrapped)
        except _NonRetryableError as exc:
            original = exc.args[0] if exc.args else None
            if isinstance(original, BaseException):
                raise original from exc
            raise


_GLOBAL_THROTTLE = DomainThrottle()
_DEFAULT_FETCH_SERVICE: FetchService | None = None


def get_default_fetch_service() -> FetchService:
    global _DEFAULT_FETCH_SERVICE
    if _DEFAULT_FETCH_SERVICE is None:
        _DEFAULT_FETCH_SERVICE = FetchService(throttle=_GLOBAL_THROTTLE)
    return _DEFAULT_FETCH_SERVICE
