"""Tests for preview-only approved glossary repair scanning."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ORM models are registered by the session-scoped autouse fixture in conftest.py.
from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryDecisionEvent, NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.services.glossary_apply_preview import GlossaryApplyPreviewRequest, GlossaryApplyPreviewService
from novelai.services.glossary_repository import GlossaryRepository

_SQLITE = "sqlite:///:memory:"


class FakeChapterStorage:
    def __init__(self) -> None:
        self.translated: dict[tuple[str, str], dict[str, Any]] = {}
        self.save_calls = 0

    def add_translated(self, novel_id: str, chapter_id: str, text: str) -> None:
        self.translated[(novel_id, chapter_id)] = {"id": chapter_id, "text": text}

    def list_stored_chapters(self, novel_id: str) -> list[str]:
        return sorted({chapter_id for stored_novel_id, chapter_id in self.translated if stored_novel_id == novel_id})

    def list_translated_chapters(self, novel_id: str) -> list[str]:
        return self.list_stored_chapters(novel_id)

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        item = self.translated.get((novel_id, chapter_id))
        return deepcopy(item) if item is not None else None

    def save_translated_chapter(self, *args: Any, **kwargs: Any) -> None:
        self.save_calls += 1
        raise AssertionError("Preview must not write translated chapters.")


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


@pytest.fixture()
def repo(session) -> GlossaryRepository:
    return GlossaryRepository(session)


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


def _approved_entry(repo: GlossaryRepository, novel: Novel, term: str, translation: str) -> NovelGlossaryEntry:
    return repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term=term,
        term_type="place",
        approved_translation=translation,
        status="approved",
    )


def _add_old_variant(
    repo: GlossaryRepository,
    novel: Novel,
    entry: NovelGlossaryEntry,
    alias_text: str,
    *,
    alias_type: str = "rejected",
) -> None:
    repo.add_glossary_alias(
        entry_id=entry.id,
        novel_id=novel.id,
        alias_text=alias_text,
        alias_type=alias_type,
    )


def test_preview_includes_only_approved_entries_and_old_variants(session, storage, repo) -> None:
    novel = _make_novel(session, "eligible")
    _make_chapter(session, novel, 1)
    approved = _approved_entry(repo, novel, "Pocott", "Pocott")
    _add_old_variant(repo, novel, approved, "Pokot")
    candidate = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Gurd",
        term_type="character",
        approved_translation="Gurd",
        status="candidate",
    )
    _add_old_variant(repo, novel, candidate, "Guld")
    rejected = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="World Tree",
        term_type="concept",
        approved_translation="Blessing",
        status="rejected",
    )
    _add_old_variant(repo, novel, rejected, "Protection")
    storage.add_translated(novel.slug, "1", "Pokot arrived. Guld and Protection stayed unchanged.")

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(entry_ids=[approved.id, candidate.id, rejected.id]),
    )

    assert result.entry_count == 1
    assert result.total_match_count == 1
    replacement = result.chapters[0].replacements[0]
    assert replacement.old_text == "Pokot"
    assert replacement.new_text == "Pocott"
    assert replacement.risk_status == "safe"
    assert any(str(candidate.id) in warning and str(rejected.id) in warning for warning in result.warnings)


def test_exact_standalone_replacement_is_safe_and_returns_compact_snippets(session, storage, repo) -> None:
    novel = _make_novel(session, "safe")
    _make_chapter(session, novel, 1)
    entry = _approved_entry(repo, novel, "Pocott", "Pocott")
    _add_old_variant(repo, novel, entry, "Pokot", alias_type="banned")
    text = "Opening. " + ("filler " * 80) + "Pokot arrived at dawn. Closing."
    storage.add_translated(novel.slug, "1", text)

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(entry_ids=[entry.id]),
    )

    replacement = result.chapters[0].replacements[0]
    assert replacement.risk_status == "safe"
    assert replacement.reason_codes == ["exact_standalone_match"]
    assert "Pokot arrived" in replacement.before_snippet
    assert "Pocott arrived" in replacement.after_snippet
    assert len(replacement.before_snippet) < len(text)
    assert result.safe_match_count == 1


def test_substring_inside_another_word_needs_review(session, storage, repo) -> None:
    novel = _make_novel(session, "substring")
    _make_chapter(session, novel, 1)
    entry = _approved_entry(repo, novel, "Pocott", "Pocott")
    _add_old_variant(repo, novel, entry, "Pokot")
    storage.add_translated(novel.slug, "1", "The Pokotian road is not a standalone village name.")

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(entry_ids=[entry.id]),
    )

    replacement = result.chapters[0].replacements[0]
    assert replacement.risk_status == "needs_review"
    assert "boundary_uncertain" in replacement.reason_codes


def test_chapter_with_old_and_new_variant_needs_review(session, storage, repo) -> None:
    novel = _make_novel(session, "old-and-new")
    _make_chapter(session, novel, 1)
    entry = _approved_entry(repo, novel, "Pocott", "Pocott")
    _add_old_variant(repo, novel, entry, "Pokot")
    storage.add_translated(novel.slug, "1", "Pocott waited while Pokot arrived.")

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(entry_ids=[entry.id]),
    )

    replacement = result.chapters[0].replacements[0]
    assert replacement.risk_status == "needs_review"
    assert "chapter_already_contains_new_text" in replacement.reason_codes


def test_same_old_variant_mapping_to_multiple_approved_entries_is_blocked(session, storage, repo) -> None:
    novel = _make_novel(session, "conflict")
    _make_chapter(session, novel, 1)
    pocott = _approved_entry(repo, novel, "Pocott", "Pocott")
    place = _approved_entry(repo, novel, "Pocott Village", "Pocott Village")
    _add_old_variant(repo, novel, pocott, "Pokot")
    _add_old_variant(repo, novel, place, "Pokot")
    storage.add_translated(novel.slug, "1", "Pokot welcomed everyone.")

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(include_all_approved=True),
    )

    assert result.blocked_match_count == 2
    assert {item.risk_status for item in result.chapters[0].replacements} == {"blocked"}
    assert all("old_variant_conflict" in item.reason_codes for item in result.chapters[0].replacements)


def test_caps_return_warnings(session, storage, repo) -> None:
    novel = _make_novel(session, "caps")
    entry = _approved_entry(repo, novel, "Pocott", "Pocott")
    _add_old_variant(repo, novel, entry, "Pokot")
    for number in range(1, 4):
        _make_chapter(session, novel, number)
        storage.add_translated(novel.slug, str(number), "Pokot. Pokot.")

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(entry_ids=[entry.id], max_chapters=2, max_matches=3),
    )

    assert result.scanned_chapter_count == 2
    assert result.total_match_count == 3
    assert any("safety cap" in warning for warning in result.warnings)
    assert any("max match" in warning for warning in result.warnings)


def test_source_agnostic_novel_isolation_and_no_storage_or_db_mutation(session, storage, repo) -> None:
    novel_a = _make_novel(session, "novel-a")
    novel_b = _make_novel(session, "novel-b")
    _make_chapter(session, novel_a, 1)
    _make_chapter(session, novel_b, 1)
    entry_a = _approved_entry(repo, novel_a, "Pocott", "Pocott")
    entry_b = _approved_entry(repo, novel_b, "Pocott", "Pocott Other")
    _add_old_variant(repo, novel_a, entry_a, "Pokot")
    _add_old_variant(repo, novel_b, entry_b, "Pokot")
    storage.add_translated(novel_a.slug, "1", "Pokot arrived.")
    storage.add_translated(novel_b.slug, "1", "Pokot arrived.")
    before_storage = deepcopy(storage.translated)
    before_entries = session.query(NovelGlossaryEntry).count()
    before_events = session.query(NovelGlossaryDecisionEvent).count()

    result = GlossaryApplyPreviewService(session, storage).preview(
        novel_a.id,
        GlossaryApplyPreviewRequest(include_all_approved=True),
    )

    assert result.entry_count == 1
    assert result.chapters[0].replacements[0].new_text == "Pocott"
    assert storage.translated == before_storage
    assert storage.save_calls == 0
    assert session.query(NovelGlossaryEntry).count() == before_entries
    assert session.query(NovelGlossaryDecisionEvent).count() == before_events


def test_provider_is_not_called(session, storage, repo) -> None:
    novel = _make_novel(session, "no-provider")
    _make_chapter(session, novel, 1)
    entry = _approved_entry(repo, novel, "Pocott", "Pocott")
    _add_old_variant(repo, novel, entry, "Pokot")
    storage.add_translated(novel.slug, "1", "Pokot arrived.")

    class Provider:
        called = False

        def translate(self, *args: Any, **kwargs: Any) -> None:
            self.called = True
            raise AssertionError("Provider must not be called.")

    provider = Provider()
    result = GlossaryApplyPreviewService(session, storage).preview(
        novel.id,
        GlossaryApplyPreviewRequest(entry_ids=[entry.id]),
    )

    assert result.total_match_count == 1
    assert provider.called is False
