"""Integration tests for the full pipeline."""

import asyncio
import pytest
from pathlib import Path
import tempfile
from zipfile import ZipFile

from novelai.app.bootstrap import bootstrap
from novelai.core.chapter_state import ChapterState
from novelai.pipeline.context import PipelineState
from novelai.pipeline.pipeline import TranslationPipeline
from novelai.pipeline.stages.fetch import FetchStage
from novelai.pipeline.stages.parse import ParseStage
from novelai.pipeline.stages.segment import SegmentStage
from novelai.pipeline.stages.translate import TranslateStage
from novelai.pipeline.stages.post_process import PostProcessStage
from novelai.services.storage_service import StorageService
from novelai.services.translation_service import TranslationService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.utils.logging import setup_logging
from tests.conftest import (
    MockTranslationProvider,
    MockSourceAdapter,
    MockGlossary,
    create_test_fixture,
)


@pytest.fixture
def integration_fixture():
    """Create integration test fixture."""
    fixture = create_test_fixture()
    yield fixture
    fixture.cleanup()


@pytest.mark.asyncio
async def test_full_translation_pipeline(integration_fixture):
    """Test complete translation pipeline."""
    # Setup
    fixture = integration_fixture
    fixture.add_source_chapter(
        "http://example.com/ch1",
        "これはテストです。\n\n次の段落です。"
    )

    # Create pipeline
    pipeline = TranslationPipeline(
        stages=[
            FetchStage(),
            ParseStage(),
            SegmentStage(),
            TranslateStage(
                provider_factory=lambda key: fixture.mock_provider,
                cache=fixture.cache,
                settings_service=fixture.settings_service,
                usage_service=fixture.usage_service,
            ),
            PostProcessStage(glossary=fixture.mock_glossary),
        ]
    )

    # Run pipeline
    context = PipelineState(
        chapter_url="http://example.com/ch1",
        provider_key="mock",
    )
    context.metadata["_source_adapter"] = fixture.mock_source

    result = await pipeline.run(context)

    # Verify
    assert result.final_text is not None
    assert "[TRANSLATED]" in result.final_text
    assert fixture.mock_provider.call_count > 0


@pytest.mark.asyncio
async def test_translation_service_integration(integration_fixture):
    """Test TranslationService with full pipeline."""
    fixture = integration_fixture
    fixture.add_source_chapter(
        "http://example.com/ch1",
        "Test content for translation."
    )

    service = fixture.translation_service
    result = await service.translate_chapter(
        source_adapter=fixture.mock_source,
        chapter_url="http://example.com/ch1",
        provider_key="mock",
    )

    assert result.final_text is not None
    assert len(result.final_text) > 0


@pytest.mark.asyncio
async def test_translation_service_builds_multilingual_prompt_request(integration_fixture):
    fixture = integration_fixture
    fixture.add_source_chapter(
        "http://example.com/ch1",
        "魔導具のテストです。",
    )

    await fixture.translation_service.translate_chapter(
        source_adapter=fixture.mock_source,
        chapter_url="http://example.com/ch1",
        provider_key="mock",
        source_language="Japanese",
        target_language="Indonesian",
        glossary=[{"source": "魔導具", "target": "perangkat sihir"}],
        style_preset="fantasy",
        consistency_mode=True,
    )

    request = fixture.mock_provider.last_request

    assert request is not None
    assert request.source_language == "Japanese"
    assert request.target_language == "Indonesian"
    assert request.consistency_mode is True
    assert "Project glossary:" in request.user_prompt
    assert "perangkat sihir" in request.user_prompt
    assert "Treat fantasy and worldbuilding terminology carefully." in request.user_prompt


@pytest.mark.asyncio
async def test_storage_with_pipeline(integration_fixture):
    """Test storage service integration with pipeline."""
    fixture = integration_fixture
    
    # Add test data
    fixture.add_test_metadata("novel1")
    chapters = fixture.add_test_chapters("novel1", count=5)

    # Query storage
    progress = fixture.storage.get_scraping_progress("novel1")
    assert progress["total"] == 5
    assert progress["success_rate"] == 100.0

    ready_chapters = fixture.storage.get_chapters_ready_for_export("novel1")
    assert len(ready_chapters) == 5


@pytest.mark.asyncio
async def test_state_machine_with_storage(integration_fixture):
    """Test state machine integration with storage."""
    fixture = integration_fixture

    # Save chapter and transition states
    fixture.storage.save_chapter("novel1", "ch1", "Test content")
    fixture.storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    
    assert fixture.storage.query_chapters("novel1").by_state(ChapterState.SCRAPED).count() == 1

    fixture.storage.update_chapter_state("novel1", "ch1", ChapterState.PARSED)
    
    assert fixture.storage.query_chapters("novel1").by_state(ChapterState.PARSED).count() == 1
    assert fixture.storage.query_chapters("novel1").by_state(ChapterState.SCRAPED).count() == 0


@pytest.mark.asyncio
async def test_query_builder_with_complex_filters(integration_fixture):
    """Test query builder with complex filtering."""
    fixture = integration_fixture

    # Add chapters with different states and errors
    fixture.storage.update_chapter_state("novel1", "ch1", ChapterState.SCRAPED)
    fixture.storage.update_chapter_state("novel1", "ch2", ChapterState.PARSED)
    fixture.storage.update_chapter_state("novel1", "ch3", ChapterState.TRANSLATED)
    fixture.storage.update_chapter_state("novel1", "ch4", ChapterState.TRANSLATED, error="Error 1")
    fixture.storage.update_chapter_state("novel1", "ch5", ChapterState.EXPORTED)

    # Complex query
    results = (
        fixture.storage.query_chapters("novel1")
        .no_errors()
        .by_states([ChapterState.PARSED, ChapterState.TRANSLATED, ChapterState.EXPORTED])
        .sort_by("state")
        .paginate(page=1, per_page=10)
        .execute()
    )

    assert len(results) == 3
    assert all(r.error_count == 0 for r in results)


@pytest.mark.asyncio
async def test_bootstrap_and_registry(integration_fixture):
    """Test bootstrap and provider registry."""
    bootstrap()

    from novelai.providers.registry import get_provider
    from novelai.sources.registry import get_source
    from novelai.export.registry import available_exporters

    # Providers and sources should be registered
    available = available_exporters()
    assert "epub" in available
    # PDF exporter not registered (not yet implemented)


def test_logging_integration():
    """Test logging setup integration."""
    setup_logging(log_level="INFO", use_json=False)
    
    import logging
    from novelai.utils.logging import get_logger

    logger = get_logger("test")
    assert logger is not None
    assert isinstance(logger, logging.Logger)


@pytest.mark.asyncio
async def test_provider_failure_recovery(integration_fixture):
    """Test handling provider failures."""
    fixture = integration_fixture
    
    # Set provider to fail
    fixture.set_provider_failure(True, "Test failure")
    
    # Should raise exception
    with pytest.raises(Exception):
        await fixture.mock_provider.translate("test")
    
    # Reset and verify it works again
    fixture.set_provider_failure(False)
    result = await fixture.mock_provider.translate("test")
    assert "[TRANSLATED]" in result["text"]


def test_mock_glossary_integration(integration_fixture):
    """Test mock glossary functionality."""
    fixture = integration_fixture
    
    fixture.mock_glossary.add_term("original", "REPLACED")
    result = fixture.mock_glossary.translate("Use original term here")
    
    assert "REPLACED" in result


def test_storage_stats(integration_fixture):
    """Test storage statistics."""
    fixture = integration_fixture
    
    fixture.add_test_metadata("novel1")
    fixture.add_test_chapters("novel1", count=3)
    
    stats = fixture.get_storage_stats()
    
    assert stats["novel_count"] == 1
    assert stats["data_dir_size"] > 0
    assert "novel1" in stats["novels"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# Full pipeline integration test: scrape → translate → export EPUB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_scrape_translate_export(integration_fixture):
    """End-to-end: mock-scrape chapters, translate them, export to EPUB."""
    fixture = integration_fixture
    novel_id = "test_novel_e2e"

    # 1. Simulate scraping: save metadata + raw chapters via storage.
    chapter_texts = {
        "1": "第一章の内容。\n\nこれは二段落目です。",
        "2": "第二章の冒険が始まった。\n\n勇者は旅立った。",
        "3": "最終章。\n\n物語は幕を閉じる。",
    }
    metadata = {
        "novel_id": novel_id,
        "title": "テスト小説",
        "author": "テスト作者",
        "source": "mock_source",
        "chapters": [
            {"id": str(i), "num": i, "title": f"第{i}章", "url": f"http://example.com/{novel_id}/{i}"}
            for i in range(1, 4)
        ],
    }
    fixture.storage.save_metadata(novel_id, metadata)

    for chapter_id, text in chapter_texts.items():
        fixture.storage.save_chapter(
            novel_id, chapter_id, text, source_key="mock_source",
        )

    stored_ids = fixture.storage.list_stored_chapters(novel_id)
    assert sorted(stored_ids) == ["1", "2", "3"]

    # 2. Translate each chapter through the real pipeline with mock provider.
    for chapter_id in chapter_texts:
        raw = fixture.storage.load_chapter(novel_id, chapter_id)
        assert raw is not None
        result = await fixture.translation_service.translate_chapter(
            source_adapter=fixture.mock_source,
            chapter_url=f"http://example.com/{novel_id}/{chapter_id}",
            provider_key="mock",
        )
        assert result.final_text is not None
        fixture.storage.save_translated_chapter(
            novel_id,
            chapter_id,
            result.final_text,
            provider="mock",
            model="mock-1.0",
        )

    translated_ids = fixture.storage.list_translated_chapters(novel_id)
    assert sorted(translated_ids) == ["1", "2", "3"]

    # 3. Export to EPUB.
    from novelai.export.epub_exporter import EPUBExporter

    meta = fixture.storage.load_metadata(novel_id)
    assert meta is not None

    chapters_for_export = []
    for chap in meta.get("chapters", []):
        chap_id = str(chap.get("id"))
        translated = fixture.storage.load_translated_chapter(novel_id, chap_id)
        assert translated is not None
        chapters_for_export.append(
            {
                "title": chap.get("title"),
                "text": translated.get("text"),
                "images": fixture.storage.load_chapter_export_images(novel_id, chap_id),
            }
        )

    output_path = str(fixture.data_dir / f"{novel_id}.epub")
    exporter = EPUBExporter()
    result_path = exporter.export(
        novel_id=novel_id, chapters=chapters_for_export, output_path=output_path,
    )

    assert Path(result_path).exists()
    assert Path(result_path).stat().st_size > 0

    # 4. Verify EPUB contents.
    with ZipFile(result_path) as epub:
        names = epub.namelist()
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/nav.xhtml" in names
        # One XHTML per chapter
        chapter_xhtml_files = [n for n in names if n.startswith("OEBPS/chapters/")]
        assert len(chapter_xhtml_files) == 3

        # Spot-check that translated text appears in a chapter file
        first_chapter_html = epub.read(chapter_xhtml_files[0]).decode("utf-8")
        assert "TRANSLATED" in first_chapter_html
