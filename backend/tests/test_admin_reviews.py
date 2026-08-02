"""Contract tests for admin review moderation endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.security import require_csrf_for_unsafe_methods, reset_public_rate_limits
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.admin_reviews import router as admin_reviews_router
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session
from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.db.models.system import AuditLog
from novelai.db.models.users import Review

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


def _make_app(db_session, role: str = "owner"):
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    _app.include_router(auth_router)
    _app.include_router(admin_reviews_router)

    def _db_override():
        yield db_session
        db_session.commit()

    _app.dependency_overrides[get_db_session] = _db_override
    _app.dependency_overrides[get_current_user] = lambda: SessionUser(user_id=1, email="owner@test.com", role=role)
    _app.dependency_overrides[require_csrf_for_unsafe_methods] = lambda: None
    return _app


@pytest.fixture()
def app(db_session):
    return _make_app(db_session, "owner")


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def _reset():
    reset_public_rate_limits()
    yield
    reset_public_rate_limits()


def _seed_review(db_session, novel, user_id: int = 10, rating: int = 5, status: str = "pending") -> Review:
    r = Review(user_id=user_id, novel_id=novel.id, rating=rating, body="Test review", status=status)
    db_session.add(r)
    db_session.flush()
    return r


class TestAdminReviewList:
    def test_list_reviews_returns_items(self, client, novel, db_session) -> None:
        _seed_review(db_session, novel)
        db_session.commit()
        resp = client.get("/api/admin/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["slug"] == "test-novel"
        assert data["items"][0]["title"] == "Test Novel"

    def test_status_filter(self, client, novel, db_session) -> None:
        _seed_review(db_session, novel, user_id=1, status="pending")
        _seed_review(db_session, novel, user_id=2, status="published")
        db_session.commit()

        pending = client.get("/api/admin/reviews?status=pending").json()
        assert pending["total"] == 1
        assert pending["items"][0]["status"] == "pending"

    def test_owner_required(self, db_session, novel) -> None:
        user_app = _make_app(db_session, "user")
        user_client = TestClient(user_app, raise_server_exceptions=False)
        resp = user_client.get("/api/admin/reviews")
        assert resp.status_code == 403


class TestAdminModeration:
    def test_publish_review(self, client, novel, db_session) -> None:
        review = _seed_review(db_session, novel)
        db_session.commit()
        resp = client.post(f"/api/admin/reviews/{review.id}/review", json={"status": "published"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    def test_reject_review(self, client, novel, db_session) -> None:
        review = _seed_review(db_session, novel)
        db_session.commit()
        resp = client.post(
            f"/api/admin/reviews/{review.id}/review",
            json={"status": "rejected", "reviewer_notes": "Inappropriate"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_invalid_status_returns_400(self, client, novel, db_session) -> None:
        review = _seed_review(db_session, novel)
        db_session.commit()
        resp = client.post(f"/api/admin/reviews/{review.id}/review", json={"status": "pending"})
        assert resp.status_code == 400

    def test_missing_review_returns_404(self, client) -> None:
        resp = client.post("/api/admin/reviews/99999/review", json={"status": "published"})
        assert resp.status_code == 404

    def test_audit_log_created(self, client, novel, db_session) -> None:
        review = _seed_review(db_session, novel)
        db_session.commit()
        before = db_session.query(AuditLog).filter(AuditLog.action == "review.moderated").count()
        client.post(f"/api/admin/reviews/{review.id}/review", json={"status": "published"})
        after = db_session.query(AuditLog).filter(AuditLog.action == "review.moderated").count()
        assert after == before + 1
