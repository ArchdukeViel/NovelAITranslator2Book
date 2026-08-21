"""Tests for the Glossary and GlossaryTerm models."""

from __future__ import annotations

import json
from typing import Any

import pytest

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
from novelai.glossary.glossary import (
    Glossary,
    GlossaryTerm,
    glossary_status_counts,
    normalize_glossary_entries,
    normalize_glossary_entry,
    rank_glossary_terms_for_text,
    summarize_term_context,
)
from novelai.services.orchestration.glossary import (
    discover_incremental_glossary_terms,
    parse_incremental_glossary_response,
    translate_glossary_terms,
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

    def test_rank_glossary_terms_excludes_pending_candidates(self) -> None:
        terms = [
            GlossaryTerm(source="pending", target="Provisional", status="pending"),
            GlossaryTerm(source="approved", target="Approved", status="approved"),
        ]
        ranked = rank_glossary_terms_for_text("pending approved", terms)
        assert [term.source for term in ranked] == ["approved"]


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


def test_incremental_glossary_response_requires_source_evidence_and_known_ids() -> None:
    result = parse_incremental_glossary_response(
        '{"items": ['
        '{"chapter_id":"ch-1","source":"魔導具","target":"magic device","confidence":0.91},'
        '{"chapter_id":"ch-1","source":"not present","target":"Invented","confidence":0.99},'
        '{"chapter_id":"unknown","source":"魔導具","target":"Unknown","confidence":0.99}'
        "]}",
        source_text_by_chapter={"ch-1": "魔導具を使う。魔導具が光る。"},
        max_terms=10,
    )
    assert len(result) == 1
    assert result[0]["safe_to_activate"] is True
    assert result[0]["occurrence_count"] == 2


class _IncrementalGlossaryStorage:
    def __init__(self) -> None:
        self.text = "Aria enters the city. Aria returns before dawn."
        self.metadata: dict[str, Any] = {}
        self.entries: list[dict[str, Any]] = []

    def load_chapter(self, novel_id: str, chapter_id: str) -> dict[str, str]:
        return {"text": self.text}

    def load_metadata(self, novel_id: str) -> dict[str, Any]:
        return self.metadata

    def save_metadata(self, novel_id: str, metadata: dict[str, Any]) -> None:
        self.metadata = metadata

    def load_glossary(self, novel_id: str) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self.entries]

    def save_glossary(self, novel_id: str, entries: list[dict[str, Any]]) -> None:
        self.entries = [dict(entry) for entry in entries]


class _IncrementalGlossaryProvider:
    key = "gemini"

    def __init__(self) -> None:
        self.calls = 0

    async def translate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            return {"text": "NOT JSON", "metadata": {"usage": {"total_tokens": 4}}}
        return {"text": '{"items": []}', "metadata": {"usage": {"total_tokens": 4}}}


class _IncrementalGlossaryService:
    def __init__(self) -> None:
        self.storage = _IncrementalGlossaryStorage()
        self.provider = _IncrementalGlossaryProvider()

    def _resolve_provider_and_model(self, provider_key: str | None, provider_model: str | None) -> tuple[str, str]:
        return provider_key or "gemini", provider_model or GEMINI_DEFAULT_MODEL

    def _provider_factory(self, provider_key: str) -> _IncrementalGlossaryProvider:
        return self.provider

    def _record_usage(self, provider_key: str, provider_model: str, metadata: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_incremental_glossary_retries_structured_response_and_resumes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_MAX_ATTEMPTS_PER_CHUNK", 2)
    service = _IncrementalGlossaryService()
    first = await discover_incremental_glossary_terms(
        service,
        "novel-1",
        [{"chapter_id": "1"}],
        provider_key="gemini",
        provider_model=GEMINI_DEFAULT_MODEL,
        source_language="Japanese",
    )
    assert service.provider.calls == 2
    assert first["provider_calls"] == 2
    assert first["changed_chapters"] == ["1"]

    resumed = await discover_incremental_glossary_terms(
        service,
        "novel-1",
        [{"chapter_id": "1"}],
        provider_key="gemini",
        provider_model=GEMINI_DEFAULT_MODEL,
        source_language="Japanese",
    )
    assert service.provider.calls == 2
    assert resumed["provider_calls"] == 0
    assert resumed["unchanged_chapters"] == ["1"]
    assert resumed["changed_chapters"] == []


class _BatchGlossaryProvider:
    key = "mock"

    def __init__(self) -> None:
        self.calls = 0

    def available_models(self) -> list[str]:
        return ["mock-1.0"]

    async def translate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        payload = json.loads(prompt.split("Input: ", 1)[1])
        return {
            "text": json.dumps(
                {"items": [{"id": item["id"], "translation": f"English {item['id']}"} for item in payload["items"]]}
            ),
            "metadata": {"usage": {"total_tokens": 20}},
        }


class _BatchGlossaryStorage:
    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self.entries = entries

    def load_glossary(self, novel_id: str) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self.entries]

    def load_metadata(self, novel_id: str) -> dict[str, Any]:
        return {}

    def save_glossary(self, novel_id: str, entries: list[dict[str, Any]]) -> None:
        self.entries = [dict(entry) for entry in entries]


class _BatchGlossaryCache:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str], str] = {}

    def get(self, text: str, provider_key: str, provider_model: str) -> str | None:
        return self.values.get((text, provider_key, provider_model))

    def set(self, text: str, provider_key: str, provider_model: str, translated_text: str) -> None:
        self.values[(text, provider_key, provider_model)] = translated_text


class _BatchGlossaryService:
    def __init__(self, entries: list[dict[str, Any]], provider: _BatchGlossaryProvider) -> None:
        self.storage = _BatchGlossaryStorage(entries)
        self._cache = _BatchGlossaryCache()
        self.provider = provider

    def _resolve_workflow_profile(self, step: str, metadata: dict[str, Any]) -> tuple[str, str]:
        return "mock", "mock-1.0"

    def _resolve_provider_and_model(self, provider_key: str | None, provider_model: str | None) -> tuple[str, str]:
        return provider_key or "mock", provider_model or "mock-1.0"

    def _provider_factory(self, provider_key: str) -> _BatchGlossaryProvider:
        return self.provider

    def _record_usage(self, provider_key: str, provider_model: str, metadata: Any) -> None:
        return None

    def _phase_payload(self, **payload: Any) -> dict[str, Any]:
        return payload


@pytest.mark.asyncio
async def test_glossary_translation_batches_twenty_terms_into_one_provider_call() -> None:
    provider = _BatchGlossaryProvider()
    service = _BatchGlossaryService(
        [{"source": f"term-{index}", "target": "", "status": "pending"} for index in range(20)],
        provider,
    )
    result = await translate_glossary_terms(service, "novel-1")
    assert provider.calls == 1
    assert result["provider_calls"] == 1
    assert result["batch_count"] == 1
    assert result["translated"] == 20
