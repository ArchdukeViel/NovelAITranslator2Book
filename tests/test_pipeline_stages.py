"""Tests for pipeline stages."""

import pytest

from novelai.pipeline.context import PipelineState
from novelai.pipeline.stages.fetch import FetchStage
from novelai.pipeline.stages.parse import ParseStage
from novelai.pipeline.stages.segment import SegmentStage
from tests.conftest import MockSourceAdapter


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
    context = PipelineState(chapter_url="test")
    context.normalized_text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"

    result = await segment.run(context)

    assert result.chunks is not None
    assert len(result.chunks) == 3
    assert result.chunks[0] == "Paragraph 1"
    assert result.chunks[1] == "Paragraph 2"


@pytest.mark.asyncio
async def test_segment_stage_empty():
    """Test SegmentStage with empty text."""
    segment = SegmentStage()
    context = PipelineState(chapter_url="test")
    context.normalized_text = ""

    result = await segment.run(context)

    assert result.chunks is not None
    assert len(result.chunks) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
