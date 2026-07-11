"""Parser tests for LLM QA structured output (REQ-4.2).

These tests verify that valid and invalid LLM QA model outputs are parsed correctly.
"""

from __future__ import annotations

import json

from novelai.translation.qa import (
    evaluate_translation_quality,
    normalized_translation_text,
)


class TestLLMQAOutputParser:
    """Tests for parsing structured LLM QA output."""

    def test_valid_structured_output_parsed(self) -> None:
        """Valid JSON with translated_text and paragraph_map parses correctly."""
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = json.dumps({
            "translated_text": "Translated text.",
            "paragraph_map": [
                {"chapter_id": "ch1", "paragraph_id": "p1", "translated_text": "Translated text."}
            ]
        })
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            structured_output=True,
        )
        assert result.passed
        assert result.errors == []

    def test_valid_fenced_json_parsed(self) -> None:
        """Fenced JSON code block is extracted and parsed."""
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = '```json\n{"translated_text": "Translated.", "paragraph_map": [{"chapter_id": "ch1", "paragraph_id": "p1", "translated_text": "Translated."}]}\n```'
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            structured_output=True,
        )
        assert result.passed

    def test_invalid_json_rejected(self) -> None:
        """Invalid JSON produces qa_failed with parse error."""
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = '{"translated_text": "Missing bracket"'
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            structured_output=True,
        )
        assert not result.passed
        assert any("json" in e.lower() or "parse" in e.lower() for e in result.errors)

    def test_missing_translated_text_rejected(self) -> None:
        """Missing translated_text field is rejected."""
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = json.dumps({"paragraph_map": []})
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            structured_output=True,
        )
        assert not result.passed
        assert any("paragraph_map" in e for e in result.errors)

    def test_missing_paragraph_map_rejected(self) -> None:
        """Missing paragraph_map field is rejected."""
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = json.dumps({"translated_text": "Translated."})
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            structured_output=True,
        )
        assert not result.passed
        assert any("paragraph_map" in e for e in result.errors)

    def test_empty_paragraph_map_rejected(self) -> None:
        """Empty paragraph_map is rejected when source has paragraphs."""
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = json.dumps({"translated_text": "Translated.", "paragraph_map": []})
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            structured_output=True,
        )
        assert not result.passed
        assert any("paragraph_map" in e for e in result.errors)

    def test_paragraph_map_mismatch_rejected(self) -> None:
        """Paragraph map chapter/paragraph IDs must match source."""
        from novelai.translation.pipeline.context import TranslationChunk
        chunk_text = "[CHAPTER ch1]\n[P p1]\nSource text."
        translated = json.dumps({
            "translated_text": "Translated.",
            "paragraph_map": [{"chapter_id": "ch2", "paragraph_id": "p1", "translated_text": "Translated."}]
        })
        chunk = TranslationChunk(
            chunk_id="c1",
            novel_id="n1",
            chapter_ids=["ch1"],
            paragraph_ids=["p1"],
            source_text="Source text.",
            char_count=12,
            paragraph_refs=[("ch1", "p1")],
        )
        result = evaluate_translation_quality(
            source_text=chunk_text,
            translated_text=translated,
            chunk=chunk,
            structured_output=True,
        )
        assert not result.passed
        assert any("chapter_mapping_invalid" in e for e in result.errors)

    def test_non_structured_output_passes_basic_checks(self) -> None:
        """Plain text output passes basic deterministic checks."""
        result = evaluate_translation_quality(
            source_text="Hello world.",
            translated_text="Hello world.",
            structured_output=False,
        )
        # Same as source should fail
        assert not result.passed
        assert "translation_same_as_source" in result.errors

    def test_normalized_text_extraction(self) -> None:
        """normalized_translation_text extracts plain text from structured output."""
        structured = json.dumps({
            "translated_text": "Plain text.",
            "paragraph_map": [{"chapter_id": "ch1", "paragraph_id": "p1", "translated_text": "Plain text."}]
        })
        normalized = normalized_translation_text(structured)
        assert normalized == "Plain text."

    def test_normalized_text_fenced_json(self) -> None:
        """normalized_translation_text handles fenced JSON."""
        fenced = '```json\n{"translated_text": "Fenced.", "paragraph_map": []}\n```'
        normalized = normalized_translation_text(fenced)
        assert normalized == "Fenced."

    def test_normalized_text_plain_passthrough(self) -> None:
        """Plain text passes through unchanged."""
        assert normalized_translation_text("Just text.") == "Just text."
