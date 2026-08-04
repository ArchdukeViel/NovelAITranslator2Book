import httpx
import pytest

from novelai.infrastructure.http.fetch_service import FetchService
from novelai.infrastructure.http.profiles import PROFILE_NOVEL18_API
from novelai.sources.syosetu_api import (
    Novel18NovelApi,
    SyosetuApiError,
    SyosetuNovelApi,
    _jst_to_utc_iso,
    parse_novel_entry,
)
from novelai.sources.taxonomy import NOVEL18_GENRE_MAP, SYOSETU_GENRE_MAP


def _make_client_factory(transport: httpx.AsyncBaseTransport):
    def factory(*args, **kwargs) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport)

    return factory


def test_jst_to_utc_iso_converts_correctly():
    assert _jst_to_utc_iso("2024-01-01 18:00:00") == "2024-01-01T09:00:00Z"
    assert _jst_to_utc_iso("2024-01-01 00:00:00") == "2023-12-31T15:00:00Z"
    assert _jst_to_utc_iso(None) is None
    assert _jst_to_utc_iso("invalid date") is None


def test_parse_novel_entry_maps_regular_genre_and_status():
    raw = {
        "ncode": "n1234ab",
        "title": " 魔法使いの旅 ",
        "writer": " 作者名 ",
        "keyword": " 魔法 冒険 異世界 ",
        "genre": 101,
        "general_firstup": "2023-05-10 12:00:00",
        "general_lastup": "2024-02-01 15:30:00",
        "novelupdated_at": "2024-02-01 15:30:00",
        "end": 0,
        "isstop": 0,
        "general_all_no": 12,
        "length": 50000,
    }
    entry, typed_meta = parse_novel_entry(raw, genre_map=SYOSETU_GENRE_MAP)
    assert entry["title"] == "魔法使いの旅"
    assert entry["author"] == "作者名"
    assert entry["source_keywords"] == ["魔法", "冒険", "異世界"]
    assert entry["source_genre_name"] == "異世界〔恋愛〕"
    assert entry["published_at"] == "2023-05-10T03:00:00Z"
    assert entry["updated_at"] == "2024-02-01T06:30:00Z"
    assert entry["publication_status"] == "completed"
    assert entry["status"] == "completed"
    assert entry["source_publication_status"] == "完結済"
    assert typed_meta.ncode == "n1234ab"
    assert typed_meta.episode_count == 12
    assert typed_meta.content_length == 50000


def test_parse_novel_entry_maps_adult_genre():
    raw = {
        "ncode": "n9999zz",
        "title": "Adult Tale",
        "nocgenre": 1,
        "end": 1,
        "isstop": 0,
    }
    entry, typed_meta = parse_novel_entry(raw, source_key="novel18_syosetu", genre_map=NOVEL18_GENRE_MAP)
    assert entry["source_genre_name"] == "男性向け（ノクターンノベルズ）"
    assert entry["publication_status"] == "ongoing"
    assert typed_meta.age_restricted is True


@pytest.mark.asyncio
async def test_syosetu_novel_api_fetches_and_parses():
    payload = [
        {"allcount": 1},
        {
            "ncode": "n1234ab",
            "title": "API Novel",
            "writer": "Author",
            "genre": 201,
            "biggenre": 2,
            "general_firstup": "2024-01-01 00:00:00",
            "end": 1,
            "isstop": 0,
            "general_all_no": 5,
        },
    ]

    seen_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    service = FetchService(client_factory=_make_client_factory(httpx.MockTransport(handler)))
    api = SyosetuNovelApi(service)

    res = await api.fetch_novel("n1234ab")
    assert res is not None
    entry, typed_meta = res
    assert entry["title"] == "API Novel"
    assert entry["author"] == "Author"
    assert typed_meta.ncode == "n1234ab"
    assert seen_requests[0].url.host == "api.syosetu.com"
    assert "/novelapi/api/" in seen_requests[0].url.path
    assert "ncode=n1234ab" in seen_requests[0].url.query.decode("utf-8")


@pytest.mark.asyncio
async def test_novel18_api_uses_correct_profile_and_path():
    payload = [
        {"allcount": 1},
        {
            "ncode": "n9999zz",
            "title": "Adult API Novel",
            "writer": "Adult Author",
            "nocgenre": 1,
            "end": 1,
        },
    ]

    seen_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    service = FetchService(client_factory=_make_client_factory(httpx.MockTransport(handler)))
    api = Novel18NovelApi(service)

    res = await api.fetch_novel("n9999zz")
    assert res is not None
    entry, typed_meta = res
    assert entry["title"] == "Adult API Novel"
    assert typed_meta.age_restricted is True
    assert seen_requests[0].url.host == "api.syosetu.com"
    assert "/novel18api/api/" in seen_requests[0].url.path
    assert api._profile == PROFILE_NOVEL18_API


@pytest.mark.asyncio
async def test_syosetu_novel_api_returns_none_on_empty_allcount():
    payload = [{"allcount": 0}]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    service = FetchService(client_factory=_make_client_factory(httpx.MockTransport(handler)))
    api = SyosetuNovelApi(service)

    entry = await api.fetch_novel("n000000")
    assert entry is None


@pytest.mark.asyncio
async def test_syosetu_novel_api_raises_error_on_bad_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json", request=request)

    service = FetchService(client_factory=_make_client_factory(httpx.MockTransport(handler)))
    api = SyosetuNovelApi(service)

    with pytest.raises(SyosetuApiError, match="invalid JSON"):
        await api.fetch_novel("n1234ab")


@pytest.mark.asyncio
async def test_fetch_novel_or_none_swallows_exception_and_logs():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error", request=request)

    service = FetchService(client_factory=_make_client_factory(httpx.MockTransport(handler)))
    api = SyosetuNovelApi(service)

    # get_text will raise SourceError on 500 status from fetcher layer
    entry = await api.fetch_novel_or_none("n1234ab")
    assert entry is None
