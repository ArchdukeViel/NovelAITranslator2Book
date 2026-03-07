from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from src.adapters.base import BaseAdapter
from src.utils import first_text, meta_content, safe_filename, stable_digest


class GenericAdapter(BaseAdapter):
    """Conservative fallback adapter for unsupported fiction pages."""

    site = "generic"

    POSITIVE_KEYWORDS = ("article", "body", "chapter", "content", "entry", "episode", "novel", "post", "story")
    NEGATIVE_KEYWORDS = ("ad", "breadcrumb", "comment", "footer", "menu", "nav", "pager", "recommend", "share", "sidebar")

    def can_handle(self, url: str, html: str | None = None) -> bool:
        return True

    def extract_title(self, soup: BeautifulSoup) -> str:
        title = first_text(soup, ("h1", "article h1", "main h1"))
        if title:
            return title
        return meta_content(soup, prop="og:title") or meta_content(soup, name="twitter:title") or "Untitled Chapter"

    def extract_chapter_body(self, soup: BeautifulSoup) -> Tag:
        preferred = (
            "article",
            "main",
            "[role='main']",
            ".entry-content",
            ".post-content",
            ".chapter-content",
            ".novel-content",
            ".episode-body",
            ".story-body",
        )
        for selector in preferred:
            candidate = soup.select_one(selector)
            if isinstance(candidate, Tag) and self._score_candidate(candidate) > 0:
                return candidate

        best_score = float("-inf")
        best_candidate: Tag | None = None
        for candidate in soup.find_all(["article", "main", "section", "div"]):
            score = self._score_candidate(candidate)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate is not None:
            return best_candidate

        body = soup.body
        if isinstance(body, Tag):
            return body
        raise ValueError("Could not locate a generic content container.")

    def extract_metadata(self, soup: BeautifulSoup, url: str) -> dict[str, str | None]:
        author = (
            meta_content(soup, name="author")
            or meta_content(soup, prop="article:author")
            or first_text(soup, ("[rel='author']", ".author", ".byline"))
        )
        timestamps = [
            value.strip()
            for value in (node.get("datetime") for node in soup.select("time[datetime]"))
            if isinstance(value, str) and value.strip()
        ]
        return {
            "author": author,
            "chapter_number": None,
            "published_at": timestamps[0] if timestamps else None,
            "updated_at": timestamps[-1] if timestamps else None,
        }

    def derive_novel_id(self, url: str, soup: BeautifulSoup, metadata: dict[str, object]) -> str:
        title = meta_content(soup, prop="og:site_name")
        if title:
            return safe_filename(title.lower(), default="generic")
        return super().derive_novel_id(url, soup, metadata)

    def derive_chapter_id(self, url: str, soup: BeautifulSoup, metadata: dict[str, object]) -> str:
        title = self.extract_title(soup)
        candidate = safe_filename(title.lower(), default="")
        if candidate:
            return candidate
        return stable_digest(url)

    def _score_candidate(self, candidate: Tag) -> float:
        text = candidate.get_text(" ", strip=True)
        text_len = len(text)
        paragraph_count = len(candidate.find_all("p"))
        break_count = len(candidate.find_all("br"))
        link_text_len = sum(len(anchor.get_text(" ", strip=True)) for anchor in candidate.find_all("a"))
        link_density = link_text_len / max(text_len, 1)

        score = float(text_len + paragraph_count * 80 + break_count * 5)
        descriptor = " ".join(
            value.lower()
            for attr in ("class", "id")
            for value in (
                candidate.get(attr, [])
                if isinstance(candidate.get(attr), list)
                else [candidate.get(attr)] if candidate.get(attr) else []
            )
            if isinstance(value, str)
        )
        if any(keyword in descriptor for keyword in self.POSITIVE_KEYWORDS):
            score += 200
        if any(keyword in descriptor for keyword in self.NEGATIVE_KEYWORDS):
            score -= 400
        score -= link_density * 300
        if text_len < 80:
            score -= 500
        return score

