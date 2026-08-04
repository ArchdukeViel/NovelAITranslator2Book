"""Syosetu official metadata API client (DEBT-API-01).

Regular novels: ``https://api.syosetu.com/novelapi/api/``
Adult (R18) novels: ``https://api.syosetu.com/novel18api/api/``

The Syosetu API returns a JSON array:
- Element 0: ``{"allcount": int}``
- Elements 1..N: novel records.

The API provides rich metadata, but HTML scraping remains authoritative for
chapters, synopsis, and body text. The API is an enrichment layer with a hard fallback:
any API failure or empty result falls back to HTML-only metadata.

Timestamps arrive in Asia/Tokyo (``YYYY-MM-DD HH:MM:SS``) and are
converted to UTC ISO-8601. JST has no daylight saving, so a fixed UTC+9
offset is used.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from novelai.infrastructure.http.fetch_service import FetchService, get_default_fetch_service
from novelai.infrastructure.http.profiles import PROFILE_NOVEL18_API, PROFILE_SYOSETU_API
from novelai.sources.status import publication_status_payload
from novelai.sources.taxonomy import (
    NOVEL18_GENRE_MAP,
    SYOSETU_GENRE_MAP,
    map_genre,
    normalize_keywords,
)

logger = logging.getLogger(__name__)

API_HOST = "https://api.syosetu.com"
REGULAR_API_PATH = "/novelapi/api/"
R18_API_PATH = "/novel18api/api/"

_JST = timezone(timedelta(hours=9))

# Standard 'of' parameter fields requested from Syosetu API
OF_FIELDS = "t-n-u-w-s-bg-g-k-gf-gl-nt-e-ga-l-ti-i-r15-bl-gl-z-t-tn-p-gp-dp-wp-mp-qp-yp-f-imp-r-a-ah-sa-ka-nu-ua-nc"

# Documented Syosetu Biggenre & Genre mappings
SYOSETU_BIGGENRE_CODES: dict[int, str] = {
    1: "恋愛",
    2: "ファンタジー",
    3: "文芸",
    4: "SF",
    98: "ノンジャンル",
    99: "その他",
}

SYOSETU_GENRE_CODES: dict[int, str] = {
    101: "異世界〔恋愛〕",
    102: "現実世界〔恋愛〕",
    201: "ハイファンタジー〔ファンタジー〕",
    202: "ローファンタジー〔ファンタジー〕",
    301: "純文学〔文芸〕",
    302: "ヒューマンドラマ〔文芸〕",
    303: "歴史〔文芸〕",
    304: "推理〔文芸〕",
    305: "ホラー〔文芸〕",
    306: "アクション〔文芸〕",
    307: "コメディー〔文芸〕",
    401: "VRゲーム〔SF〕",
    402: "宇宙〔SF〕",
    403: "空想科学〔SF〕",
    404: "パニック〔SF〕",
    9901: "童話〔その他〕",
    9902: "詩〔その他〕",
    9903: "エッセイ〔その他〕",
    9904: "リプレイ〔その他〕",
    9999: "その他〔その他〕",
    9801: "ノンジャンル〔ノンジャンル〕",
}

NOCGENRE_CODES: dict[int, str] = {
    1: "男性向け（ノクターンノベルズ）",
    2: "女性向け（ムーンライトノベルズ）",
    3: "大人向け（ミッドナイトノベルズ）",
}


@dataclass(frozen=True)
class SyosetuWorkMetadata:
    source_key: str
    ncode: str
    canonical_url: str

    title: str
    author: str
    synopsis: str | None

    source_biggenre_code: int | None
    source_genre_code: int | None
    source_nocgenre_code: int | None
    source_genre_name: str | None
    source_keywords: tuple[str, ...]

    novel_type: int
    publication_status: str
    is_long_stopped: bool

    episode_count: int
    content_length: int
    estimated_reading_minutes: int | None
    illustration_count: int

    first_published_at: str | None
    last_episode_published_at: str | None
    work_updated_at: str | None
    api_record_updated_at: str | None

    age_restricted: bool
    raw_api_fields: dict[str, Any] = field(default_factory=dict)


class SyosetuApiError(Exception):
    """Raised when the Syosetu API response cannot be interpreted."""


def _jst_to_utc_iso(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    utc = parsed.replace(tzinfo=_JST).astimezone(UTC)
    return utc.isoformat().replace("+00:00", "Z")


def _parse_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def parse_novel_entry(
    raw: dict[str, Any],
    *,
    source_key: str = "syosetu_ncode",
    genre_map: dict[str, str] = SYOSETU_GENRE_MAP,
) -> tuple[dict[str, Any], SyosetuWorkMetadata]:
    """Map a raw API entry to unified metadata dictionary and SyosetuWorkMetadata object."""
    ncode = str(raw.get("ncode", "")).strip().lower()

    title = str(raw.get("title", "")).strip()
    writer = str(raw.get("writer", "")).strip()
    synopsis = str(raw.get("story", "")).strip() or None

    keywords_raw = raw.get("keyword") or raw.get("keywords")
    source_keywords: tuple[str, ...] = ()
    if isinstance(keywords_raw, str) and keywords_raw.strip():
        source_keywords = tuple(normalize_keywords(keywords_raw))

    biggenre_code = _parse_int(raw.get("biggenre"))
    genre_code = _parse_int(raw.get("genre"))
    nocgenre_code = _parse_int(raw.get("nocgenre"))

    genre_name: str | None = None
    if genre_code is not None and genre_code in SYOSETU_GENRE_CODES:
        genre_name = SYOSETU_GENRE_CODES[genre_code]
    elif biggenre_code is not None and biggenre_code in SYOSETU_BIGGENRE_CODES:
        genre_name = SYOSETU_BIGGENRE_CODES[biggenre_code]
    elif nocgenre_code is not None and nocgenre_code in NOCGENRE_CODES:
        genre_name = NOCGENRE_CODES[nocgenre_code]

    genre_slug: str | None = None
    if genre_name is not None:
        genre_slug = map_genre(genre_name, genre_map)

    # Dates: JST -> UTC
    first_up = _jst_to_utc_iso(raw.get("general_firstup"))
    last_up = _jst_to_utc_iso(raw.get("general_lastup"))
    novel_updated_at = _jst_to_utc_iso(raw.get("novelupdated_at"))
    updated_at = _jst_to_utc_iso(raw.get("updated_at"))

    # Publication status from official flags:
    # novel_type: 1 = serialized (連載), 2 = short story (短編)
    # end: 0 = ended/completed (完結済), 1 = ongoing (連載中) for novel_type=1 (Note official Syosetu API: end=0 is completed!)
    # isstop: 1 = update suspended (休載)
    novel_type_raw = _parse_int(raw.get("novel_type")) or 1
    end_flag = _parse_int(raw.get("end"))
    isstop_flag = _parse_int(raw.get("isstop"))

    is_long_stopped = isstop_flag == 1

    if novel_type_raw == 2:
        status_jp = "短編"
    elif end_flag == 0:
        status_jp = "完結済"
    elif is_long_stopped:
        status_jp = "休載"
    else:
        status_jp = "連載中"

    status_payload = publication_status_payload(status_jp)

    episode_count = _parse_int(raw.get("general_all_no")) or (1 if novel_type_raw == 2 else 0)
    content_length = _parse_int(raw.get("length")) or 0
    reading_minutes = _parse_int(raw.get("time"))
    illustration_count = _parse_int(raw.get("sasie_cnt")) or 0

    isr15 = _parse_int(raw.get("isr15")) == 1
    age_restricted = nocgenre_code is not None or isr15 or source_key == "novel18_syosetu"

    canonical_url = (
        f"https://novel18.syosetu.com/{ncode}/"
        if source_key == "novel18_syosetu"
        else f"https://ncode.syosetu.com/{ncode}/"
    )

    typed_metadata = SyosetuWorkMetadata(
        source_key=source_key,
        ncode=ncode,
        canonical_url=canonical_url,
        title=title,
        author=writer,
        synopsis=synopsis,
        source_biggenre_code=biggenre_code,
        source_genre_code=genre_code,
        source_nocgenre_code=nocgenre_code,
        source_genre_name=genre_name,
        source_keywords=source_keywords,
        novel_type=novel_type_raw,
        publication_status=status_payload.get("publication_status", "ongoing"),
        is_long_stopped=is_long_stopped,
        episode_count=episode_count,
        content_length=content_length,
        estimated_reading_minutes=reading_minutes,
        illustration_count=illustration_count,
        first_published_at=first_up,
        last_episode_published_at=last_up,
        work_updated_at=novel_updated_at,
        api_record_updated_at=updated_at,
        age_restricted=age_restricted,
        raw_api_fields=raw,
    )

    entry: dict[str, Any] = {
        "title": title,
        "author": writer,
        "synopsis": synopsis,
        "source_keywords": list(source_keywords),
        "source_genre_name": genre_name,
        "genre_slug": genre_slug,
        "published_at": first_up,
        "updated_at": last_up,
        "api_novel_updated_at": novel_updated_at,
        "api_record_updated_at": updated_at,
        "api_episode_count": episode_count,
        "content_length": content_length,
        "illustration_count": illustration_count,
        "reading_minutes": reading_minutes,
        "is_long_stopped": is_long_stopped,
        "age_restricted": age_restricted,
        **status_payload,
    }

    return entry, typed_metadata


class SyosetuNovelApi:
    """Client for the official Syosetu / Novel18 metadata API."""

    def __init__(
        self,
        fetch_service: FetchService | None = None,
        *,
        api_path: str = REGULAR_API_PATH,
        profile: str = PROFILE_SYOSETU_API,
        source_key: str = "syosetu_ncode",
        genre_map: dict[str, str] = SYOSETU_GENRE_MAP,
    ) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()
        self._api_path = api_path
        self._profile = profile
        self._source_key = source_key
        self._genre_map = genre_map

    def api_url(self, ncode: str) -> str:
        clean_ncode = ncode.strip().lower()
        return f"{API_HOST}{self._api_path}?ncode={clean_ncode}&of={OF_FIELDS}&out=json"

    async def fetch_novel(self, ncode: str) -> tuple[dict[str, Any], SyosetuWorkMetadata] | None:
        """Fetch one novel's metadata.

        Returns tuple of (mapped entry dict, SyosetuWorkMetadata) or None when ncode not found.
        Raises SyosetuApiError for invalid API JSON or shape.
        """
        clean_ncode = ncode.strip().lower()
        url = self.api_url(clean_ncode)
        result = await self._fetch_service.get_text(
            url,
            source_key="syosetu_api",
            profile=self._profile,
        )
        try:
            payload = json.loads(result.text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SyosetuApiError(f"Syosetu API returned invalid JSON for {clean_ncode}") from exc

        if not isinstance(payload, list) or len(payload) == 0:
            raise SyosetuApiError(f"Syosetu API returned non-list response for {clean_ncode}")

        count_header = payload[0]
        if not isinstance(count_header, dict) or "allcount" not in count_header:
            raise SyosetuApiError(f"Syosetu API response missing count header for {clean_ncode}")

        allcount = _parse_int(count_header.get("allcount"))
        if allcount is None or allcount == 0 or len(payload) < 2:
            return None

        raw_entry = payload[1]
        if not isinstance(raw_entry, dict):
            raise SyosetuApiError(f"Syosetu API entry is not an object for {clean_ncode}")

        returned_ncode = str(raw_entry.get("ncode", "")).strip().lower()
        if returned_ncode and returned_ncode != clean_ncode:
            raise SyosetuApiError(
                f"Syosetu API returned mismatched ncode: expected {clean_ncode}, got {returned_ncode}"
            )

        entry, typed_meta = parse_novel_entry(
            raw_entry,
            source_key=self._source_key,
            genre_map=self._genre_map,
        )
        entry["api_allcount"] = allcount
        if allcount > 1:
            entry["api_warnings"] = [f"api_allcount_mismatch:{allcount}"]

        return entry, typed_meta

    async def fetch_novel_or_none(self, ncode: str) -> tuple[dict[str, Any], SyosetuWorkMetadata] | None:
        """Advisory wrapper: never raises; returns None on any failure."""
        try:
            return await self.fetch_novel(ncode)
        except Exception as exc:
            logger.warning("Syosetu API fetch failed for %s: %s", ncode, exc)
            return None


class Novel18NovelApi(SyosetuNovelApi):
    """Client for the official Novel18 metadata API (adult profile)."""

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        super().__init__(
            fetch_service,
            api_path=R18_API_PATH,
            profile=PROFILE_NOVEL18_API,
            source_key="novel18_syosetu",
            genre_map=NOVEL18_GENRE_MAP,
        )
