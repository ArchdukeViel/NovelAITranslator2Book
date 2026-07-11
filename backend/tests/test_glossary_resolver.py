"""Tests for GlossaryResolver: global + novel merge logic.

Uses SQLite in-memory; no live services required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.glossary_resolver import GlossaryResolver

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
def resolver(repo) -> GlossaryResolver:
    return GlossaryResolver(repo)


def _make_novel(session, slug: str = "test-novel") -> Novel:
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", status="ongoing")
    session.add(novel)
    session.flush()
    return novel


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_global_only(resolver, repo, session) -> None:
    """Only global approved entries → all appear in resolved output."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Magic",
        term_type="term",
        approved_translation="Mahou",
        status="approved",
    )
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Sword",
        term_type="item",
        approved_translation="Ken",
        status="approved",
    )
    session.commit()

    novel = _make_novel(session)
    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 2
    assert resolved[0].source_text == "Magic"
    assert resolved[1].source_text == "Sword"


def test_novel_only(resolver, repo, session) -> None:
    """Only novel approved entries → all appear in resolved output."""
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="Hero",
        term_type="character",
        approved_translation="Yuusha",
        status="approved",
    )
    session.commit()

    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 1
    assert resolved[0].source_text == "Hero"


def test_novel_overrides_global(resolver, repo, session) -> None:
    """Novel-scoped entry overrides global entry for same normalized term."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Dragon",
        term_type="creature",
        approved_translation="Ryu",
        status="approved",
    )
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="Dragon",
        term_type="creature",
        approved_translation="Doragon",
        status="approved",
    )
    session.commit()

    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 1
    assert resolved[0].source_text == "Dragon"
    # Novel override: "Doragon" not "Ryu"
    assert resolved[0].target_text == "Doragon"
    assert resolved[0].scope == "novel"


def test_global_kept_when_no_novel_override(resolver, repo, session) -> None:
    """Global entry persists when no novel entry overrides it."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Castle",
        term_type="place",
        approved_translation="Shiro",
        status="approved",
    )
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="Village",
        term_type="place",
        approved_translation="Mura",
        status="approved",
    )
    session.commit()

    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 2
    terms = {(t.source_text, t.target_text) for t in resolved}
    assert ("Castle", "Shiro") in terms  # global kept
    assert ("Village", "Mura") in terms  # novel added


def test_candidate_excluded_from_resolved(resolver, repo, session) -> None:
    """Candidate entries are excluded from resolved output."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Demon",
        term_type="creature",
        approved_translation="Maou",
        status="candidate",
    )
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="Angel",
        term_type="creature",
        approved_translation="Tenshi",
        status="candidate",
    )
    session.commit()

    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 0


def test_rejected_excluded_from_resolved(resolver, repo, session) -> None:
    """Rejected entries are excluded from resolved output."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="God",
        term_type="term",
        approved_translation="Kami",
        status="rejected",
    )
    novel = _make_novel(session)
    session.commit()

    resolved = resolver.resolve(novel.id)
    assert len(resolved) == 0


def test_mixed_status_excludes_non_approved(resolver, repo, session) -> None:
    """Only approved entries appear; candidates/rejected are excluded."""
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="King",
        term_type="title",
        approved_translation="Ou",
        status="approved",
    )
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="Queen",
        term_type="title",
        approved_translation="Joou",
        status="rejected",
    )
    session.commit()

    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 1
    assert resolved[0].source_text == "King"


def test_glossary_hash_deterministic(resolver, repo, session) -> None:
    """Same data produces same glossary_hash."""
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="Elf",
        term_type="creature",
        approved_translation="Yousei",
        status="approved",
    )
    session.commit()

    resolved_a = resolver.resolve(novel.id)
    resolved_b = resolver.resolve(novel.id)

    assert resolved_a.glossary_hash == resolved_b.glossary_hash


def test_glossary_hash_different_for_different_data(resolver, repo, session) -> None:
    """Different data produces different glossary_hash."""
    novel_a = _make_novel(session, "novel-a")
    novel_b = _make_novel(session, "novel-b")

    repo.create_glossary_entry(
        novel_id=novel_a.id,
        scope="novel",
        canonical_term="Cat",
        term_type="creature",
        approved_translation="Neko",
        status="approved",
    )
    repo.create_glossary_entry(
        novel_id=novel_b.id,
        scope="novel",
        canonical_term="Dog",
        term_type="creature",
        approved_translation="Inu",
        status="approved",
    )
    session.commit()

    hash_a = resolver.resolve(novel_a.id).glossary_hash
    hash_b = resolver.resolve(novel_b.id).glossary_hash

    assert hash_a != hash_b


def test_case_insensitive_override(resolver, repo, session) -> None:
    """Novel override matches global entry case-insensitively."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Demon Lord",
        term_type="title",
        approved_translation="Maou",
        status="approved",
    )
    novel = _make_novel(session)
    repo.create_glossary_entry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="demon lord",
        term_type="title",
        approved_translation="Maou-sama",
        status="approved",
    )
    session.commit()

    resolved = resolver.resolve(novel.id)

    assert len(resolved) == 1
    assert resolved[0].target_text == "Maou-sama"


def test_multiple_novels_independent_resolution(resolver, repo, session) -> None:
    """Each novel resolves independently; overrides don't leak across novels."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Spell",
        term_type="term",
        approved_translation="Jumon",
        status="approved",
    )
    novel_a = _make_novel(session, "novel-a")
    novel_b = _make_novel(session, "novel-b")

    # Novel A overrides Spell
    repo.create_glossary_entry(
        novel_id=novel_a.id,
        scope="novel",
        canonical_term="Spell",
        term_type="term",
        approved_translation="Mahou",
        status="approved",
    )
    session.commit()

    resolved_a = resolver.resolve(novel_a.id)
    resolved_b = resolver.resolve(novel_b.id)

    # Novel A: overridden
    assert resolved_a[0].target_text == "Mahou"
    # Novel B: global remains
    assert resolved_b[0].target_text == "Jumon"


def test_global_approved_entry_method(resolver, repo, session) -> None:
    """list_approved_global_entries returns only global + approved."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Tome",
        term_type="item",
        approved_translation="Shomotsu",
        status="approved",
    )
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Scroll",
        term_type="item",
        approved_translation="Maki",
        status="candidate",
    )
    session.commit()

    rows = repo.list_approved_global_entries()
    assert len(rows) == 1
    assert rows[0].canonical_term == "Tome"


def test_global_get_entry(resolver, repo, session) -> None:
    """get_glossary_entry with novel_id=None returns global entries."""
    repo.create_glossary_entry(
        novel_id=None,
        scope="global",
        canonical_term="Potion",
        term_type="item",
        approved_translation="Yakusui",
        status="approved",
    )
    session.commit()

    entry = repo.get_glossary_entry(1, novel_id=None)
    assert entry is not None
    assert entry.canonical_term == "Potion"
