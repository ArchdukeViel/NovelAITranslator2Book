"""Tests for provider-assisted glossary candidate suggestions.

Provider calls are faked. The service reads synthetic saved chapter payloads and
may write only glossary candidate data in apply-mode tests.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryAlias, NovelGlossaryEntry, NovelGlossarySourceProvenance
from novelai.db.models.novel import Novel
from novelai.services.glossary_provider_suggestion import GlossaryProviderSuggestionService
from novelai.services.glossary_repository import GlossaryRepository

_SQLITE = "sqlite:///:memory:"


class FakeChapterStorage:
    def __init__(self) -> None:
        self.raw: dict[tuple[str, str], dict[str, Any]] = {}
        self.translated: dict[tuple[str, str], dict[str, Any]] = {}

    def add_raw(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        *,
        source_key: str = "kakuyomu",
        input_adapter_key: str | None = None,
    ) -> None:
        self.raw[(novel_id, chapter_id)] = {
            "id": chapter_id,
            "text": text,
            "source_key": source_key,
            "input_adapter_key": input_adapter_key,
        }

    def add_translated(self, novel_id: str, chapter_id: str, text: str) -> None:
        self.translated[(novel_id, chapter_id)] = {
            "id": chapter_id,
            "text": text,
            "provider": "fixture",
            "model": "fixture-model",
        }

    def list_stored_chapters(self, novel_id: str) -> list[str]:
        return sorted({chapter_id for nid, chapter_id in self.raw | self.translated if nid == novel_id})

    def load_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        item = self.raw.get((novel_id, chapter_id))
        return deepcopy(item) if item is not None else None

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        item = self.translated.get((novel_id, chapter_id))
        return deepcopy(item) if item is not None else None


class FakeProvider:
    def __init__(self, payload: dict[str, Any] | str) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def suggest_glossary_candidates(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


@pytest.fixture()
def session():
    engine = create_engine(_SQLITE)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def storage() -> FakeChapterStorage:
    return FakeChapterStorage()


def _make_novel(session, slug: str) -> Novel:
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", status="ongoing")
    session.add(novel)
    session.flush()
    return novel


def _make_chapter(session, novel: Novel, number: int) -> Chapter:
    chapter = Chapter(novel_id=novel.id, chapter_number=number, title=f"Chapter {number}")
    session.add(chapter)
    session.flush()
    return chapter


def _seed_chapter(storage: FakeChapterStorage, novel_slug: str) -> None:
    storage.add_raw(novel_slug, "1", "ポコット村でギルドと会った。世界樹は村の近くにある。")
    storage.add_translated(novel_slug, "1", "Pocott Village met the Guild. The World Tree watched over it.")


def _provider_payload(*, confidence: float = 0.86) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "raw_term": "ポコット村",
                "suggested_translation": "Pocott Village",
                "term_type": "place",
                "confidence": confidence,
                "aliases": [
                    {
                        "alias_text": "Pokot Village",
                        "alias_type": "observed",
                        "applies_to": "translated_text",
                        "reason": "Observed alternate rendering.",
                    }
                ],
                "evidence": [
                    {
                        "source_chapter_id": "1",
                        "context_ref": "chapter:1",
                        "summary": "Repeated place name.",
                    }
                ],
                "rationale": "Place name with a consistent English rendering.",
            }
        ],
        "warnings": [{"message": "Fixture warning."}],
    }


def test_dry_run_calls_fake_provider_and_writes_no_entries(session, storage) -> None:
    novel = _make_novel(session, "dry-provider")
    _make_chapter(session, novel, 1)
    _seed_chapter(storage, novel.slug)
    provider = FakeProvider(_provider_payload())

    result = GlossaryProviderSuggestionService(session, storage, provider).suggest_from_saved_chapters(novel.id)

    assert result.dry_run is True
    assert result.candidates_found == 1
    assert result.provider_warnings == ["Fixture warning"]
    assert len(provider.prompts) == 1
    assert "Return strict JSON only" in provider.prompts[0]
    assert "Do not translate, rewrite, repair" in provider.prompts[0]
    assert "Allowed term_type values are exactly:" in provider.prompts[0]
    assert "character" in provider.prompts[0]
    assert "species" in provider.prompts[0]
    assert result.scanned_chapter_count == 1
    assert result.highest_scanned_chapter_number == 1
    assert session.query(NovelGlossaryEntry).count() == 0


def test_apply_creates_candidate_entries_only(session, storage) -> None:
    novel = _make_novel(session, "apply-provider")
    _make_chapter(session, novel, 1)
    _seed_chapter(storage, novel.slug)

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(_provider_payload()),
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    entry = session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="ポコット村").one()
    assert result.candidates_created == 1
    assert result.candidates[0].action == "created"
    assert entry.status == "candidate"
    assert entry.enforcement_level == "none"
    assert entry.owner_locked is False
    assert entry.public_visible is False
    assert entry.approved_translation == "Pocott Village"


def test_provider_candidates_never_approve_or_overwrite_approved_entries(session, storage) -> None:
    novel = _make_novel(session, "approved-provider")
    _seed_chapter(storage, novel.slug)
    repo = GlossaryRepository(session)
    approved = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="ポコット村",
        term_type="place",
        approved_translation="Owner Pocott",
        status="approved",
        owner_locked=True,
        admin_notes="Owner note.",
    )

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(_provider_payload(confidence=1.0)),
        repository=repo,
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    session.refresh(approved)
    assert result.candidates_skipped == 1
    assert result.candidates[0].action == "skipped"
    assert approved.status == "approved"
    assert approved.approved_translation == "Owner Pocott"
    assert approved.owner_locked is True
    assert approved.admin_notes == "Owner note."
    assert session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="ポコット村").count() == 1


def test_duplicate_provider_candidates_merge_existing_candidate(session, storage) -> None:
    novel = _make_novel(session, "merge-provider")
    _seed_chapter(storage, novel.slug)
    repo = GlossaryRepository(session)
    existing = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="ポコット村",
        term_type="place",
        approved_translation="Pocott Village",
        status="candidate",
        confidence=0.2,
        admin_notes="Do not touch.",
    )
    payload = _provider_payload(confidence=0.9)
    payload["candidates"].append(deepcopy(payload["candidates"][0]))

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(payload),
        repository=repo,
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    session.refresh(existing)
    assert result.candidates_found == 1
    assert result.candidates_merged == 1
    assert existing.status == "candidate"
    assert existing.confidence == 0.9
    assert existing.admin_notes == "Do not touch."
    assert session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="ポコット村").count() == 1


def test_invalid_json_returns_warning_and_writes_nothing(session, storage) -> None:
    novel = _make_novel(session, "bad-json")
    _seed_chapter(storage, novel.slug)

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider("not json"),
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    assert result.candidates_found == 0
    assert any("invalid JSON" in warning for warning in result.warnings)
    assert session.query(NovelGlossaryEntry).count() == 0


def test_invalid_candidate_fields_are_skipped_and_confidence_is_clamped(session, storage) -> None:
    novel = _make_novel(session, "validation-provider")
    _seed_chapter(storage, novel.slug)
    provider = FakeProvider(
        {
            "candidates": [
                {"raw_term": "", "suggested_translation": "Blank", "term_type": "place", "confidence": 0.5},
                {"raw_term": "Chapter", "suggested_translation": "Chapter", "term_type": "concept", "confidence": 0.5},
                {
                    "raw_term": "世界樹",
                    "suggested_translation": "World Tree",
                    "term_type": "mystery-kind",
                    "confidence": 1.4,
                    "aliases": [],
                    "evidence": [{"source_chapter_id": "1"}],
                    "rationale": "Valid after normalization.",
                },
                {"raw_term": "ギルド", "suggested_translation": "Guild", "term_type": "organization", "confidence": "high"},
            ],
        }
    )

    result = GlossaryProviderSuggestionService(session, storage, provider).suggest_from_saved_chapters(novel.id)

    assert result.candidates_found == 1
    candidate = result.candidates[0]
    assert candidate.raw_term == "世界樹"
    assert candidate.term_type == "other"
    assert candidate.confidence == 1.0
    assert any("blank" in warning for warning in result.provider_warnings)
    assert any("generic" in warning for warning in result.provider_warnings)
    assert any("mystery-kind" in warning and "other" in warning for warning in result.provider_warnings)
    assert any("confidence" in warning for warning in result.provider_warnings)


def test_provider_term_type_aliases_are_normalized_with_specific_warnings(session, storage) -> None:
    novel = _make_novel(session, "term-type-provider")
    _seed_chapter(storage, novel.slug)
    provider = FakeProvider(
        {
            "candidates": [
                {
                    "raw_term": "ãƒã‚³ãƒƒãƒˆ",
                    "suggested_translation": "Pocott",
                    "term_type": "village",
                    "confidence": 0.9,
                    "aliases": [],
                    "evidence": [{"source_chapter_id": "1"}],
                },
                {
                    "raw_term": "ã‚°ãƒ«ãƒ‰",
                    "suggested_translation": "Gurd",
                    "term_type": "person",
                    "confidence": 0.8,
                    "aliases": [],
                    "evidence": [{"source_chapter_id": "1"}],
                },
                {
                    "raw_term": "ä¸–ç•Œæ¨¹ã®åŠ è­·",
                    "suggested_translation": "Blessing of the World Tree",
                    "term_type": "blessing",
                    "confidence": 0.7,
                    "aliases": [],
                    "evidence": [{"source_chapter_id": "1"}],
                },
                {
                    "raw_term": "ã‚¨ãƒ«ãƒ•",
                    "suggested_translation": "Elf",
                    "term_type": "race",
                    "confidence": 0.6,
                    "aliases": [],
                    "evidence": [{"source_chapter_id": "1"}],
                },
            ],
        }
    )

    result = GlossaryProviderSuggestionService(session, storage, provider).suggest_from_saved_chapters(novel.id)

    assert [candidate.term_type for candidate in result.candidates] == ["place", "character", "concept", "species"]
    assert any("'village'" in warning and "'place'" in warning for warning in result.provider_warnings)
    assert any("'person'" in warning and "'character'" in warning for warning in result.provider_warnings)
    assert any("'blessing'" in warning and "'concept'" in warning for warning in result.provider_warnings)
    assert any("'race'" in warning and "'species'" in warning for warning in result.provider_warnings)


def test_provider_chapter_scope_reports_scan_count_and_safety_cap(session, storage) -> None:
    novel = _make_novel(session, "scope-provider")
    for number in range(1, 4):
        _make_chapter(session, novel, number)
        storage.add_raw(novel.slug, str(number), f"raw {number} ãƒã‚³ãƒƒãƒˆ")
        storage.add_translated(novel.slug, str(number), f"translated {number} Pocott")

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(_provider_payload()),
    ).suggest_from_saved_chapters(novel.id, max_chapters=2, chapter_scope="latest")

    assert result.scanned_chapter_count == 2
    assert result.highest_scanned_chapter_number == 3
    assert any("scanned 2 of 3 saved chapters" in warning for warning in result.warnings)
    assert "Chapter ref: 3" in result.candidates[0].chapter_refs or result.highest_scanned_chapter_number == 3


def test_aliases_store_only_safe_alias_types(session, storage) -> None:
    novel = _make_novel(session, "alias-provider")
    _seed_chapter(storage, novel.slug)
    payload = _provider_payload()
    payload["candidates"][0]["aliases"] = [
        {"alias_text": "Pokot Village", "alias_type": "observed"},
        {"alias_text": "Pocott source", "alias_type": "source_variant"},
        {"alias_text": "Do Not Use", "alias_type": "banned"},
    ]

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(payload),
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    aliases = session.query(NovelGlossaryAlias).filter_by(novel_id=novel.id).all()
    assert result.candidates_created == 1
    assert {alias.alias_text for alias in aliases} == {"Pokot Village", "Pocott source"}
    assert {alias.alias_type for alias in aliases} == {"observed", "source_variant"}
    assert any("unsupported alias_type" in warning for warning in result.provider_warnings)


def test_apply_creates_compact_provider_provenance_without_long_excerpts(session, storage) -> None:
    novel = _make_novel(session, "provenance-provider")
    chapter = _make_chapter(session, novel, 1)
    _seed_chapter(storage, novel.slug)
    payload = _provider_payload()
    payload["candidates"][0]["evidence"] = [
        {
            "source_chapter_id": "1",
            "summary": "This is a very long excerpt-like string that keeps going past what should be treated as "
            "compact evidence because it contains far too many words for a short reference.",
        }
    ]

    GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(payload),
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    entry = session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="ポコット村").one()
    provenance = session.query(NovelGlossarySourceProvenance).filter_by(glossary_entry_id=entry.id).one()
    assert provenance.chapter_id == chapter.id
    assert provenance.evidence_ref == "provider_suggestion:1"
    assert provenance.local_reference == "chapter:1"
    assert provenance.evidence_quality == "translated_only"
    assert provenance.raw_source_term == "ポコット村"
    assert provenance.observed_translated_term == "Pocott Village"
    assert storage.translated[(novel.slug, "1")]["text"] not in {
        provenance.evidence_ref,
        provenance.local_reference,
        provenance.raw_source_term,
        provenance.observed_translated_term,
    }


def test_blocked_alias_conflict_is_skipped(session, storage) -> None:
    novel = _make_novel(session, "blocked-provider")
    _seed_chapter(storage, novel.slug)
    repo = GlossaryRepository(session)
    entry = repo.create_glossary_entry(novel_id=novel.id, canonical_term="Pocott", term_type="place", status="approved")
    repo.add_glossary_alias(
        entry_id=entry.id,
        novel_id=novel.id,
        alias_text="ポコット村",
        alias_type="rejected",
    )

    result = GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(_provider_payload()),
        repository=repo,
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    assert result.candidates_skipped == 1
    assert result.candidates[0].action == "conflict"
    assert any("rejected/banned alias" in conflict for conflict in result.conflicts)
    assert session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="ポコット村").count() == 0


def test_provider_suggestion_does_not_mutate_chapter_storage(session, storage) -> None:
    novel = _make_novel(session, "no-rewrite-provider")
    _seed_chapter(storage, novel.slug)
    before_raw = deepcopy(storage.raw)
    before_translated = deepcopy(storage.translated)

    GlossaryProviderSuggestionService(
        session,
        storage,
        FakeProvider(_provider_payload()),
    ).suggest_from_saved_chapters(novel.id, dry_run=False)

    assert storage.raw == before_raw
    assert storage.translated == before_translated
