from __future__ import annotations

from typing import Any

import pytest

from novelai.core.errors import SourceError
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.sources.base import SourceAdapter
from novelai.sources.generic import GenericSource
from novelai.sources.quality import evaluate_chapter_quality, evaluate_metadata_quality
from novelai.sources.syosetu_ncode import SyosetuNcodeSource
from tests.conftest import create_test_fixture


class EmptyChapterSource(SourceAdapter):
    @property
    def key(self) -> str:
        return "empty_source"

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {
            "source": self.key,
            "source_key": self.key,
            "source_url": url,
            "title": "Empty Source Novel",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.test/1"}],
        }

    async def fetch_chapter(self, url: str) -> str:
        return ""

    async def fetch_chapter_payload(self, url: str, *, on_retry=None) -> dict[str, Any]:
        return {"text": "", "images": []}


def test_empty_chapter_fails_quality_gate():
    result = evaluate_chapter_quality("", source_key="syosetu_ncode")

    assert result.passed is False
    assert "chapter_text_empty" in result.errors


def test_nav_menu_heavy_text_fails_or_warns():
    result = evaluate_chapter_quality(
        "Home\nLogin\nRegister\nSearch\nProfile\nNext\nPrevious\nComments",
        source_key="generic",
    )

    assert "chapter_navigation_boilerplate" in result.errors or "chapter_navigation_boilerplate" in result.warnings


def test_age_gate_detection_fails_quality_gate():
    result = evaluate_chapter_quality(
        "年齢確認 18歳未満の方は閲覧できません over18 ageauth",
        source_key="novel18_syosetu",
    )

    assert result.passed is False
    assert "age_gate" in result.errors


def test_duplicate_chapter_url_warns_metadata_quality():
    result = evaluate_metadata_quality(
        {
            "source": "syosetu_ncode",
            "source_key": "syosetu_ncode",
            "source_url": "https://ncode.syosetu.com/n1234ab/",
            "title": "Valid Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "One", "url": "https://ncode.syosetu.com/n1234ab/1/"},
                {"id": "2", "num": 2, "title": "Two", "url": "https://ncode.syosetu.com/n1234ab/1/"},
            ],
        },
        source_key="syosetu_ncode",
        novel_id="n1234ab",
    )

    assert result.passed is True
    assert "metadata_duplicate_chapter_url" in result.warnings


def test_valid_dedicated_source_quality_passes():
    metadata = evaluate_metadata_quality(
        {
            "source": "syosetu_ncode",
            "source_key": "syosetu_ncode",
            "source_url": "https://ncode.syosetu.com/n1234ab/",
            "title": "Valid Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "One", "url": "https://ncode.syosetu.com/n1234ab/1/"}
            ],
        },
        source_key="syosetu_ncode",
        novel_id="n1234ab",
    )
    chapter = evaluate_chapter_quality(
        "これは有効な本文です。" * 20,
        source_key="syosetu_ncode",
    )

    assert metadata.passed is True
    assert metadata.errors == []
    assert chapter.passed is True
    assert "age_gate" not in chapter.errors


@pytest.mark.asyncio
async def test_generic_low_confidence_toc_marks_needs_review(monkeypatch):
    html = """
    <html>
      <head><title>Fallback Page</title></head>
      <body>
        <main>
          <a href="/login">Login</a>
          <a href="/profile">Profile</a>
          <a href="/search">Search</a>
          <a href="/tags">Tags</a>
        </main>
      </body>
    </html>
    """
    source = GenericSource()

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        return html

    monkeypatch.setattr(source, "_fetch_page", fake_fetch_page)

    metadata = await source.fetch_metadata("https://example.test/novel")

    assert metadata["source_quality_status"] == "needs_review"
    assert metadata["generic_confidence"]["score"] < 0.75
    assert "generic_low_confidence" in metadata["generic_confidence"]["warnings"]


def test_syosetu_age_gate_html_is_classified_before_body_selector_error():
    source = SyosetuNcodeSource()

    with pytest.raises(SourceError, match=r"age gate|auth redirect"):
        source._parse_chapter_payload(
            "<html><body>redirect/ageauth/ 年齢確認 18歳未満 over18</body></html>",
            "https://novel18.syosetu.com/n1234ab/1/",
        )


@pytest.mark.asyncio
async def test_crawler_quality_gate_prevents_empty_chapter_save():
    fixture = create_test_fixture()
    try:
        source = EmptyChapterSource()
        orchestrator = NovelOrchestrationService(
            storage=fixture.storage,
            translation=fixture.translation_service,
            source_factory=lambda key: source,
            settings_service=fixture.settings_service,
            translation_cache=fixture.cache,
            usage_service=fixture.usage_service,
        )
        await orchestrator.scrape_metadata(
            source_key=source.key,
            novel_id="empty_source_novel",
            source_identifier="https://example.test/novel",
        )

        result = await orchestrator.scrape_chapters(
            source_key=source.key,
            novel_id="empty_source_novel",
            chapters="1",
        )

        # Empty chapter is recorded as a failure, not a raised exception
        assert result["failed"] == 1
        assert result["failures"][0]["error_type"] == "SourceError"
        assert "chapter_text_empty" in result["failures"][0]["error_message"]

        # No chapter content saved
        assert fixture.storage.load_chapter("empty_source_novel", "1") is None
    finally:
        fixture.cleanup()
