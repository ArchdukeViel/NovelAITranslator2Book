from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.adapters.base import BaseAdapter
from src.utils import domain_for_url, meta_content


class KakuyomuAdapter(BaseAdapter):
    """Adapter for Kakuyomu reading pages."""

    site = "kakuyomu"
    domains = ("kakuyomu.jp",)
    WORK_PATH_PATTERN = re.compile(r"/works/([^/?#]+)(?:/|$)")
    EPISODE_PATH_PATTERN = re.compile(r"/works/([^/]+)/episodes/([^/?#]+)")

    def can_handle(self, url: str, html: str | None = None) -> bool:
        if domain_for_url(url) == "kakuyomu.jp":
            return True
        if html is None:
            return False
        soup = BeautifulSoup(html, "lxml")
        return soup.select_one(".widget-episodeBody") is not None or soup.select_one(".js-episode-body") is not None

    def extract_title(self, soup: BeautifulSoup) -> str:
        selectors = (
            ".widget-episodeTitle",
            "h1#contentMain-title",
            "h1[itemprop='name']",
            "header h1",
        )
        title = self._first_text(soup, selectors)
        if title:
            return title
        return meta_content(soup, prop="og:title") or "Untitled Kakuyomu Chapter"

    def extract_chapter_body(self, soup: BeautifulSoup) -> Tag:
        selectors = (
            ".widget-episodeBody",
            ".js-episode-body",
            "[data-episode-body]",
            "article .widget-episodeBody",
        )
        for selector in selectors:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                return node
        raise ValueError("Could not locate Kakuyomu chapter body.")

    def extract_metadata(self, soup: BeautifulSoup, url: str) -> dict[str, str | None]:
        author = self._first_text(
            soup,
            (
                ".widget-authorName",
                "[itemprop='author']",
                "[rel='author']",
            ),
        ) or meta_content(soup, name="author")
        time_nodes = [node.get("datetime") for node in soup.select("time[datetime]")]
        timestamps = [value.strip() for value in time_nodes if isinstance(value, str) and value.strip()]
        return {
            "author": author,
            "chapter_number": self._chapter_number_from_title(self.extract_title(soup)),
            "published_at": timestamps[0] if timestamps else None,
            "updated_at": timestamps[-1] if timestamps else None,
        }

    def derive_novel_id(self, url: str, soup: BeautifulSoup, metadata: dict[str, Any]) -> str:
        match = self.EPISODE_PATH_PATTERN.search(url)
        if match:
            return match.group(1)
        match = self.WORK_PATH_PATTERN.search(url)
        if match:
            return match.group(1)
        return super().derive_novel_id(url, soup, metadata)

    def derive_chapter_id(self, url: str, soup: BeautifulSoup, metadata: dict[str, Any]) -> str:
        match = self.EPISODE_PATH_PATTERN.search(url)
        if match:
            return match.group(2)
        return super().derive_chapter_id(url, soup, metadata)

    def _chapter_number_from_title(self, title: str) -> str | None:
        match = re.match(r"^\D*(\d+)", title)
        return match.group(1) if match else None
