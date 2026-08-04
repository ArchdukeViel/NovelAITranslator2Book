"""Syosetu official metadata API client (DEBT-API-01).

Regular novels: ``https://api.syosetu.com/novelapi/api/``
Adult (R18) novels: ``https://api.syosetu.com/novel18api/api/``

The API returns structured metadata (title, author, genre, keywords,
dates, status) but never the synopsis or the chapter list, so HTML
scraping remains authoritative for chapters, synopsis, and body text.
The API is an enrichment layer with a hard fallback: any API failure or
empty result falls back to HTML-only metadata instead of raising.

Timestamps arrive in Asia/Tokyo (``YYYY-MM-DD HH:MM:SS``) and are
converted to UTC ISO-8601. JST has no daylight saving, so a fixed UTC+9
offset is used (no tzdata dependency on Windows).
"""

from __future__ import annotations

import json
import logging
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

# ``of`` field list: only fields the metadata enrichment consumes.
OF_FIELDS = "title,writer,biggenre,genre,keywords,general_firstup,general_lastup,novel_type,end,isstop,novelupdated_at"

# Numeric API genre codes (genre = fine-grained, biggenre = top level).
# Only unambiguous codes are mapped; unknown codes stay unmapped.
SYOSETU_BIGGENRE_CODES: dict[str, str] = {
    "1": "恋愛",
    "2": "ファンタジー",
    "3": "文芸",
    "4": "SF",
    "98": "ノンジャンル",
    "99": "その他",
}

SYOSETU_GENRE_CODES: dict[str, str] = {
    "101": "異世界転生",
    "102": "異世界転移",
    "201": "現代ファンタジー",
    "301": "ハイファンタジー",
    "302": "ローファンタジー",
    "401": "SF",
    "402": "パニック",
    "9901": "恋愛",
    "9902": "ホラー",
    "9903": "ミステリー",
    "9904": "アクション",
    "9905": "コメディ",
    "9906": "ドラマ",
    "9907": "日常",
    "9908": "歴史",
    "9909": "詩",
    "9910": "エッセイ",
}


class SyosetuApiError(Exception):
    """Raised when the Syosetu API response cannot be interpreted.

    Callers must treat this as advisory: HTML fallback is always safe.
    """


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


def parse_novel_entry(raw: dict[str, Any], *, genre_map: dict[str, str]) -> dict[str, Any]:
    """Map a raw API entry to unified metadata fields.

    Returns a dict with only fields the API can provide; callers merge it
    over HTML-derived metadata. The ``api_warnings`` list is included so
    anomalies (unexpected allcount) surface in the final metadata.
    """
    entry: dict[str, Any] = {
        "api_allcount": _parse_int(raw.get("allcount")),
    }
    warnings: list[str] = []

    title = raw.get("title")
    if isinstance(title, str) and title.strip():
        entry["title"] = title.strip()
    writer = raw.get("writer")
    if isinstance(writer, str) and writer.strip():
        entry["author"] = writer.strip()

    keywords_raw = raw.get("keywords")
    if isinstance(keywords_raw, str) and keywords_raw.strip():
        keywords = normalize_keywords(keywords_raw)
        if keywords:
            entry["source_keywords"] = keywords

    # Genre: prefer the fine-grained code, fall back to biggenre.
    genre_name: str | None = None
    genre_code = raw.get("genre")
    if isinstance(genre_code, str) and genre_code in SYOSETU_GENRE_CODES:
        genre_name = SYOSETU_GENRE_CODES[genre_code]
    if genre_name is None:
        biggenre_code = raw.get("biggenre")
        if isinstance(biggenre_code, str) and biggenre_code in SYOSETU_BIGGENRE_CODES:
            genre_name = SYOSETU_BIGGENRE_CODES[biggenre_code]
    if genre_name is not None:
        entry["source_genre_name"] = genre_name
        slug = map_genre(genre_name, genre_map)
        if slug is not None:
            entry["genre_slug"] = slug

    # Dates: JST → UTC.
    first_up = _jst_to_utc_iso(raw.get("general_firstup"))
    last_up = _jst_to_utc_iso(raw.get("general_lastup"))
    novel_updated_at = _jst_to_utc_iso(raw.get("novelupdated_at"))
    if first_up is not None:
        entry["published_at"] = first_up
    if last_up is not None:
        entry["updated_at"] = last_up
    if novel_updated_at is not None:
        entry["api_novel_updated_at"] = novel_updated_at

    # Publication status from explicit flags (authoritative over text):
    # ``end`` = completed flag, ``isstop`` = update-suspended flag.
    end_flag = raw.get("end")
    isstop_flag = raw.get("isstop")
    if end_flag == "1" or end_flag == 1:
        status_payload = publication_status_payload("完結済")
    elif isstop_flag == "1" or isstop_flag == 1:
        status_payload = publication_status_payload("休載")
    else:
        status_payload = publication_status_payload("連載中")
    entry.update(status_payload)

    # A single-ncode query must return exactly one entry; anything else
    # means the response does not describe this novel.
    allcount = _parse_int(raw.get("allcount"))
    if allcount is not None and allcount != 1:
        warnings.append(f"api_allcount_mismatch:{allcount}")

    if warnings:
        entry["api_warnings"] = warnings
    return entry


class SyosetuNovelApi:
    """Client for the official Syosetu / Novel18 metadata API."""

    def __init__(
        self,
        fetch_service: FetchService | None = None,
        *,
        api_path: str = REGULAR_API_PATH,
        profile: str = PROFILE_SYOSETU_API,
        genre_map: dict[str, str] = SYOSETU_GENRE_MAP,
    ) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()
        self._api_path = api_path
        self._profile = profile
        self._genre_map = genre_map

    def api_url(self, ncode: str) -> str:
        return f"{API_HOST}{self._api_path}?ncode={ncode.strip().lower()}&of={OF_FIELDS}&out=json"

    async def fetch_novel(self, ncode: str) -> dict[str, Any] | None:
        """Fetch one novel's metadata.

        Returns the parsed, mapped entry dict or ``None`` when the API has
        no entry for this ncode. Raises :class:`SyosetuApiError` only for
        unparseable responses; network failures surface as
        :class:`~novelai.core.errors.SourceError` from the fetch layer.
        """
        url = self.api_url(ncode)
        result = await self._fetch_service.get_text(
            url,
            source_key="syosetu_api",
            profile=self._profile,
        )
        try:
            payload = json.loads(result.text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SyosetuApiError(f"Syosetu API returned invalid JSON for {ncode}") from exc

        allcount = _parse_int(payload.get("allcount"))
        titles = payload.get("title")
        if allcount in (None, 0) or not isinstance(titles, list) or not titles:
            return None
        raw_entry = titles[0]
        if not isinstance(raw_entry, dict):
            raise SyosetuApiError(f"Syosetu API entry is not an object for {ncode}")
        return parse_novel_entry(raw_entry, genre_map=self._genre_map)

    async def fetch_novel_or_none(self, ncode: str) -> dict[str, Any] | None:
        """Advisory wrapper: never raises; returns None on any failure."""
        try:
            return await self.fetch_novel(ncode)
        except Exception as exc:  # advisory by contract
            logger.warning("Syosetu API fetch failed for %s: %s", ncode, exc)
            return None


class Novel18NovelApi(SyosetuNovelApi):
    """Client for the official Novel18 metadata API (adult profile)."""

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        super().__init__(
            fetch_service,
            api_path=R18_API_PATH,
            profile=PROFILE_NOVEL18_API,
            genre_map=NOVEL18_GENRE_MAP,
        )
