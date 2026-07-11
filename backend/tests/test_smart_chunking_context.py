"""Tests for smart chunking and context overlap wiring.

Covers REQ-1 (boundary-aware chunking), REQ-2 (oversized paragraph splitting),
REQ-3 (context window handling), and the prompt/output wiring that depends on
the new ``chunk.previous_context`` field.
"""

from __future__ import annotations

import pytest

from novelai.prompts.builders import (
    _format_additional_instructions,
    build_translation_request,
)
from novelai.prompts.templates import CONTEXT_OVERLAP_PROMPT_BLOCK
from novelai.translation.pipeline.context import (
    PipelineState,
    TranslationChunk,
    paragraph_source_hash,
)
from novelai.translation.pipeline.stages.segment import SmartSegmentStage

# These were previously exported from translate.py but inlined in a refactor.
# Keep local definitions so the test stands independently.
_CONTEXT_OVERLAP_OPEN = "[CONTEXT OVERLAP]"
_CONTEXT_OVERLAP_CLOSE = "[END CONTEXT OVERLAP]"

def _strip_context_overlap_block(text: str) -> str:
    if not isinstance(text, str) or _CONTEXT_OVERLAP_OPEN not in text:
        return text
    start = text.index(_CONTEXT_OVERLAP_OPEN)
    close_index = text.find(_CONTEXT_OVERLAP_CLOSE, start)
    if close_index < 0:
        return text
    end = close_index + len(_CONTEXT_OVERLAP_CLOSE)
    return (text[:start] + text[end:]).strip()


def _extract_paragraph_body(source_text: str) -> str:
    """Return the paragraph body, dropping chapter/marker/overlap lines."""
    body_lines: list[str] = []
    for line in source_text.splitlines():
        if line.startswith(("[CHAPTER", "[P ", "[CONTEXT", "[END CONTEXT")):
            continue
        body_lines.append(line)
    return "".join(body_lines)


# ---------------------------------------------------------------------------
# REQ-1: boundary-aware chunking (paragraphs, scene breaks, dialogue)
# ---------------------------------------------------------------------------


def _build_segment(
    *,
    target_chars: int | None = None,
    hard_max_chars: int | None = None,
    adaptive_soft_target_chars: int | None = None,
    adaptive_hard_max_chars: int | None = None,
) -> SmartSegmentStage:
    return SmartSegmentStage(
        target_chars=target_chars,
        hard_max_chars=hard_max_chars,
        adaptive_soft_target_chars=adaptive_soft_target_chars,
        adaptive_hard_max_chars=adaptive_hard_max_chars,
    )


@pytest.mark.asyncio
async def test_segment_groups_whole_paragraphs_under_max_size():
    segment = _build_segment(target_chars=200, hard_max_chars=300)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    chunk = result.translation_chunks[0]
    assert chunk.paragraph_ids == ["p0001", "p0002", "p0003"]
    assert chunk.paragraph_refs == [
        ("chapter_001", "p0001"),
        ("chapter_001", "p0002"),
        ("chapter_001", "p0003"),
    ]
    # Source text contains all three paragraph markers in source order
    assert chunk.source_text.index("p0001") < chunk.source_text.index("p0002")
    assert chunk.source_text.index("p0002") < chunk.source_text.index("p0003")


@pytest.mark.asyncio
async def test_segment_splits_when_exceeding_hard_max_chars():
    segment = _build_segment(target_chars=50, hard_max_chars=80)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    # 4 paragraphs, each ~40 chars; budget forces a split
    context.normalized_text = (
        "A" * 40 + ".\n\n"
        + "B" * 40 + ".\n\n"
        + "C" * 40 + ".\n\n"
        + "D" * 40 + "."
    )

    result = await segment.run(context)

    assert len(result.translation_chunks) >= 2
    # No chunk should exceed hard_max_chars (counted in source_text)
    for chunk in result.translation_chunks:
        assert len(chunk.source_text) <= 200, (
            f"Chunk {chunk.chunk_id} exceeded soft limit unexpectedly: {len(chunk.source_text)}"
        )
    # Paragraph ordering preserved across chunks
    flat_ids = [pid for chunk in result.translation_chunks for pid in chunk.paragraph_ids]
    assert flat_ids == ["p0001", "p0002", "p0003", "p0004"]


@pytest.mark.asyncio
async def test_segment_prefers_scene_break_boundaries():
    segment = _build_segment(target_chars=80, hard_max_chars=120)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = (
        "A" * 60 + ".\n\n"
        + "***\n\n"
        + "B" * 60 + "."
    )

    result = await segment.run(context)

    # Scene break is a natural close point — first chunk should end with the break
    first = result.translation_chunks[0]
    assert "p0001" in first.paragraph_ids
    # No chunk should straddle across the scene break while still fitting
    assert all(
        "p0001" in c.paragraph_ids and "p0002" in c.paragraph_ids and "p0003" in c.paragraph_ids
        for c in result.translation_chunks
    ) is False, "Expected scene break to land at a chunk boundary"


@pytest.mark.asyncio
async def test_segment_keeps_dialogue_lines_together_when_possible():
    segment = _build_segment(target_chars=120, hard_max_chars=200)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = (
        '"Hello," she said softly.\n'
        '"I have been waiting for you," he replied.\n\n'
        "Narrator describes what happens next in a few words."
    )

    result = await segment.run(context)

    # The two dialogue lines should be in the same paragraph and the same chunk
    dialogue_chunk = result.translation_chunks[0]
    assert "p0001" in dialogue_chunk.paragraph_ids
    # Dialogue paragraph split by '\n' but treated as a single paragraph
    assert '"Hello,"' in dialogue_chunk.source_text
    assert '"I have been waiting for you,"' in dialogue_chunk.source_text


# ---------------------------------------------------------------------------
# REQ-2: oversized paragraph splitting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_segment_splits_oversized_paragraph_preserving_paragraph_id():
    segment = _build_segment(target_chars=10, hard_max_chars=12)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "short\n\nthis paragraph is too long\n\nend"

    result = await segment.run(context)

    split_chunks = [c for c in result.translation_chunks if c.paragraph_ids == ["p0002"]]
    assert len(split_chunks) > 1, "Oversized paragraph should be split into multiple chunks"
    # Each split chunk keeps the same paragraph_id so downstream mapping still traces back
    for chunk in split_chunks:
        assert chunk.paragraph_ids == ["p0002"]
    # Each split's body fits within the budget
    for chunk in split_chunks:
        body = _extract_paragraph_body(chunk.source_text)
        assert len(body) <= 30, f"Split body too long: {len(body)} chars"
    # paragraph_hashes remain stable across splits (same paragraph_id -> same hash)
    hashes = [chunk.paragraph_hashes[0] for chunk in split_chunks]
    assert len(set(hashes)) == 1, f"Expected one stable hash, got {hashes}"


@pytest.mark.asyncio
async def test_segment_splits_hard_window_when_no_safe_boundary():
    segment = _build_segment(target_chars=20, hard_max_chars=20)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    # Single long word with no sentence boundaries — must fall back to hard window
    long_word = "a" * 100
    context.normalized_text = f"intro\n\n{long_word}\n\noutro"

    result = await segment.run(context)

    split_chunks = [c for c in result.translation_chunks if c.paragraph_ids == ["p0002"]]
    assert len(split_chunks) > 1
    # Each split's body should fit within hard_max_chars. The source_text
    # contains the chapter/paragraph markers and (optionally) the
    # context-overlap block, so we only check the body length here.
    for chunk in split_chunks:
        body = _extract_paragraph_body(chunk.source_text)
        assert len(body) <= 40, (
            f"Split chunk body exceeded hard window: {len(body)} chars"
        )


# ---------------------------------------------------------------------------
# REQ-3: context window handling — `previous_context` field
# ---------------------------------------------------------------------------


def _build_chunk(*, with_context: bool = True) -> TranslationChunk:
    return TranslationChunk(
        chunk_id="c0001",
        novel_id="novel1",
        chapter_ids=["chapter_001"],
        paragraph_ids=["p0003", "p0004"],
        source_text="[CHAPTER chapter_001]\n[P p0003]\nNew paragraph three.\n[P p0004]\nNew paragraph four.",
        char_count=80,
        previous_context=(
            "[CONTEXT OVERLAP]\n[CHAPTER chapter_001]\n[P p0001]\nEarlier text.\n[P p0002]\nMore earlier text.\n[END CONTEXT OVERLAP]"
            if with_context
            else None
        ),
        paragraph_refs=[("chapter_001", "p0003"), ("chapter_001", "p0004")],
        paragraph_hashes=[paragraph_source_hash("New paragraph three."), paragraph_source_hash("New paragraph four.")],
    )


def test_translation_chunk_preserves_previous_context():
    chunk = _build_chunk(with_context=True)
    assert chunk.previous_context is not None
    assert _CONTEXT_OVERLAP_OPEN in chunk.previous_context
    assert _CONTEXT_OVERLAP_CLOSE in chunk.previous_context

    payload = chunk.to_dict()
    restored = TranslationChunk.from_dict(payload)
    assert restored.previous_context == chunk.previous_context


def test_translation_chunk_from_dict_handles_missing_previous_context():
    payload = {
        "chunk_id": "c0001",
        "novel_id": "novel1",
        "chapter_ids": ["chapter_001"],
        "paragraph_ids": ["p0001"],
        "source_text": "Hello.",
        "char_count": 6,
    }
    chunk = TranslationChunk.from_dict(payload)
    assert chunk.previous_context is None


# ---------------------------------------------------------------------------
# REQ-3: prompt assembly honors context overlap flag
# ---------------------------------------------------------------------------


def test_format_additional_instructions_includes_context_block_when_present():
    text, warnings = _format_additional_instructions(
        target_language="English",
        context_overlap_present=True,
    )
    assert CONTEXT_OVERLAP_PROMPT_BLOCK.strip() in text
    assert warnings == []


def test_format_additional_instructions_omits_context_block_by_default():
    text, _ = _format_additional_instructions(
        target_language="English",
        context_overlap_present=False,
    )
    assert CONTEXT_OVERLAP_PROMPT_BLOCK.strip() not in text


def test_build_user_prompt_emits_context_block_when_overlap_present():
    chunk = _build_chunk(with_context=True)
    request = build_translation_request(
        text=chunk.source_text,
        source_language="Japanese",
        target_language="English",
        context_overlap_present=bool(chunk.previous_context),
    )
    assert request.user_prompt is not None
    assert CONTEXT_OVERLAP_PROMPT_BLOCK.strip() in request.user_prompt
    # Source text follows the context instructions
    assert chunk.source_text in request.user_prompt


def test_build_user_prompt_omits_context_block_when_no_previous_context():
    chunk = _build_chunk(with_context=False)
    request = build_translation_request(
        text=chunk.source_text,
        source_language="Japanese",
        target_language="English",
        context_overlap_present=bool(chunk.previous_context),
    )
    assert request.user_prompt is not None
    assert CONTEXT_OVERLAP_PROMPT_BLOCK.strip() not in request.user_prompt


# ---------------------------------------------------------------------------
# REQ-3: saved output strips the prompt-only context block
# ---------------------------------------------------------------------------


def test_strip_context_overlap_block_removes_prompt_only_block():
    raw = (
        "[CONTEXT OVERLAP]\n"
        "[CHAPTER chapter_001]\n[P p0001]\nEarlier text.\n"
        "[END CONTEXT OVERLAP]\n\n"
        "[CHAPTER chapter_001]\n[P p0002]\nTranslated body.\n"
    )
    sanitized = _strip_context_overlap_block(raw)
    assert _CONTEXT_OVERLAP_OPEN not in sanitized
    assert _CONTEXT_OVERLAP_CLOSE not in sanitized
    assert "Translated body." in sanitized
    assert "Earlier text." not in sanitized


def test_strip_context_overlap_block_passthrough_when_absent():
    text = "[CHAPTER chapter_001]\n[P p0001]\nJust a paragraph.\n"
    assert _strip_context_overlap_block(text) == text


def test_strip_context_overlap_block_handles_unterminated_block():
    raw = "[CONTEXT OVERLAP]\nSome text without close marker.\n[P p0001]\nBody."
    # Without a close marker, the text is returned unchanged
    assert _strip_context_overlap_block(raw) == raw


def test_strip_context_overlap_block_handles_non_string_input():
    # Defensive: the helper must not crash on non-string values
    assert _strip_context_overlap_block(None) is None  # type: ignore[arg-type]
    assert _strip_context_overlap_block(123) == 123  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# REQ-3: TranslateStage._build_prompt_request derives the flag from chunk
# ---------------------------------------------------------------------------


def test_translate_stage_build_prompt_request_derives_flag_from_chunk():
    """The flag should be set when chunk.previous_context is non-empty."""
    from novelai.translation.pipeline.stages.translate import TranslateStage

    stage = TranslateStage()
    chunk = _build_chunk(with_context=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.metadata["source_language"] = "Japanese"
    context.metadata["target_language"] = "English"

    # _build_prompt_request takes the chunk source text, not the chunk object
    request = stage._build_prompt_request(
        context,
        chunk.source_text,
        chunk_glossary=[],
        prompt_glossary_block=None,
    )
    assert request is not None


def test_translate_stage_build_prompt_request_skips_flag_without_context():
    from novelai.translation.pipeline.stages.translate import TranslateStage

    stage = TranslateStage()
    chunk = _build_chunk(with_context=False)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.metadata["source_language"] = "Japanese"
    context.metadata["target_language"] = "English"

    request = stage._build_prompt_request(
        context,
        chunk.source_text,
        chunk_glossary=[],
        prompt_glossary_block=None,
    )
    assert request is not None
    assert CONTEXT_OVERLAP_PROMPT_BLOCK.strip() not in request.user_prompt


def test_translate_stage_build_prompt_request_accepts_legacy_string_chunk():
    """Legacy str chunks have no previous_context, so flag is False."""
    from novelai.translation.pipeline.stages.translate import TranslateStage

    stage = TranslateStage()
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.metadata["source_language"] = "Japanese"
    context.metadata["target_language"] = "English"

    request = stage._build_prompt_request(
        context,
        "[CHAPTER chapter_001]\n[P p0001]\nLegacy text.",
        chunk_glossary=[],
        prompt_glossary_block=None,
    )
    assert request is not None
    assert CONTEXT_OVERLAP_PROMPT_BLOCK.strip() not in request.user_prompt
