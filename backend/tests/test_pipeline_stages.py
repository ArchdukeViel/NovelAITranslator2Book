"""Tests for pipeline stages."""

import pytest

from novelai.translation.pipeline.context import PipelineState, TranslationChunk
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.segment import SegmentStage, SmartSegmentStage
from tests.conftest import MockSourceAdapter


class _FailingStage(PipelineStage):
    async def run(self, context: PipelineState) -> PipelineState:
        raise RuntimeError("stage boom")


@pytest.fixture
def mock_source():
    """Provide mock source adapter."""
    source = MockSourceAdapter()
    source.add_chapter(
        "http://example.com/ch1",
        "Chapter 1 content\n\n段落2の内容です。\n\nMore content here.",
    )
    return source


@pytest.fixture
def pipeline_context():
    """Provide pipeline context."""
    return PipelineState(chapter_url="http://example.com/ch1")


@pytest.mark.asyncio
async def test_fetch_stage(mock_source, pipeline_context):
    """Test FetchStage."""
    fetch = FetchStage()
    pipeline_context.metadata["_source_adapter"] = mock_source

    result = await fetch.run(pipeline_context)

    assert result.raw_text is not None
    assert len(result.raw_text) > 0
    assert "Chapter 1" in result.raw_text
    assert mock_source.call_count == 1


@pytest.mark.asyncio
async def test_parse_stage(pipeline_context):
    """Test ParseStage."""
    parse = ParseStage()
    pipeline_context.raw_text = "Hello <ruby>world</ruby>!\n\n  Multiple   spaces  \n\nOK"

    result = await parse.run(pipeline_context)

    assert result.normalized_text is not None
    assert "<ruby>" not in result.normalized_text  # Ruby text removed
    assert "Multiple" in result.normalized_text  # Whitespace normalized


@pytest.mark.asyncio
async def test_segment_stage():
    """Test SegmentStage."""
    segment = SegmentStage()
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"

    result = await segment.run(context)

    assert result.chunks is not None
    assert len(result.paragraphs) == 3
    assert [paragraph.paragraph_id for paragraph in result.paragraphs] == ["p0001", "p0002", "p0003"]
    assert [paragraph.chapter_id for paragraph in result.paragraphs] == ["chapter_001"] * 3
    assert len(result.translation_chunks) == 1
    assert result.translation_chunks[0].chunk_id == "c0001"
    assert result.translation_chunks[0].novel_id == "novel1"
    assert result.translation_chunks[0].chapter_ids == ["chapter_001"]
    assert result.translation_chunks[0].paragraph_ids == ["p0001", "p0002", "p0003"]
    assert result.chunks == [result.translation_chunks[0].source_text]
    assert "[CHAPTER chapter_001]" in result.chunks[0]
    assert "[P p0001]" in result.chunks[0]
    assert "Paragraph 1" in result.chunks[0]


@pytest.mark.asyncio
async def test_segment_stage_empty():
    """Test SegmentStage with empty text."""
    segment = SegmentStage()
    context = PipelineState(chapter_url="test")
    context.normalized_text = ""

    result = await segment.run(context)

    assert result.chunks is not None
    assert len(result.chunks) == 0
    assert result.paragraphs == []
    assert result.translation_chunks == []


@pytest.mark.asyncio
async def test_pipeline_records_stage_transition_events():
    segment = SegmentStage()
    pipeline = TranslationPipeline([segment])
    context = PipelineState(
        chapter_url="test",
        job_id="job_1",
        activity_id="activity_1",
        novel_id="novel1",
        chapter_id="chapter_001",
        source_key="kakuyomu",
    )
    context.normalized_text = "Paragraph 1"

    result = await pipeline.run(context)

    assert [event["status_after"] for event in result.pipeline_events] == ["running", "segmented"]
    assert result.pipeline_events[0]["job_id"] == "job_1"
    assert result.pipeline_events[0]["activity_id"] == "activity_1"
    assert result.pipeline_events[0]["source_key"] == "kakuyomu"
    assert result.pipeline_events[1]["stage_name"] == "SegmentStage"
    assert result.pipeline_events[1]["timestamp"]


@pytest.mark.asyncio
async def test_pipeline_records_failed_stage_event():
    pipeline = TranslationPipeline([_FailingStage()])
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")

    with pytest.raises(RuntimeError, match="stage boom"):
        await pipeline.run(context)

    assert context.errors[0]["stage_name"] == "_FailingStage"
    assert context.pipeline_events[-1]["status_after"] == "failed"
    assert context.pipeline_events[-1]["error_code"] == "RuntimeError"


@pytest.mark.asyncio
async def test_smart_segment_stage_is_deterministic():
    """Same normalized input should produce the same paragraph and chunk IDs."""
    text = "Alpha\n\nBeta\n\nGamma"

    first = PipelineState(chapter_url="https://example.com/novel1/1", novel_id="novel1", chapter_id="1")
    first.normalized_text = text
    second = PipelineState(chapter_url="https://example.com/novel1/1", novel_id="novel1", chapter_id="1")
    second.normalized_text = text

    segment = SmartSegmentStage(target_chars=4500, hard_max_chars=7000)
    first_result = await segment.run(first)
    second_result = await segment.run(second)

    assert [paragraph.to_dict() for paragraph in first_result.paragraphs] == [
        paragraph.to_dict() for paragraph in second_result.paragraphs
    ]
    assert [chunk.to_dict() for chunk in first_result.translation_chunks] == [
        chunk.to_dict() for chunk in second_result.translation_chunks
    ]


@pytest.mark.asyncio
async def test_smart_segment_stage_packs_normal_chapter_by_budget():
    """Paragraphs should be packed into budget-aware chunks instead of one call per paragraph."""
    segment = SmartSegmentStage(
        target_chars=25,
        hard_max_chars=40,
        overlap_paragraphs=1,
        conditional_overlap_enabled=False,
    )
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "aaaaaaaaaa\n\nbbbbbbbbbb\n\ncccccccccc\n\ndddddddddd"

    result = await segment.run(context)

    assert len(result.paragraphs) == 4
    assert len(result.translation_chunks) == 2
    assert [chunk.chunk_id for chunk in result.translation_chunks] == ["c0001", "c0002"]
    assert result.translation_chunks[0].paragraph_ids == ["p0001", "p0002"]
    assert result.translation_chunks[1].paragraph_ids == ["p0003", "p0004"]
    assert result.translation_chunks[1].previous_context == "bbbbbbbbbb"


@pytest.mark.asyncio
async def test_smart_segment_stage_keeps_short_chapter_as_single_chunk():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "Short chapter."

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    chunk = result.translation_chunks[0]
    assert chunk.chapter_ids == ["chapter_001"]
    assert chunk.paragraph_ids == ["p0001"]
    assert chunk.char_count == len("Short chapter.")


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_keeps_chapter_below_hard_max_as_single_chunk():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "a" * 6000

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    assert result.translation_chunks[0].char_count == 6000
    assert result.metadata["segmentation"]["adaptive_chunking_enabled"] is True


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_reduces_mid_length_extra_chunks():
    text = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000])
    adaptive = SmartSegmentStage(adaptive_chunking_enabled=True)
    baseline = SmartSegmentStage(adaptive_chunking_enabled=False)

    adaptive_context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    baseline_context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    adaptive_context.normalized_text = text
    baseline_context.normalized_text = text

    adaptive_result = await adaptive.run(adaptive_context)
    baseline_result = await baseline.run(baseline_context)

    assert len(baseline_result.translation_chunks) == 3
    assert len(adaptive_result.translation_chunks) == 2
    assert [chunk.char_count for chunk in adaptive_result.translation_chunks] == [6000, 3000]


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_balances_twelve_thousand_chars_into_two_chunks():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000])

    result = await segment.run(context)

    assert len(result.translation_chunks) == 2
    assert [chunk.char_count for chunk in result.translation_chunks] == [6000, 6000]
    assert all(chunk.char_count <= 7000 for chunk in result.translation_chunks)


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_preserves_refs_and_previous_context():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True, boundary_context_chars=160)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    paragraphs = ["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000]
    context.normalized_text = "\n\n".join(paragraphs)

    result = await segment.run(context)

    assert [chunk.paragraph_ids for chunk in result.translation_chunks] == [
        ["p0001", "p0002"],
        ["p0003", "p0004"],
    ]
    assert result.translation_chunks[1].paragraph_refs == [
        ("chapter_001", "p0003"),
        ("chapter_001", "p0004"),
    ]
    assert result.translation_chunks[1].previous_context == paragraphs[1][-160:]


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_uses_zero_overlap_for_safe_boundary():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(
        [
            ("a" * 2999) + ".",
            ("b" * 2999) + ".",
            ("c" * 2999) + ".",
            ("d" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    assert len(result.translation_chunks) == 2
    assert "[CONTEXT OVERLAP]" not in result.translation_chunks[1].source_text
    assert result.translation_chunks[1].paragraph_ids == ["p0003", "p0004"]


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_uses_overlap_for_unsafe_quote_boundary():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    unsafe_previous = "「" + ("b" * 2999)
    context.normalized_text = "\n\n".join(
        [
            ("a" * 2999) + ".",
            unsafe_previous,
            ("c" * 2999) + ".",
            ("d" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    second_chunk = result.translation_chunks[1]
    assert second_chunk.paragraph_ids == ["p0003", "p0004"]
    assert second_chunk.paragraph_refs == [("chapter_001", "p0003"), ("chapter_001", "p0004")]
    assert second_chunk.source_text.startswith("[CONTEXT OVERLAP]\n" + unsafe_previous)


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_uses_zero_overlap_after_scene_separator():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(
        [
            "a" * 3000,
            "***",
            ("b" * 2999) + ".",
            ("c" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    assert len(result.translation_chunks) == 2
    assert result.translation_chunks[0].paragraph_ids == ["p0001", "p0002"]
    assert result.translation_chunks[1].paragraph_ids == ["p0003", "p0004"]
    assert "[CONTEXT OVERLAP]" not in result.translation_chunks[1].source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_previous_context_is_capped_without_source_duplication():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True, boundary_context_chars=25)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    previous_tail = "b" * 30 + "."
    context.normalized_text = "\n\n".join(
        [
            "a" * 3000,
            previous_tail,
            ("c" * 2999) + ".",
            ("d" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    second_chunk = result.translation_chunks[1]
    assert second_chunk.previous_context == previous_tail[-25:]
    assert previous_tail not in second_chunk.source_text
    assert "[CONTEXT OVERLAP]" not in second_chunk.source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_disabled_preserves_legacy_context():
    segment = SmartSegmentStage(
        adaptive_chunking_enabled=True,
        conditional_overlap_enabled=False,
        overlap_paragraphs=1,
    )
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    paragraphs = ["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000]
    context.normalized_text = "\n\n".join(paragraphs)

    result = await segment.run(context)

    assert result.translation_chunks[1].previous_context == paragraphs[1]
    assert "[CONTEXT OVERLAP]" not in result.translation_chunks[1].source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_bundles_multiple_short_neighboring_chapters():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150, max_chapters_per_bundle=3)
    context = PipelineState(chapter_url="bundle", novel_id="novel1")
    context.metadata["_normalized_chapters"] = [
        {"novel_id": "novel1", "chapter_id": "chapter_001", "text": "One."},
        {"novel_id": "novel1", "chapter_id": "chapter_002", "text": "Two."},
        {"novel_id": "novel1", "chapter_id": "chapter_003", "text": "Three."},
    ]

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    chunk = result.translation_chunks[0]
    assert chunk.chapter_ids == ["chapter_001", "chapter_002", "chapter_003"]
    assert chunk.paragraph_ids == ["p0001", "p0001", "p0001"]
    assert chunk.paragraph_refs == [
        ("chapter_001", "p0001"),
        ("chapter_002", "p0001"),
        ("chapter_003", "p0001"),
    ]
    assert "[CHAPTER chapter_001]" in chunk.source_text
    assert "[CHAPTER chapter_002]" in chunk.source_text
    assert "[CHAPTER chapter_003]" in chunk.source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_bundles_multiple_short_neighboring_chapters():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True, max_chapters_per_bundle=3)
    context = PipelineState(chapter_url="bundle", novel_id="novel1")
    context.metadata["_normalized_chapters"] = [
        {"novel_id": "novel1", "chapter_id": "chapter_001", "text": "One."},
        {"novel_id": "novel1", "chapter_id": "chapter_002", "text": "Two."},
        {"novel_id": "novel1", "chapter_id": "chapter_003", "text": "Three."},
    ]

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    assert result.translation_chunks[0].chapter_ids == ["chapter_001", "chapter_002", "chapter_003"]


@pytest.mark.asyncio
async def test_smart_segment_stage_splits_long_chapter_without_paragraph_loss():
    segment = SmartSegmentStage(target_chars=30, hard_max_chars=45)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join([f"paragraph-{index:02d}" for index in range(1, 8)])

    result = await segment.run(context)

    assert len(result.translation_chunks) > 1
    refs = [ref for chunk in result.translation_chunks for ref in chunk.paragraph_refs]
    expected = [("chapter_001", f"p{index:04d}") for index in range(1, 8)]
    assert refs == expected
    assert all(chunk.char_count <= 45 for chunk in result.translation_chunks)


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_disabled_preserves_baseline_chunk_count():
    segment = SmartSegmentStage(adaptive_chunking_enabled=False)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000])

    result = await segment.run(context)

    assert len(result.translation_chunks) == 4
    assert result.metadata["segmentation"]["adaptive_chunking_enabled"] is False


@pytest.mark.asyncio
async def test_smart_segment_stage_isolates_oversized_paragraph_with_warning():
    segment = SmartSegmentStage(target_chars=10, hard_max_chars=12)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "short\n\nthis paragraph is too long\n\nend"

    result = await segment.run(context)

    oversized_chunks = [
        chunk
        for chunk in result.translation_chunks
        if chunk.paragraph_ids == ["p0002"]
    ]
    assert len(oversized_chunks) == 1
    warnings = result.metadata["segmentation"]["warnings"]
    assert any("Oversized paragraph chapter_001/p0002" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_smart_segment_stage_preserves_image_placeholders_and_scene_breaks_in_order():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "[Image: cover]\n\n***\n\nThe story continues."

    result = await segment.run(context)

    assert [paragraph.text for paragraph in result.paragraphs] == [
        "[Image: cover]",
        "***",
        "The story continues.",
    ]
    source_text = result.translation_chunks[0].source_text
    assert source_text.index("[Image: cover]") < source_text.index("***") < source_text.index("The story continues.")


@pytest.mark.asyncio
async def test_translation_chunk_serialization_preserves_split_metadata():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150)
    context = PipelineState(chapter_url="bundle", novel_id="novel1")
    context.metadata["_normalized_chapters"] = [
        {"novel_id": "novel1", "chapter_id": "chapter_001", "text": "One.\n\nTwo."},
        {"novel_id": "novel1", "chapter_id": "chapter_002", "text": "Three."},
    ]

    result = await segment.run(context)
    payload = result.translation_chunks[0].to_dict()
    restored = TranslationChunk.from_dict(payload)

    assert restored.chunk_id == "c0001"
    assert restored.chapter_ids == ["chapter_001", "chapter_002"]
    assert restored.paragraph_refs == [
        ("chapter_001", "p0001"),
        ("chapter_001", "p0002"),
        ("chapter_002", "p0001"),
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
