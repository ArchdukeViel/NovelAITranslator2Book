"""Tests for the Glossary and GlossaryTerm models."""

from __future__ import annotations

import pytest

from novelai.glossary.glossary import (
    Glossary,
    GlossaryTerm,
    glossary_status_counts,
    rank_glossary_terms_for_text,
    summarize_term_context,
    normalize_glossary_entries,
    normalize_glossary_entry,
)


class TestGlossaryTerm:
    def test_normalized_strips_whitespace(self) -> None:
        term = GlossaryTerm(source="  hello  ", target="  world  ")
        n = term.normalized()
        assert n.source == "hello"
        assert n.target == "world"

    def test_normalized_raises_on_empty_source(self) -> None:
        with pytest.raises(ValueError, match="source"):
            GlossaryTerm(source="  ", target="ok").normalized()

    def test_normalized_raises_on_empty_target(self) -> None:
        with pytest.raises(ValueError, match="target"):
            GlossaryTerm(source="ok", target="  ").normalized()

    def test_normalized_clears_blank_notes(self) -> None:
        term = GlossaryTerm(source="a", target="b", notes="  ")
        assert term.normalized().notes is None

    def test_normalized_keeps_valid_notes(self) -> None:
        term = GlossaryTerm(source="a", target="b", notes=" hint ")
        assert term.normalized().notes == "hint"

    def test_normalized_rejects_invalid_status(self) -> None:
        with pytest.raises(ValueError, match="status"):
            GlossaryTerm(source="a", target="b", status="bad").normalized()

    def test_normalized_derives_context_summary_from_history(self) -> None:
        term = GlossaryTerm(
            source="hero",
            target="Hero",
            context_history=("Brave hero arrives", "Hero protects town"),
        ).normalized()
        assert term.context_summary is not None
        assert "hero" in term.context_summary.casefold()


class TestGlossary:
    def test_add_term_and_as_entries(self) -> None:
        g = Glossary()
        g.add_term("alpha", "A")
        g.add_term("beta", "B")
        entries = g.as_entries()
        assert len(entries) == 2
        assert entries[0].source == "alpha"
        assert entries[1].source == "beta"

    def test_add_term_overwrites_same_source(self) -> None:
        g = Glossary()
        g.add_term("key", "v1")
        g.add_term("key", "v2")
        assert len(g.as_entries()) == 1
        assert g.as_entries()[0].target == "v2"

    def test_from_entries_with_dicts(self) -> None:
        entries = [
            {"source": "s1", "target": "t1"},
            {"source": "s2", "target": "t2"},
        ]
        g = Glossary.from_entries(entries)
        assert len(g.as_entries()) == 2

    def test_from_entries_with_term_objects(self) -> None:
        terms = [GlossaryTerm(source="a", target="b")]
        g = Glossary.from_entries(terms)
        assert g.as_entries()[0].source == "a"

    def test_translate_applies_substitutions(self) -> None:
        g = Glossary()
        g.add_term("猫", "cat")
        g.add_term("犬", "dog")
        result = g.translate("猫と犬")
        assert result == "catとdog"

    def test_translate_longest_match_first(self) -> None:
        g = Glossary()
        g.add_term("東京都", "Tokyo Metropolis")
        g.add_term("東京", "Tokyo")
        result = g.translate("東京都はすごい")
        assert "Tokyo Metropolis" in result


class TestNormalizeFunctions:
    def test_normalize_glossary_entry_from_dict(self) -> None:
        entry = normalize_glossary_entry({"source": "x", "target": "y"})
        assert entry.source == "x"

    def test_normalize_glossary_entry_from_term(self) -> None:
        term = GlossaryTerm(source="a", target="b")
        entry = normalize_glossary_entry(term)
        assert entry.source == "a"

    def test_normalize_glossary_entry_raises_on_bad_type(self) -> None:
        with pytest.raises(TypeError, match="Unsupported"):
            normalize_glossary_entry("bad")  # type: ignore[arg-type]

    def test_normalize_glossary_entries_none_returns_empty(self) -> None:
        assert normalize_glossary_entries(None) == []

    def test_normalize_glossary_entries_deduplicates(self) -> None:
        entries = [
            {"source": "dup", "target": "first"},
            {"source": "dup", "target": "second"},
        ]
        result = normalize_glossary_entries(entries)
        assert len(result) == 1
        assert result[0].target == "second"

    def test_normalize_glossary_entries_from_glossary_object(self) -> None:
        g = Glossary()
        g.add_term("x", "y")
        result = normalize_glossary_entries(g)
        assert len(result) == 1


class TestGlossaryContextRanking:
    def test_summarize_term_context_deduplicates_and_limits(self) -> None:
        summary = summarize_term_context(
            [
                "The hero enters the city",
                "The hero enters the city",
                "The hero saves the village",
                "The hero meets the king",
            ],
            max_items=2,
        )
        assert summary == "The hero enters the city | The hero saves the village"

    def test_rank_glossary_terms_prefers_direct_mentions(self) -> None:
        terms = [
            GlossaryTerm(source="hero", target="Hero", status="approved"),
            GlossaryTerm(source="village chief", target="Village Chief", status="approved"),
            GlossaryTerm(source="artifact", target="Artifact", status="pending"),
        ]
        ranked = rank_glossary_terms_for_text(
            "The hero bowed before the village chief.",
            terms,
            chunk_index=3,
            max_entries=2,
        )
        assert [term.source for term in ranked] == ["hero", "village chief"]

    def test_rank_glossary_terms_excludes_ignored_terms(self) -> None:
        terms = [
            GlossaryTerm(source="hero", target="Hero", status="ignored"),
            GlossaryTerm(source="mage", target="Mage", status="approved"),
        ]
        ranked = rank_glossary_terms_for_text("The hero and mage arrived.", terms)
        assert [term.source for term in ranked] == ["mage"]


class TestGlossaryStatusCounts:
    def test_glossary_status_counts_tracks_reviewed_and_pending(self) -> None:
        counts = glossary_status_counts(
            [
                {"source": "a", "target": "A", "status": "pending"},
                {"source": "b", "target": "B", "status": "approved"},
                {"source": "c", "target": "C", "status": "ignored"},
                {"source": "d", "target": "D", "status": "translated"},
            ]
        )
        assert counts["total"] == 4
        assert counts["pending"] == 1
        assert counts["approved"] == 1
        assert counts["ignored"] == 1
        assert counts["translated"] == 1
        assert counts["reviewed"] == 3
