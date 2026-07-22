"""Tests for approved glossary prompt injection block generation.

Uses SQLite in-memory only. No providers, scraping, storage mutation,
translation jobs, or saved chapter repair are involved.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.services.glossary_prompt_injection import (
    GlossaryPromptInjectionOptions,
    GlossaryPromptInjectionService,
)
from novelai.services.glossary_repository import GlossaryRepository

pytestmark = pytest.mark.slow

_SQLITE = "sqlite:///:memory:"


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
def repo(session) -> GlossaryRepository:
    return GlossaryRepository(session)


@pytest.fixture()
def service(repo) -> GlossaryPromptInjectionService:
    return GlossaryPromptInjectionService(repo)


def _make_novel(session, slug: str) -> Novel:
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", publication_status="ongoing")
    session.add(novel)
    session.flush()
    return novel


def _entry(
    repo: GlossaryRepository,
    novel_id: int,
    term: str,
    translation: str | None,
    *,
    status: str = "approved",
    owner_locked: bool = False,
    confidence: float | None = None,
) -> NovelGlossaryEntry:
    return repo.create_glossary_entry(
        novel_id=novel_id,
        canonical_term=term,
        term_type="other",
        approved_translation=translation,
        status=status,
        owner_locked=owner_locked,
        confidence=confidence,
    )


def test_only_approved_entries_are_included(session, repo, service) -> None:
    novel = _make_novel(session, "approved-only")
    _entry(repo, novel.id, "seireikai", "Spirit Realm")
    _entry(repo, novel.id, "candidate-term", "Candidate", status="candidate")
    _entry(repo, novel.id, "recommended-term", "Recommended", status="recommended")
    _entry(repo, novel.id, "rejected-term", "Rejected", status="rejected")
    _entry(repo, novel.id, "deprecated-term", "Deprecated", status="deprecated")
    session.commit()

    block = service.build_for_chapter(novel.id)

    assert "- seireikai => Spirit Realm" in block.rendered_text
    assert "candidate-term" not in block.rendered_text
    assert "recommended-term" not in block.rendered_text
    assert "rejected-term" not in block.rendered_text
    assert "deprecated-term" not in block.rendered_text
    assert [term.term for term in block.included_terms] == ["seireikai"]


def test_approved_entries_without_translation_are_skipped(session, repo, service) -> None:
    novel = _make_novel(session, "missing-translation")
    _entry(repo, novel.id, "maso", "magicules")
    missing = _entry(repo, novel.id, "nameless", None)
    blank = _entry(repo, novel.id, "blank", " ")
    session.commit()

    block = service.build_for_chapter(novel.id)

    assert "- maso => magicules" in block.rendered_text
    assert "nameless" not in block.rendered_text
    assert "blank" not in block.rendered_text
    assert {item.entry_id: item.reason for item in block.skipped_terms} == {
        missing.id: "missing_approved_translation",
        blank.id: "missing_approved_translation",
    }
    assert "glossary_entry_missing_required_field" in block.warnings


def test_provider_suggested_reviewing_entries_are_excluded(session, repo, service) -> None:
    novel = _make_novel(session, "provider-reviewing")
    _entry(repo, novel.id, "approved-term", "Approved")
    provider_candidate = _entry(
        repo,
        novel.id,
        "provider-suggestion",
        "Provider Suggestion",
        status="candidate",
    )
    repo.add_source_provenance(
        novel_id=novel.id,
        entry_id=provider_candidate.id,
        source_site="provider_suggestion",
        source_adapter="provider_suggestion",
        observed_translated_term="Provider Suggestion",
        evidence_quality="provider_output",
    )
    session.commit()

    block = service.build_for_chapter(novel.id, raw_chapter_text="provider-suggestion approved-term")

    assert "approved-term" in block.rendered_text
    assert "provider-suggestion" not in block.rendered_text


def test_canonical_term_and_translation_render_deterministically(session, repo, service) -> None:
    novel = _make_novel(session, "rendering")
    _entry(repo, novel.id, "maso", "magicules", owner_locked=True)
    _entry(repo, novel.id, "seireikai", "Spirit Realm")
    session.commit()

    block = service.build_for_chapter(novel.id)

    assert block.rendered_text == (
        "GLOSSARY FOR THIS NOVEL\n"
        "These are approved owner glossary rules. Use them consistently when the source term appears.\n"
        "The glossary is authoritative. If a source term appears below you MUST use its approved translation.\n"
        "\n"
        "LOCKED (override any other translation):\n"
        "- maso => magicules\n"
        "\n"
        "APPROVED (preferred translation):\n"
        "- seireikai => Spirit Realm"
    )


def test_rejected_and_banned_aliases_render_only_as_avoid_variants(session, repo, service) -> None:
    novel = _make_novel(session, "avoid-aliases")
    entry = _entry(repo, novel.id, "seireikai", "Spirit Realm")
    repo.add_glossary_alias(entry_id=entry.id, novel_id=novel.id, alias_text="Spirit World", alias_type="rejected")
    repo.add_glossary_alias(entry_id=entry.id, novel_id=novel.id, alias_text="Spirit Plane", alias_type="banned")
    repo.add_glossary_alias(entry_id=entry.id, novel_id=novel.id, alias_text="Spirit Country", alias_type="deprecated")
    session.commit()

    block = service.build_for_chapter(novel.id)

    assert "- seireikai => Spirit Realm" in block.rendered_text
    assert '- seireikai: avoid "Spirit World"' in block.rendered_text
    assert '- seireikai: avoid "Spirit Plane"' in block.rendered_text
    assert "Spirit Country" not in block.rendered_text


def test_allowed_observed_and_source_variant_aliases_match_but_do_not_render_as_canonical(
    session, repo, service
) -> None:
    novel = _make_novel(session, "match-aliases")
    entry = _entry(repo, novel.id, "World Tree", "World Tree")
    other = _entry(repo, novel.id, "Origin", "Origin")
    repo.add_glossary_alias(entry_id=entry.id, novel_id=novel.id, alias_text="Sacred Tree", alias_type="allowed")
    repo.add_glossary_alias(entry_id=entry.id, novel_id=novel.id, alias_text="worldtree", alias_type="observed")
    repo.add_glossary_alias(entry_id=entry.id, novel_id=novel.id, alias_text="sekai-ju", alias_type="source_variant")
    session.commit()

    block = service.build_for_chapter(novel.id, raw_chapter_text="The sekai-ju shook.")

    assert [term.entry_id for term in block.included_terms][:2] == [entry.id, other.id]
    assert "- World Tree => World Tree" in block.rendered_text
    assert "Sacred Tree =>" not in block.rendered_text
    assert "worldtree =>" not in block.rendered_text
    assert "sekai-ju =>" not in block.rendered_text


def test_chapter_aware_filtering_prioritizes_raw_matches_then_owner_locked(session, repo, service) -> None:
    novel = _make_novel(session, "chapter-aware")
    locked = _entry(repo, novel.id, "Locked Term", "Locked Translation", owner_locked=True)
    matched = _entry(repo, novel.id, "Matched Term", "Matched Translation")
    _entry(repo, novel.id, "Other Term", "Other Translation")
    session.commit()

    block = service.build_for_chapter(novel.id, raw_chapter_text="The chapter mentions Matched Term.")

    assert [term.entry_id for term in block.included_terms[:2]] == [matched.id, locked.id]
    assert block.included_terms[0].matched_in_raw is True


def test_translated_context_is_secondary_signal(session, repo, service) -> None:
    novel = _make_novel(session, "translated-context")
    raw_matched = _entry(repo, novel.id, "Raw Match", "Raw Translation")
    translated_matched = _entry(repo, novel.id, "Translated Match", "Translated Translation")
    session.commit()

    block = service.build_for_chapter(
        novel.id,
        raw_chapter_text="Raw Match appears here.",
        translated_context="Translated Match appears in prior output.",
    )

    assert [term.entry_id for term in block.included_terms[:2]] == [raw_matched.id, translated_matched.id]
    assert block.included_terms[1].matched_in_translated_context is True


def test_fallback_without_chapter_text_includes_high_priority_terms(session, repo, service) -> None:
    novel = _make_novel(session, "fallback")
    locked = _entry(repo, novel.id, "Locked", "Locked", owner_locked=True)
    avoided = _entry(repo, novel.id, "Avoided", "Avoided")
    plain = _entry(repo, novel.id, "Plain", "Plain")
    repo.add_glossary_alias(entry_id=avoided.id, novel_id=novel.id, alias_text="Bad Avoided", alias_type="banned")
    session.commit()

    block = service.build_for_chapter(novel.id)

    assert [term.entry_id for term in block.included_terms] == [locked.id, avoided.id, plain.id]


def test_budget_limits_max_terms_and_returns_truncation_warning(session, repo, service) -> None:
    novel = _make_novel(session, "max-terms")
    first = _entry(repo, novel.id, "Alpha", "A", owner_locked=True)
    second = _entry(repo, novel.id, "Beta", "B")
    session.commit()

    block = service.build_for_chapter(novel.id, options=GlossaryPromptInjectionOptions(max_terms=1))

    assert [term.entry_id for term in block.included_terms] == [first.id]
    assert {item.entry_id: item.reason for item in block.skipped_terms} == {
        second.id: "max_terms_exceeded",
    }
    assert block.truncated is True
    assert "glossary_prompt_truncated" in block.warnings


def test_budget_limits_max_characters_without_cutting_lines(session, repo, service) -> None:
    novel = _make_novel(session, "max-chars")
    first = _entry(repo, novel.id, "Alpha", "A", owner_locked=True)
    second = _entry(repo, novel.id, "Very Long Canonical Term", "Very Long Translation")
    session.commit()

    first_only = service.build_for_chapter(novel.id, options=GlossaryPromptInjectionOptions(max_terms=1))
    block = service.build_for_chapter(
        novel.id,
        options=GlossaryPromptInjectionOptions(max_block_chars=len(first_only.rendered_text)),
    )

    assert [term.entry_id for term in block.included_terms] == [first.id]
    assert {item.entry_id: item.reason for item in block.skipped_terms} == {
        second.id: "max_block_chars_exceeded",
    }
    assert block.rendered_text == first_only.rendered_text
    assert "Very Long Canonical Term" not in block.rendered_text


def test_source_agnostic_novel_isolation(session, repo, service) -> None:
    novel_a = _make_novel(session, "novel-a")
    novel_b = _make_novel(session, "novel-b")
    _entry(repo, novel_a.id, "Pocott", "Pocott Village")
    _entry(repo, novel_b.id, "Pocott", "Pocott Person")
    session.commit()

    block_a = service.build_for_chapter(novel_a.id)
    block_b = service.build_for_chapter(novel_b.id)

    assert "Pocott Village" in block_a.rendered_text
    assert "Pocott Person" not in block_a.rendered_text
    assert "Pocott Person" in block_b.rendered_text
    assert "Pocott Village" not in block_b.rendered_text


def test_simple_conflicts_produce_warnings(session, repo, service) -> None:
    novel = _make_novel(session, "conflicts")
    spirit = _entry(repo, novel.id, "Spirit Realm", "Spirit Realm")
    world = _entry(repo, novel.id, "Spirit World", "Spirit World")
    mana = _entry(repo, novel.id, "mana", "magicules")
    magicules = _entry(repo, novel.id, "magicule-source", "magicule")
    repo.add_glossary_alias(entry_id=spirit.id, novel_id=novel.id, alias_text="Spirit World", alias_type="allowed")
    repo.add_glossary_alias(entry_id=mana.id, novel_id=novel.id, alias_text="magicule", alias_type="banned")
    session.commit()

    block = service.build_for_chapter(novel.id)

    assert any("matches approved canonical term" in warning for warning in block.conflict_warnings)
    assert any("matches approved translation" in warning for warning in block.conflict_warnings)
    assert {term.entry_id for term in block.included_terms} == {spirit.id, world.id, mana.id, magicules.id}


def test_output_does_not_include_full_chapter_text_or_mutate_db(session, repo, service) -> None:
    novel = _make_novel(session, "safe-output")
    _entry(repo, novel.id, "Alpha", "A")
    long_chapter_text = "Alpha " + "chapter text should not be copied " * 40
    before_entries = session.query(NovelGlossaryEntry).count()
    session.commit()

    block = service.build_for_chapter(novel.id, raw_chapter_text=long_chapter_text)
    after_entries = session.query(NovelGlossaryEntry).count()

    assert "chapter text should not be copied" not in block.rendered_text
    assert before_entries == after_entries
    assert len(session.dirty) == 0


def test_no_matching_terms_returns_empty_block_when_budget_cannot_fit_header(session, repo, service) -> None:
    novel = _make_novel(session, "empty-budget")
    _entry(repo, novel.id, "Alpha", "A")
    session.commit()

    block = service.build_for_chapter(novel.id, options=GlossaryPromptInjectionOptions(max_block_chars=1))

    assert block.empty is True
    assert block.rendered_text == ""
    assert "glossary_prompt_empty" in block.warnings
    assert "glossary_prompt_truncated" in block.warnings
