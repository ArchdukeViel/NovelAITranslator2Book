"""Dummy source adapter for e2e integration tests.

Reads a static HTML fixture and returns metadata + chapter content
conforming to the SourceAdapter interface. No HTTP requests, no
external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from novelai.sources.base import SourceAdapter

FIXTURE_DIR = Path(__file__).resolve().parent / "test_novel"
HTML_PATH = FIXTURE_DIR / "index.html"


class DummySource(SourceAdapter):
    """Self-contained source adapter backed by a static HTML fixture."""

    source_key = "dummy-e2e"

    def can_handle(self, identifier_or_url: str) -> bool:
        return identifier_or_url == "dummy://test-novel"

    async def fetch_metadata(
        self, url: str, *, max_chapter: int | None = None
    ) -> dict[str, Any]:
        soup = self._load()
        chapters: list[dict[str, Any]] = []
        for el in soup.select(".chapter"):
            ch_id_str = el.get("id", "")
            # Crawler expects integer chapter IDs
            ch_id = int(str(ch_id_str)) if str(ch_id_str).isdigit() else len(chapters) + 1
            title_el = el.find("h2")
            title = title_el.get_text(strip=True) if title_el else ""
            chapters.append({
                "id": ch_id,
                "num": len(chapters) + 1,
                "title": title,
                # http:// scheme is required by validate_safe_url
                "url": f"http://dummy-e2e.chapter/{ch_id}",
            })
        return {
            "title": "テスト小説",
            "source_url": url,
            "language": "ja",
            "origin_type": "url",
            "chapters": chapters,
        }

    async def fetch_chapter(self, url: str) -> str:
        # url is http://dummy-e2e.chapter/{id}
        ch_id = url.rsplit("/", 1)[-1]
        soup = self._load()
        ch = soup.find(id=ch_id)
        if ch is None:
            raise ValueError(f"Chapter {ch_id} not found in fixture (url={url})")
        paragraphs = [p.get_text(strip=True) for p in ch.find_all("p")]
        return "\n\n".join(paragraphs)
        paragraphs = [p.get_text(strip=True) for p in ch.find_all("p")]
        return "\n\n".join(paragraphs)

    def _load(self) -> BeautifulSoup:
        with open(HTML_PATH, encoding="utf-8") as f:
            return BeautifulSoup(f.read(), "html.parser")
