"""Tests for source-agnostic glossary ORM models.

Uses SQLite in-memory; no Postgres service required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
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
def novel(session):
    n = Novel(slug="test-novel", title="Test Novel", language="ja", status="ongoing")
    session.add(n)
    session.commit()
    return n


@pytest.fixture()
def user(session):
    u = User(email="reader@example.com", role="user")
    session.add(u)
    session.commit()
    return u


@pytest.fixture()
def glossary_entry(session, novel):
    entry = NovelGlossaryEntry(
        novel_id=novel.id,
        canonical_term="Pocott",
        term_type="place",
        approved_translation="Pocott",
        status="approved",
        enforcement_level="warning",
        owner_locked=True,
    )
    session.add(entry)
    session.commit()
    return entry


def _fk_targets(table, column_name: str) -> set[str]:
    column = table.c[column_name]
    return {fk.target_fullname for fk in column.foreign_keys}


def _index_columns(table) -> dict[str, tuple[str, ...]]:
    return {index.name: tuple(column.name for column in index.columns) for index in table.indexes}


class TestGlossaryMetadata:
    def test_tables_registered_in_metadata(self) -> None:
        expected = {
            "novel_glossary_entries",
            "novel_glossary_aliases",
            "novel_glossary_source_provenance",
            "novel_glossary_decision_events",
            "novel_glossary_qa_findings",
            "user_glossary_display_overrides",
        }
        assert expected.issubset(Base.metadata.tables)

    def test_entry_foreign_keys_target_platform_models(self) -> None:
        table = NovelGlossaryEntry.__table__
        assert _fk_targets(table, "novel_id") == {"novels.id"}
        assert _fk_targets(table, "first_seen_chapter_id") == {"chapters.id"}
        assert _fk_targets(table, "last_seen_chapter_id") == {"chapters.id"}
        assert _fk_targets(table, "created_by_user_id") == {"users.id"}
        assert _fk_targets(table, "updated_by_user_id") == {"users.id"}

    def test_key_indexes_and_constraints_exist(self) -> None:
        entry_indexes = _index_columns(NovelGlossaryEntry.__table__)
        assert entry_indexes["ix_novel_glossary_entries_novel_id_status"] == ("novel_id", "status")
        assert entry_indexes["ix_novel_glossary_entries_novel_id_canonical_term"] == (
            "novel_id",
            "canonical_term",
        )

        alias_indexes = _index_columns(NovelGlossaryAlias.__table__)
        assert alias_indexes["ix_novel_glossary_aliases_entry_type"] == ("glossary_entry_id", "alias_type")
        assert alias_indexes["ix_novel_glossary_aliases_novel_alias_type"] == (
            "novel_id",
            "alias_text",
            "alias_type",
        )

        qa_indexes = _index_columns(NovelGlossaryQAFinding.__table__)
        assert qa_indexes["ix_novel_glossary_qa_findings_novel_chapter_status_severity"] == (
            "novel_id",
            "chapter_id",
            "status",
            "severity",
        )

        constraints = {constraint.name for constraint in UserGlossaryDisplayOverride.__table__.constraints}
        assert "uq_user_glossary_display_overrides_user_novel_entry" in constraints


class TestGlossaryModels:
    def test_create_entry_with_defaults(self, session, novel) -> None:
        entry = NovelGlossaryEntry(
            novel_id=novel.id,
            canonical_term="World Tree",
            term_type="concept",
        )
        session.add(entry)
        session.commit()
        result = session.query(NovelGlossaryEntry).filter_by(canonical_term="World Tree").one()
        assert result.status == "candidate"
        assert result.enforcement_level == "none"
        assert result.owner_locked is False
        assert result.public_visible is False
        assert result.replacement_policy == "preview_required"
        assert result.matching_policy == "exact_phrase"
        assert result.created_at is not None
        assert result.updated_at is not None

    def test_create_alias_provenance_decision_and_qa_rows(self, session, novel, user, glossary_entry) -> None:
        alias = NovelGlossaryAlias(
            glossary_entry_id=glossary_entry.id,
            novel_id=novel.id,
            alias_text="Pokot",
            alias_type="banned",
            applies_to="qa",
        )
        provenance = NovelGlossarySourceProvenance(
            glossary_entry_id=glossary_entry.id,
            novel_id=novel.id,
            source_site="kakuyomu",
            source_adapter="kakuyomu",
            source_novel_id="16817330655991571532",
            observed_translated_term="Pocott",
            evidence_ref="audit:chapter-3",
            evidence_quality="translated_only",
        )
        decision = NovelGlossaryDecisionEvent(
            novel_id=novel.id,
            glossary_entry_id=glossary_entry.id,
            actor_user_id=user.id,
            event_type="approve",
            decision_source="owner",
            rationale="Owner-approved canonical spelling.",
        )
        finding = NovelGlossaryQAFinding(
            novel_id=novel.id,
            glossary_entry_id=glossary_entry.id,
            finding_type="banned_alias",
            severity="warning",
            matched_text="Pokot",
            suggested_text="Pocott",
        )
        session.add_all([alias, provenance, decision, finding])
        session.commit()

        assert session.query(NovelGlossaryAlias).filter_by(alias_text="Pokot").one().alias_type == "banned"
        assert session.query(NovelGlossarySourceProvenance).one().source_site == "kakuyomu"
        assert session.query(NovelGlossaryDecisionEvent).one().decision_source == "owner"
        assert session.query(NovelGlossaryQAFinding).one().status == "open"

    def test_user_display_override_unique_per_user_novel_entry(self, session, novel, user, glossary_entry) -> None:
        session.add(
            UserGlossaryDisplayOverride(
                user_id=user.id,
                novel_id=novel.id,
                glossary_entry_id=glossary_entry.id,
                display_term="Pocott",
            )
        )
        session.commit()
        session.add(
            UserGlossaryDisplayOverride(
                user_id=user.id,
                novel_id=novel.id,
                glossary_entry_id=glossary_entry.id,
                display_term="Pocott Village",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()

    def test_models_do_not_store_large_source_snippet_column(self) -> None:
        provenance_columns = {column.name for column in NovelGlossarySourceProvenance.__table__.columns}
        assert "evidence_snippet" not in provenance_columns
        assert "source_text" not in provenance_columns
