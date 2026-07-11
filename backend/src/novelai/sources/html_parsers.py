from __future__ import annotations

from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag


class HTMLParserMixin:
    """Shared HTML extraction helpers used by source adapters.

    Provide small, well-tested extraction utilities to avoid repeating the
    same selector/meta logic across multiple adapters.
    """

    @staticmethod
    def extract_title(soup: BeautifulSoup, selectors: Iterable[str]) -> str | None:
        for selector in selectors:
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
    def extract_author(soup: BeautifulSoup, selectors: Iterable[str]) -> str | None:
        for selector in selectors:
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
