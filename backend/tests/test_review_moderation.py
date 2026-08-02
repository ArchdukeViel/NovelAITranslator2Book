"""Service-level tests for review moderation contract."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.db.models.users import Review
from novelai.services.review_service import ReviewService

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
    engine = create_engine(_SQLITE, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def novel(db_session):
    n = Novel(slug="test-novel", title="Test Novel", language="ja", publication_status="ongoing")
    db_session.add(n)
    db_session.commit()
    return n


@pytest.fixture()
def svc(db_session):
    return ReviewService(db_session=db_session)


class TestUpsertResetsModeration:
    def test_new_review_is_pending(self, svc, novel) -> None:
        result = svc.upsert_review(1, "test-novel", 5, "Great")
        assert result["status"] == "pending"
        assert result["id"] is not None

    def test_edit_resets_to_pending(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "Great")
        review = db_session.query(Review).filter_by(user_id=1).one()
        review.status = "published"
        db_session.flush()

        result = svc.upsert_review(1, "test-novel", 4, "Updated")
        assert result["status"] == "pending"
        assert result["rating"] == 4

    def test_upsert_clears_moderation_fields(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "Great")
        svc.moderate_review(
            db_session.query(Review).filter_by(user_id=1).one().id,
            "published",
            reviewer_notes="Good",
            reviewed_by_user_id=99,
        )
        svc.upsert_review(1, "test-novel", 3, "Changed")
        review = db_session.query(Review).filter_by(user_id=1).one()
        assert review.status == "pending"
        assert review.moderated_at is None
        assert review.reviewer_notes is None

    def test_updated_at_changes_on_edit(self, svc, novel) -> None:
        first = svc.upsert_review(1, "test-novel", 5, "Great")
        second = svc.upsert_review(1, "test-novel", 4, "Updated")
        assert second["updated_at"] >= first["updated_at"]


class TestModerateReview:
    def test_publish_review(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "Great")
        review = db_session.query(Review).filter_by(user_id=1).one()
        result = svc.moderate_review(review.id, "published", reviewer_notes="OK", reviewed_by_user_id=99)
        assert result is not None
        assert result.status == "published"
        assert result.moderated_at is not None
        assert result.reviewer_notes == "OK"
        assert result.reviewed_by_user_id == 99

    def test_reject_review(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "Great")
        review = db_session.query(Review).filter_by(user_id=1).one()
        result = svc.moderate_review(review.id, "rejected")
        assert result is not None
        assert result.status == "rejected"

    def test_invalid_status_raises(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "Great")
        review = db_session.query(Review).filter_by(user_id=1).one()
        with pytest.raises(ValueError, match="Invalid status"):
            svc.moderate_review(review.id, "pending")

    def test_nonexistent_returns_none(self, svc) -> None:
        assert svc.moderate_review(99999, "published") is None


class TestListPublishedReviews:
    def _seed(self, svc, db_session, count: int, status: str = "published", uid_start: int = 100) -> list[int]:
        """Create reviews and set their status. Returns review ids."""
        ids = []
        for i in range(count):
            uid = uid_start + i
            svc.upsert_review(uid, "test-novel", 3 + (i % 3), f"Review {uid}")
            review = db_session.query(Review).filter_by(user_id=uid).one()
            review.status = status
            db_session.flush()
            ids.append(review.id)
        return ids

    def test_only_published_visible(self, svc, novel, db_session) -> None:
        self._seed(svc, db_session, 3, "published", uid_start=100)
        self._seed(svc, db_session, 2, "pending", uid_start=200)
        self._seed(svc, db_session, 1, "rejected", uid_start=300)
        items, _ = svc.list_published_reviews("test-novel")
        assert len(items) == 3
        # Items must not expose user_id or status.
        for item in items:
            assert "user_id" not in item
            assert "status" not in item

    def test_pagination_cursor_walk(self, svc, novel, db_session) -> None:
        self._seed(svc, db_session, 5, "published", uid_start=400)
        page1, cursor1 = svc.list_published_reviews("test-novel", limit=2)
        assert len(page1) == 2
        assert cursor1 is not None

        page2, cursor2 = svc.list_published_reviews("test-novel", limit=2, cursor=cursor1)
        assert len(page2) == 2
        assert cursor2 is not None

        page3, cursor3 = svc.list_published_reviews("test-novel", limit=2, cursor=cursor2)
        assert len(page3) == 1
        assert cursor3 is None

    def test_bad_cursor_ignored(self, svc, novel, db_session) -> None:
        self._seed(svc, db_session, 2, "published", uid_start=500)
        items, _ = svc.list_published_reviews("test-novel", cursor="garbage")
        assert len(items) == 2


class TestListAllReviews:
    def test_status_filter(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "A")
        svc.upsert_review(2, "test-novel", 4, "B")
        review_b = db_session.query(Review).filter_by(user_id=2).one()
        review_b.status = "published"
        db_session.flush()

        pending, total_p = svc.list_all_reviews(status="pending")
        assert total_p == 1
        assert all(r["status"] == "pending" for r in pending)

        _published, total_pub = svc.list_all_reviews(status="published")
        assert total_pub == 1

        _all_reviews, total_all = svc.list_all_reviews()
        assert total_all == 2

    def test_includes_novel_metadata(self, svc, novel, db_session) -> None:
        svc.upsert_review(1, "test-novel", 5, "A")
        items, _ = svc.list_all_reviews()
        assert items[0]["slug"] == "test-novel"
        assert items[0]["title"] == "Test Novel"
        assert "user_id" in items[0]


class TestDeleteReview:
    def test_delete_returns_id(self, svc, novel) -> None:
        svc.upsert_review(1, "test-novel", 5, "Great")
        review_id = svc.delete_review(1, "test-novel")
        assert review_id is not None

    def test_delete_missing_returns_none(self, svc, novel) -> None:
        assert svc.delete_review(1, "test-novel") is None
