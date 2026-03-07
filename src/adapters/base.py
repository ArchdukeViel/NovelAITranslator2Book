from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

import httpx
from bs4 import BeautifulSoup, Tag
from bs4.element import PageElement

from src.clean import clean_chapter_html
from src.utils import domain_for_url, first_text, meta_content, safe_filename, stable_digest


class BaseAdapter(ABC):
    """Base interface for site-specific chapter extraction adapters."""

    site = "generic"
    domains: tuple[str, ...] = ()

    def can_handle(self, url: str, html: str | None = None) -> bool:
        host = domain_for_url(url)
        return host in self.domains

    @abstractmethod
    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the chapter title from a parsed page."""

    @abstractmethod
    def extract_chapter_body(self, soup: BeautifulSoup) -> Tag | Sequence[PageElement] | str:
        """Extract the chapter-body node(s) before generic cleaning."""

    def extract_metadata(self, soup: BeautifulSoup, url: str) -> dict[str, str | None]:
        """Extract author/date metadata. Adapters can override as needed."""
        return {
            "author": meta_content(soup, name="author"),
            "chapter_number": None,
            "published_at": None,
            "updated_at": None,
        }

    def normalize_chapter_html(
        self,
        node_or_nodes: Tag | Sequence[PageElement] | str,
        *,
        base_url: str | None = None,
    ) -> str:
        fragment = clean_chapter_html(node_or_nodes, base_url=base_url)
        if not fragment.strip():
            raise ValueError(f"{self.__class__.__name__} produced an empty chapter fragment.")
        return fragment

    def derive_novel_id(
        self,
        url: str,
        soup: BeautifulSoup,
        metadata: dict[str, Any],
    ) -> str:
        parsed = httpx.URL(url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return safe_filename(path_parts[0], default=self.site)
        return safe_filename(parsed.host or self.site, default=self.site)

    def derive_chapter_id(
        self,
        url: str,
        soup: BeautifulSoup,
        metadata: dict[str, Any],
    ) -> str:
        parsed = httpx.URL(url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2:
            return safe_filename(path_parts[-1], default="chapter")
        return stable_digest(url)

    def build_ids(
        self,
        url: str,
        soup: BeautifulSoup,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        return (
            self.derive_novel_id(url, soup, metadata),
            self.derive_chapter_id(url, soup, metadata),
        )

    @staticmethod
    def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
        return first_text(soup, selectors)

