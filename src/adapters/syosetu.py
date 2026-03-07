from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.adapters.base import BaseAdapter
from src.utils import domain_for_url, meta_content


class SyosetuAdapter(BaseAdapter):
    """Adapter for Syosetu / Narou chapter pages."""

    site = "syosetu"
    domains = ("ncode.syosetu.com", "novel18.syosetu.com")

    NOVEL_ID_PATTERN = re.compile(r"/(n\d{4}[a-z]{2})(?:/|$)", re.IGNORECASE)
    CHAPTER_ID_PATTERN = re.compile(r"/(n\d{4}[a-z]{2})/(\d+)/?$", re.IGNORECASE)
    DATE_PATTERN = re.compile(r"\d{4}/\d{2}/\d{2}(?: \d{2}:\d{2})?")

    def can_handle(self, url: str, html: str | None = None) -> bool:
        host = domain_for_url(url)
        if host in self.domains:
            return True
        if html is None:
            return False
        soup = BeautifulSoup(html, "lxml")
        return soup.find(id="novel_honbun") is not None or soup.find("p", class_="novel_subtitle") is not None

    def extract_title(self, soup: BeautifulSoup) -> str:
        selectors = (
            ".p-novel__title--chapter",
            "p.novel_subtitle",
            ".p-novel__title",
            "p.novel_title",
            "h1.p-novel__title",
        )
        title = self._first_text(soup, selectors)
        if title:
            return title
        return meta_content(soup, prop="og:title") or "Untitled Syosetu Chapter"

    def extract_chapter_body(self, soup: BeautifulSoup) -> list[Tag]:
        selectors = (
            "#novel_p",
            ".p-novel__text--preface",
            "#novel_honbun",
            ".p-novel__text--body",
            ".js-novel-text",
            "#novel_a",
            ".p-novel__text--afterword",
        )
        sections: list[Tag] = []
        for selector in selectors:
            for node in soup.select(selector):
                if isinstance(node, Tag):
                    sections.append(node)
        if sections:
            return sections
        raise ValueError("Could not locate Syosetu chapter body.")

    def extract_metadata(self, soup: BeautifulSoup, url: str) -> dict[str, str | None]:
        author = self._first_text(soup, ("#novel_writername", ".p-novel__author"))
        title = self.extract_title(soup)
        number_match = re.match(r"^\D*(\d+)", title)
        text_blob = soup.get_text(" ", strip=True)
        dates = self.DATE_PATTERN.findall(text_blob)
        return {
            "author": author,
            "chapter_number": number_match.group(1) if number_match else self._chapter_number_from_url(url),
            "published_at": dates[0] if dates else None,
            "updated_at": dates[-1] if dates else None,
        }

    def derive_novel_id(self, url: str, soup: BeautifulSoup, metadata: dict[str, Any]) -> str:
        match = self.NOVEL_ID_PATTERN.search(url)
        if match:
            return match.group(1).lower()
        return super().derive_novel_id(url, soup, metadata)

    def derive_chapter_id(self, url: str, soup: BeautifulSoup, metadata: dict[str, Any]) -> str:
        match = self.CHAPTER_ID_PATTERN.search(url)
        if match:
            return match.group(2)
        return "1"

    def _chapter_number_from_url(self, url: str) -> str | None:
        match = self.CHAPTER_ID_PATTERN.search(url)
        return match.group(2) if match else None

