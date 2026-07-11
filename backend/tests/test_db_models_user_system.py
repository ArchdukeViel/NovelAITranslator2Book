"""Tests for User, ReadingProgress, ReadingHistory, LibraryItem,
Review, NovelRequest, AuditLog, and SystemSetting ORM models."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.db.models.system import AuditLog, SystemSetting
from novelai.db.models.users import (
    LibraryItem,
    NovelRequest,
    ReadingHistory,
    ReadingProgress,
    Review,
    User,
)

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
def user(session):
    u = User(email="test@example.com", role="user")
    session.add(u)
    session.commit()
    return u


@pytest.fixture()
def novel(session):
    n = Novel(slug="test-novel", title="Test Novel", language="ja", status="ongoing")
    session.add(n)
    session.commit()
    return n


@pytest.fixture()
def chapter(session, novel):
    c = Chapter(novel_id=novel.id, chapter_number=1)
    session.add(c)
    session.commit()
    return c


class TestUser:
    def test_create_user(self, session) -> None:
        u = User(email="new@example.com", role="user")
        session.add(u)
        session.commit()
        result = session.query(User).filter_by(email="new@example.com").one()
        assert result.role == "user"
        assert result.is_active is True

    def test_email_unique(self, session, user) -> None:
        session.add(User(email="test@example.com", role="user"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_owner_role(self, session) -> None:
        owner = User(email="owner@example.com", role="owner")
        session.add(owner)
        session.commit()
        assert owner.role == "owner"

    def test_oauth_fields(self, session) -> None:
        u = User(
            email="oauth@example.com",
            role="user",
            auth_provider="google",
            auth_provider_subject="google-sub-12345",
        )
        session.add(u)
        session.commit()
        result = session.query(User).filter_by(email="oauth@example.com").one()
        assert result.auth_provider == "google"
        assert result.auth_provider_subject == "google-sub-12345"

    def test_repr(self, session, user) -> None:
        assert "test@example.com" in repr(user)
        assert "user" in repr(user)


class TestReadingProgress:
    def test_create_progress(self, session, user, novel) -> None:
        rp = ReadingProgress(user_id=user.id, novel_id=novel.id, progress_percent=0.5)
        session.add(rp)
        session.commit()
        result = session.query(ReadingProgress).filter_by(
            user_id=user.id, novel_id=novel.id
        ).one()
        assert result.progress_percent == pytest.approx(0.5)

    def test_composite_pk(self, session, user, novel) -> None:
        session.add(ReadingProgress(user_id=user.id, novel_id=novel.id, progress_percent=0.2))
        session.commit()
        # Upsert via update
        rp = session.query(ReadingProgress).filter_by(
            user_id=user.id, novel_id=novel.id
        ).one()
        rp.progress_percent = 0.8
        session.commit()
        refreshed = session.query(ReadingProgress).filter_by(
            user_id=user.id, novel_id=novel.id
        ).one()
        assert refreshed.progress_percent == pytest.approx(0.8)


class TestReadingHistory:
    def test_create_history(self, session, user, novel, chapter) -> None:
        entry = ReadingHistory(user_id=user.id, novel_id=novel.id, chapter_id=chapter.id)
        session.add(entry)
        session.commit()
        result = session.query(ReadingHistory).filter_by(user_id=user.id).one()
        assert result.novel_id == novel.id

    def test_multiple_history_entries(self, session, user, novel) -> None:
        session.add(ReadingHistory(user_id=user.id, novel_id=novel.id))
        session.add(ReadingHistory(user_id=user.id, novel_id=novel.id))
        session.commit()
        count = session.query(ReadingHistory).filter_by(user_id=user.id).count()
        assert count == 2


class TestLibraryItem:
    def test_add_to_library(self, session, user, novel) -> None:
        item = LibraryItem(user_id=user.id, novel_id=novel.id)
        session.add(item)
        session.commit()
        result = session.query(LibraryItem).filter_by(
            user_id=user.id, novel_id=novel.id
        ).one()
        assert result.status == "reading"

    def test_composite_pk_unique(self, session, user, novel) -> None:
        session.add(LibraryItem(user_id=user.id, novel_id=novel.id))
        session.commit()
        session.add(LibraryItem(user_id=user.id, novel_id=novel.id))
        with pytest.raises(IntegrityError):
            session.commit()


class TestReview:
    def test_create_review(self, session, user, novel) -> None:
        review = Review(user_id=user.id, novel_id=novel.id, rating=5, body="Great novel!")
        session.add(review)
        session.commit()
        result = session.query(Review).filter_by(user_id=user.id).one()
        assert result.rating == 5
        assert result.body == "Great novel!"

    def test_rating_nullable(self, session, user, novel) -> None:
        review = Review(user_id=user.id, novel_id=novel.id, body="No rating, just comment")
        session.add(review)
        session.commit()
        assert review.rating is None


class TestNovelRequest:
    def test_create_request(self, session, user) -> None:
        req = NovelRequest(
            user_id=user.id,
            request_type="new_novel",
            source_url="https://example.com/novel",
        )
        session.add(req)
        session.commit()
        result = session.query(NovelRequest).filter_by(user_id=user.id).one()
        assert result.status == "pending"
        assert result.request_type == "new_novel"

    def test_requests_never_auto_trigger_jobs(self) -> None:
        """NovelRequest has no job_trigger or auto_translate column."""
        cols = {c.name for c in NovelRequest.__table__.columns}
        forbidden = {"auto_translate", "job_trigger", "trigger_job"}
        assert not cols & forbidden


class TestAuditLog:
    def test_create_audit_log(self, session) -> None:
        log = AuditLog(
            actor_user_id=1,
            action="novel.delete",
            target_type="novel",
            target_id="42",
            metadata_json='{"reason": "takedown"}',
        )
        session.add(log)
        session.commit()
        result = session.query(AuditLog).filter_by(action="novel.delete").one()
        assert result.actor_user_id == 1
        assert result.target_id == "42"

    def test_repr(self, session) -> None:
        log = AuditLog(action="settings.update", actor_user_id=1)
        session.add(log)
        session.commit()
        assert "settings.update" in repr(log)


class TestSystemSetting:
    def test_create_setting(self, session) -> None:
        setting = SystemSetting(key="feature_x", value_json='"enabled"', updated_by=1)
        session.add(setting)
        session.commit()
        result = session.query(SystemSetting).filter_by(key="feature_x").one()
        assert result.value_json == '"enabled"'

    def test_key_is_primary_key(self, session) -> None:
        session.add(SystemSetting(key="unique_key", value_json='"a"'))
        session.commit()
        session.add(SystemSetting(key="unique_key", value_json='"b"'))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_repr(self, session) -> None:
        s = SystemSetting(key="my_key")
        session.add(s)
        session.commit()
        assert "my_key" in repr(s)
