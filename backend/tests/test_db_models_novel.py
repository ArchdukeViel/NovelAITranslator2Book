"""Tests for the Novel ORM model.

Uses SQLite in-memory; no Postgres required.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.novel import GLOSSARY_STATUS_VALUES, Novel

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
        novel = Novel(slug="test-novel", title="Test Novel", language="ja", publication_status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="test-novel").one()
        assert result.title == "Test Novel"
        assert result.id is not None

    def test_slug_unique_constraint(self, session) -> None:
        session.add(Novel(slug="dup-slug", title="Novel A", language="ja", publication_status="ongoing"))
        session.commit()
        session.add(Novel(slug="dup-slug", title="Novel B", language="ja", publication_status="ongoing"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_optional_fields_nullable(self, session) -> None:
        novel = Novel(slug="minimal", title="Minimal Novel", language="ja", publication_status="unknown")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="minimal").one()
        assert result.original_title is None
        assert result.author is None
        assert result.synopsis is None
        assert result.cover_storage_key is None

    def test_is_published_defaults_false(self, session) -> None:
        novel = Novel(slug="unpublished", title="Unpublished", language="ja", publication_status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="unpublished").one()
        assert result.is_published is False

    def test_glossary_status_defaults_pending_and_revision_zero(self, session) -> None:
        novel = Novel(slug="glossary-defaults", title="Glossary Defaults", language="ja", publication_status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="glossary-defaults").one()
        assert result.glossary_status == "glossary_pending"
        assert result.glossary_revision == 0

    def test_glossary_status_validation(self, session) -> None:
        novel = Novel(slug="glossary-valid", title="Glossary Valid", language="ja", publication_status="ongoing")
        for status in GLOSSARY_STATUS_VALUES:
            novel.glossary_status = status
            assert novel.glossary_status == status
        with pytest.raises(ValueError):
            novel.glossary_status = "ready"

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
    @given(st.text().filter(lambda value: value not in GLOSSARY_STATUS_VALUES))
    def test_glossary_status_validation_rejects_invalid_values(self, session, invalid_status: str) -> None:
        novel = Novel(slug="glossary-invalid", title="Glossary Invalid", language="ja", publication_status="ongoing")
        with pytest.raises(ValueError):
            novel.glossary_status = invalid_status

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
    @given(st.sampled_from(sorted(GLOSSARY_STATUS_VALUES)))
    def test_glossary_status_validation_accepts_valid_values(self, session, status: str) -> None:
        novel = Novel(slug="glossary-accepted", title="Glossary Accepted", language="ja", publication_status="ongoing")
        novel.glossary_status = status
        assert novel.glossary_status == status

    def test_timestamps_set_on_create(self, session) -> None:
        novel = Novel(slug="timestamped", title="Timestamped", language="ja", publication_status="ongoing")
        session.add(novel)
        session.commit()
        result = session.query(Novel).filter_by(slug="timestamped").one()
        assert result.created_at is not None
        assert result.updated_at is not None

    def test_repr(self, session) -> None:
        novel = Novel(slug="repr-test", title="Repr Test", language="ja", publication_status="ongoing")
        session.add(novel)
        session.commit()
        assert "repr-test" in repr(novel)
        assert "Repr Test" in repr(novel)
