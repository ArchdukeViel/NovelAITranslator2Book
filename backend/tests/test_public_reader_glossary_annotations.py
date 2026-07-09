"""Tests for public reader glossary annotations — term selection, matching, safety."""

from __future__ import annotations

import json

from novelai.services.public_glossary_annotations import (
    MAX_ANNOTATIONS,
    find_annotations,
    select_public_terms,
)


class TestTermSelection:
    def test_selects_approved_character(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "魔王", "approved_translation": "Demon King",
             "term_type": "character", "status": "approved"},
        ])
        assert len(terms) == 1
        assert terms[0]["display_term"] == "Demon King"
        assert terms[0]["term_type"] == "character"

    def test_skips_pending_term(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "魔王", "approved_translation": "Demon King",
             "term_type": "character", "status": "pending"},
        ])
        assert len(terms) == 0

    def test_skips_unknown_term_type(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "internal", "approved_translation": "x",
             "term_type": "admin_note", "status": "approved"},
        ])
        assert len(terms) == 0

    def test_includes_aliases(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "魔王", "approved_translation": "Demon King",
             "term_type": "character", "status": "approved",
             "aliases": [{"alias_text": "Dark Lord"}]},
        ])
        assert len(terms[0].get("aliases", [])) == 1

    def test_skips_no_canonical_or_translation(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "", "approved_translation": "",
             "term_type": "character", "status": "approved"},
        ])
        assert len(terms) == 0

    def test_admin_only_fields_excluded(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "魔王", "approved_translation": "Demon King",
             "term_type": "character", "status": "approved",
             "internal_notes": "secret", "confidence_score": 0.9},
        ])
        assert "internal_notes" not in terms[0]
        assert "confidence_score" not in terms[0]

    def test_reading_field(self) -> None:
        terms = select_public_terms([
            {"id": 1, "canonical_term": "魔王", "approved_translation": "Demon King",
             "term_type": "character", "status": "approved", "reading": "maou"},
        ])
        assert terms[0]["reading"] == "maou"


class TestAnnotationMatching:
    def test_matches_display_term_in_text(self) -> None:
        annotations = find_annotations(
            [{"term_id": 1, "display_term": "Demon King", "canonical_term": "魔王"}],
            "The Demon King appeared. The Demon King laughed.",
        )
        assert len(annotations) == 1
        assert len(annotations[0]["matches"]) == 2

    def test_matches_case_insensitive(self) -> None:
        annotations = find_annotations(
            [{"term_id": 1, "display_term": "demon king"}],
            "The Demon King appeared.",
        )
        assert len(annotations[0]["matches"]) == 1

    def test_no_match_returns_empty(self) -> None:
        annotations = find_annotations(
            [{"term_id": 1, "display_term": "Dark Lord"}],
            "The Demon King appeared.",
        )
        assert len(annotations) == 0

    def test_bounded_to_max(self) -> None:
        many_terms = [
            {"term_id": i, "display_term": f"Term{i}"}
            for i in range(100)
        ]
        text = " ".join([f"Term{i}" for i in range(100)])
        annotations = find_annotations(many_terms, text)
        assert len(annotations) <= MAX_ANNOTATIONS

    def test_matches_in_blocks(self) -> None:
        annotations = find_annotations(
            [{"term_id": 1, "display_term": "Demon King"}],
            "ignored",
            blocks=[{"text": "The Demon King appeared."}, {"text": "Other text."}],
        )
        assert len(annotations) == 1
        assert annotations[0]["matches"][0]["block_index"] == 0
        assert annotations[0]["matches"][0]["start"] == 4

    def test_serializable(self) -> None:
        annotations = find_annotations(
            [{"term_id": 1, "display_term": "Demon King"}],
            "The Demon King appeared.",
        )
        json.dumps(annotations)
        assert annotations[0]["term_id"] == 1
        assert annotations[0]["display_term"] == "Demon King"
