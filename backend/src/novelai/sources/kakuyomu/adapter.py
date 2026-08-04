"""Kakuyomu source adapter implementation."""

from __future__ import annotations

import logging
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
from novelai.sources.kakuyomu.parser import (
    BODY_SELECTORS,
    REMOVE_FROM_BODY_SELECTORS,
    TITLE_SELECTORS,
    extract_chapters_from_next_data,
)
from novelai.sources.quality import detect_age_gate_text, detect_block_page_text
from novelai.sources.source_layout import source_blocks_from_text_blocks
from novelai.sources.status import publication_status_payload
from novelai.utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)


class KakuyomuSource(SourceAdapter):
    source_key = "kakuyomu"
    """Source adapter for Kakuyomu works and episodes."""

    WORK_ID_PATTERN = re.compile(r"^\d{12,}$")
    WORK_PATH_PATTERN = re.compile(r"/works/([^/?#]+)(?:/|$)", re.IGNORECASE)
    EPISODE_PATH_PATTERN = re.compile(r"/works/([^/]+)/episodes/([^/?#]+)", re.IGNORECASE)
    BODY_SELECTORS = BODY_SELECTORS
    TITLE_SELECTORS = TITLE_SELECTORS
    AUTHOR_SELECTORS = (
        ".widget-authorName",
        "[itemprop='author']",
        "[rel='author']",
        "[data-author-name]",
    )
    TOC_ROOT_SELECTORS = (
        ".widget-toc",
        ".widget-toc-main",
        "[data-work-toc]",
        "#contentMain",
        "main",
    )
    EPISODE_TITLE_SELECTORS = (
        ".widget-toc-episode-episodeTitleLabel",
        ".widget-toc-episode-episodeTitle",
        ".widget-toc-episodeTitleLabel",
        ".widget-toc-episodeTitle",
        ".episode-title",
    )
    REMOVE_FROM_BODY_SELECTORS = REMOVE_FROM_BODY_SELECTORS
    RUBY_REMOVE_SELECTORS = ("rt", "rp")
    SEPARATOR_LINE = "-" * 60
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    PUBLICATION_STATUS_TEXT_MARKERS = (
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

    def can_handle(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            parsed_url = httpx.URL(candidate)
        except Exception:
            return False

        host = (parsed_url.host or "").lower()
        return host == "kakuyomu.jp" and self.WORK_PATH_PATTERN.search(parsed_url.path) is not None

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        candidate = identifier_or_url.strip().rstrip("/")
        if not candidate:
            return candidate

        if self.WORK_ID_PATTERN.fullmatch(candidate):
            return candidate

        if not candidate.startswith(("http://", "https://")):
            return candidate

        try:
            parsed_url = httpx.URL(candidate)
        except Exception:
            return candidate

        match = self.EPISODE_PATH_PATTERN.search(parsed_url.path)
        if match:
            return match.group(1)

        match = self.WORK_PATH_PATTERN.search(parsed_url.path)
        if match:
            return match.group(1)

        return candidate.strip("/")

    def _normalize_url(self, identifier_or_url: str) -> str:
        work_id = self.normalize_novel_id(identifier_or_url)
        return f"https://kakuyomu.jp/works/{work_id.strip('/')}"

    @staticmethod
    def _request_headers() -> dict[str, str]:
        return {"User-Agent": KakuyomuSource.USER_AGENT}

    @staticmethod
    def _decode_page_body(body: bytes) -> str:
        return body.decode("utf-8", errors="replace")

    @staticmethod
    def _preflight_check(html: str, url: str) -> None:
        if detect_block_page_text(html):
            raise SourceError(f"Kakuyomu page at {url} appears to be blocked (Cloudflare, CAPTCHA, or bot challenge).")
        if detect_age_gate_text(html):
            raise SourceError(f"Kakuyomu page at {url} appears to require age verification or adult confirmation.")

    async def _fetch_page(self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None) -> str:
        try:
            result = await self._fetch_service.get_text(
                url,
                source_key=self.source_key,
                headers=self._request_headers(),
                on_retry=on_retry,
            )
        except SourceError as exc:
            raise SourceError(f"Failed to fetch Kakuyomu page from {url}: {exc}") from exc
        html = self._decode_page_body(result.body)
        self._preflight_check(html, url)
        return html

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> dict[str, Any]:
        try:
            result = await self._fetch_service.get_bytes(url, source_key=self.source_key, referer=referer)
        except SourceError as exc:
            raise SourceError(f"Failed to fetch Kakuyomu asset from {url}: {exc}") from exc

        return {
            "url": result.final_url,
            "content": result.body,
            "content_type": result.headers.get("content-type"),
        }

    def _first_text(self, soup: BeautifulSoup | Tag, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            node = soup.select_one(selector)
            if not isinstance(node, Tag):
                continue
            text = node.get_text(" ", strip=True)
            if text:
                return text
        return None

    def _extract_work_title(self, soup: BeautifulSoup) -> str | None:
        return HTMLParserMixin.extract_title(soup, self.TITLE_SELECTORS)

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        author = HTMLParserMixin.extract_author(soup, self.AUTHOR_SELECTORS)
        if author:
            return author
        meta = soup.find("meta", attrs={"name": "author"})
        content = meta.get("content") if isinstance(meta, Tag) else None
        return content.strip() if isinstance(content, str) and content.strip() else None

    def _extract_synopsis(self, soup: BeautifulSoup) -> str | None:
        for selector in (
            ".widget-workSynopsis",
            ".widget-work-introduction",
            "[itemprop='description']",
            "meta[name='description']",
            "meta[property='og:description']",
        ):
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

    def _extract_episode_title(self, anchor: Tag, fallback_index: int) -> str:
        title = self._first_text(anchor, self.EPISODE_TITLE_SELECTORS)
        if title:
            return title
        text = anchor.get_text(" ", strip=True)
        return text or f"Episode {fallback_index}"

    def _extract_chapters_from_html(self, soup: BeautifulSoup, url: str) -> list[dict[str, str | int]]:
        work_id = self.normalize_novel_id(url)
        toc_roots: list[Tag] = []
        for selector in self.TOC_ROOT_SELECTORS:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                toc_roots.append(node)
        if not toc_roots:
            toc_roots.append(soup)

        chapters: list[dict[str, str | int]] = []
        seen_urls: set[str] = set()
        base_url = httpx.URL(url)
        current_part: str | None = None

        for root in toc_roots:
            for element in root.find_all(["a", "h3", "h4", "div", "li", "span"], recursive=True):
                if not isinstance(element, Tag):
                    continue

                if element.name.lower() in {"h3", "h4", "div", "li", "span"}:
                    cls_list = element.get("class") or []
                    cls_str = " ".join(cls_list if isinstance(cls_list, list) else [str(cls_list)])
                    if "widget-toc-chapter" in cls_str or "widget-toc-heading" in cls_str or "chapter-title" in cls_str:
                        heading_text = element.get_text(" ", strip=True)
                        if heading_text:
                            current_part = heading_text
                        continue

                if element.name.lower() != "a":
                    continue

                href = attribute_to_str(element.get("href"))
                if href is None:
                    continue

                try:
                    abs_url = str(base_url.join(href))
                    parsed = httpx.URL(abs_url)
                except Exception:
                    continue

                match = self.EPISODE_PATH_PATTERN.search(parsed.path)
                if not match:
                    continue
                if match.group(1) != work_id:
                    continue

                canonical_url = f"https://kakuyomu.jp/works/{work_id}/episodes/{match.group(2)}"
                if canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                index = len(chapters) + 1
                chapter_item: dict[str, str | int] = {
                    "id": str(index),
                    "num": index,
                    "title": self._extract_episode_title(element, index),
                    "url": canonical_url,
                    "source_episode_id": match.group(2),
                }
                if current_part:
                    chapter_item["part"] = current_part
                chapters.append(chapter_item)

        return chapters

    def _extract_chapters(self, soup: BeautifulSoup, url: str) -> list[dict[str, str | int]]:
        chapters = extract_chapters_from_next_data(soup, self.normalize_novel_id(url))
        if chapters:
            return chapters
        return self._extract_chapters_from_html(soup, url)

    def _extract_publication_status_text(self, soup: BeautifulSoup) -> str | None:
        status_selectors = (
            ".widget-workHeader-status",
            ".widget-work-status",
            "[data-work-status]",
            ".work-status",
        )
        for selector in status_selectors:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                text = node.get_text(" ", strip=True)
                if text:
                    return text

        for container in soup.find_all(["dl", "div", "p", "li", "span"]):
            if not isinstance(container, Tag):
                continue
            text = container.get_text(" ", strip=True)
            if not text or len(text) > 200:
                continue
            for marker in self.PUBLICATION_STATUS_TEXT_MARKERS:
                if marker in text:
                    return text
        return None

    def _parse_metadata_html(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        novel_id = self.normalize_novel_id(url)
        title = self._extract_work_title(soup) or f"Work {novel_id}"
        author = self._extract_author(soup)
        synopsis = self._extract_synopsis(soup)
        chapters = self._extract_chapters(soup, url)
        status_text = self._extract_publication_status_text(soup)

        return {
            "source_key": self.source_key,
            "source_url": url,
            "source_novel_id": novel_id,
            "novel_id": novel_id,
            "title": title,
            "author": author,
            "synopsis": synopsis,
            "chapters": chapters,
            **publication_status_payload(status_text),
        }

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        full_url = self._normalize_url(url)
        html = await self._fetch_page(full_url, on_retry=None)
        metadata = self._parse_metadata_html(html, full_url)
        if max_chapter is not None and isinstance(metadata.get("chapters"), list):
            metadata["chapters"] = [
                ch
                for ch in metadata["chapters"]
                if isinstance(ch, dict) and isinstance(ch.get("num"), int) and ch["num"] <= max_chapter
            ]
        return metadata

    def _parse_chapter_payload(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        body_node = soup.select_one(", ".join(self.BODY_SELECTORS))
        if not isinstance(body_node, Tag):
            raise SourceError(f"Unable to find episode body at {url}")

        for sel in self.REMOVE_FROM_BODY_SELECTORS:
            for tag in body_node.select(sel):
                tag.decompose()

        for sel in self.RUBY_REMOVE_SELECTORS:
            for tag in body_node.find_all(sel):
                tag.decompose()
        for ruby in body_node.find_all("ruby"):
            ruby.unwrap()

        images = extract_image_references(body_node, base_url=url)
        for img in body_node.find_all("img"):
            img.replace_with(image_placeholder(img))

        for hr in body_node.find_all("hr"):
            hr.replace_with(f"\n\n{self.SEPARATOR_LINE}\n\n")

        for br in body_node.find_all("br"):
            br.replace_with("\n")

        raw_blocks: list[str] = []
        for element in iter_story_blocks(body_node, ("p", "blockquote", "figure", "hr", "img")):
            if isinstance(element, Tag):
                text = normalize_text(element.get_text(separator="", strip=False))
                if text:
                    raw_blocks.append(text)

        if not raw_blocks:
            text = normalize_text(body_node.get_text(separator="", strip=False))
            if text:
                raw_blocks.append(text)

        full_text = "\n\n".join(raw_blocks)
        source_blocks = source_blocks_from_text_blocks(raw_blocks)

        return {
            "text": full_text,
            "images": images,
            "source_blocks": source_blocks,
        }

    async def fetch_chapter_payload(
        self,
        url: str,
        *,
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> dict[str, Any]:
        html = await self._fetch_page(url, on_retry=on_retry)
        return self._parse_chapter_payload(html, url)

    async def fetch_chapter(self, url: str) -> str:
        payload = await self.fetch_chapter_payload(url)
        return str(payload.get("text", ""))
