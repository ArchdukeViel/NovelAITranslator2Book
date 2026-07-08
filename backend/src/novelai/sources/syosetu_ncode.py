from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.infrastructure.http.fetch_service import FetchService, get_default_fetch_service
from novelai.sources._helpers import (
    attribute_to_str,
    extract_image_references,
    image_placeholder,
    iter_story_blocks,
)
from novelai.sources.base import SourceAdapter
from novelai.sources.html_parsers import HTMLParserMixin
from novelai.sources.quality import detect_age_gate_text, detect_block_page_text
from novelai.sources.source_layout import normalize_source_blocks, source_blocks_from_text_blocks
from novelai.sources.status import normalize_publication_status, publication_status_payload
from novelai.sources.taxonomy import (
    SYOSETU_GENRE_MAP,
    map_genre,
    normalize_keywords,
)
from novelai.utils.text_normalization import normalize_text


class SyosetuNcodeSource(SourceAdapter):
    """Source adapter for syosetu.com novels (ncode)."""

    NOVEL_ID_PATTERN = re.compile(r"^n\d{4}[a-z]{2}$", re.IGNORECASE)
    NOVEL_ID_PATH_PATTERN = re.compile(r"/(n\d{4}[a-z]{2})(?:/|$)", re.IGNORECASE)
    SOURCE_DATE_PATTERN = re.compile(r"\d{4}/\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2})?")
    PART_HEADING_CLASSES = {
        "chapter_title",
        "p-eplist__chapter-title",
        "p-eplist__volume-title",
        "p-eplist__part-title",
        "p-eplist__group-title",
    }
    CHAPTER_ROW_CLASSES = {
        "novel_sublist2",
        "p-eplist__sublist",
        "p-eplist__episode",
        "p-eplist__item",
    }
    BODY_SELECTORS = (
        "#novel_honbun",
        ".p-novel__text--body",
        ".js-novel-text",
        ".p-novel__body .p-novel__text",
        ".p-novel__body",
        ".p-novel__text",
        ".novel_view",
    )
    PREFACE_SELECTORS = (
        "#novel_p",
        ".p-novel__text--preface",
        ".p-novel__preface",
    )
    AFTERWORD_SELECTORS = (
        "#novel_a",
        ".p-novel__text--afterword",
        ".p-novel__afterword",
    )
    REMOVE_FROM_SECTION_SELECTORS = (
        ".novel_bn",
    )
    RUBY_REMOVE_SELECTORS = ("rt", "rp")
    SEPARATOR_LINE = "-" * 60
    PUBLICATION_STATUS_LABEL_MARKERS = (
        "掲載状態",
        "連載状態",
        "状態",
        "ステータス",
        "作品種別",
        "種別",
    )
    PUBLICATION_STATUS_VALUE_MARKERS = (
        "完結済",
        "連載終了",
        "完結",
        "完了",
        "連載中",
        "更新中",
        "休載",
        "一時停止",
        "停止",
        "中断",
    )

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()

    @property
    def key(self) -> str:
        return "syosetu_ncode"

    def matches_url(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            host = httpx.URL(candidate).host or ""
        except Exception:
            return False

        return host.lower() == "ncode.syosetu.com"

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        candidate = identifier_or_url.strip().rstrip("/")
        if not candidate:
            return candidate

        if self.NOVEL_ID_PATTERN.fullmatch(candidate):
            return candidate.lower()

        if candidate.startswith(("http://", "https://")):
            try:
                parsed_url = httpx.URL(candidate)
            except Exception:
                return candidate
            path = parsed_url.path
            match = self.NOVEL_ID_PATH_PATTERN.search(path)
            if match:
                return match.group(1).lower()
            path_parts = [part for part in path.split("/") if part]
            for part in path_parts:
                if self.NOVEL_ID_PATTERN.fullmatch(part):
                    return part.lower()
        return candidate.strip("/")

    def _normalize_url(self, identifier_or_url: str) -> str:
        # Accept either a full URL or the ncode identifier.
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
        # Syosetu/Novel18 pages are UTF-8. Some responses omit a charset, which
        # can make httpx decode them as latin-1/cp1252 and produce mojibake.
        return response.content.decode("utf-8", errors="replace")

    @staticmethod
    def _decode_page_body(body: bytes) -> str:
        return body.decode("utf-8", errors="replace")

    async def _fetch_page(self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None) -> str:
        result = await self._fetch_service.get_text(
            url,
            source_key=self.key,
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
            source_key=self.key,
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

    @staticmethod
    def _classes(tag: Tag) -> set[str]:
        raw_classes = tag.get("class") or []
        values = raw_classes if isinstance(raw_classes, list) else [raw_classes]
        return {str(value).strip() for value in values if str(value).strip()}

    def _is_part_heading(self, tag: Tag) -> bool:
        classes = self._classes(tag)
        if classes.intersection(self.PART_HEADING_CLASSES):
            return True
        if tag.name.lower() not in {"h2", "h3", "h4", "div", "p"}:
            return False
        if tag.find("a", href=True):
            return False
        text = tag.get_text(" ", strip=True)
        if not text:
            return False
        lowered = text.lower()
        if "chapter" in lowered or "part" in lowered or "arc" in lowered:
            return True
        return bool(re.search(r"(?:^|\s)(?:第?[0-9０-９一二三四五六七八九十百]+[章部編]|[0-9０-９]+章)(?:\s|　|$)", text))

    def _extract_source_date_from_text(self, text: str) -> str | None:
        match = self.SOURCE_DATE_PATTERN.search(text)
        return match.group(0) if match else None

    def _extract_source_date_from_node(self, node: Tag) -> str | None:
        for time_node in node.find_all("time"):
            if not isinstance(time_node, Tag):
                continue
            datetime_value = time_node.get("datetime")
            if isinstance(datetime_value, str) and datetime_value.strip():
                source_date = self._extract_source_date_from_text(datetime_value)
                if source_date:
                    return source_date
                return datetime_value.strip()
            source_date = self._extract_source_date_from_text(time_node.get_text(" ", strip=True))
            if source_date:
                return source_date

        source_date = self._extract_source_date_from_text(node.get_text(" ", strip=True))
        if source_date:
            return source_date

        title_value = node.get("title")
        if isinstance(title_value, str):
            return self._extract_source_date_from_text(title_value)
        return None

    def _chapter_row_container(self, anchor: Tag) -> Tag | None:
        current: Tag | None = anchor
        for _ in range(5):
            if current is None:
                break
            if self._classes(current).intersection(self.CHAPTER_ROW_CLASSES):
                return current
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return anchor.parent if isinstance(anchor.parent, Tag) else None

    def _extract_chapter_date(self, anchor: Tag) -> str | None:
        candidates: list[Tag] = []
        row = self._chapter_row_container(anchor)
        if row is not None:
            candidates.append(row)
        if isinstance(anchor.parent, Tag):
            candidates.append(anchor.parent)
            for sibling in list(anchor.parent.next_siblings)[:4] + list(anchor.parent.previous_siblings)[-4:]:
                if isinstance(sibling, Tag):
                    candidates.append(sibling)
        if row is not None:
            for sibling in list(row.next_siblings)[:3] + list(row.previous_siblings)[-3:]:
                if isinstance(sibling, Tag):
                    candidates.append(sibling)

        for candidate in candidates:
            source_date = self._extract_source_date_from_node(candidate)
            if source_date:
                return source_date
        return None

    def _extract_chapter_part(self, anchor: Tag, current_part: str | None) -> str | None:
        if current_part:
            return current_part
        if isinstance(anchor.parent, Tag):
            for sibling in reversed(list(anchor.parent.previous_siblings)[-8:]):
                if isinstance(sibling, Tag) and self._is_part_heading(sibling):
                    text = sibling.get_text(" ", strip=True)
                    if text:
                        return text
        return None

    def _extract_chapters(
        self,
        soup: BeautifulSoup,
        url: str,
        title: str | None,
        *,
        initial_part: str | None = None,
    ) -> list[dict[str, Any]]:
        base_url = httpx.URL(url)
        novel_id = self.normalize_novel_id(url)
        chapter_pattern = re.compile(rf"^/{re.escape(novel_id)}/(\d+)/?$", re.IGNORECASE)
        chapter_urls: dict[int, dict[str, Any]] = {}
        current_part = initial_part.strip() if isinstance(initial_part, str) and initial_part.strip() else None

        for node in soup.find_all(["div", "section", "h2", "h3", "h4", "p", "li", "a"], recursive=True):
            if not isinstance(node, Tag):
                continue

            if self._is_part_heading(node):
                text = node.get_text(" ", strip=True)
                if text:
                    current_part = text
                continue

            if node.name.lower() != "a":
                continue

            href = attribute_to_str(node.get("href"))
            if href is None:
                continue

            absolute_url = str(base_url.join(href))
            match = chapter_pattern.match(httpx.URL(absolute_url).path)
            if not match:
                continue

            chapter_number = int(match.group(1))
            chapter: dict[str, Any] = {
                "id": str(chapter_number),
                "num": chapter_number,
                "title": node.get_text(strip=True) or f"Chapter {chapter_number}",
                "url": absolute_url,
            }
            part = self._extract_chapter_part(node, current_part)
            if part:
                chapter["part"] = part
            date_added = self._extract_chapter_date(node)
            if date_added:
                chapter["date_added"] = date_added
            existing = chapter_urls.get(chapter_number)
            if existing is not None:
                if part and not existing.get("part"):
                    existing["part"] = part
                if date_added and not existing.get("date_added"):
                    existing["date_added"] = date_added
                continue
            chapter_urls[chapter_number] = chapter

        if chapter_urls:
            return [chapter_urls[index] for index in sorted(chapter_urls)]

        if self._find_story_body(soup) is None:
            return []

        return [
            {
                "id": "1",
                "num": 1,
                "title": title or "Chapter 1",
                "url": str(base_url),
            }
        ]

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

    def _is_story_body(self, candidate: Tag) -> bool:
        raw_classes = candidate.get("class") or []
        classes = {
            value.lower()
            for value in (raw_classes if isinstance(raw_classes, list) else [raw_classes])
            if isinstance(value, str)
        }
        if "p-novel__text--preface" in classes or "p-novel__text--afterword" in classes:
            return False
        return candidate.get("id") not in {"novel_p", "novel_a"}

    def _prepare_story_section(self, section: Tag) -> Tag | None:
        section_soup = BeautifulSoup(str(section), "lxml")
        prepared = section_soup.select_one(section.name)
        if not isinstance(prepared, Tag):
            return None

        for removable in self.REMOVE_FROM_SECTION_SELECTORS:
            for tag in prepared.select(removable):
                tag.decompose()

        for ruby_selector in self.RUBY_REMOVE_SELECTORS:
            for tag in prepared.find_all(ruby_selector):
                tag.decompose()
        for ruby in prepared.find_all("ruby"):
            ruby.unwrap()

        if not prepared.get_text(separator="\n", strip=True) and not prepared.find(["hr", "img"]):
            return None
        return prepared

    def _normalize_story_text(self, text: str) -> str:
        return normalize_text(text)

    def _extract_text_from_tag(self, tag: Tag) -> str:
        if tag.name.lower() == "img":
            return image_placeholder(tag)

        for image in tag.find_all("img"):
            image.replace_with(image_placeholder(image))
        for hr in tag.find_all("hr"):
            hr.replace_with(f"\n\n{self.SEPARATOR_LINE}\n\n")
        for br in tag.find_all("br"):
            br.replace_with("\n")
        return self._normalize_story_text(tag.get_text(separator="", strip=False))

    def _render_story_section(self, section: Tag) -> str:
        blocks: list[str] = []
        for element in iter_story_blocks(section, ("p", "blockquote", "figure", "hr", "img")):
            if not isinstance(element, Tag):
                continue
            if element.name.lower() == "hr":
                blocks.append(self.SEPARATOR_LINE)
                continue
            block = self._extract_text_from_tag(element)
            if block:
                blocks.append(block)

        if blocks:
            return "\n\n".join(blocks)
        return self._extract_text_from_tag(section)

    def _extract_source_blocks_from_section(self, section: Tag) -> list[dict[str, Any]]:
        blocks: list[str] = []
        for element in iter_story_blocks(section, ("p", "blockquote", "figure", "hr", "img")):
            if not isinstance(element, Tag):
                continue
            if element.name.lower() == "hr":
                blocks.append("")
                continue
            block = self._extract_text_from_tag(element)
            if block:
                blocks.append(block)

        if blocks:
            return source_blocks_from_text_blocks(blocks)
        fallback = self._extract_text_from_tag(section)
        return source_blocks_from_text_blocks([fallback] if fallback else [])

    def _find_story_section(self, soup: BeautifulSoup, selectors: tuple[str, ...]) -> Tag | None:
        for selector in selectors:
            for candidate in soup.select(selector):
                if not isinstance(candidate, Tag):
                    continue
                if selector in self.BODY_SELECTORS and not self._is_story_body(candidate):
                    continue
                prepared = self._prepare_story_section(candidate)
                if prepared is not None:
                    return prepared
        return None

    def _find_story_body(self, soup: BeautifulSoup) -> Tag | None:
        return self._find_story_section(soup, self.BODY_SELECTORS)

    def _find_story_sections(self, soup: BeautifulSoup) -> list[Tag]:
        sections: list[Tag] = []
        preface = self._find_story_section(soup, self.PREFACE_SELECTORS)
        body = self._find_story_body(soup)
        afterword = self._find_story_section(soup, self.AFTERWORD_SELECTORS)

        for section in (preface, body, afterword):
            if section is not None:
                sections.append(section)
        return sections

    def _extract_dates(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        date_text = soup.get_text(separator="|", strip=True)
        dates = re.findall(r"\d{4}/\d{2}/\d{2}", date_text)
        published_at = dates[0] if dates else None
        updated_at = dates[-1] if dates else None
        return published_at, updated_at

    # ------------------------------------------------------------------
    # Taxonomy extraction — genre and keywords
    # ------------------------------------------------------------------

    @property
    def _genre_map(self) -> dict[str, str]:
        """Genre text → slug mapping. Subclasses may override."""
        return SYOSETU_GENRE_MAP

    def _extract_source_genre(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """Extract genre/category text and mapped slug from the novel info page.

        Returns (source_genre_name, genre_slug) where genre_slug may be None
        if the source text doesn't map to a known internal genre.
        """
        # Try modern Syosetu selectors first, then legacy patterns
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

        # Fallback: look for genre links by href pattern
        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag):
                continue
            href = attribute_to_str(anchor.get("href")) or ""
            if "/genre/" in href and "syosetu.com" in href:
                text = anchor.get_text(strip=True)
                if text:
                    slug = map_genre(text, self._genre_map)
                    return text, slug

        return None, None

    def _extract_source_keywords(self, soup: BeautifulSoup) -> list[str]:
        """Extract author-set keywords from the novel info page.

        Syosetu keywords are typically rendered as linked elements
        with specific class patterns or inside a keyword section.
        """
        # Try keyword-specific selectors
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

        # Fallback: look for links with keyword-like href patterns
        if not keywords:
            for anchor in soup.find_all("a", href=True):
                if not isinstance(anchor, Tag):
                    continue
                href = attribute_to_str(anchor.get("href")) or ""
                if "/tag/" in href and "syosetu.com" in href:
                    text = anchor.get_text(strip=True)
                    if text:
                        keywords.append(text)

        return normalize_keywords(keywords)

    def _extract_publication_status_text(self, soup: BeautifulSoup) -> str | None:
        for row in soup.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all(["th", "td"])
                if isinstance(cell, Tag)
            ]
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

        return {
            "source": self.key,
            "source_url": url,
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
            rendered
            for rendered in (
                self._render_story_section(section)
                for section in sections
            )
            if rendered
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
        html = await self._fetch_page(url, on_retry=None)
        metadata = self._parse_metadata_html(html, url)
        try:
            infotop_url = self._infotop_url(url)
            infotop_html = await self._fetch_page(infotop_url, on_retry=None)
        except SourceError:
            pass
        else:
            self._merge_publication_status(
                metadata,
                self._publication_status_payload_from_html(infotop_html, infotop_url),
            )
        soup = BeautifulSoup(html, "lxml")
        page_numbers = self._extract_page_numbers(soup, url)
        if len(page_numbers) == 1:
            metadata["chapters"] = self._apply_chapter_cap(metadata.get("chapters", []), max_chapter)
            return metadata

        chapters_by_number = {
            int(chapter["num"]): chapter
            for chapter in metadata.get("chapters", [])
            if isinstance(chapter, dict) and isinstance(chapter.get("num"), int)
        }
        current_part = self._last_chapter_part(metadata.get("chapters"))
        if max_chapter is not None and chapters_by_number:
            highest_known_chapter = max(chapters_by_number)
            if highest_known_chapter >= max_chapter:
                metadata["chapters"] = [
                    chapter
                    for number, chapter in sorted(chapters_by_number.items())
                    if number <= max_chapter
                ]
                return metadata

        for page_number in page_numbers[1:]:
            page_url = f"{url}?p={page_number}"
            page_html = await self._fetch_page(page_url, on_retry=None)
            page_soup = BeautifulSoup(page_html, "lxml")
            for chapter in self._extract_chapters(page_soup, url, metadata.get("title"), initial_part=current_part):
                chapter_part = chapter.get("part") or chapter.get("volume") or chapter.get("arc") or chapter.get("section")
                if isinstance(chapter_part, str) and chapter_part.strip():
                    current_part = chapter_part.strip()
                if isinstance(chapter.get("num"), int):
                    chapters_by_number[int(chapter["num"])] = chapter
            if max_chapter is not None and chapters_by_number and max(chapters_by_number) >= max_chapter:
                break

        metadata["chapters"] = [
            chapters_by_number[number]
            for number in sorted(chapters_by_number)
            if max_chapter is None or number <= max_chapter
        ]
        return metadata

    async def fetch_chapter(self, url: str) -> str:
        html = await self._fetch_page(url, on_retry=None)
        return str(self._parse_chapter_payload(html, url).get("text", ""))

    async def fetch_chapter_payload(
        self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None
    ) -> dict[str, Any]:
        html = await self._fetch_page(url, on_retry=on_retry)
        return self._parse_chapter_payload(html, url)
