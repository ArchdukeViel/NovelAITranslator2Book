"""Tests for no-provider glossary candidate import.

Uses in-memory SQLite and synthetic chapter text. No providers, scraping,
translation, real storage, or chapter repair are involved.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryEntry, NovelGlossarySourceProvenance
from novelai.db.models.novel import Novel
from novelai.services.glossary_candidate_import import GlossaryCandidateImporter
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
        source_key: str = "stub",
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


def _seed_repeated_translations(storage: FakeChapterStorage, novel_slug: str) -> None:
    storage.add_translated(
        novel_slug,
        "1",
        "Pocott Village welcomed travelers. The World Tree watched over Pocott Village.",
    )
    storage.add_translated(
        novel_slug,
        "2",
        "Gurd visited Pocott Village. The World Tree blessed Gurd near Pocott Village.",
    )


def test_dry_run_returns_candidates_without_writing_entries(session, storage) -> None:
    novel = _make_novel(session, "dry-run")
    _make_chapter(session, novel, 1)
    _make_chapter(session, novel, 2)
    _seed_repeated_translations(storage, novel.slug)

    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(novel.id)

    assert result.dry_run is True
    assert result.candidates_found > 0
    assert any(candidate.canonical_term == "Pocott Village" for candidate in result.candidates)
    assert session.query(NovelGlossaryEntry).count() == 0


def test_apply_creates_backend_candidate_entries_only(session, storage) -> None:
    novel = _make_novel(session, "apply")
    _make_chapter(session, novel, 1)
    _seed_repeated_translations(storage, novel.slug)

    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(novel.id, dry_run=False)

    entries = session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id).all()
    assert result.candidates_created == len(entries)
    assert entries
    assert {entry.status for entry in entries} == {"candidate"}
    assert all(entry.owner_locked is False for entry in entries)
    assert all(entry.enforcement_level == "none" for entry in entries)


def test_approved_existing_entry_is_not_overwritten(session, storage) -> None:
    novel = _make_novel(session, "approved-skip")
    _seed_repeated_translations(storage, novel.slug)
    repo = GlossaryRepository(session)
    approved = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Pocott Village",
        term_type="place",
        approved_translation="Pocott Village",
        status="approved",
        owner_locked=True,
        admin_notes="Owner decision.",
    )

    result = GlossaryCandidateImporter(session, storage, repository=repo).import_from_saved_chapters(
        novel.id,
        dry_run=False,
    )

    session.refresh(approved)
    assert approved.status == "approved"
    assert approved.owner_locked is True
    assert approved.admin_notes == "Owner decision."
    assert result.candidates_skipped >= 1
    assert session.query(NovelGlossaryEntry).filter_by(canonical_term="Pocott Village").count() == 1


def test_duplicate_candidates_merge_into_existing_candidate(session, storage) -> None:
    novel = _make_novel(session, "merge")
    _seed_repeated_translations(storage, novel.slug)
    repo = GlossaryRepository(session)
    existing = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Pocott Village",
        term_type="place",
        approved_translation="Pocott Village",
        status="candidate",
        confidence=0.1,
    )

    result = GlossaryCandidateImporter(session, storage, repository=repo).import_from_saved_chapters(
        novel.id,
        dry_run=False,
    )

    session.refresh(existing)
    assert result.candidates_merged >= 1
    assert existing.status == "candidate"
    assert existing.confidence is not None and existing.confidence > 0.1
    assert session.query(NovelGlossaryEntry).filter_by(canonical_term="Pocott Village").count() == 1


def test_candidates_across_different_novels_remain_separate(session, storage) -> None:
    novel_a = _make_novel(session, "novel-a")
    novel_b = _make_novel(session, "novel-b")
    _seed_repeated_translations(storage, novel_a.slug)
    _seed_repeated_translations(storage, novel_b.slug)

    importer = GlossaryCandidateImporter(session, storage)
    importer.import_from_saved_chapters(novel_a.id, dry_run=False)
    importer.import_from_saved_chapters(novel_b.id, dry_run=False)

    entry_a = session.query(NovelGlossaryEntry).filter_by(novel_id=novel_a.id, canonical_term="Pocott Village").one()
    entry_b = session.query(NovelGlossaryEntry).filter_by(novel_id=novel_b.id, canonical_term="Pocott Village").one()
    assert entry_a.id != entry_b.id


def test_apply_creates_compact_source_agnostic_provenance(session, storage) -> None:
    novel = _make_novel(session, "provenance")
    chapter = _make_chapter(session, novel, 1)
    storage.add_raw(novel.slug, "1", "ポコットで会った。ポコットは村です。", source_key="kakuyomu")
    storage.add_translated(
        novel.slug,
        "1",
        "Pocott Village appeared. Pocott Village remained peaceful.",
    )

    GlossaryCandidateImporter(session, storage).import_from_saved_chapters(novel.id, dry_run=False)

    entry = session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="Pocott Village").one()
    provenance = session.query(NovelGlossarySourceProvenance).filter_by(glossary_entry_id=entry.id).all()
    assert provenance
    assert all(item.novel_id == novel.id for item in provenance)
    assert all(item.chapter_id == chapter.id for item in provenance if item.source_chapter_id == "1")
    assert all(item.evidence_ref == "saved_chapter:1" for item in provenance if item.source_chapter_id == "1")
    assert all((item.observed_translated_term or "") != storage.translated[(novel.slug, "1")]["text"] for item in provenance)


def test_banned_or_rejected_alias_conflict_is_reported_and_skipped(session, storage) -> None:
    novel = _make_novel(session, "banned")
    _seed_repeated_translations(storage, novel.slug)
    repo = GlossaryRepository(session)
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Pocott",
        term_type="place",
        status="approved",
    )
    repo.add_glossary_alias(
        entry_id=entry.id,
        novel_id=novel.id,
        alias_text="Pocott Village",
        alias_type="banned",
    )

    result = GlossaryCandidateImporter(session, storage, repository=repo).import_from_saved_chapters(
        novel.id,
        dry_run=False,
    )

    assert any("Pocott Village" in conflict for conflict in result.conflicts)
    assert session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="Pocott Village").count() == 0


def test_raw_text_unavailable_path_works_with_translated_text_only(session, storage) -> None:
    novel = _make_novel(session, "translated-only")
    storage.add_translated(novel.slug, "1", "World Tree. World Tree. World Tree.")

    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(novel.id)

    assert any("Raw chapter text was unavailable" in warning for warning in result.warnings)
    assert any(candidate.canonical_term == "World Tree" for candidate in result.candidates)


def test_import_does_not_mutate_translated_chapter_text(session, storage) -> None:
    novel = _make_novel(session, "no-rewrite")
    _seed_repeated_translations(storage, novel.slug)
    before = deepcopy(storage.translated)

    GlossaryCandidateImporter(session, storage).import_from_saved_chapters(novel.id, dry_run=False)

    assert storage.translated == before


def test_no_provider_call_is_required_or_invoked(session, storage) -> None:
    novel = _make_novel(session, "no-provider")
    _seed_repeated_translations(storage, novel.slug)

    class ProviderTrap:
        def translate(self, *_args: Any, **_kwargs: Any) -> None:
            raise AssertionError("provider should not be called")

    _provider = ProviderTrap()
    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(novel.id)

    assert result.candidates_found > 0
