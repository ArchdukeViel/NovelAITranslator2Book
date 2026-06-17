from __future__ import annotations

import re
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
from novelai.sources.taxonomy import (
    KAKUYOMU_GENRE_MAP,
    map_genre,
    normalize_keywords,
)
from novelai.utils.text_normalization import normalize_text


class KakuyomuSource(SourceAdapter):
    """Source adapter for Kakuyomu works and episodes."""

    WORK_ID_PATTERN = re.compile(r"^\d{12,}$")
    WORK_PATH_PATTERN = re.compile(r"/works/([^/?#]+)(?:/|$)", re.IGNORECASE)
    EPISODE_PATH_PATTERN = re.compile(r"/works/([^/]+)/episodes/([^/?#]+)", re.IGNORECASE)
    BODY_SELECTORS = (
        ".widget-episodeBody",
        ".js-episode-body",
        "[data-episode-body]",
        "article [itemprop='articleBody']",
        ".episode-body",
    )
    TITLE_SELECTORS = (
        ".widget-workTitle",
        ".widget-workCard-title",
        "#workTitle",
        "h1[itemprop='name']",
        "main h1",
    )
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
    REMOVE_FROM_BODY_SELECTORS = (
        ".widget-episode-actions",
        ".shareButtons",
        ".share-buttons",
        ".widget-share",
        ".js-share",
    )
    RUBY_REMOVE_SELECTORS = ("rt", "rp")
    SEPARATOR_LINE = "-" * 60
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()

    @property
    def key(self) -> str:
        return "kakuyomu"

    def matches_url(self, identifier_or_url: str) -> bool:
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
        return f"https://kakuyomu.jp/works/{work_id.strip('/')}/"

    @staticmethod
    def _request_headers() -> dict[str, str]:
        return {"User-Agent": KakuyomuSource.USER_AGENT}

    @staticmethod
    def _decode_page_body(body: bytes) -> str:
        # Kakuyomu pages are UTF-8. Force-decode to avoid mojibake
        # when the server omits a charset in the Content-Type header.
        return body.decode("utf-8", errors="replace")

    @staticmethod
    def _preflight_check(html: str, url: str) -> None:
        """Reject obvious blocked, age-gated, or bot-challenge pages.

        Raises SourceError if the raw HTML matches known block/age-gate patterns.
        """
        if detect_block_page_text(html):
            raise SourceError(
                f"Kakuyomu page at {url} appears to be blocked (Cloudflare, CAPTCHA, or bot challenge)."
            )
        if detect_age_gate_text(html):
            raise SourceError(
                f"Kakuyomu page at {url} appears to require age verification or adult confirmation."
            )

    async def _fetch_page(self, url: str) -> str:
        try:
            result = await self._fetch_service.get_text(
                url,
                source_key=self.key,
                headers=self._request_headers(),
            )
        except SourceError as exc:
            raise SourceError(f"Failed to fetch Kakuyomu page from {url}: {exc}") from exc
        html = self._decode_page_body(result.body)
        self._preflight_check(html, url)
        return html

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> dict[str, Any]:
        try:
            result = await self._fetch_service.get_bytes(url, source_key=self.key, referer=referer)
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

    def _extract_chapters(self, soup: BeautifulSoup, url: str, work_title: str | None) -> list[dict[str, str | int]]:
        base_url = httpx.URL(url)
        work_id = self.normalize_novel_id(url)
        seen_episode_ids: set[str] = set()
        chapter_rows: list[dict[str, str | int]] = []

        roots: list[Tag] = []
        for selector in self.TOC_ROOT_SELECTORS:
            roots.extend(node for node in soup.select(selector) if isinstance(node, Tag))
            if roots:
                break
        if not roots:
            roots = [node for node in soup.find_all("main") if isinstance(node, Tag)] or [soup]

        for root in roots:
            for anchor in root.find_all("a", href=True):
                if not isinstance(anchor, Tag):
                    continue
                href = attribute_to_str(anchor.get("href"))
                if href is None:
                    continue

                absolute_url = str(base_url.join(href))
                parsed_url = httpx.URL(absolute_url)
                match = self.EPISODE_PATH_PATTERN.search(parsed_url.path)
                if not match or match.group(1) != work_id:
                    continue

                episode_id = match.group(2)
                if episode_id in seen_episode_ids:
                    continue

                seen_episode_ids.add(episode_id)
                index = len(chapter_rows) + 1
                chapter_rows.append(
                    {
                        "id": str(index),
                        "num": index,
                        "title": self._extract_episode_title(anchor, index),
                        "url": absolute_url,
                        "source_episode_id": episode_id,
                    }
                )

            if chapter_rows:
                break

        if chapter_rows:
            return chapter_rows

        body = self._find_story_body(soup)
        episode_match = self.EPISODE_PATH_PATTERN.search(base_url.path)
        if body is not None and episode_match:
            return [
                {
                    "id": "1",
                    "num": 1,
                    "title": self._extract_episode_page_title(soup) or work_title or "Episode 1",
                    "url": str(base_url),
                    "source_episode_id": episode_match.group(2),
                }
            ]

        return []

    def _extract_episode_page_title(self, soup: BeautifulSoup) -> str | None:
        return self._first_text(
            soup,
            (
                ".widget-episodeTitle",
                "h1#contentMain-title",
                "h1[itemprop='name']",
                "article h1",
            ),
        )

    def _extract_dates(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        timestamps = [
            value.strip()
            for value in (node.get("datetime") for node in soup.select("time[datetime]"))
            if isinstance(value, str) and value.strip()
        ]
        published_at = timestamps[0] if timestamps else None
        updated_at = timestamps[-1] if timestamps else None
        return published_at, updated_at

    # ------------------------------------------------------------------
    # Taxonomy extraction — genre and tags
    # ------------------------------------------------------------------

    def _extract_source_genre(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """Extract genre/category text and mapped slug from the Kakuyomu work page.

        Returns (source_genre_name, genre_slug) where genre_slug may be None
        if the source text doesn't map to a known internal genre.
        """
        genre_selectors = (
            ".widget-workGenre",
            ".widget-work-genre",
            ".work-genre",
            "[class*='genre'] a",
            "[class*='Genre'] a",
            "[class*='category'] a",
        )
        for selector in genre_selectors:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                text = node.get_text(strip=True)
                if text:
                    slug = map_genre(text, KAKUYOMU_GENRE_MAP)
                    return text, slug

        return None, None

    def _extract_source_tags(self, soup: BeautifulSoup) -> list[str]:
        """Extract author-set tags from the Kakuyomu work page."""
        tag_selectors = (
            ".widget-workTag a",
            ".widget-work-tag a",
            ".work-tag a",
            "[class*='workTag'] a",
            "[class*='work-tag'] a",
            ".tag a",
        )
        tags: list[str] = []
        for selector in tag_selectors:
            nodes = soup.select(selector)
            if nodes:
                for node in nodes:
                    if isinstance(node, Tag):
                        text = node.get_text(strip=True)
                        if text:
                            tags.append(text)
                if tags:
                    break

        return normalize_keywords(tags)

    def _find_story_body(self, soup: BeautifulSoup) -> Tag | None:
        for selector in self.BODY_SELECTORS:
            candidate = soup.select_one(selector)
            if isinstance(candidate, Tag):
                return candidate
        return None

    def _prepare_story_body(self, section: Tag) -> Tag | None:
        section_soup = BeautifulSoup(str(section), "lxml")
        prepared = section_soup.select_one(section.name)
        if not isinstance(prepared, Tag):
            return None

        for removable in self.REMOVE_FROM_BODY_SELECTORS:
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

    def _render_story_body(self, section: Tag) -> str:
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

    def _parse_metadata_html(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title = self._extract_work_title(soup)
        author = self._extract_author(soup)
        synopsis = self._extract_synopsis(soup)
        chapters = self._extract_chapters(soup, url, title)
        published_at, updated_at = self._extract_dates(soup)
        source_genre_name, genre_slug = self._extract_source_genre(soup)
        source_tags = self._extract_source_tags(soup)

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
            "source_tags": source_tags,
        }

    def _parse_chapter_payload(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body = self._find_story_body(soup)
        if body is None:
            raise SourceError("Unable to find chapter text on Kakuyomu page")

        prepared = self._prepare_story_body(body)
        if prepared is None:
            raise SourceError("Chapter text was empty on Kakuyomu page")

        images = extract_image_references(prepared, base_url=url)
        text = self._render_story_body(prepared)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if not text:
            raise SourceError("Chapter text was empty on Kakuyomu page")
        return {
            "text": text,
            "images": images,
        }

    def _parse_chapter_html(self, html: str, url: str = "https://kakuyomu.jp/") -> str:
        return str(self._parse_chapter_payload(html, url).get("text", ""))

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        url = self._normalize_url(url)
        html = await self._fetch_page(url)
        metadata = self._parse_metadata_html(html, url)
        if max_chapter is not None:
            metadata["chapters"] = [
                chapter
                for chapter in metadata.get("chapters", [])
                if isinstance(chapter, dict)
                and isinstance(chapter.get("num"), int)
                and int(chapter["num"]) <= max_chapter
            ]
        return metadata

    async def fetch_chapter(self, url: str) -> str:
        html = await self._fetch_page(url)
        return str(self._parse_chapter_payload(html, url).get("text", ""))

    async def fetch_chapter_payload(self, url: str) -> dict[str, Any]:
        html = await self._fetch_page(url)
        return self._parse_chapter_payload(html, url)
