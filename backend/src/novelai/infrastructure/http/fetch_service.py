from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from novelai.config.settings import settings
from novelai.core.errors import SourceError
from novelai.infrastructure.http.cache import FetchCache, FetchCacheEntry, LRUFetchCache
from novelai.infrastructure.http.client import create_async_client, validate_safe_url
from novelai.infrastructure.http.retry import Retrier, RetryConfig
from novelai.infrastructure.http.throttle import DomainThrottle

MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # legacy fallback cap (per-kind limits come from settings)

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

# Headers that must not leak across origins on a redirect hop.  The first
# group is outright security-sensitive (credentials / validators); the
# second is conditional-request state tied to the original resource.
_CROSS_ORIGIN_STRIPPED_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "host",
        "if-none-match",
        "if-modified-since",
        "if-match",
        "if-unmodified-since",
        "if-range",
    }
)


def _origin(url: str) -> tuple[str, str]:
    """Return the (scheme, hostname) origin tuple for an HTTP URL."""
    parsed = urlparse(url)
    return parsed.scheme.lower(), (parsed.hostname or "").lower()


def _strip_origin_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of ``headers`` with cross-origin-sensitive entries removed.

    Headers are stripped case-insensitively; the returned dict is a fresh
    copy so the caller's headers are not mutated.  ``User-Agent`` and
    ``Accept`` are intentionally preserved — they are safe to forward and
    help the destination return appropriate content.
    """
    return {key: value for key, value in headers.items() if key.lower() not in _CROSS_ORIGIN_STRIPPED_HEADERS}


def _kind_limit_bytes(kind: str) -> int:
    """Return the configured response-size limit for a fetch kind."""
    return {
        "api": settings.HTTP_API_RESPONSE_MAX_BYTES,
        "html": settings.HTTP_HTML_RESPONSE_MAX_BYTES,
        "asset": settings.HTTP_ASSET_RESPONSE_MAX_BYTES,
    }.get(kind, settings.HTTP_HTML_RESPONSE_MAX_BYTES)


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header into seconds (seconds or HTTP-date).

    Returns ``None`` when the value is absent or unparseable so callers fall
    back to the regular backoff schedule.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
        if seconds >= 0 and seconds == seconds:  # reject NaN
            return seconds
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None
    delta = (parsed - datetime.now(UTC)).total_seconds()
    return max(0.0, delta)


@dataclass(frozen=True)
class _FetchedBody:
    """A fully streamed response with the validated final URL."""

    final_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    text: str


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
    """Central HTTP fetcher for source adapters.

    HTTP clients are pooled per request profile (``regular`` vs ``r18``,
    etc.) and reused across requests; per-request headers, referers, and
    cookies are attached to individual calls. Responses are cached through
    a bounded, TTL-aware cache keyed by ``(source_key, profile, url)`` so
    identical URLs fetched under different profiles never collide.
    """

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
        self._cache = cache or LRUFetchCache()
        # Pooled clients keyed by request profile ("" for the default).
        self._clients: dict[str, httpx.AsyncClient] = {}

    async def get_text(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: Any = None,
        on_retry: Callable[[int, Exception], None] | None = None,
        profile: str | None = None,
        kind: str = "html",
    ) -> FetchResult:
        return await self._fetch(
            url,
            source_key=source_key,
            referer=referer,
            headers=headers,
            cookies=cookies,
            on_retry=on_retry,
            kind=kind,
            profile=profile,
        )

    async def get_bytes(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: Any = None,
        on_retry: Callable[[int, Exception], None] | None = None,
        profile: str | None = None,
        kind: str = "asset",
    ) -> FetchResult:
        return await self._fetch(
            url,
            source_key=source_key,
            referer=referer,
            headers=headers,
            cookies=cookies,
            on_retry=on_retry,
            kind=kind,
            profile=profile,
        )

    async def _fetch(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None,
        headers: dict[str, str] | None,
        cookies: Any,
        kind: str,
        profile: str | None,
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> FetchResult:
        requested_url = validate_safe_url(url)
        request_headers = dict(headers or {})
        if referer and referer.strip():
            request_headers["Referer"] = referer.strip()
        request_headers.update(self._cache.conditional_headers(source_key, requested_url, profile=profile))

        started = perf_counter()
        try:
            fetched = await self._with_retry(
                lambda: self._request(
                    requested_url,
                    headers=request_headers,
                    cookies=cookies,
                    profile=profile,
                    kind=kind,
                ),
                on_retry=on_retry,
            )
        except httpx.HTTPStatusError as exc:
            await self._throttle.after_response(requested_url, exc.response.status_code)
            raise SourceError(
                f"Failed to fetch {source_key} page from {requested_url} (status={exc.response.status_code})."
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"Failed to fetch {source_key} page from {requested_url}: {exc}") from exc

        elapsed = perf_counter() - started
        final_url = validate_safe_url(fetched.final_url)
        if fetched.status_code == 304:
            cached = self._cache.get(source_key, requested_url, profile=profile)
            if cached is None:
                raise SourceError(f"{source_key} returned 304 for {requested_url}, but no cached response exists.")
            return FetchResult(
                requested_url=requested_url,
                final_url=final_url,
                status_code=304,
                headers=fetched.headers,
                text=cached.text,
                body=cached.body,
                source_key=source_key,
                fetched_at=_utc_now_iso(),
                from_cache=True,
                elapsed_seconds=elapsed,
            )

        headers_payload = fetched.headers
        body = fetched.body
        text = fetched.text
        result = FetchResult(
            requested_url=requested_url,
            final_url=final_url,
            status_code=fetched.status_code,
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
                kind=kind,
                profile=profile,
            )
        )
        return result

    async def _request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        cookies: Any,
        profile: str | None,
        kind: str,
    ) -> _FetchedBody:
        """Fetch ``url`` with bounded, validated manual redirect handling.

        Redirect hops are followed only after the resolved destination passes
        SSRF validation (scheme, credentials, hostname, resolved addresses).
        Bodies are read incrementally and rejected as soon as the applicable
        per-kind size limit is exceeded.

        Section 11: cross-origin redirects must not leak credentials,
        validators, or origin-specific ``Referer`` headers to the new host.
        The per-hop headers are re-derived from the caller's input on each
        hop, sensitive entries are stripped when the origin changes, and
        the throttle accounts for every requested destination (not only the
        initial URL).
        """
        client = self._pooled_client(profile)
        current = url
        visited: set[str] = {url}
        max_redirects = settings.HTTP_MAX_REDIRECTS
        current_origin = _origin(current)
        current_headers = dict(headers)

        for _ in range(max_redirects + 1):
            # Per-hop throttle accounting.
            await self._throttle.before_request(current)
            async with client.stream("GET", current, headers=current_headers, cookies=cookies) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location or not location.strip():
                        raise SourceError(f"Redirect response from {current} without Location header.")
                    next_url = urljoin(current, location.strip())
                    # Validate before requesting the destination (SSRF).
                    validate_safe_url(next_url)
                    if next_url in visited:
                        raise SourceError(f"Redirect loop detected at {next_url}.")
                    next_origin = _origin(next_url)
                    # Rebuild per-hop headers so we can strip credentials /
                    # validators when the origin changes.
                    if next_origin != current_origin:
                        current_headers = _strip_origin_sensitive_headers(headers)
                        # Referer is origin-specific too: pointing the new
                        # host at the original URL would leak the previous
                        # origin to the redirect target.  Drop it.
                        current_headers.pop("Referer", None)
                    else:
                        # Same-origin redirect: keep the caller's headers
                        # and set Referer to the URL we're coming FROM.
                        current_headers = dict(headers)
                        current_headers["Referer"] = current
                    visited.add(next_url)
                    current = next_url
                    current_origin = next_origin
                    continue
                body = await self._read_body_limited(response, current, kind)
                if response.status_code != 304:
                    response.raise_for_status()
                await self._throttle.after_response(current, response.status_code)
                return _FetchedBody(
                    final_url=current,
                    status_code=response.status_code,
                    headers=_headers_dict(response.headers),
                    body=body,
                    text=body.decode(response.encoding or "utf-8", errors="replace"),
                )

        raise SourceError(f"Too many redirects (max {max_redirects}) fetching {url}.")

    async def _read_body_limited(self, response: httpx.Response, url: str, kind: str) -> bytes:
        """Stream a response body, enforcing the per-kind limit incrementally."""
        limit = _kind_limit_bytes(kind)
        declared = response.headers.get("content-length")
        if declared:
            try:
                if int(declared) > limit:
                    raise SourceError(
                        f"Declared Content-Length {declared} for {url} exceeds the {kind} limit of {limit} bytes."
                    )
            except ValueError:
                # Malformed header: rely on streaming enforcement below.
                pass
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > limit:
                raise SourceError(f"Response from {url} exceeds the {kind} size limit of {limit} bytes.")
            chunks.append(chunk)
        return b"".join(chunks)

    def _pooled_client(self, profile: str | None) -> httpx.AsyncClient:
        key = profile or ""
        client = self._clients.get(key)
        if client is None:
            client = self._client_factory()
            self._clients[key] = client
        return client

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    def cache_stats(self) -> dict[str, int | float | None]:
        if isinstance(self._cache, LRUFetchCache):
            return self._cache.stats()
        return {}

    async def _with_retry(
        self, fn: Callable[[], Any], *, on_retry: Callable[[int, Exception], None] | None = None
    ) -> _FetchedBody:
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

        def _retry_after_override(retry_number: int, exc: Exception) -> float | None:
            """Honor a valid ``Retry-After`` header, bounded by configuration."""
            if not isinstance(exc, httpx.HTTPStatusError):
                return None
            parsed = _parse_retry_after(exc.response.headers.get("retry-after"))
            if parsed is None:
                return None
            return min(parsed, float(settings.HTTP_RETRY_AFTER_MAX_SECONDS))

        async def _wrapped() -> _FetchedBody:
            try:
                return await fn()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in self._RETRYABLE_STATUS_CODES:
                    raise _NonRetryableError(exc) from exc
                raise

        try:
            return await retrier.execute_async(
                _wrapped,
                on_retry=on_retry,
                retry_delay_override=_retry_after_override,
            )
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
