"""Tests for glossary diagnostics admin surfacing — normalizer, aggregation, safety."""

from __future__ import annotations

import json

from novelai.services.glossary_diagnostics import (
    MAX_DIAGNOSTIC_ITEMS,
    MAX_TERM_LENGTH,
    aggregate_glossary_diagnostics,
    normalize_glossary_diagnostics,
)


class TestNormalizer:
    def test_empty_metadata(self) -> None:
        r = normalize_glossary_diagnostics({})
        assert r["diagnostics_available"] is False

    def test_none_metadata(self) -> None:
        r = normalize_glossary_diagnostics(None)
        assert r["diagnostics_available"] is False

    def test_with_glossary_term_count(self) -> None:
        r = normalize_glossary_diagnostics({"glossary_term_count": 10, "glossary_revision": 5})
        assert r["diagnostics_available"] is True
        assert r["glossary_revision"] == 5
        assert r["term_count_available"] == 10

    def test_with_glossary_hash(self) -> None:
        r = normalize_glossary_diagnostics({"glossary_hash": "abc123", "glossary_term_count_injected": 3})
        assert r["diagnostics_available"] is True
        assert r["glossary_hash"] == "abc123"
        assert r["term_count_injected"] == 3

    def test_with_injection_service_metadata(self) -> None:
        r = normalize_glossary_diagnostics({
            "glossary_injection": {
                "terms_available": 15,
                "terms_injected": 12,
                "truncated": True,
                "warnings": ["long_term_warning"],
            }
        })
        assert r["diagnostics_available"] is True
        assert r["term_count_available"] == 15
        assert r["term_count_injected"] == 12
        assert r["prompt_block_truncated"] is True
        assert "long_term_warning" in r["warnings"]

    def test_prompt_truncated_flag(self) -> None:
        r = normalize_glossary_diagnostics({"glossary_term_count": 5, "glossary_prompt_truncated": True})
        assert r["prompt_block_truncated"] is True

    def test_missing_fields_default_to_zero(self) -> None:
        r = normalize_glossary_diagnostics({"glossary_term_count": 1})
        assert r["conflict_count"] == 0
        assert r["warning_count"] == 0
        assert r["term_count_injected"] == 0

    def test_warnings_list_bounded(self) -> None:
        many_warnings = [f"warning_{i}" for i in range(100)]
        r = normalize_glossary_diagnostics({
            "glossary_term_count": 1,
            "glossary_warnings": many_warnings,
        })
        assert len(r["warnings"]) <= MAX_DIAGNOSTIC_ITEMS

    def test_conflicts_list_bounded(self) -> None:
        many = [f"conflict_{i}" for i in range(100)]
        r = normalize_glossary_diagnostics({
            "glossary_term_count": 1,
            "glossary_conflicts": many,
        })
        assert len(r["conflicts"]) <= MAX_DIAGNOSTIC_ITEMS

    def test_overlong_terms_truncated(self) -> None:
        r = normalize_glossary_diagnostics({
            "glossary_term_count": 1,
            "glossary_warnings": ["x" * 100],
        })
        assert len(r["warnings"][0]) <= MAX_TERM_LENGTH

    def test_serializable(self) -> None:
        r = normalize_glossary_diagnostics({
            "glossary_term_count": 5,
            "glossary_revision": 3,
            "glossary_hash": "h1",
            "glossary_term_count_injected": 4,
            "glossary_conflicts": ["term_a", "term_b"],
            "glossary_warnings": ["warning_1"],
        })
        json.dumps(r)
        assert r["conflict_count"] == 2
        assert r["warning_count"] == 1

    def test_unavailable_state(self) -> None:
        r = normalize_glossary_diagnostics({"source_text": "something"})
        assert r["diagnostics_available"] is False


class TestAggregation:
    def test_empty_list(self) -> None:
        r = aggregate_glossary_diagnostics([])
        assert r["chapters_with_diagnostics"] == 0
        assert r["chapters_missing_diagnostics"] == 0

    def test_single_chapter(self) -> None:
        r = aggregate_glossary_diagnostics([
            {"diagnostics_available": True, "term_count_available": 10, "term_count_injected": 8,
             "conflict_count": 1, "warning_count": 2, "prompt_block_truncated": False},
        ])
        assert r["chapters_with_diagnostics"] == 1
        assert r["total_terms_available"] == 10
        assert r["total_terms_injected"] == 8
        assert r["total_conflicts"] == 1
        assert r["total_warnings"] == 2
        assert r["chapters_with_conflicts"] == 1
        assert r["chapters_with_warnings"] == 1

    def test_mixed_available_and_unavailable(self) -> None:
        r = aggregate_glossary_diagnostics([
            {"diagnostics_available": True, "term_count_available": 5, "term_count_injected": 3,
             "conflict_count": 0, "warning_count": 0, "prompt_block_truncated": False},
            {"diagnostics_available": False},
        ])
        assert r["chapters_with_diagnostics"] == 1
        assert r["chapters_missing_diagnostics"] == 1
        assert r["total_terms_available"] == 5

    def test_zero_injected_terms(self) -> None:
        r = aggregate_glossary_diagnostics([
            {"diagnostics_available": True, "term_count_available": 5, "term_count_injected": 0,
             "conflict_count": 0, "warning_count": 0, "prompt_block_truncated": False},
        ])
        assert r["chapters_with_zero_injected_terms"] == 1

    def test_truncated_blocks(self) -> None:
        r = aggregate_glossary_diagnostics([
            {"diagnostics_available": True, "term_count_available": 5, "term_count_injected": 3,
             "conflict_count": 0, "warning_count": 0, "prompt_block_truncated": True},
        ])
        assert r["chapters_with_truncated_blocks"] == 1
