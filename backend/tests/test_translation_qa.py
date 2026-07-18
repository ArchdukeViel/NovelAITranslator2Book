from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.providers.base import TranslationProvider
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.translation.pipeline.context import PipelineState, TranslationChunk
from novelai.translation.pipeline.pipeline import PipelineStageError, TranslationPipeline
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.post_process import PostProcessStage
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage
from novelai.translation.qa import (
    TranslationQAError,
    evaluate_translation_quality,
    normalized_translation_text,
)
from novelai.translation.service import TranslationService
from tests.conftest import create_test_fixture


def _chunk(
    *,
    chapter_ids: list[str] | None = None,
    paragraph_refs: list[tuple[str, str]] | None = None,
) -> TranslationChunk:
    refs = paragraph_refs or [("chapter_001", "p0001"), ("chapter_001", "p0002")]
    chapters = chapter_ids or list(dict.fromkeys(chapter_id for chapter_id, _ in refs))
    paragraph_ids = [paragraph_id for _, paragraph_id in refs]
    lines: list[str] = []
    current_chapter: str | None = None
    for chapter_id, paragraph_id in refs:
        if chapter_id != current_chapter:
            lines.append(f"[CHAPTER {chapter_id}]")
            current_chapter = chapter_id
        lines.append(f"[P {paragraph_id}]")
        lines.append(f"Source paragraph {chapter_id}/{paragraph_id}.")
    return TranslationChunk(
        chunk_id="c0001",
        novel_id="novel1",
        chapter_ids=chapters,
        paragraph_ids=paragraph_ids,
        source_text="\n".join(lines),
        char_count=120,
        paragraph_refs=refs,
    )


def test_translation_qa_rejects_empty_output():
    result = evaluate_translation_quality(source_text="Source text", translated_text="")

    assert not result.passed
    assert "translation_empty" in result.errors


def test_translation_qa_rejects_identical_source_target():
    result = evaluate_translation_quality(source_text="Same text", translated_text="Same text")

    assert not result.passed
    assert "translation_same_as_source" in result.errors


def test_translation_qa_rejects_missing_image_placeholder():
    result = evaluate_translation_quality(
        source_text="[Image: cover]\n\nA scene begins.",
        translated_text="A scene begins.",
    )

    assert not result.passed
    assert "image_placeholder_missing" in result.errors


def test_translation_qa_rejects_missing_text_placeholder():
    result = evaluate_translation_quality(
        source_text="Hello {CHARACTER_NAME}.",
        translated_text="Hello.",
    )

    assert not result.passed
    assert "placeholder_missing" in result.errors


def test_translation_qa_rejects_missing_scene_break():
    result = evaluate_translation_quality(
        source_text="Before.\n\n***\n\nAfter.",
        translated_text="Before.\n\nAfter.",
    )

    assert not result.passed
    assert "scene_break_missing" in result.errors


def test_translation_qa_rejects_very_short_suspicious_output():
    result = evaluate_translation_quality(
        source_text=" ".join(["source"] * 80),
        translated_text="Ok.",
    )

    assert not result.passed
    assert "translation_too_short" in result.errors


def test_translation_qa_accepts_normal_plain_text_with_single_chapter_warning():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text="Chapter one.\n\nThe scene continues.",
        chunk=chunk,
    )

    assert result.passed
    assert "paragraph_mapping_unavailable" in result.warnings


def test_translation_qa_accepts_complete_paragraph_map():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"One.\\n\\nTwo.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p0002","translated_text":"Two."}'
            "]}"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert result.passed
    assert result.errors == []


def test_translation_qa_extracts_fenced_structured_json():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '```json\n{"translated_text":"One.\\n\\nTwo.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p0002","translated_text":"Two."}'
            "]}\n```"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert result.passed
    assert result.errors == []


def test_translation_qa_extracts_commentary_with_single_structured_json_object():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            'Here is the JSON:\n{"translated_text":"One.\\n\\nTwo.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p0002","translated_text":"Two."}'
            "]}\nDone."
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert result.passed
    assert result.errors == []


def test_translation_qa_rejects_ambiguous_multiple_structured_json_objects():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"One.","paragraph_map":[]}\n'
            '{"translated_text":"Two.","paragraph_map":[]}'
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert not result.passed
    assert "structured_output_required" in result.errors[0]
    assert "multiple parseable objects" in result.errors[0]


def test_translation_qa_missing_paragraph_id_fails():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"One.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."}'
            "]}"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert not result.passed
    assert "paragraph_missing" in result.errors
    diagnostics = result.to_dict()["diagnostics"]["paragraph_map"]
    assert diagnostics["expected_count"] == 2
    assert diagnostics["output_count"] == 1
    assert diagnostics["missing_ids"] == ["chapter_001:p0002"]
    assert diagnostics["unexpected_ids"] == []


def test_translation_qa_reports_final_marker_omission_without_text_excerpts():
    refs = [("chapter_001", f"p{index:04d}") for index in range(1, 110)]
    chunk = _chunk(paragraph_refs=refs)
    translated = "\n".join(
        line
        for index in range(1, 109)
        for line in (f"[P p{index:04d}]", "Translated paragraph.")
    )

    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=translated,
        chunk=chunk,
    )

    assert not result.passed
    assert "paragraph_missing" in result.errors
    diagnostics = result.to_dict()["diagnostics"]["marker_coverage"]
    assert diagnostics["expected_count"] == 109
    assert diagnostics["output_count"] == 108
    assert diagnostics["missing_ids"] == ["chapter_001:p0109"]
    assert diagnostics["unexpected_ids"] == []
    assert "Translated paragraph." not in str(diagnostics)


def test_translation_qa_duplicate_paragraph_id_fails():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"One. Duplicate.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"Duplicate."}'
            "]}"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert not result.passed
    assert "paragraph_duplicate" in result.errors
    diagnostics = result.to_dict()["diagnostics"]["paragraph_map"]
    assert diagnostics["duplicate_ids"] == ["chapter_001:p0001"]


def test_translation_qa_unexpected_paragraph_id_fails():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"One. Two. Extra.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p0002","translated_text":"Two."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p9999","translated_text":"Extra."}'
            "]}"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert not result.passed
    assert "paragraph_unexpected" in result.errors
    diagnostics = result.to_dict()["diagnostics"]["paragraph_map"]
    assert diagnostics["unexpected_ids"] == ["chapter_001:p9999"]


def test_translation_qa_structured_paragraph_order_mismatch_fails():
    chunk = _chunk()
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"Two. One.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0002","translated_text":"Two."},'
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."}'
            "]}"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert not result.passed
    assert "paragraph_order_mismatch" in result.errors


def test_translation_qa_accepts_multi_chapter_mapping():
    chunk = _chunk(
        chapter_ids=["chapter_001", "chapter_002"],
        paragraph_refs=[("chapter_001", "p0001"), ("chapter_002", "p0001")],
    )
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text=(
            '{"translated_text":"One. Two.","paragraph_map":['
            '{"chapter_id":"chapter_001","paragraph_id":"p0001","translated_text":"One."},'
            '{"chapter_id":"chapter_002","paragraph_id":"p0001","translated_text":"Two."}'
            "]}"
        ),
        chunk=chunk,
        structured_output=True,
    )

    assert result.passed
    assert "chapter_mapping_invalid" not in result.errors


def test_translation_qa_rejects_unsafe_multi_chapter_plain_text():
    chunk = _chunk(
        chapter_ids=["chapter_001", "chapter_002"],
        paragraph_refs=[("chapter_001", "p0001"), ("chapter_002", "p0001")],
    )
    result = evaluate_translation_quality(
        source_text=chunk.source_text,
        translated_text="One translated blob without mapping.",
        chunk=chunk,
    )

    assert not result.passed
    assert "chapter_mapping_invalid" in result.errors


def test_translation_qa_rejects_provider_refusal_and_error_text():
    refusal = evaluate_translation_quality(
        source_text="Translate this chapter.",
        translated_text="As an AI language model, I can't comply with this request.",
    )
    provider_error = evaluate_translation_quality(
        source_text="Translate this chapter.",
        translated_text="RESOURCE_EXHAUSTED: quota exceeded",
    )

    assert "provider_refusal_detected" in refusal.errors
    assert "provider_error_text_detected" in provider_error.errors


def test_translation_qa_allows_refusal_like_story_prose():
    source_text = "\n".join(
        [
            "[CHAPTER 2]",
            "[P p0001]",
            "兄たちは外で私と歩くのを嫌がった。",
            "[P p0002]",
            "それでも私は平気な顔をしていた。",
        ]
    )
    translated_text = "\n".join(
        [
            "[CHAPTER 2]",
            "[P p0001]",
            "My brothers would refuse to walk next to me in public.",
            "[P p0002]",
            "Even so, I kept a calm expression.",
        ]
    )

    result = evaluate_translation_quality(source_text=source_text, translated_text=translated_text)

    assert result.passed
    assert "provider_refusal_detected" not in result.errors


@pytest.mark.asyncio
async def test_translation_qa_stage_marks_failed_chunk_state():
    chunk = _chunk()
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.translation_chunks = [chunk]
    context.chunks = [chunk.source_text]
    context.translations = [""]
    context.chunk_states = {
        "c0001": {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001", "p0002"],
            "status": "translated",
        }
    }

    with pytest.raises(TranslationQAError):
        await TranslationQAStage().run(context)

    assert context.chunk_states["c0001"]["status"] == "qa_failed"
    assert context.chunk_states["c0001"]["error_code"] == "translation_empty"
    assert context.metadata["qa_result"]["passed"] is False
    assert "qa_diagnostics" in context.chunk_states["c0001"]


def test_translation_qa_normalizes_structured_output_text():
    text = normalized_translation_text(
        '{"translated_text":"Final translated text.","paragraph_map":[]}'
    )

    assert text == "Final translated text."


class EmptyOutputProvider(TranslationProvider):
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
        return {"text": "", "metadata": {}}


@pytest.mark.asyncio
async def test_orchestration_does_not_save_final_translation_when_qa_fails():
    fixture = create_test_fixture()
    try:
        novel_id = "qa_no_save"
        fixture.storage.save_metadata(
            novel_id,
            {
                "novel_id": novel_id,
                "title": "QA No Save",
                "source": "mock_source",
                "source_language": "Japanese",
                "chapters": [
                    {"id": "1", "num": 1, "title": "Chapter 1", "url": "http://example.com/qa/1"}
                ],
            },
        )
        fixture.storage.save_chapter(
            novel_id,
            "1",
            "Source paragraph one.\n\nSource paragraph two.",
            source_key="mock_source",
            source_url="http://example.com/qa/1",
        )
        pipeline = TranslationPipeline(
            stages=[
                FetchStage(),
                ParseStage(),
                SmartSegmentStage(),
                TranslateStage(
                    provider_factory=lambda key: EmptyOutputProvider(),
                    cache=fixture.cache,
                    settings_service=fixture.settings_service,
                    usage_service=fixture.usage_service,
                    storage=fixture.storage,
                ),
                TranslationQAStage(),
                PostProcessStage(),
            ]
        )
        orchestrator = NovelOrchestrationService(
            storage=fixture.storage,
            translation=TranslationService(pipeline=pipeline),
            source_factory=lambda key: fixture.mock_source,
            settings_service=fixture.settings_service,
            translation_cache=fixture.cache,
            usage_service=fixture.usage_service,
        )

        with pytest.raises(PipelineStageError) as exc_info:
            await orchestrator.translate_chapters(
                source_key="mock_source",
                novel_id=novel_id,
                chapters="1",
                provider_key="mock",
                provider_model="mock-1.0",
                force=True,
                source_language="Japanese",
                target_language="English",
                job_id="job_qa_no_save",
                skip_glossary_gate=True,
            )

        assert isinstance(exc_info.value.original, TranslationQAError)

        assert fixture.storage.load_translated_chapter(novel_id, "1") is None
        state = fixture.storage.load_chapter_state(novel_id, "1")
        assert state is not None
        assert state["current_state"] == ChapterState.QA_FAILED
    finally:
        fixture.cleanup()
