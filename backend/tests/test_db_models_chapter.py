"""Tests for the Chapter ORM model and Novel.chapters relationship.

Uses SQLite in-memory; no Postgres required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel

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


class TestChapterModel:
    def test_create_chapter(self, session, novel) -> None:
        chapter = Chapter(novel_id=novel.id, chapter_number=1, title="Chapter 1")
        session.add(chapter)
        session.commit()
        result = session.query(Chapter).filter_by(novel_id=novel.id, chapter_number=1).one()
        assert result.title == "Chapter 1"
        assert result.id is not None

    def test_default_statuses(self, session, novel) -> None:
        chapter = Chapter(novel_id=novel.id, chapter_number=1)
        session.add(chapter)
        session.commit()
        result = session.query(Chapter).filter_by(novel_id=novel.id).one()
        assert result.raw_status == "pending"
        assert result.translation_status == "pending"

    def test_optional_fields_nullable(self, session, novel) -> None:
        chapter = Chapter(novel_id=novel.id, chapter_number=1)
        session.add(chapter)
        session.commit()
        result = session.query(Chapter).filter_by(novel_id=novel.id).one()
        assert result.title is None
        assert result.source_url is None
        assert result.raw_storage_key is None
        assert result.translated_storage_key is None
        assert result.word_count is None

    def test_foreign_key_required(self, session) -> None:
        # SQLite requires PRAGMA foreign_keys = ON to enforce FK constraints.
        session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys = ON"))
        chapter = Chapter(novel_id=9999, chapter_number=1)
        session.add(chapter)
        with pytest.raises(Exception):
            session.commit()

    def test_cascade_delete(self, session, novel) -> None:
        chapter = Chapter(novel_id=novel.id, chapter_number=1)
        session.add(chapter)
        session.commit()
        chapter_id = chapter.id
        session.delete(novel)
        session.commit()
        result = session.query(Chapter).filter_by(id=chapter_id).one_or_none()
        assert result is None

    def test_timestamps_set_on_create(self, session, novel) -> None:
        chapter = Chapter(novel_id=novel.id, chapter_number=1)
        session.add(chapter)
        session.commit()
        result = session.query(Chapter).filter_by(novel_id=novel.id).one()
        assert result.created_at is not None
        assert result.updated_at is not None

    def test_repr(self, session, novel) -> None:
        chapter = Chapter(novel_id=novel.id, chapter_number=7)
        session.add(chapter)
        session.commit()
        assert str(novel.id) in repr(chapter)
        assert "7" in repr(chapter)


class TestNovelChaptersRelationship:
    def test_novel_chapters_backref(self, session, novel) -> None:
        session.add(Chapter(novel_id=novel.id, chapter_number=1))
        session.add(Chapter(novel_id=novel.id, chapter_number=2))
        session.commit()
        session.refresh(novel)
        assert len(novel.chapters) == 2

    def test_chapters_ordered_by_number(self, session, novel) -> None:
        session.add(Chapter(novel_id=novel.id, chapter_number=3))
        session.add(Chapter(novel_id=novel.id, chapter_number=1))
        session.add(Chapter(novel_id=novel.id, chapter_number=2))
        session.commit()
        chapters = (
            session.query(Chapter)
            .filter_by(novel_id=novel.id)
            .order_by(Chapter.chapter_number)
            .all()
        )
        assert [c.chapter_number for c in chapters] == [1, 2, 3]
