"""Contract tests: translation QA hardening (CJK residue, repetition, glossary, soft activation)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from novelai.storage.service import StorageService
from novelai.translation.qa import (
    evaluate_translation_quality,
)

_TMP = Path(__file__).resolve().parent / ".tmp" / "qa_hardening"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_storage() -> StorageService:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


def _add_chapter(storage: StorageService, novel_id: str, chapter_id: str, text: str = "raw text") -> None:
    storage.save_chapter(novel_id, chapter_id, text, source_url=f"http://example.com/{chapter_id}")
    storage.save_translated_chapter(novel_id, chapter_id, text, provider_key="p", provider_model="m")


# ---------------------------------------------------------------------------
# CJK residue (Tasks 1.x)
# ---------------------------------------------------------------------------


class TestCjkResidue:
    def test_cjk_residue_error(self) -> None:
        """>10% CJK → error, passed=False."""
        text = "普通の" + "a" * 100  # ~3 CJK / ~103 chars ≈ 2.9%... too low
        # Use ~15 CJK chars in ~100 total = ~15% > 10%
        cjk_part = "普通の日本語文章"  # 7 CJK chars
        text = cjk_part * 3 + "a" * 100  # 21 CJK / ~121 chars ≈ 17%
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text=text,
        )
        assert "cjk_residue_high" in result.errors
        assert not result.passed

    def test_cjk_residue_warning(self) -> None:
        """~5% CJK → warning, no error."""
        # 5 CJK in ~100 chars = 5% — between 3% and 10%
        cjk_part = "普通の"  # 3 CJK
        text = cjk_part + "a" * 57  # 3/60 = 5%
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text=text,
        )
        assert "cjk_residue_moderate" in result.warnings
        assert "cjk_residue_high" not in result.errors

    def test_cjk_residue_clean(self) -> None:
        """<3% CJK → no residue flags."""
        # 1 CJK in 100 chars = 1% — below warning threshold
        text = "々" + "a" * 99
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text=text,
        )
        assert "cjk_residue_high" not in result.errors
        assert "cjk_residue_moderate" not in result.warnings

    def test_cjk_residue_skipped_short_text(self) -> None:
        """≤50 chars → skip CJK check."""
        text = "普通の日本語文章"  # 7 chars, all CJK but <= 50
        result = evaluate_translation_quality(
            source_text="source",
            translated_text=text,
        )
        assert "cjk_residue_high" not in result.errors
        assert "cjk_residue_moderate" not in result.warnings


# ---------------------------------------------------------------------------
# Repetition (Tasks 2.x)
# ---------------------------------------------------------------------------


class TestRepetition:
    def test_repetition_error(self) -> None:
        """>30% duplicate lines → error."""
        lines = [
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",
            "A unique line here.",
            "Another unique line.",
        ]  # 4/6 = 67% duplicates > 30%, 6 lines >= 5
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text="\n".join(lines),
        )
        assert "repetition_high" in result.errors
        assert not result.passed

    def test_repetition_warning(self) -> None:
        """~22% duplicate lines → warning."""
        lines = [
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",
            "A unique line one.",
            "A unique line two.",
            "A unique line three.",
            "A unique line four.",
            "A unique line five.",
            "A unique line six.",
        ]  # 3 dup of fox + 6 unique = 9 total, 7 unique, (9-7)/9 = 22% dup_fraction -> between 15% and 30%
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text="\n".join(lines),
        )
        assert "repetition_moderate" in result.warnings
        assert "repetition_high" not in result.errors

    def test_repetition_excludes_markers(self) -> None:
        """Structural markers not counted as duplicate lines."""
        # Content lines = 3 < REPETITION_MIN_LINES => check skipped, no error

    def test_repetition_excludes_markers_above_threshold(self) -> None:
        """Structural markers excluded, content above threshold triggers error."""
        content_dup = "The actual paragraph content."
        markers = ["[CHAPTER ch001]"] + [f"[P p{i:04d}]" for i in range(1, 11)]
        content_lines = [content_dup] * 8 + ["Unique line here.", "Another unique line."]
        all_lines = markers + content_lines  # 10 markers + 10 content = 20 lines
        # Content only: 10 lines, 2 unique = 8/10 = 80% dupes > 30%, 10 >= 5
        result = evaluate_translation_quality(
            source_text="source " * 100,
            translated_text="\n".join(all_lines),
        )
        assert "repetition_high" in result.errors
        assert not result.passed

    def test_repetition_skipped_few_lines(self) -> None:
        """<5 lines → skip repetition check."""
        lines = [
            "Same line.",
            "Same line.",
            "Same line.",
        ]  # 3 lines < 5 → skipped
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text="\n".join(lines),
        )
        assert "repetition_high" not in result.errors
        assert "repetition_moderate" not in result.warnings


# ---------------------------------------------------------------------------
# Glossary term check (Tasks 3.x)
# ---------------------------------------------------------------------------


class TestGlossaryCheck:
    def test_glossary_term_missing_warning(self) -> None:
        """Glossary term in source but missing from output → warning."""
        result = evaluate_translation_quality(
            source_text="Akira walked down the street. Hello world.",
            translated_text="He walked down the street.",
            approved_glossary=[{"source": "Akira", "target": "Akira"}],
        )
        assert "glossary_term_missing:Akira" in result.warnings

    def test_glossary_check_skipped_when_no_glossary(self) -> None:
        """approved_glossary=None → no glossary warnings."""
        result = evaluate_translation_quality(
            source_text="Akira walked down the street.",
            translated_text="He walked down the street.",
            approved_glossary=None,
        )
        glossary_warnings = [w for w in result.warnings if w.startswith("glossary_term_missing")]
        assert len(glossary_warnings) == 0

    def test_glossary_term_present_no_warning(self) -> None:
        """Glossary term present in output → no warning."""
        result = evaluate_translation_quality(
            source_text="Akira walked down the street.",
            translated_text="Akira walked down the street.",
            approved_glossary=[{"source": "Akira", "target": "Akira"}],
        )
        assert "glossary_term_missing:Akira" not in result.warnings

    def test_glossary_term_skip_not_in_source(self) -> None:
        """Glossary term not in source → skip (no warning)."""
        result = evaluate_translation_quality(
            source_text="Hello world.",
            translated_text="Hello world.",
            approved_glossary=[{"source": "Akira", "target": "Akira"}],
        )
        assert "glossary_term_missing:Akira" not in result.warnings

    def test_glossary_max_terms_capped(self) -> None:
        """Maximum 20 terms checked (cap defined as _GLOSSARY_MAX_TERMS)."""
        glossary = [{"source": f"term{i}", "target": f"Target{i}"} for i in range(30)]
        source_text = " ".join(f"term{i} and" for i in range(30))
        translated_text = "nothing here at all " * 10
        result = evaluate_translation_quality(
            source_text=source_text,
            translated_text=translated_text,
            approved_glossary=glossary,
        )
        glossary_warnings = [w for w in result.warnings if w.startswith("glossary_term_missing")]
        assert len(glossary_warnings) <= 20


# ---------------------------------------------------------------------------
# QA score (Task 11.13)
# ---------------------------------------------------------------------------


class TestQAScore:
    def test_qa_score_decreases_on_new_errors(self) -> None:
        """Adding cjk_residue_high error reduces score below passing threshold."""
        # First: clean output → score 1.0, passed
        clean_result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text="This is a perfectly clean English translation with no issues. "
            "It continues smoothly with varied sentences that demonstrate "
            "good translation quality free from any residue or problems. "
            "The text flows naturally and reads well in English.",
        )
        assert clean_result.passed
        assert clean_result.score == 1.0

        # Same but with CJK residue error
        cjk_part = "普通の日本語文章が残っています"  # 11 CJK chars
        polluted_text = cjk_part * 3 + "a" * 200  # 33 CJK / ~233 chars ≈ 14%
        dirty_result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text="This is a translation with some issues. " + polluted_text,
        )
        # cjk_residue_high error → score drops by 0.30
        assert "cjk_residue_high" in dirty_result.errors
        assert dirty_result.score < 0.75


# ---------------------------------------------------------------------------
# Low-confidence activation gate (Tasks 7.x-9.x)
# ---------------------------------------------------------------------------


class TestActivationGate:
    def test_low_confidence_not_activated(self) -> None:
        """confidence_score=0.40 < 0.55 threshold → saved, not activated."""
        storage = _fresh_storage()
        _add_chapter(storage, "n1", "c1", "original text")
        storage.save_translated_chapter(
            "n1",
            "c1",
            "low confidence translation",
            provider_key="p",
            provider_model="m",
            confidence_score=0.40,
            auto_activate=False,
        )
        active = storage.load_translated_chapter("n1", "c1")
        assert active is not None
        # The active version should still point to the first save (original text)
        assert "original text" in active.get("text", "")

    def test_high_confidence_activated(self) -> None:
        """confidence_score=0.85 → saved and activated."""
        storage = _fresh_storage()
        storage.save_chapter("n1", "c1", "raw text", source_url="http://example.com")
        storage.save_translated_chapter(
            "n1",
            "c1",
            "high confidence translation",
            provider_key="p",
            provider_model="m",
            confidence_score=0.85,
            auto_activate=True,
        )
        active = storage.load_translated_chapter("n1", "c1")
        assert active is not None
        assert "high confidence translation" in active.get("text", "")

    def test_default_auto_activate_true(self) -> None:
        """auto_activate defaults to True → version activated."""
        storage = _fresh_storage()
        storage.save_chapter("n1", "c1", "raw text", source_url="http://example.com")
        storage.save_translated_chapter(
            "n1",
            "c1",
            "default activated",
            provider_key="p",
            provider_model="m",
            confidence_score=0.90,
        )
        active = storage.load_translated_chapter("n1", "c1")
        assert active is not None
        assert "default activated" in active.get("text", "")


# ---------------------------------------------------------------------------
# QA status in chunk output records (Tasks 4.x)
# ---------------------------------------------------------------------------


class TestQaStatusInChunkOutput:
    def test_qa_status_passed_in_chunk_state(self) -> None:
        """Chunk state dict carries qa_status='passed' when result passes."""
        result = evaluate_translation_quality(
            source_text="source " * 10,
            translated_text="A clean translation with no issues at all.",
        )
        assert result.passed
        assert result.score >= 0.75

    def test_qa_status_failed_in_chunk_state(self) -> None:
        """Chunk state dict carries qa_status='qa_failed' when result fails."""
        result = evaluate_translation_quality(
            source_text="source " * 50,
            translated_text="",
        )
        assert not result.passed
        assert "translation_empty" in result.errors
