"""Blocker G tests: manual redirect validation, streaming size limits, Retry-After, aclose."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import httpx
import pytest

from novelai.config.settings import settings
from novelai.core.errors import SourceError
from novelai.infrastructure.http.cache import InMemoryFetchCache
from novelai.infrastructure.http.client import create_async_client
from novelai.infrastructure.http.fetch_service import FetchService
from novelai.infrastructure.http.throttle import DomainThrottle


class RecordingThrottle(DomainThrottle):
    def __init__(self) -> None:
        super().__init__(min_delay_seconds=0.0)
        self.urls: list[str] = []

    async def before_request(self, url: str) -> None:
        self.urls.append(url)

    async def after_response(self, url: str, status_code: int) -> None:
        pass


def _service(handler) -> FetchService:
    return FetchService(
        client_factory=lambda **kwargs: create_async_client(transport=httpx.MockTransport(handler), **kwargs),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )


class TrackingStream(httpx.AsyncByteStream):
    """AsyncByteStream that records how many chunks were actually yielded."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.iterated_chunks = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            self.iterated_chunks += 1
            yield chunk


@pytest.mark.asyncio
async def test_same_origin_redirect_followed_and_final_url_recorded():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/next"}, request=request)
        return httpx.Response(200, text="destination", request=request)

    service = _service(handler)
    result = await service.get_text("https://example.test/start", source_key="test_source")

    assert result.status_code == 200
    assert result.final_url == "https://example.test/next"
    assert result.text == "destination"
    assert result.requested_url == "https://example.test/start"


@pytest.mark.asyncio
async def test_cross_origin_public_redirect_followed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/ok"}, request=request)
        return httpx.Response(200, text="cdn body", request=request)

    service = _service(handler)
    result = await service.get_text("https://example.test/start", source_key="test_source")

    assert result.final_url == "https://cdn.test/ok"
    assert result.text == "cdn body"


@pytest.mark.asyncio
async def test_redirect_to_loopback_rejected_before_destination_request():
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/evil"}, request=request)

    service = _service(handler)

    with pytest.raises(SourceError):
        await service.get_text("https://example.test/start", source_key="test_source")

    # Only the initial request was made; the private destination was never hit.
    assert requested == ["https://example.test/start"]


@pytest.mark.asyncio
async def test_redirect_with_unsupported_scheme_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "ftp://example.test/file"}, request=request)

    service = _service(handler)

    with pytest.raises(SourceError):
        await service.get_text("https://example.test/start", source_key="test_source")


@pytest.mark.asyncio
async def test_redirect_without_location_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={}, request=request)

    service = _service(handler)

    with pytest.raises(SourceError, match="Location"):
        await service.get_text("https://example.test/start", source_key="test_source")


@pytest.mark.asyncio
async def test_redirect_loop_detected():
    def handler(request: httpx.Request) -> httpx.Response:
        target = "/b" if request.url.path == "/a" else "/a"
        return httpx.Response(302, headers={"Location": target}, request=request)

    service = _service(handler)

    with pytest.raises(SourceError, match="Redirect loop"):
        await service.get_text("https://example.test/a", source_key="test_source")


@pytest.mark.asyncio
async def test_too_many_redirects_bounded(monkeypatch):
    monkeypatch.setattr(settings, "HTTP_MAX_REDIRECTS", 2)
    counter = {"hops": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["hops"] += 1
        return httpx.Response(302, headers={"Location": f"/hop{counter['hops']}"}, request=request)

    service = _service(handler)

    with pytest.raises(SourceError, match="Too many redirects"):
        await service.get_text("https://example.test/start", source_key="test_source")

    # initial + 2 hops = 3 requests for max_redirects=2
    assert counter["hops"] == 3


@pytest.mark.asyncio
async def test_declared_content_length_over_limit_rejected_before_body_read(monkeypatch):
    monkeypatch.setattr(settings, "HTTP_HTML_RESPONSE_MAX_BYTES", 1024)
    stream = TrackingStream([b"x" * 2048])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=stream,
            headers={"content-length": "2048"},
            request=request,
        )

    service = _service(handler)

    with pytest.raises(SourceError, match="Content-Length"):
        await service.get_text("https://example.test/big", source_key="test_source")

    # The declared size is rejected before any body bytes are read.
    assert stream.iterated_chunks == 0


@pytest.mark.asyncio
async def test_streamed_body_over_limit_stops_early(monkeypatch):
    monkeypatch.setattr(settings, "HTTP_HTML_RESPONSE_MAX_BYTES", 1024)
    stream = TrackingStream([b"z" * 512] * 5)  # 2560 bytes total

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, request=request)

    service = _service(handler)

    with pytest.raises(SourceError, match="size limit"):
        await service.get_text("https://example.test/stream", source_key="test_source")

    # 512 + 512 = 1024 fits; the third chunk crosses the limit and stops the read.
    assert stream.iterated_chunks == 3


@pytest.mark.asyncio
async def test_per_kind_limits_enforced(monkeypatch):
    monkeypatch.setattr(settings, "HTTP_API_RESPONSE_MAX_BYTES", 2048)
    monkeypatch.setattr(settings, "HTTP_HTML_RESPONSE_MAX_BYTES", 4096)
    monkeypatch.setattr(settings, "HTTP_ASSET_RESPONSE_MAX_BYTES", 8192)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"b" * 5000, request=request)

    service = _service(handler)

    # 5000 > api limit of 2048
    with pytest.raises(SourceError, match=r"api limit"):
        await service.get_text("https://example.test/api", source_key="test_source", kind="api")
    # 5000 > html limit of 4096
    with pytest.raises(SourceError, match=r"html limit"):
        await service.get_text("https://example.test/page", source_key="test_source", kind="html")
    # 5000 < asset limit of 8192
    result = await service.get_bytes("https://example.test/img", source_key="test_source")
    assert result.body == b"b" * 5000


@pytest.mark.asyncio
async def test_retry_after_seconds_honored(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "60"}, request=request)
        return httpx.Response(200, text="recovered", request=request)

    service = _service(handler)
    result = await service.get_text("https://example.test/rate", source_key="test_source")

    assert result.text == "recovered"
    assert delays == [60.0]


@pytest.mark.asyncio
async def test_retry_after_seconds_bounded_by_config(monkeypatch):
    monkeypatch.setattr(settings, "HTTP_RETRY_AFTER_MAX_SECONDS", 120)
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503, headers={"Retry-After": "5000"}, request=request)
        return httpx.Response(200, text="recovered", request=request)

    service = _service(handler)
    result = await service.get_text("https://example.test/rate", source_key="test_source")

    assert result.text == "recovered"
    assert delays == [120.0]


@pytest.mark.asyncio
async def test_retry_after_http_date_honored(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    retry_date = format_datetime(datetime.now(UTC) + timedelta(seconds=10), usegmt=True)
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": retry_date}, request=request)
        return httpx.Response(200, text="recovered", request=request)

    service = _service(handler)
    result = await service.get_text("https://example.test/date", source_key="test_source")

    assert result.text == "recovered"
    assert 8 <= delays[0] <= 12


@pytest.mark.asyncio
async def test_aclose_closes_every_pooled_client_exactly_once():
    closed: list[int] = []

    class TrackingClient:
        def __init__(self, inner: httpx.AsyncClient) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        async def aclose(self) -> None:
            closed.append(1)
            await self._inner.aclose()

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        inner = create_async_client(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text="ok", request=req)),
            **kwargs,
        )
        return TrackingClient(inner)  # type: ignore[return-value]

    service = FetchService(
        client_factory=factory,
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )

    await service.get_text("https://example.test/a", source_key="test_source")
    await service.get_text("https://example.test/b", source_key="test_source", profile="r18")

    await service.aclose()
    assert len(closed) == 2

    # A second close is a no-op: the pool was cleared.
    await service.aclose()
    assert len(closed) == 2


@pytest.fixture
def redirect_service():
    """FetchService with a RecordingThrottle and an InMemoryFetchCache,
    plus a transport that records request headers on each hop."""
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://cdn.test/next"}, request=request)
        return httpx.Response(200, text="destination", request=request)

    service = FetchService(
        client_factory=lambda **kwargs: create_async_client(transport=httpx.MockTransport(handler), **kwargs),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )
    # Attach the recorded_requests list so tests can inspect headers.
    service._recorded_requests = recorded_requests  # type: ignore[attr-defined]
    return service


def _headers_lower(request: httpx.Request) -> dict[str, str]:
    return {k.lower(): v for k, v in request.headers.items()}


@pytest.mark.asyncio
async def test_cross_origin_redirect_strips_authorization_header(redirect_service):
    """Section 11: Authorization must be stripped on cross-origin redirect."""
    service = redirect_service
    await service.get_text(
        "https://example.test/start",
        source_key="test_source",
        headers={"Authorization": "Bearer secret-token"},
    )

    recorded = service._recorded_requests
    assert len(recorded) == 2  # start + redirect
    # First request has Authorization
    assert "authorization" in _headers_lower(recorded[0])
    # Second (cross-origin) request must NOT have Authorization
    assert "authorization" not in _headers_lower(recorded[1])


@pytest.mark.asyncio
async def test_cross_origin_redirect_strips_cookie_and_validators(redirect_service):
    """Section 11: Cookie, If-None-Match, If-Modified-Since stripped on cross-origin."""
    service = redirect_service
    await service.get_text(
        "https://example.test/start",
        source_key="test_source",
        headers={
            "Cookie": "session=abc",
            "If-None-Match": '"abc123"',
            "If-Modified-Since": "Wed, 21 Oct 2026 07:28:00 GMT",
        },
    )

    recorded = service._recorded_requests
    assert len(recorded) == 2
    # First request has sensitive headers
    h0 = _headers_lower(recorded[0])
    assert "cookie" in h0
    assert "if-none-match" in h0
    assert "if-modified-since" in h0
    # Second (cross-origin) request must NOT have them
    h1 = _headers_lower(recorded[1])
    assert "cookie" not in h1
    assert "if-none-match" not in h1
    assert "if-modified-since" not in h1


@pytest.mark.asyncio
async def test_cross_origin_redirect_strips_referer(redirect_service):
    """Section 11: Referer is origin-specific; dropped on cross-origin redirect."""
    service = redirect_service
    await service.get_text(
        "https://example.test/start",
        source_key="test_source",
        headers={"Referer": "https://example.test/referer"},
    )

    recorded = service._recorded_requests
    assert len(recorded) == 2
    # First request has Referer
    assert "referer" in _headers_lower(recorded[0])
    # Second (cross-origin) must NOT have Referer
    assert "referer" not in _headers_lower(recorded[1])


@pytest.mark.asyncio
async def test_same_origin_redirect_preserves_headers_and_updates_referer(redirect_service):
    """Same-origin redirect keeps safe headers and updates Referer to previous URL."""
    # Modify handler for same-origin redirect
    recorded_requests: list[httpx.Request] = []

    def same_origin_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/next"}, request=request)
        return httpx.Response(200, text="destination", request=request)

    service = FetchService(
        client_factory=lambda **kwargs: create_async_client(
            transport=httpx.MockTransport(same_origin_handler), **kwargs
        ),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )

    await service.get_text(
        "https://example.test/start",
        source_key="test_source",
        headers={
            "Authorization": "Bearer token",
            "Referer": "https://example.test/original",
        },
    )

    assert len(recorded_requests) == 2
    # Same-origin: Authorization should be preserved
    assert "authorization" in _headers_lower(recorded_requests[1])
    # Referer should be updated to the previous URL
    h1 = _headers_lower(recorded_requests[1])
    assert h1["referer"] == "https://example.test/start"


@pytest.mark.asyncio
async def test_throttle_receives_per_hop_url(redirect_service):
    """Section 11: throttle.before_request called for every redirect hop."""
    service = redirect_service
    throttle = service._throttle
    assert isinstance(throttle, RecordingThrottle)

    await service.get_text("https://example.test/start", source_key="test_source")

    # Two hops: start -> cdn.test
    urls = throttle.urls
    assert len(urls) == 2
    assert urls[0] == "https://example.test/start"
    assert urls[1] == "https://cdn.test/next"
