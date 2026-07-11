"""Tests for glossary repository/service data access.

Uses SQLite in-memory; no live Postgres, providers, scraping, storage, or
translation services are required.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import (
    NovelGlossaryAlias,
    NovelGlossaryDecisionEvent,
    NovelGlossaryEntry,
    NovelGlossaryQAFinding,
    NovelGlossarySourceProvenance,
    UserGlossaryDisplayOverride,
)
from novelai.db.models.novel import Novel
from novelai.db.models.users import User
from novelai.services.glossary_repository import GlossaryRepository

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
def user(session) -> User:
    user = User(email="owner@example.com", role="owner")
    session.add(user)
    session.flush()
    return user


def _make_novel(session, slug: str) -> Novel:
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", status="ongoing")
    session.add(novel)
    session.flush()
    return novel


def _make_chapter(session, novel: Novel, number: int = 1) -> Chapter:
    chapter = Chapter(novel_id=novel.id, chapter_number=number, title=f"Chapter {number}")
    session.add(chapter)
    session.flush()
    return chapter


def test_create_list_update_glossary_entry_scoped_by_novel(session, repo, user) -> None:
    novel_a = _make_novel(session, "repo-a")
    novel_b = _make_novel(session, "repo-b")

    entry = repo.create_glossary_entry(
        novel_id=novel_a.id,
        canonical_term="Pocott",
        term_type="place",
        status="candidate",
        actor_user_id=user.id,
    )
    repo.create_glossary_entry(
        novel_id=novel_b.id,
        canonical_term="World Tree",
        term_type="concept",
    )

    repo.update_glossary_entry(
        entry.id,
        novel_id=novel_a.id,
        approved_translation="Pocott Village",
        public_visible=True,
        actor_user_id=user.id,
    )
    session.commit()

    entries_a = repo.list_glossary_entries_for_novel(novel_a.id)
    entries_b = repo.list_glossary_entries_for_novel(novel_b.id)
    assert [item.canonical_term for item in entries_a] == ["Pocott"]
    assert [item.canonical_term for item in entries_b] == ["World Tree"]
    assert entries_a[0].approved_translation == "Pocott Village"
    assert repo.get_glossary_entry(entry.id, novel_id=novel_b.id) is None


def test_status_change_creates_decision_event(session, repo, user) -> None:
    novel = _make_novel(session, "decision")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Blessing of the World Tree",
        term_type="skill",
    )

    repo.change_glossary_entry_status(
        entry.id,
        novel_id=novel.id,
        status="approved",
        actor_user_id=user.id,
        rationale="Owner approved the canonical skill name.",
    )
    session.commit()

    events = session.query(NovelGlossaryDecisionEvent).order_by(NovelGlossaryDecisionEvent.id).all()
    assert [event.event_type for event in events] == ["create", "approve"]
    approve_event = events[-1]
    assert approve_event.actor_user_id == user.id
    assert json.loads(approve_event.old_value_json) == {"status": "candidate"}
    assert json.loads(approve_event.new_value_json) == {"status": "approved"}
    assert entry.status == "approved"
    assert novel.glossary_revision == 1


def test_approved_entry_changes_increment_glossary_revision(session, repo, user) -> None:
    novel = _make_novel(session, "revision-approved")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Pocott",
        term_type="place",
        approved_translation="Pocott",
        status="approved",
    )
    assert novel.glossary_revision == 1

    repo.update_glossary_entry(
        entry.id,
        novel_id=novel.id,
        approved_translation="Pocott Village",
        actor_user_id=user.id,
    )
    assert novel.glossary_revision == 2

    repo.change_glossary_entry_status(
        entry.id,
        novel_id=novel.id,
        status="deprecated",
        actor_user_id=user.id,
    )
    assert novel.glossary_revision == 3


def test_non_approved_entry_changes_do_not_increment_glossary_revision(session, repo, user) -> None:
    novel = _make_novel(session, "revision-candidate")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Gurd",
        term_type="character",
        status="candidate",
    )

    repo.update_glossary_entry(
        entry.id,
        novel_id=novel.id,
        admin_notes="still under review",
        actor_user_id=user.id,
    )

    assert novel.glossary_revision == 0


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
@given(st.integers(min_value=0, max_value=1_000))
def test_approved_entry_changes_increment_glossary_revision_property(session, repo, user, revision: int) -> None:
    novel = _make_novel(session, f"revision-approved-{revision}")
    novel.glossary_revision = revision
    session.flush()

    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Pocott",
        term_type="place",
        approved_translation="Pocott",
        status="approved",
    )
    assert novel.glossary_revision == revision + 1

    repo.update_glossary_entry(
        entry.id,
        novel_id=novel.id,
        approved_translation="Pocott Village",
        actor_user_id=user.id,
    )
    assert novel.glossary_revision == revision + 2

    repo.change_glossary_entry_status(
        entry.id,
        novel_id=novel.id,
        status="deprecated",
        actor_user_id=user.id,
    )
    assert novel.glossary_revision == revision + 3


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
@given(st.sampled_from(["candidate", "recommended"]))
def test_non_approved_entry_changes_do_not_increment_glossary_revision_property(session, repo, status: str) -> None:
    novel = _make_novel(session, f"revision-{status}")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Gurd",
        term_type="character",
        status=status,
    )

    repo.update_glossary_entry(
        entry.id,
        novel_id=novel.id,
        admin_notes="still under review",
        actor_user_id=None,
    )

    assert novel.glossary_revision == 0


def test_lock_unlock_and_deprecate_entry_create_owner_events(session, repo, user) -> None:
    novel = _make_novel(session, "state-events")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Order of Knights",
        term_type="organization",
    )

    repo.lock_glossary_entry(entry.id, novel_id=novel.id, actor_user_id=user.id)
    repo.unlock_glossary_entry(entry.id, novel_id=novel.id, actor_user_id=user.id)
    repo.deprecate_glossary_entry(entry.id, novel_id=novel.id, actor_user_id=user.id)
    session.commit()

    event_types = [
        event.event_type
        for event in session.query(NovelGlossaryDecisionEvent).order_by(NovelGlossaryDecisionEvent.id)
    ]
    assert event_types == ["create", "lock", "unlock", "deprecate"]
    assert entry.owner_locked is False
    assert entry.status == "deprecated"
    assert entry.deprecated_at is not None


def test_allowed_and_banned_alias_creation_is_entry_and_novel_scoped(session, repo, user) -> None:
    novel = _make_novel(session, "aliases")
    other_novel = _make_novel(session, "other-aliases")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Albert",
        term_type="character",
    )

    allowed = repo.add_glossary_alias(
        entry_id=entry.id,
        novel_id=novel.id,
        alias_text="Al",
        alias_type="allowed",
        actor_user_id=user.id,
    )
    banned = repo.add_glossary_alias(
        entry_id=entry.id,
        novel_id=novel.id,
        alias_text="Alberto",
        alias_type="banned",
        actor_user_id=user.id,
    )
    repo.remove_or_deprecate_glossary_alias(banned.id, novel_id=novel.id, actor_user_id=user.id)
    session.commit()

    aliases = repo.list_aliases_for_entry(entry.id, novel_id=novel.id)
    assert [(alias.alias_text, alias.alias_type) for alias in aliases] == [
        ("Al", "allowed"),
        ("Alberto", "deprecated"),
    ]
    assert allowed.novel_id == novel.id
    with pytest.raises(LookupError):
        repo.list_aliases_for_entry(entry.id, novel_id=other_novel.id)
    assert session.query(NovelGlossaryDecisionEvent).filter_by(event_type="alias_change").count() == 3


def test_source_provenance_stores_source_adapter_as_provenance_only(session, repo) -> None:
    novel = _make_novel(session, "provenance")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Pocott",
        term_type="place",
    )

    provenance = repo.add_source_provenance(
        novel_id=novel.id,
        entry_id=entry.id,
        source_site="kakuyomu",
        source_adapter="kakuyomu",
        source_novel_id="16817330655991571532",
        observed_translated_term="Pocott",
        evidence_ref="audit:chapter-3",
        evidence_quality="mojibake",
    )
    session.commit()

    assert provenance.novel_id == novel.id
    assert provenance.source_site == "kakuyomu"
    assert provenance.source_adapter == "kakuyomu"
    assert repo.list_source_provenance_for_novel(novel.id) == [provenance]
    assert repo.list_source_provenance_for_entry(entry.id, novel_id=novel.id) == [provenance]
    assert session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id).count() == 1


def test_qa_finding_creation_and_status_update(session, repo, user) -> None:
    novel = _make_novel(session, "qa")
    chapter = _make_chapter(session, novel, 7)
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="House Vanclyft",
        term_type="family_house",
    )

    finding = repo.create_qa_finding(
        novel_id=novel.id,
        chapter_id=chapter.id,
        glossary_entry_id=entry.id,
        finding_type="banned_alias",
        severity="warning",
        matched_text="Vancroft",
        suggested_text="House Vanclyft",
        context_ref="p0004",
    )
    repo.update_qa_finding_status(
        finding.id,
        novel_id=novel.id,
        status="dismissed",
        reviewer_user_id=user.id,
        reviewer_notes="False positive in quoted context.",
    )
    session.commit()

    by_novel = repo.list_qa_findings_for_novel(novel.id)
    by_chapter = repo.list_qa_findings_for_chapter(chapter.id, novel_id=novel.id)
    assert by_novel == [finding]
    assert by_chapter == [finding]
    assert finding.status == "dismissed"
    assert finding.reviewer_user_id == user.id
    assert finding.resolved_at is not None
    assert session.query(NovelGlossaryQAFinding).count() == 1


def test_user_display_override_upserts_and_disable_does_not_mutate_entry(session, repo, user) -> None:
    novel = _make_novel(session, "override")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Spirit Realm",
        term_type="place",
        approved_translation="Spirit Realm",
    )

    first = repo.set_user_display_override(
        user_id=user.id,
        novel_id=novel.id,
        entry_id=entry.id,
        display_term="Spirit World",
    )
    second = repo.set_user_display_override(
        user_id=user.id,
        novel_id=novel.id,
        entry_id=entry.id,
        display_term="Spirit Realm",
    )
    disabled = repo.disable_user_display_override(user_id=user.id, novel_id=novel.id, entry_id=entry.id)
    session.commit()

    assert first.id == second.id
    assert disabled is not None
    assert disabled.enabled is False
    assert disabled.display_term == "Spirit Realm"
    assert entry.approved_translation == "Spirit Realm"
    assert repo.get_user_display_overrides_for_novel(user_id=user.id, novel_id=novel.id) == [disabled]
    assert session.query(UserGlossaryDisplayOverride).count() == 1


def test_operations_do_not_require_source_site_as_ownership(session, repo) -> None:
    novel = _make_novel(session, "source-free")

    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Ori",
        term_type="character",
    )
    session.commit()

    assert entry.id is not None
    assert entry.novel_id == novel.id
    assert repo.list_glossary_entries_for_novel(novel.id) == [entry]
    assert session.query(NovelGlossarySourceProvenance).count() == 0


def test_no_global_uniqueness_assumption_across_different_novels(session, repo) -> None:
    novel_a = _make_novel(session, "same-term-a")
    novel_b = _make_novel(session, "same-term-b")

    entry_a = repo.create_glossary_entry(
        novel_id=novel_a.id,
        canonical_term="Pocott",
        term_type="place",
        approved_translation="Pocott",
    )
    entry_b = repo.create_glossary_entry(
        novel_id=novel_b.id,
        canonical_term="Pocott",
        term_type="character",
        approved_translation="Pocott",
    )
    session.commit()

    assert entry_a.id != entry_b.id
    assert repo.list_glossary_entries_for_novel(novel_a.id) == [entry_a]
    assert repo.list_glossary_entries_for_novel(novel_b.id) == [entry_b]
    assert session.query(NovelGlossaryEntry).filter_by(canonical_term="Pocott").count() == 2


def test_invalid_source_scoped_alias_operation_is_rejected_by_novel_scope(session, repo) -> None:
    novel = _make_novel(session, "scope-a")
    other_novel = _make_novel(session, "scope-b")
    entry = repo.create_glossary_entry(
        novel_id=novel.id,
        canonical_term="Ellen",
        term_type="character",
    )

    with pytest.raises(LookupError):
        repo.add_glossary_alias(
            entry_id=entry.id,
            novel_id=other_novel.id,
            alias_text="Eren",
            alias_type="banned",
        )

    assert session.query(NovelGlossaryAlias).count() == 0
