"""Generic source adapter for arbitrary novel sites.

Falls back to heuristic content extraction when no site-specific adapter
matches.  Expects a full novel/chapter URL rather than a site-specific ID.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.infrastructure.http.fetch_service import FetchService, get_default_fetch_service
from novelai.sources._helpers import (
    extract_image_references,
    image_placeholder,
    iter_story_blocks,
)
from novelai.sources.base import SourceAdapter
from novelai.sources.html_parsers import HTMLParserMixin
from novelai.sources.quality import (
    QualityGateResult,
    detect_age_gate_text,
    detect_block_page_text,
)
from novelai.utils.text_normalization import normalize_text as _shared_normalize_text

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

_GENERIC_POSITIVE_LINK_RE = re.compile(r"(chapter|episode|ep\.?|read|part|story|\d+)", re.IGNORECASE)
_GENERIC_NEGATIVE_LINK_RE = re.compile(
    r"(login|register|search|tag|author|profile|comment|privacy|terms|rss|feed|"
    r"home|about|contact|category|archive)",
    re.IGNORECASE,
)
_GENERIC_ASSET_PATH_RE = re.compile(r"\.(?:jpg|jpeg|png|gif|webp|svg|css|js|ico|xml|json)$", re.IGNORECASE)


class GenericSource(SourceAdapter):
    """Heuristic scraper for any novel URL not matched by a dedicated adapter."""

    source_key = "generic"

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

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

    async def _fetch_page(self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None) -> str:
        try:
            result = await self._fetch_service.get_text(url, source_key=self.source_key, on_retry=on_retry)
        except SourceError as exc:
            raise SourceError(f"Failed to fetch page from {url}: {exc}") from exc
        return result.text

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
    def _strip_ruby_annotations(section: Tag) -> None:
        """Remove ruby/furigana annotations in-place, keeping base text.

        Mirrors the pattern used by SyosetuNcodeSource:
        - Remove <rt> (ruby text) and <rp> (ruby parenthesis) tags.
        - Unwrap <ruby> so only the base kanji/text remains.
        """
        for tag_name in ("rt", "rp"):
            for tag in section.find_all(tag_name):
                tag.decompose()
        for ruby in section.find_all("ruby"):
            ruby.unwrap()

    @staticmethod
    def _preflight_check(html: str, url: str) -> None:
        """Reject obvious blocked, age-gated, or bot-challenge pages.

        Raises SourceError if the raw HTML matches known block/age-gate patterns.
        """
        if detect_block_page_text(html):
            raise SourceError(
                f"Page at {url} appears to be blocked (Cloudflare, CAPTCHA, or bot challenge)."
            )
        if detect_age_gate_text(html):
            raise SourceError(
                f"Page at {url} appears to require age verification or adult confirmation."
            )

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
        return HTMLParserMixin.extract_title(soup, _TITLE_SELECTORS)

    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> str | None:
        return HTMLParserMixin.extract_author(soup, _AUTHOR_SELECTORS)

    @staticmethod
    def _extract_synopsis(soup: BeautifulSoup) -> str | None:
        for selector in ("meta[name='description']", "meta[property='og:description']", ".synopsis", ".summary", ".description"):
            node = soup.select_one(selector)
            if not isinstance(node, Tag):
                continue
            content = node.get("content")
            if isinstance(content, str) and content.strip():
                return _shared_normalize_text(content)
            text = node.get_text("\n", strip=True)
            if text:
                return _shared_normalize_text(text)
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

    def _score_toc_confidence(
        self,
        soup: BeautifulSoup,
        base_url: str,
        chapters: list[dict[str, str | int]],
    ) -> QualityGateResult:
        warnings: list[str] = []
        errors: list[str] = []
        if not chapters:
            warnings.append("generic_single_page_or_no_toc")
            return QualityGateResult(passed=True, score=0.45, warnings=warnings, errors=errors)

        chapter_urls = [str(chapter.get("url") or "") for chapter in chapters if isinstance(chapter, dict)]
        positive = 0
        negative = 0
        duplicate_paths = 0
        paths: list[str] = []
        container_bonus = 0
        if soup.select("article a[href], main a[href], [role='main'] a[href], .toc a[href], .chapter-list a[href], .episode-list a[href]"):
            container_bonus = 1

        for chapter in chapters:
            url = str(chapter.get("url") or "")
            title = str(chapter.get("title") or "")
            parsed = urlparse(url)
            path = parsed.path.rstrip("/").lower()
            paths.append(path)
            combined = f"{path} {title}"
            if _GENERIC_POSITIVE_LINK_RE.search(combined):
                positive += 1
            if _GENERIC_NEGATIVE_LINK_RE.search(combined) or _GENERIC_ASSET_PATH_RE.search(path):
                negative += 1
            if len(title.strip()) <= 2:
                negative += 1

        duplicate_paths = len(paths) - len(set(paths))
        if duplicate_paths:
            warnings.append("generic_duplicate_paths")
        if negative:
            warnings.append("generic_negative_links")
        if positive == 0:
            warnings.append("generic_no_chapter_like_links")

        sibling_bonus = 0
        path_prefixes = [path.rsplit("/", 1)[0] for path in paths if "/" in path]
        if path_prefixes and len(set(path_prefixes)) <= max(1, len(path_prefixes) // 2):
            sibling_bonus = 1

        raw_score = 0.35
        raw_score += min(0.30, positive / max(1, len(chapter_urls)) * 0.30)
        raw_score += 0.15 * container_bonus
        raw_score += 0.15 * sibling_bonus
        raw_score -= min(0.25, negative / max(1, len(chapter_urls)) * 0.25)
        raw_score -= min(0.15, duplicate_paths / max(1, len(chapter_urls)) * 0.15)
        score = max(0.0, min(1.0, round(raw_score, 3)))
        if score < 0.40 and negative > positive:
            errors.append("generic_very_low_confidence_with_negative_signals")
        elif score < 0.60:
            warnings.append("generic_low_confidence")
        elif score < 0.75:
            warnings.append("generic_needs_review")
        return QualityGateResult(passed=len(errors) == 0, score=score, warnings=list(dict.fromkeys(warnings)), errors=errors)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return _shared_normalize_text(text)

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
        html = await self._fetch_page(url, on_retry=None)
        self._preflight_check(html, url)
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        title = self._extract_title(soup)
        author = self._extract_author(soup)
        synopsis = self._extract_synopsis(soup)
        chapters = self._extract_chapters_from_toc(soup, url)
        confidence = self._score_toc_confidence(soup, url, chapters)

        if max_chapter is not None:
            chapters = [c for c in chapters if isinstance(c.get("num"), int) and int(c["num"]) <= max_chapter]

        # If no chapters detected, treat the URL itself as a single chapter.
        if not chapters and self._find_body(soup) is not None:
            chapters = [{"id": "1", "num": 1, "title": title or "Chapter 1", "url": url}]

        return {
            "source_key": self.source_key,
            "source_url": url,
            "title": title,
            "author": author,
            "synopsis": synopsis,
            "chapters": chapters,
            "generic_confidence": confidence.to_dict(),
            "source_quality_status": "needs_review" if confidence.score < 0.75 else "passed",
            "source_genre_name": None,
            "genre_slug": None,
            "source_keywords": [],
            "source_tags": [],
        }

    async def fetch_chapter(self, url: str) -> str:
        html = await self._fetch_page(url, on_retry=None)
        self._preflight_check(html, url)
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        body = self._find_body(soup)
        if body is None:
            raise SourceError("Unable to locate story content on the page.")

        self._strip_ruby_annotations(body)
        text = self._render_body(body)
        if not text:
            raise SourceError("Extracted chapter text was empty.")
        return text

    async def fetch_chapter_payload(
        self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None
    ) -> dict[str, Any]:
        html = await self._fetch_page(url, on_retry=on_retry)
        self._preflight_check(html, url)
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        body = self._find_body(soup)
        if body is None:
            raise SourceError("Unable to locate story content on the page.")

        images = extract_image_references(body, base_url=url)
        self._strip_ruby_annotations(body)
        text = self._render_body(body)
        if not text:
            raise SourceError("Extracted chapter text was empty.")
        return {"text": text, "images": images}
