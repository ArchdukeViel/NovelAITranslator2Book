"""Generic source adapter for arbitrary novel sites.

Falls back to heuristic content extraction when no site-specific adapter
matches.  Expects a full novel/chapter URL rather than a site-specific ID.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.sources._helpers import (
    extract_image_references,
    image_placeholder,
    iter_story_blocks,
)
from novelai.sources.base import SourceAdapter, validate_url

# Selectors tried in order to find the main story text.
_BODY_SELECTORS: tuple[str, ...] = (
    "article",
    "[role='main']",
    "main",
    "#content",
    ".content",
    "#story",
    ".story",
    ".chapter-content",
    ".entry-content",
    ".post-content",
    ".novel-text",
)

_TITLE_SELECTORS: tuple[str, ...] = (
    "h1",
    "meta[property='og:title']",
    "title",
)

_AUTHOR_SELECTORS: tuple[str, ...] = (
    "[rel='author']",
    "[itemprop='author']",
    "meta[name='author']",
)

_REMOVE_SELECTORS: tuple[str, ...] = (
    "nav",
    "header",
    "footer",
    "aside",
    ".sidebar",
    ".comments",
    ".ad",
    ".advertisement",
    "script",
    "style",
    "iframe",
)


class GenericSource(SourceAdapter):
    """Heuristic scraper for any novel URL not matched by a dedicated adapter."""

    @property
    def key(self) -> str:
        return "generic"

    # The generic adapter is a fallback — it never claims to "match" a URL
    # by itself.  The caller should pass source_key="generic" explicitly.

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        """Use the URL's hostname + path as a stable id."""
        candidate = identifier_or_url.strip().rstrip("/")
        if candidate.startswith(("http://", "https://")):
            parsed = urlparse(candidate)
            # e.g.  example.com/novels/12345
            return f"{parsed.netloc}{parsed.path}".rstrip("/")
        return candidate

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _request_headers(*, referer: str | None = None) -> dict[str, str]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if isinstance(referer, str) and referer.strip():
            headers["Referer"] = referer.strip()
        return headers

    async def _fetch_page(self, url: str) -> str:
        validate_url(url)
        await self._rate_limit()
        try:
            async def _do_request() -> httpx.Response:
                async with httpx.AsyncClient(
                    timeout=30,
                    headers=self._request_headers(),
                    follow_redirects=True,
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp

            resp = await self._with_retry(_do_request)
        except httpx.HTTPStatusError as exc:
            raise SourceError(
                f"Failed to fetch page from {url} (status={exc.response.status_code})."
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"Failed to fetch page from {url}: {exc}") from exc
        return resp.text

    # ------------------------------------------------------------------
    # HTML extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_soup(soup: BeautifulSoup) -> None:
        """Remove non-content elements in-place."""
        for selector in _REMOVE_SELECTORS:
            for tag in soup.select(selector):
                tag.decompose()

    @staticmethod
    def _find_body(soup: BeautifulSoup) -> Tag | None:
        for selector in _BODY_SELECTORS:
            candidate = soup.select_one(selector)
            if isinstance(candidate, Tag) and candidate.get_text(strip=True):
                return candidate
        # Last resort: <body> itself.
        body = soup.find("body")
        return body if isinstance(body, Tag) else None

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str | None:
        for selector in _TITLE_SELECTORS:
            node = soup.select_one(selector)
            if node is None:
                continue
            if isinstance(node, Tag) and node.name == "meta":
                content = node.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            elif isinstance(node, Tag):
                text = node.get_text(strip=True)
                if text:
                    return text
        return None

    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> str | None:
        for selector in _AUTHOR_SELECTORS:
            node = soup.select_one(selector)
            if node is None:
                continue
            if isinstance(node, Tag) and node.name == "meta":
                content = node.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            elif isinstance(node, Tag):
                text = node.get_text(strip=True)
                if text:
                    return text
        return None

    def _extract_chapters_from_toc(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict[str, str | int]]:
        """Try to discover a table-of-contents link list."""
        chapters: list[dict[str, str | int]] = []
        seen_urls: set[str] = set()

        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower()

        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag):
                continue
            href = anchor.get("href")
            if not isinstance(href, str) or not href.strip():
                continue
            absolute = urljoin(base_url, href.strip())
            parsed = urlparse(absolute)
            # Stay on the same domain.
            if parsed.netloc.lower() != base_domain:
                continue
            # Skip self-links and anchors.
            normalised = parsed._replace(fragment="").geturl()
            if normalised in seen_urls:
                continue
            if normalised.rstrip("/") == base_url.rstrip("/"):
                continue
            text = anchor.get_text(strip=True)
            if not text:
                continue
            seen_urls.add(normalised)
            index = len(chapters) + 1
            chapters.append(
                {"id": str(index), "num": index, "title": text, "url": absolute}
            )

        return chapters

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip(" \t") for line in text.split("\n")]
        normalised: list[str] = []
        for line in lines:
            if line:
                normalised.append(line)
            elif normalised and normalised[-1] != "":
                normalised.append("")
        return "\n".join(normalised).strip()

    def _render_body(self, section: Tag) -> str:
        for img in section.find_all("img"):
            img.replace_with(image_placeholder(img))
        for br in section.find_all("br"):
            br.replace_with("\n")

        blocks: list[str] = []
        for element in iter_story_blocks(section, ("p", "blockquote", "figure", "div", "h2", "h3")):
            if not isinstance(element, Tag):
                continue
            block = self._normalize_text(element.get_text(separator="", strip=False))
            if block:
                blocks.append(block)

        if blocks:
            text = "\n\n".join(blocks)
        else:
            text = self._normalize_text(section.get_text(separator="\n", strip=False))

        return re.sub(r"\n{3,}", "\n\n", text)

    # ------------------------------------------------------------------
    # Public SourceAdapter interface
    # ------------------------------------------------------------------

    async def fetch_metadata(
        self, url: str, *, max_chapter: int | None = None
    ) -> dict[str, Any]:
        html = await self._fetch_page(url)
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        title = self._extract_title(soup)
        author = self._extract_author(soup)
        chapters = self._extract_chapters_from_toc(soup, url)

        if max_chapter is not None:
            chapters = [c for c in chapters if isinstance(c.get("num"), int) and int(c["num"]) <= max_chapter]

        # If no chapters detected, treat the URL itself as a single chapter.
        if not chapters and self._find_body(soup) is not None:
            chapters = [{"id": "1", "num": 1, "title": title or "Chapter 1", "url": url}]

        return {
            "source": self.key,
            "source_url": url,
            "title": title,
            "author": author,
            "chapters": chapters,
        }

    async def fetch_chapter(self, url: str) -> str:
        html = await self._fetch_page(url)
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        body = self._find_body(soup)
        if body is None:
            raise SourceError("Unable to locate story content on the page.")

        text = self._render_body(body)
        if not text:
            raise SourceError("Extracted chapter text was empty.")
        return text

    async def fetch_chapter_payload(self, url: str) -> dict[str, Any]:
        html = await self._fetch_page(url)
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        body = self._find_body(soup)
        if body is None:
            raise SourceError("Unable to locate story content on the page.")

        images = extract_image_references(body, base_url=url)
        text = self._render_body(body)
        if not text:
            raise SourceError("Extracted chapter text was empty.")
        return {"text": text, "images": images}
