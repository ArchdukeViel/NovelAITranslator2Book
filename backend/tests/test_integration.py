"""Integration tests for the full pipeline."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.logging_config import setup_logging
from novelai.providers.base import TranslationProvider
from novelai.runtime.bootstrap import bootstrap
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.pipeline import PipelineStageError, TranslationPipeline
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.post_process import PostProcessStage
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.scheduler import SchedulerPausedError
from novelai.translation.service import TranslationService
from tests.conftest import (
    create_test_fixture,
)

pytestmark = pytest.mark.slow


class FallbackPipelineProvider:
    def __init__(self, key: str) -> None:
        self._key = key
        self.models_seen: list[str | None] = []

    @property
    def key(self) -> str:
        return self._key

    def available_models(self) -> list[str]:
        if self.key == "gemini":
            return ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
        return ["google/gemma-4-31b-it"]

    async def translate(self, prompt: str, model: str | None = None, **kwargs: object) -> dict[str, object]:
        self.models_seen.append(model)
        if self.key == "gemini":
            raise ProviderError(
                code=ProviderErrorCode.QUOTA_EXHAUSTED,
                provider_key="gemini",
                provider_model=model or "gemini-3.1-flash-lite",
                message="Gemini daily quota exceeded",
            )
        return {"text": f"[{model}] {prompt}", "metadata": {"usage": {"total_tokens": 7}}}


class TraceFailingProvider(TranslationProvider):
    @property
    def key(self) -> str:
        return "mock"

    def available_models(self) -> list[str]:
        return ["mock-1.0"]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        raise ProviderError(
            code=ProviderErrorCode.RATE_LIMITED,
            provider_key="mock",
            provider_model=model or "mock-1.0",
            message="model is cooling down",
            retry_after_seconds=21,
        )


@pytest.fixture
def integration_fixture():
    """Create integration test fixture."""
    fixture = create_test_fixture()
    yield fixture
    fixture.cleanup()


def _seed_trace_chapter(fixture: Any, novel_id: str = "trace_novel") -> None:
    fixture.storage.save_metadata(
        novel_id,
        {
            "novel_id": novel_id,
            "title": "Trace Novel",
            "source_key": "mock_source",
            "source_language": "Japanese",
            "chapters": [
                {
                    "id": "1",
                    "num": 1,
                    "title": "Chapter 1",
                    "url": f"http://example.com/{novel_id}/1",
                }
            ],
        },
    )
    fixture.storage.save_chapter(
        novel_id,
        "1",
        "First paragraph.\n\nSecond paragraph.",
        title="Chapter 1",
        source_key="mock_source",
        source_url=f"http://example.com/{novel_id}/1",
    )


def _trace_orchestrator(fixture: Any, provider: TranslationProvider | None = None) -> NovelOrchestrationService:
    pipeline = TranslationPipeline(
        stages=[
            FetchStage(),
            ParseStage(),
            SmartSegmentStage(),
            TranslateStage(
                provider_factory=lambda key: provider or fixture.mock_provider,
                cache=fixture.cache,
                settings_service=fixture.settings_service,
                usage_service=fixture.usage_service,
            ),
            PostProcessStage(glossary=fixture.mock_glossary),
        ]
    )
    return NovelOrchestrationService(
        storage=fixture.storage,
        translation=TranslationService(pipeline=pipeline),
        source_factory=lambda key: fixture.mock_source,
        settings_service=fixture.settings_service,
        translation_cache=fixture.cache,
        usage_service=fixture.usage_service,
    )


async def _run_trace_failure(
    fixture: Any,
    orchestrator: NovelOrchestrationService,
    *,
    job_id: str,
) -> list[dict[str, Any]]:
    _seed_trace_chapter(fixture)
    with pytest.raises(RuntimeError):
        await orchestrator.translate_chapters(
            source_key="mock_source",
            novel_id="trace_novel",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            job_id=job_id,
            activity_id=f"activity_{job_id}",
            force=True,
            source_language="Japanese",
            target_language="English",
            skip_glossary_gate=True,
        )
    return fixture.storage.list_pipeline_events(
        job_id=job_id,
        novel_id="trace_novel",
        chapter_id="1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage_cls", "expected_stage"),
    [
        (FetchStage, "FetchStage"),
        (ParseStage, "ParseStage"),
        (SmartSegmentStage, "SmartSegmentStage"),
    ],
)
async def test_orchestration_failure_persists_actual_failed_stage(
    integration_fixture,
    monkeypatch,
    stage_cls,
    expected_stage,
):
    fixture = integration_fixture

    async def fail_stage(self, context):
        raise RuntimeError(f"{expected_stage} exploded")

    monkeypatch.setattr(stage_cls, "run", fail_stage)

    events = await _run_trace_failure(
        fixture,
        _trace_orchestrator(fixture),
        job_id=f"job_{expected_stage.lower()}",
    )

    failed_events = [event for event in events if event.get("status_after") == "failed"]
    assert failed_events
    assert failed_events[-1]["stage_name"] == expected_stage
    assert failed_events[-1]["message"] == f"{expected_stage} exploded"


@pytest.mark.asyncio
async def test_orchestration_provider_failure_persists_translate_stage(integration_fixture):
    fixture = integration_fixture

    events = await _run_trace_failure(
        fixture,
        _trace_orchestrator(fixture, provider=TraceFailingProvider()),
        job_id="job_translate_provider_failure",
    )

    failed_events = [event for event in events if event.get("status_after") == "failed"]
    assert failed_events
    assert failed_events[-1]["stage_name"] == "TranslateStage"
    assert failed_events[-1]["error_code"] == ProviderErrorCode.RATE_LIMITED.value
    assert failed_events[-1]["provider_key"] == "mock"
    assert failed_events[-1]["provider_model"] == "mock-1.0"


@pytest.mark.asyncio
async def test_full_translation_pipeline(integration_fixture):
    """Test complete translation pipeline."""
    # Setup
    fixture = integration_fixture
    fixture.add_source_chapter("http://example.com/ch1", "これはテストです。\n\n次の段落です。")

    # Create pipeline
    pipeline = TranslationPipeline(
        stages=[
            FetchStage(),
            ParseStage(),
            SmartSegmentStage(),
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
    assert result.pipeline_events
    assert any(event.get("stage_name") == "TranslateStage" for event in result.pipeline_events)
    assert result.chunk_states
    first_chunk_state = next(iter(result.chunk_states.values()))
    assert first_chunk_state["provider_key"] == "mock"
    assert first_chunk_state["provider_model"] == "gemini-3.1-flash-lite"
    assert first_chunk_state["status"] == "translated"


@pytest.mark.asyncio
async def test_translation_service_integration(integration_fixture):
    """Test TranslationService with full pipeline."""
    fixture = integration_fixture
    fixture.add_source_chapter("http://example.com/ch1", "Test content for translation.")

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
async def test_translate_stage_falls_back_from_gemini_to_dummy(integration_fixture):
    fixture = integration_fixture
    gemini_provider = FallbackPipelineProvider("gemini")
    dummy_provider = FallbackPipelineProvider("dummy")
    fixture.add_source_chapter("http://example.com/fallback", "ãƒ†ã‚¹ãƒˆã§ã™ã€‚")
    fixture.settings_service.set_preferred_provider("gemini")
    fixture.settings_service.set_preferred_model("gemini-3.1-flash-lite")
    fixture.settings_service.set_api_key("gemini-key", provider_key="gemini")

    pipeline = TranslationPipeline(
        stages=[
            FetchStage(),
            ParseStage(),
            SmartSegmentStage(),
            TranslateStage(
                provider_factory=lambda key: gemini_provider if key == "gemini" else dummy_provider,  # type: ignore[arg-type]
                cache=fixture.cache,
                settings_service=fixture.settings_service,
                usage_service=fixture.usage_service,
            ),
            PostProcessStage(),
        ]
    )
    context = PipelineState(chapter_url="http://example.com/fallback", provider_key="gemini")
    context.metadata["_source_adapter"] = fixture.mock_source
    context.metadata["source_language"] = "Japanese"
    context.metadata["target_language"] = "English"

    # Scheduler tries all Gemini models before giving up (all raise QUOTA_EXHAUSTED).
    # The dummy provider is never called because the scheduler's fallback chain
    # only includes Gemini models, not the dummy provider.
    with pytest.raises(PipelineStageError) as exc_info:
        await pipeline.run(context)
    assert isinstance(exc_info.value.__cause__, SchedulerPausedError)

    assert "gemini-3.1-flash-lite" in gemini_provider.models_seen
    assert dummy_provider.models_seen == []


@pytest.mark.asyncio
async def test_translate_stage_selects_relevant_glossary_per_chunk(integration_fixture):
    fixture = integration_fixture
    fixture.add_source_chapter(
        "http://example.com/ch2",
        "英雄は剣を抜いた。\n\n魔導具が光った。",
    )

    pipeline = TranslationPipeline(
        stages=[
            FetchStage(),
            ParseStage(),
            SmartSegmentStage(target_chars=1, hard_max_chars=100),
            TranslateStage(
                provider_factory=lambda key: fixture.mock_provider,
                cache=fixture.cache,
                settings_service=fixture.settings_service,
                usage_service=fixture.usage_service,
            ),
            PostProcessStage(glossary=fixture.mock_glossary),
        ]
    )

    context = PipelineState(chapter_url="http://example.com/ch2", provider_key="mock")
    context.metadata["_source_adapter"] = fixture.mock_source
    context.metadata["source_language"] = "Japanese"
    context.metadata["target_language"] = "English"
    context.metadata["glossary_max_entries"] = 1
    context.metadata["glossary"] = [
        {"source": "英雄", "target": "hero", "status": "approved"},
        {"source": "魔導具", "target": "magic device", "status": "approved"},
    ]

    result = await pipeline.run(context)

    request = fixture.mock_provider.last_request
    assert request is not None
    assert len(request.glossary_entries) == 1
    assert request.glossary_entries[0].source == "魔導具"
    runtime_state = result.metadata.get("glossary_runtime_state")
    assert isinstance(runtime_state, list)
    assert len(runtime_state) == 2
    assert any(isinstance(item.get("context_summary"), str) and item.get("context_summary") for item in runtime_state)


@pytest.mark.asyncio
async def test_storage_with_pipeline(integration_fixture):
    """Test storage service integration with pipeline."""
    fixture = integration_fixture

    # Add test data
    fixture.add_test_metadata("novel1")
    fixture.add_test_chapters("novel1", count=5)

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

    from novelai.export.registry import available_exporters

    # Providers and sources should be registered
    available = available_exporters()
    assert "epub" in available
    # PDF exporter is deprecated (DEBT-007) and not registered.
    assert "pdf" not in available


def test_logging_integration():
    """Test logging setup integration."""
    setup_logging(log_level="INFO", use_json=False)

    import logging

    from novelai.logging_config import get_logger

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
    with pytest.raises(Exception, match="Test failure"):
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
        "source_key": "mock_source",
        "chapters": [
            {"id": str(i), "num": i, "title": f"第{i}章", "url": f"http://example.com/{novel_id}/{i}"}
            for i in range(1, 4)
        ],
    }
    fixture.storage.save_metadata(novel_id, metadata)

    for chapter_id, text in chapter_texts.items():
        fixture.storage.save_chapter(
            novel_id,
            chapter_id,
            text,
            source_key="mock_source",
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
        novel_id=novel_id,
        chapters=chapters_for_export,
        output_path=output_path,
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
