"""Syosetu source adapter implementation."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.infrastructure.http.fetch_service import FetchService, get_default_fetch_service
from novelai.infrastructure.http.profiles import PROFILE_ASSETS, PROFILE_SYOSETU_HTML
from novelai.sources._helpers import (
    attribute_to_str,
    extract_image_references,
)
from novelai.sources.base import SourceAdapter
from novelai.sources.html_parsers import HTMLParserMixin
from novelai.sources.quality import (
    detect_age_gate_text,
    detect_block_page_text,
)
from novelai.sources.source_layout import normalize_source_blocks
from novelai.sources.status import normalize_publication_status, publication_status_payload
from novelai.sources.syosetu.parser import (
    AFTERWORD_SELECTORS,
    BODY_SELECTORS,
    CHAPTER_ROW_CLASSES,
    NOVEL_ID_PATH_PATTERN,
    NOVEL_ID_PATTERN,
    PART_HEADING_CLASSES,
    PREFACE_SELECTORS,
    PUBLICATION_STATUS_LABEL_MARKERS,
    PUBLICATION_STATUS_VALUE_MARKERS,
    REMOVE_FROM_SECTION_SELECTORS,
    RUBY_REMOVE_SELECTORS,
    SEPARATOR_LINE,
    SOURCE_DATE_PATTERN,
    extract_chapters,
    extract_source_blocks_from_section,
    find_story_body,
    find_story_sections,
    normalize_syosetu_novel_id,
    render_story_section,
)
from novelai.sources.syosetu_api import Novel18NovelApi, SyosetuNovelApi
from novelai.sources.taxonomy import SYOSETU_GENRE_MAP, map_genre, normalize_keywords
from novelai.utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)


class SyosetuNcodeSource(SourceAdapter):
    source_key = "syosetu_ncode"
    """Source adapter for syosetu.com novels (ncode)."""

    NOVEL_ID_PATTERN = NOVEL_ID_PATTERN
    NOVEL_ID_PATH_PATTERN = NOVEL_ID_PATH_PATTERN
    SOURCE_DATE_PATTERN = SOURCE_DATE_PATTERN
    PART_HEADING_CLASSES = PART_HEADING_CLASSES
    CHAPTER_ROW_CLASSES = CHAPTER_ROW_CLASSES
    BODY_SELECTORS = BODY_SELECTORS
    PREFACE_SELECTORS = PREFACE_SELECTORS
    AFTERWORD_SELECTORS = AFTERWORD_SELECTORS
    REMOVE_FROM_SECTION_SELECTORS = REMOVE_FROM_SECTION_SELECTORS
    RUBY_REMOVE_SELECTORS = RUBY_REMOVE_SELECTORS
    SEPARATOR_LINE = SEPARATOR_LINE
    PUBLICATION_STATUS_LABEL_MARKERS = PUBLICATION_STATUS_LABEL_MARKERS
    PUBLICATION_STATUS_VALUE_MARKERS = PUBLICATION_STATUS_VALUE_MARKERS

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()

    def can_handle(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            host = httpx.URL(candidate).host or ""
        except Exception:
            return False

        return host.lower() == "ncode.syosetu.com"

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        return normalize_syosetu_novel_id(identifier_or_url)

    def _normalize_url(self, identifier_or_url: str) -> str:
        novel_id = self.normalize_novel_id(identifier_or_url)
        return f"https://ncode.syosetu.com/{novel_id.strip('/')}/"

    def _infotop_url(self, identifier_or_url: str) -> str:
        root_url = httpx.URL(self._normalize_url(identifier_or_url))
        novel_id = self.normalize_novel_id(identifier_or_url)
        host = root_url.host or "ncode.syosetu.com"
        return f"{root_url.scheme}://{host}/novelview/infotop/ncode/{novel_id.strip('/')}/"

    def _build_request_cookies(self) -> httpx.Cookies | None:
        return None

    def _validate_fetched_page(self, requested_url: str, final_url: httpx.URL, html: str) -> None:
        return None

    def _request_headers(self, *, referer: str | None = None) -> dict[str, str]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if isinstance(referer, str) and referer.strip():
            headers["Referer"] = referer.strip()
        return headers

    @staticmethod
    def _decode_page_response(response: httpx.Response) -> str:
        return response.content.decode("utf-8", errors="replace")

    @staticmethod
    def _decode_page_body(body: bytes) -> str:
        return body.decode("utf-8", errors="replace")

    @property
    def _request_profile(self) -> str:
        return PROFILE_SYOSETU_HTML

    async def _fetch_page(self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None) -> str:
        result = await self._fetch_service.get_text(
            url,
            source_key=self.source_key,
            profile=self._request_profile,
            headers=self._request_headers(),
            cookies=self._build_request_cookies(),
            on_retry=on_retry,
        )
        html = self._decode_page_body(result.body)
        self._validate_fetched_page(url, httpx.URL(result.final_url), html)
        return html

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> dict[str, Any]:
        response = await self._fetch_service.get_bytes(
            url,
            source_key=self.source_key,
            profile=PROFILE_ASSETS,
            referer=referer,
            headers=self._request_headers(referer=referer),
            cookies=self._build_request_cookies(),
        )
        return {
            "url": response.final_url,
            "content": response.body,
            "content_type": response.headers.get("content-type"),
        }

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        selectors = (
            ".p-novel__title",
            "h1.p-novel__title",
            "p.novel_title",
            "h1.novel_title",
        )
        return HTMLParserMixin.extract_title(soup, selectors)

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        selectors = (".p-novel__author", "#novel_writername")
        return HTMLParserMixin.extract_author(soup, selectors)

    def _extract_synopsis(self, soup: BeautifulSoup) -> str | None:
        selectors = (
            ".p-novel__summary",
            "#novel_ex",
            ".novel_ex",
            "meta[name='description']",
            "meta[property='og:description']",
        )
        for selector in selectors:
            node = soup.select_one(selector)
            if not isinstance(node, Tag):
                continue
            content = node.get("content")
            if isinstance(content, str) and content.strip():
                return normalize_text(content)
            text = node.get_text("\n", strip=True)
            if text:
                return normalize_text(text)
        return None

    def _extract_page_numbers(self, soup: BeautifulSoup, url: str) -> list[int]:
        base_url = httpx.URL(url)
        novel_id = self.normalize_novel_id(url)
        page_numbers = {1}

        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag):
                continue
            href = attribute_to_str(anchor.get("href"))
            if href is None:
                continue

            absolute_url = base_url.join(href)
            candidate = httpx.URL(str(absolute_url))
            if self.normalize_novel_id(str(candidate)) != novel_id:
                continue
            if candidate.path.rstrip("/") != f"/{novel_id}":
                continue

            page_number = candidate.params.get("p")
            if page_number and page_number.isdigit():
                page_numbers.add(int(page_number))

        return sorted(page_numbers)

    def _extract_chapters(
        self,
        soup: BeautifulSoup,
        url: str,
        title: str | None,
        *,
        initial_part: str | None = None,
    ) -> list[dict[str, Any]]:
        return extract_chapters(soup, url, title, initial_part=initial_part)

    @staticmethod
    def _apply_chapter_cap(chapters: list[dict[str, Any]], max_chapter: int | None) -> list[dict[str, Any]]:
        if max_chapter is None:
            return chapters
        return [
            chapter
            for chapter in chapters
            if isinstance(chapter.get("num"), int) and int(chapter["num"]) <= max_chapter
        ]

    @staticmethod
    def _last_chapter_part(chapters: Any) -> str | None:
        if not isinstance(chapters, list):
            return None
        for chapter in reversed(chapters):
            if not isinstance(chapter, dict):
                continue
            part = chapter.get("part") or chapter.get("volume") or chapter.get("arc") or chapter.get("section")
            if isinstance(part, str) and part.strip():
                return part.strip()
        return None

    def _find_story_sections(self, soup: BeautifulSoup) -> list[Tag]:
        return find_story_sections(soup)

    def _find_story_body(self, soup: BeautifulSoup) -> Tag | None:
        return find_story_body(soup)

    def _render_story_section(self, section: Tag) -> str:
        return render_story_section(section)

    def _extract_source_blocks_from_section(self, section: Tag) -> list[dict[str, Any]]:
        return extract_source_blocks_from_section(section)

    def _extract_dates(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        date_text = soup.get_text(separator="|", strip=True)
        dates = re.findall(r"\d{4}/\d{2}/\d{2}", date_text)
        published_at = dates[0] if dates else None
        updated_at = dates[-1] if dates else None
        return published_at, updated_at

    @property
    def _genre_map(self) -> dict[str, str]:
        return SYOSETU_GENRE_MAP

    def _extract_source_genre(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        genre_selectors = (
            ".p-novel__meta .p-novel__meta--genre a",
            ".p-novel__meta--genre a",
            "#novel_genre a",
            "#novelgenre a",
        )
        for selector in genre_selectors:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                text = node.get_text(strip=True)
                if text:
                    slug = map_genre(text, self._genre_map)
                    return text, slug

        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag):
                continue
            href = attribute_to_str(anchor.get("href")) or ""
            parsed = urlparse(href)
            if (
                parsed.hostname
                and parsed.hostname.endswith(".syosetu.com")
                and parsed.path
                and parsed.path.startswith("/genre/")
            ):
                text = anchor.get_text(strip=True)
                if text:
                    slug = map_genre(text, self._genre_map)
                    return text, slug

        return None, None

    def _extract_source_keywords(self, soup: BeautifulSoup) -> list[str]:
        keyword_selectors = (
            ".p-novel__meta--keyword a",
            "#novel_keyword a",
            "#novelkeyword a",
            ".novelkeyword_logs",
        )
        keywords: list[str] = []
        for selector in keyword_selectors:
            nodes = soup.select(selector)
            if nodes:
                for node in nodes:
                    if isinstance(node, Tag):
                        text = node.get_text(strip=True)
                        if text:
                            keywords.append(text)
                if keywords:
                    break

        if not keywords:
            for anchor in soup.find_all("a", href=True):
                if not isinstance(anchor, Tag):
                    continue
                href = attribute_to_str(anchor.get("href")) or ""
                parsed = urlparse(href)
                if (
                    parsed.hostname
                    and parsed.hostname.endswith(".syosetu.com")
                    and parsed.path
                    and parsed.path.startswith("/tag/")
                ):
                    text = anchor.get_text(strip=True)
                    if text:
                        keywords.append(text)

        return normalize_keywords(keywords)

    def _extract_publication_status_text(self, soup: BeautifulSoup) -> str | None:
        for row in soup.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
            if len(cells) < 2:
                continue
            label = cells[0]
            value = " ".join(cells[1:]).strip()
            if any(marker in label for marker in self.PUBLICATION_STATUS_LABEL_MARKERS):
                if normalize_publication_status(value) != "unknown":
                    return value

        for container in soup.find_all(["dl", "div", "p", "li", "section"]):
            if not isinstance(container, Tag):
                continue
            text = container.get_text(" ", strip=True)
            if not text or len(text) > 240:
                continue
            if not any(marker in text for marker in self.PUBLICATION_STATUS_LABEL_MARKERS):
                continue
            if normalize_publication_status(text) != "unknown":
                return text

        page_text = soup.get_text(" ", strip=True)
        for marker in self.PUBLICATION_STATUS_VALUE_MARKERS:
            if marker in page_text:
                return marker
        return None

    def _publication_status_payload_from_html(self, html: str, url: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        payload = publication_status_payload(self._extract_publication_status_text(soup))
        payload["source_publication_status_page"] = url
        return payload

    @staticmethod
    def _merge_publication_status(metadata: dict[str, Any], payload: dict[str, str]) -> None:
        incoming_status = payload.get("publication_status")
        current_status = metadata.get("publication_status")
        if incoming_status != "unknown" or current_status in (None, "unknown"):
            metadata.update(payload)

    def _parse_metadata_html(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title = self._extract_title(soup)
        author = self._extract_author(soup)
        synopsis = self._extract_synopsis(soup)
        chapters = self._extract_chapters(soup, url, title)
        published_at, updated_at = self._extract_dates(soup)
        source_genre_name, genre_slug = self._extract_source_genre(soup)
        source_keywords = self._extract_source_keywords(soup)
        status_payload = self._publication_status_payload_from_html(html, url)

        novel_id = self.normalize_novel_id(url)
        return {
            "source_key": self.source_key,
            "source_url": url,
            "source_novel_id": novel_id,
            "novel_id": novel_id,
            "title": title,
            "author": author,
            "synopsis": synopsis,
            "published_at": published_at,
            "updated_at": updated_at,
            "chapters": chapters,
            "source_genre_name": source_genre_name,
            "genre_slug": genre_slug,
            "source_keywords": source_keywords,
            **status_payload,
        }

    def _parse_chapter_payload(self, html: str, url: str) -> dict[str, Any]:
        if detect_age_gate_text(html):
            raise SourceError("Syosetu page appears to be an age gate or auth redirect.")
        if detect_block_page_text(html):
            raise SourceError("Syosetu page appears to be blocked or unavailable.")
        soup = BeautifulSoup(html, "lxml")
        sections = self._find_story_sections(soup)
        if not sections:
            raise SourceError("Unable to find chapter text on Syosetu page")

        images: list[dict[str, Any]] = []
        for section in sections:
            images.extend(extract_image_references(section, base_url=url, start_index=len(images)))
        text = "\n\n".join(
            rendered for rendered in (self._render_story_section(section) for section in sections) if rendered
        )
        text = re.sub(r"\n{3,}", "\n\n", text)
        source_blocks: list[dict[str, Any]] = []
        for index, section in enumerate(sections):
            if index > 0:
                source_blocks.append({"type": "break"})
            source_blocks.extend(self._extract_source_blocks_from_section(section))
        source_blocks = normalize_source_blocks(source_blocks)
        if not text:
            raise SourceError("Chapter text was empty on Syosetu page")
        return {
            "text": text,
            "images": images,
            "source_blocks": source_blocks,
        }

    def _parse_chapter_html(self, html: str, url: str = "https://ncode.syosetu.com/") -> str:
        return str(self._parse_chapter_payload(html, url).get("text", ""))

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        url = self._normalize_url(url)
        novel_id = self.normalize_novel_id(url)

        # 1. Official API integration with HTML fallback provenance
        api_client = (
            Novel18NovelApi(self._fetch_service)
            if self.source_key == "novel18_syosetu"
            else SyosetuNovelApi(self._fetch_service)
        )
        api_result = await api_client.fetch_novel_or_none(novel_id)

        metadata_provenance: dict[str, Any] = {}
        api_entry: dict[str, Any] = {}
        if api_result is not None:
            api_entry, _typed_meta = api_result
            metadata_provenance = {
                "metadata_extraction_mode": "api_plus_html",
                "metadata_api_status": "success",
                "metadata_api_endpoint": "adult" if self.source_key == "novel18_syosetu" else "regular",
                "api_episode_count": api_entry.get("api_episode_count"),
            }
        else:
            metadata_provenance = {
                "metadata_extraction_mode": "html_fallback",
                "metadata_api_status": "failed_or_missing",
                "metadata_api_error_category": "api_miss_or_error",
            }

        # 2. Fetch HTML work page
        html = await self._fetch_page(url, on_retry=None)
        metadata = self._parse_metadata_html(html, url)

        # Merge precedence: API overrides HTML fields where available, preserving HTML-only chapter links/URLs
        for key in (
            "title",
            "author",
            "synopsis",
            "source_keywords",
            "source_genre_name",
            "genre_slug",
            "published_at",
            "updated_at",
            "api_novel_updated_at",
            "api_record_updated_at",
            "publication_status",
            "status",
            "source_publication_status",
            "is_long_stopped",
            "content_length",
            "illustration_count",
        ):
            if key in api_entry and api_entry[key] is not None:
                metadata[key] = api_entry[key]

        metadata.update(metadata_provenance)

        infotop_url = self._infotop_url(url)
        try:
            infotop_html = await self._fetch_page(infotop_url, on_retry=None)
            self._merge_publication_status(
                metadata,
                self._publication_status_payload_from_html(infotop_html, infotop_url),
            )
        except SourceError as exc:
            logger.warning("Failed to fetch infotop page for %s: %s", url, exc)
            metadata["infotop_fetch_failed"] = True
            metadata["infotop_fetch_url"] = infotop_url

        soup = BeautifulSoup(html, "lxml")
        page_numbers = self._extract_page_numbers(soup, url)

        if max_chapter is not None:
            capped_pages: list[int] = []
            for page in page_numbers:
                capped_pages.append(page)
                current_chapters = metadata.get("chapters", [])
                if (
                    current_chapters
                    and max(int(c.get("num", 0)) for c in current_chapters if isinstance(c.get("num"), int))
                    >= max_chapter
                ):
                    break
            page_numbers = capped_pages

        for page in page_numbers[1:]:
            page_url = f"{url.rstrip('/')}/?p={page}"
            page_html = await self._fetch_page(page_url, on_retry=None)
            page_soup = BeautifulSoup(page_html, "lxml")
            page_chapters = self._extract_chapters(
                page_soup,
                url,
                metadata.get("title"),
                initial_part=self._last_chapter_part(metadata.get("chapters")),
            )
            existing_chapters = metadata.get("chapters", [])
            seen_ids = {c["id"] for c in existing_chapters if isinstance(c, dict) and "id" in c}
            for ch in page_chapters:
                if ch["id"] not in seen_ids:
                    existing_chapters.append(ch)
                    seen_ids.add(ch["id"])
            metadata["chapters"] = existing_chapters
            if max_chapter is not None:
                max_num = max((int(c.get("num", 0)) for c in page_chapters if isinstance(c.get("num"), int)), default=0)
                if max_num >= max_chapter:
                    break

        metadata["chapters"] = self._apply_chapter_cap(metadata.get("chapters", []), max_chapter)
        return metadata

    async def fetch_chapter_payload(
        self,
        url: str,
        *,
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> dict[str, Any]:
        html = await self._fetch_page(url, on_retry=on_retry)
        return self._parse_chapter_payload(html, url)

    async def fetch_chapter(self, url: str) -> str:
        return self._parse_chapter_html(await self._fetch_page(url))
