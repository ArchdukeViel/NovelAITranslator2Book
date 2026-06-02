"""Tests for the chapter state machine."""

from __future__ import annotations

from novelai.core.chapter_state import ChapterMetadata, ChapterState


def test_chapter_state_values() -> None:
    assert ChapterState.SCRAPED.value == "scraped"
    assert ChapterState.TRANSLATED.value == "translated"
    assert ChapterState.EXPORTED.value == "exported"


def test_chapter_metadata_defaults_to_scraped() -> None:
    meta = ChapterMetadata(chapter_id="ch-1")
    assert meta.current_state == ChapterState.SCRAPED
    assert meta.error_count == 0
    assert meta.transitions == []


def test_transition_records_state_change() -> None:
    meta = ChapterMetadata(chapter_id="ch-1")
    meta.transition_to(ChapterState.PARSED)

    assert meta.current_state == ChapterState.PARSED
    assert len(meta.transitions) == 1
    assert meta.transitions[0].from_state == ChapterState.SCRAPED
    assert meta.transitions[0].to_state == ChapterState.PARSED


def test_transition_with_error_increments_error_count() -> None:
    meta = ChapterMetadata(chapter_id="ch-1")
    meta.transition_to(ChapterState.PARSED, error="timeout")

    assert meta.error_count == 1
    assert meta.transitions[0].error == "timeout"


def test_can_proceed_to_allows_forward_and_same_state() -> None:
    meta = ChapterMetadata(chapter_id="ch-1")
    meta.transition_to(ChapterState.PARSED)

    assert meta.can_proceed_to(ChapterState.PARSED)
    assert meta.can_proceed_to(ChapterState.SEGMENTED)
    assert meta.can_proceed_to(ChapterState.EXPORTED)
    assert not meta.can_proceed_to(ChapterState.SCRAPED)


def test_get_state_progress_counts_transitions() -> None:
    meta = ChapterMetadata(chapter_id="ch-1")
    meta.transition_to(ChapterState.PARSED)
    meta.transition_to(ChapterState.SEGMENTED)
    meta.transition_to(ChapterState.TRANSLATED)

    progress = meta.get_state_progress()
    assert progress["parsed"] == 1
    assert progress["segmented"] == 1
    assert progress["translated"] == 1
    assert progress["scraped"] == 0
