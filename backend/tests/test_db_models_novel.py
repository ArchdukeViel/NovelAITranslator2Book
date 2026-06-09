"""Tests for the Novel ORM model.

Uses SQLite in-memory; no Postgres required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
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


class TestNovelModel:
    def test_create_novel(self, session) -> None:
        novel = Novel(slug="test-novel", title="Test Novel", language="ja", status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="test-novel").one()
        assert result.title == "Test Novel"
        assert result.id is not None

    def test_slug_unique_constraint(self, session) -> None:
        session.add(Novel(slug="dup-slug", title="Novel A", language="ja", status="ongoing"))
        session.commit()
        session.add(Novel(slug="dup-slug", title="Novel B", language="ja", status="ongoing"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_optional_fields_nullable(self, session) -> None:
        novel = Novel(slug="minimal", title="Minimal Novel", language="ja", status="unknown")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="minimal").one()
        assert result.original_title is None
        assert result.author is None
        assert result.synopsis is None
        assert result.cover_storage_key is None

    def test_is_published_defaults_false(self, session) -> None:
        novel = Novel(slug="unpublished", title="Unpublished", language="ja", status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="unpublished").one()
        assert result.is_published is False

    def test_timestamps_set_on_create(self, session) -> None:
        novel = Novel(slug="timestamped", title="Timestamped", language="ja", status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="timestamped").one()
        assert result.created_at is not None
        assert result.updated_at is not None

    def test_repr(self, session) -> None:
        novel = Novel(slug="repr-test", title="Repr Test", language="ja", status="ongoing")
        session.add(novel)
        session.commit()
        assert "repr-test" in repr(novel)
        assert "Repr Test" in repr(novel)
