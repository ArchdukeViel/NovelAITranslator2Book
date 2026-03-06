from __future__ import annotations

from typing import Any

from novelai.sources.base import SourceAdapter


class ExampleSource(SourceAdapter):
    """A simple example source adapter that returns hard-coded content."""

    @property
    def key(self) -> str:
        return "example"

    async def fetch_metadata(self, url: str) -> dict[str, Any]:
        return {
            "title": "Example Novel",
            "author": "Demo Author",
            "chapters": [
                {"id": "ch1", "title": "Chapter 1", "url": url + "#1"},
                {"id": "ch2", "title": "Chapter 2", "url": url + "#2"},
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return "This is a placeholder chapter text for URL: " + url


