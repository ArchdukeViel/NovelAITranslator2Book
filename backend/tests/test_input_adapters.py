from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from novelai.inputs.web import WebDocumentAdapter


class _StubWebSource:
    source_key = "stub"

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        return {
            "title": "Web Title",
            "author": "Web Author",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "title": "One", "url": f"{url}/1"},
            ],
        }

    async def fetch_chapter_payload(self, url: str, *, on_retry=None) -> dict[str, object]:
        return {"text": "Body", "images": []}


def test_web_adapter_accepts_only_http_urls() -> None:
    adapter = WebDocumentAdapter()

    assert adapter.probe("https://example.com/story") is True
    assert adapter.probe("http://example.com/story") is True
    assert adapter.probe("C:/books/story.txt") is False
    assert adapter.probe("story.epub") is False


@pytest.mark.asyncio
async def test_web_adapter_wraps_registered_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = MagicMock()
    registry.get_adapter.return_value = _StubWebSource()
    monkeypatch.setattr("novelai.inputs.web.get_registry", lambda: registry)
    adapter = WebDocumentAdapter()

    document = await adapter.import_document("https://example.com/story")

    assert document.title == "Web Title"
    assert document.origin_type == "url"
    assert document.origin_uri_or_path == "https://example.com/story"
    assert document.document_type == "web_novel"
    assert document.units[0].text == "Body"
