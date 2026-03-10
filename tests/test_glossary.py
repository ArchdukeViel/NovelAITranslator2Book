"""Tests for the Glossary and GlossaryTerm models."""

from __future__ import annotations

import pytest

from novelai.glossary.glossary import (
    Glossary,
    GlossaryTerm,
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
