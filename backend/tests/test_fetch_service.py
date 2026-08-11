from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from novelai.core.errors import SourceError
from novelai.infrastructure.http.cache import InMemoryFetchCache, LRUFetchCache
from novelai.infrastructure.http.client import create_async_client
from novelai.infrastructure.http.fetch_service import FetchResult, FetchService
from novelai.infrastructure.http.throttle import DomainThrottle
from novelai.sources.generic import GenericSource
from novelai.sources.kakuyomu import KakuyomuSource
from novelai.sources.syosetu_ncode import SyosetuNcodeSource


class RecordingThrottle(DomainThrottle):
    def __init__(self) -> None:
        super().__init__(min_delay_seconds=0.0)
        self.before_urls: list[str] = []
        self.after_statuses: list[tuple[str, int]] = []

    async def before_request(self, url: str) -> None:
        self.before_urls.append(url)

    async def after_response(self, url: str, status_code: int) -> None:
        self.after_statuses.append((url, status_code))


def _client_factory(transport: httpx.AsyncBaseTransport):
    def factory(**kwargs: Any) -> httpx.AsyncClient:
        return create_async_client(transport=transport, **kwargs)

    return factory


@pytest.mark.asyncio
async def test_fetch_service_successful_text_response_uses_shared_client():
    seen_headers: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(dict(request.headers))
        return httpx.Response(
            200,
            text="hello",
            headers={"ETag": '"v1"', "Content-Type": "text/plain"},
            request=request,
        )

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )

    result = await service.get_text("https://example.test/page", source_key="test_source")

    assert result.requested_url == "https://example.test/page"
    assert result.final_url == "https://example.test/page"
    assert result.status_code == 200
    assert result.text == "hello"
    assert result.body == b"hello"
    assert result.source_key == "test_source"
    assert result.from_cache is False
    assert "NovelAI" in seen_headers["user-agent"]


@pytest.mark.asyncio
async def test_fetch_service_rejects_unsafe_url_before_http_call():
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text="should not happen", request=request)

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )

    with pytest.raises(SourceError):
        await service.get_text("http://127.0.0.1/private", source_key="test_source")

    assert called is False


@pytest.mark.asyncio
async def test_fetch_service_calls_throttle_hooks():
    throttle = RecordingThrottle()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok", request=request)

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=throttle,
        cache=InMemoryFetchCache(),
    )

    await service.get_text("https://example.test/throttle", source_key="test_source")

    assert throttle.before_urls == ["https://example.test/throttle"]
    assert throttle.after_statuses == [("https://example.test/throttle", 200)]


@pytest.mark.asyncio
async def test_fetch_service_uses_conditional_cache_on_304():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, text="cached body", headers={"ETag": '"v1"'}, request=request)
        assert request.headers["if-none-match"] == '"v1"'
        return httpx.Response(304, headers={"ETag": '"v1"'}, request=request)

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )

    first = await service.get_text("https://example.test/cache", source_key="test_source")
    second = await service.get_text("https://example.test/cache", source_key="test_source")

    assert first.from_cache is False
    assert second.from_cache is True
    assert second.status_code == 304
    assert second.text == "cached body"
    assert second.body == b"cached body"


@pytest.mark.asyncio
async def test_fetch_service_pools_client_per_profile():
    created: list[str] = []

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        created.append(str(kwargs))
        return httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, text="ok", request=req)))

    service = FetchService(
        client_factory=factory,
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )

    await service.get_text("https://example.test/a", source_key="test_source")
    await service.get_text("https://example.test/b", source_key="test_source")
    await service.get_text("https://example.test/c", source_key="test_source", profile="r18")

    # One client per profile; sequential requests reuse the pooled client.
    assert len(created) == 2


@pytest.mark.asyncio
async def test_fetch_service_profiles_do_not_share_cache_entries():
    seen_profiles: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_profiles.append(request.headers.get("x-profile", ""))
        return httpx.Response(200, text="body", request=request)

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=RecordingThrottle(),
        cache=LRUFetchCache(max_bytes=None),
    )

    await service.get_text("https://example.test/page", source_key="test_source", profile="regular")
    await service.get_text("https://example.test/page", source_key="test_source", profile="r18")
    # Identical URL under a different profile is a cache miss (no collision).
    await service.get_text("https://example.test/page", source_key="test_source", profile="regular")

    assert seen_profiles == ["", "", ""]
    stats = service.cache_stats()
    assert stats["size"] == 2
    assert stats["hits"] == 1
    assert stats["misses"] == 2


@pytest.mark.asyncio
async def test_fetch_service_asset_fetches_use_asset_kind_entries():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"}, request=request)

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=RecordingThrottle(),
        cache=LRUFetchCache(max_bytes=None),
    )

    result = await service.get_bytes(
        "https://example.test/img.png", source_key="test_source", referer="https://example.test/page"
    )

    assert result.body == b"\x89PNG"
    # Kind-aware TTL: the asset entry uses the asset TTL budget.
    stats = service.cache_stats()
    assert stats["size"] == 1


class FakeFetchService(FetchService):
    def __init__(self, html: str) -> None:
        self.html = html
        self.body = html.encode("utf-8")
        self.calls: list[dict[str, Any]] = []

    async def get_text(
        self,
        url: str,
        *,
        source_key: str,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: Any = None,
        on_retry: Any = None,
        profile: str | None = None,
        kind: str = "html",
    ) -> FetchResult:
        self.calls.append(
            {
                "url": url,
                "source_key": source_key,
                "referer": referer,
                "headers": headers,
                "cookies": cookies,
                "profile": profile,
                "kind": kind,
            }
        )
        return FetchResult(
            requested_url=url,
            final_url=url,
            status_code=200,
            headers={"content-type": "text/html"},
            text=self.html,
            body=self.body,
            source_key=source_key,
            fetched_at="2026-06-04T00:00:00Z",
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
        self.calls.append(
            {
                "url": url,
                "source_key": source_key,
                "referer": referer,
                "headers": headers,
                "cookies": cookies,
                "profile": profile,
                "kind": kind,
            }
        )
        return FetchResult(
            requested_url=url,
            final_url=url,
            status_code=200,
            headers={"content-type": "image/png"},
            text=self.html,
            body=self.body,
            source_key=source_key,
            fetched_at="2026-06-04T00:00:00Z",
        )


@pytest.mark.asyncio
async def test_syosetu_adapter_uses_fetch_service():
    html = """
    <html>
      <h1 class="novel_title">Test Novel</h1>
      <div id="novel_ex">Synopsis</div>
      <div class="novel_sublist2"><a href="/n1234ab/1/">Chapter One</a></div>
    </html>
    """
    fake_fetch = FakeFetchService(html)
    source = SyosetuNcodeSource(fetch_service=fake_fetch)

    metadata = await source.fetch_metadata("https://ncode.syosetu.com/n1234ab/")

    assert metadata["title"] == "Test Novel"
    assert metadata["source_key"] == "syosetu_ncode"
    assert metadata["chapters"][0]["url"] == "https://ncode.syosetu.com/n1234ab/1/"
    # First call is official Syosetu API fetch attempt, followed by HTML page fetch
    assert any(c["source_key"] == "syosetu_ncode" for c in fake_fetch.calls)


@pytest.mark.asyncio
async def test_kakuyomu_adapter_uses_fetch_service():
    html = """
    <html>
      <h1 class="widget-workTitle">Kakuyomu Work</h1>
      <a class="widget-toc-episode-episodeTitle" href="/works/16818093000000000000/episodes/16818093000000000001">Episode One</a>
    </html>
    """
    fake_fetch = FakeFetchService(html)
    source = KakuyomuSource(fetch_service=fake_fetch)

    metadata = await source.fetch_metadata("https://kakuyomu.jp/works/16818093000000000000/")

    assert metadata["title"] == "Kakuyomu Work"
    assert metadata["source_key"] == "kakuyomu"
    assert metadata["chapters"][0]["source_episode_id"] == "16818093000000000001"
    assert fake_fetch.calls[0]["source_key"] == "kakuyomu"


@pytest.mark.asyncio
async def test_kakuyomu_asset_fetch_uses_fetch_service():
    fake_fetch = FakeFetchService("")
    fake_fetch.body = b"image-bytes"
    source = KakuyomuSource(fetch_service=fake_fetch)

    asset = await source.fetch_asset(
        "https://kakuyomu.jp/images/scene.png",
        referer="https://kakuyomu.jp/works/16818093000000000000/",
    )

    assert asset["content"] == b"image-bytes"
    assert asset["content_type"] == "image/png"
    assert fake_fetch.calls[0]["referer"] == "https://kakuyomu.jp/works/16818093000000000000/"


@pytest.mark.asyncio
async def test_generic_adapter_uses_fetch_service():
    html = """
    <html>
      <head><title>Generic Novel</title></head>
      <body>
        <main>
          <a href="/novel/chapter-1">Chapter 1</a>
          <a href="/novel/chapter-2">Chapter 2</a>
        </main>
      </body>
    </html>
    """
    fake_fetch = FakeFetchService(html)
    source = GenericSource(fetch_service=fake_fetch)

    metadata = await source.fetch_metadata("https://example.com/novel")

    assert metadata["title"] == "Generic Novel"
    assert metadata["source_key"] == "generic"
    assert [chapter["url"] for chapter in metadata["chapters"]] == [
        "https://example.com/novel/chapter-1",
        "https://example.com/novel/chapter-2",
    ]
    assert fake_fetch.calls[0]["source_key"] == "generic"


@pytest.mark.asyncio
async def test_source_adapter_unsafe_url_rejected_through_fetch_service():
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text="should not happen", request=request)

    service = FetchService(
        client_factory=_client_factory(httpx.MockTransport(handler)),
        throttle=RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )
    source = GenericSource(fetch_service=service)

    with pytest.raises(SourceError):
        await source.fetch_metadata("http://127.0.0.1/private")

    assert called is False
