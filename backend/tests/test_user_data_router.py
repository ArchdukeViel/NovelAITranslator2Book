"""Tests for the user data router (/api/user/).

Uses SQLite in-memory + SessionMiddleware; no real DB or network required.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.roles import require_role
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_db_session
from novelai.api.routers.user_data import router as user_data_router
from novelai.db.base import Base

# Import ALL models so Base.metadata knows about every table before create_all.
import novelai.db.models.novel      # noqa: F401
import novelai.db.models.chapter    # noqa: F401
import novelai.db.models.jobs       # noqa: F401
import novelai.db.models.users      # noqa: F401
import novelai.db.models.system     # noqa: F401

from novelai.db.models.novel import Novel

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
    # StaticPool + check_same_thread=False: lets FastAPI's threadpool workers
    # reuse the same in-memory SQLite connection safely across threads.
    engine = create_engine(
        _SQLITE,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def seeded_novel(db_session):
    novel = Novel(slug="test-novel", title="Test Novel", language="ja", status="ongoing")
    db_session.add(novel)
    db_session.commit()
    return novel


@pytest.fixture()
def app(db_session):
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    _app.include_router(user_data_router)
    _app.dependency_overrides[get_db_session] = lambda: db_session
    return _app


@pytest.fixture()
def guest_client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def user_client(app):
    """Client with a user session injected via get_current_user override."""
    from novelai.api.auth.session import get_current_user
    _user = SessionUser(user_id=42, email="user@test.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: _user
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_guest_blocked_from_library(self, guest_client) -> None:
        resp = guest_client.get("/api/user/library")
        assert resp.status_code == 401

    def test_guest_blocked_from_progress(self, guest_client) -> None:
        resp = guest_client.get("/api/user/progress/some-novel")
        assert resp.status_code == 401

    def test_guest_blocked_from_history(self, guest_client) -> None:
        resp = guest_client.get("/api/user/history")
        assert resp.status_code == 401

    def test_guest_blocked_from_requests(self, guest_client) -> None:
        resp = guest_client.get("/api/user/requests")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

class TestLibrary:
    def test_empty_library(self, user_client) -> None:
        resp = user_client.get("/api/user/library")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_to_library(self, user_client, db_session, seeded_novel) -> None:
        resp = user_client.post("/api/user/library/test-novel")
        assert resp.status_code == 201
        assert resp.json()["slug"] == "test-novel"

    def test_add_unknown_novel_returns_404(self, user_client) -> None:
        resp = user_client.post("/api/user/library/does-not-exist")
        assert resp.status_code == 404

    def test_add_twice_returns_already_in_library(self, user_client, seeded_novel) -> None:
        user_client.post("/api/user/library/test-novel")
        resp = user_client.post("/api/user/library/test-novel")
        assert resp.status_code == 201
        assert resp.json()["message"] == "already_in_library"

    def test_list_library_after_add(self, user_client, seeded_novel) -> None:
        user_client.post("/api/user/library/test-novel")
        resp = user_client.get("/api/user/library")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "test-novel"

    def test_remove_from_library(self, user_client, seeded_novel) -> None:
        user_client.post("/api/user/library/test-novel")
        resp = user_client.delete("/api/user/library/test-novel")
        assert resp.status_code == 204
        assert user_client.get("/api/user/library").json() == []

    def test_remove_unknown_is_no_op(self, user_client, seeded_novel) -> None:
        resp = user_client.delete("/api/user/library/test-novel")
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Reading progress
# ---------------------------------------------------------------------------

class TestReadingProgress:
    def test_get_progress_no_record(self, user_client, seeded_novel) -> None:
        resp = user_client.get("/api/user/progress/test-novel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress_percent"] == 0.0
        assert data["chapter_id"] is None

    def test_update_progress(self, user_client, seeded_novel) -> None:
        resp = user_client.put(
            "/api/user/progress/test-novel",
            json={"progress_percent": 0.75},
        )
        assert resp.status_code == 200
        assert resp.json()["progress_percent"] == 0.75

    def test_progress_persists_after_update(self, user_client, seeded_novel) -> None:
        user_client.put("/api/user/progress/test-novel", json={"progress_percent": 0.5})
        resp = user_client.get("/api/user/progress/test-novel")
        assert resp.json()["progress_percent"] == 0.5

    def test_progress_404_for_unknown_novel(self, user_client) -> None:
        resp = user_client.get("/api/user/progress/unknown")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reading history
# ---------------------------------------------------------------------------

class TestReadingHistory:
    def test_record_history(self, user_client, seeded_novel) -> None:
        resp = user_client.post("/api/user/history?slug=test-novel")
        assert resp.status_code == 201
        assert resp.json()["recorded"] is True

    def test_list_history(self, user_client, seeded_novel) -> None:
        user_client.post("/api/user/history?slug=test-novel")
        resp = user_client.get("/api/user/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_multiple_history_entries(self, user_client, seeded_novel) -> None:
        user_client.post("/api/user/history?slug=test-novel")
        user_client.post("/api/user/history?slug=test-novel")
        resp = user_client.get("/api/user/history")
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class TestReviews:
    def test_post_review(self, user_client, seeded_novel) -> None:
        resp = user_client.post(
            "/api/user/reviews/test-novel",
            json={"rating": 5, "body": "Great novel!"},
        )
        assert resp.status_code == 201
        assert resp.json()["rating"] == 5

    def test_review_without_rating(self, user_client, seeded_novel) -> None:
        resp = user_client.post(
            "/api/user/reviews/test-novel",
            json={"body": "No rating"},
        )
        assert resp.status_code == 201

    def test_review_404_for_unknown(self, user_client) -> None:
        resp = user_client.post("/api/user/reviews/unknown", json={"rating": 3})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class TestNovelRequests:
    def test_submit_request(self, user_client) -> None:
        resp = user_client.post(
            "/api/user/requests",
            json={"request_type": "new_novel", "source_url": "https://example.com/novel"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_list_requests(self, user_client) -> None:
        user_client.post("/api/user/requests", json={"request_type": "new_novel"})
        resp = user_client.get("/api/user/requests")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_requests_never_auto_trigger_jobs(self, user_client) -> None:
        """Requests land as 'pending' — owner must approve (architecture §20)."""
        resp = user_client.post(
            "/api/user/requests",
            json={"request_type": "translate_chapter"},
        )
        assert resp.json()["status"] == "pending"
        # There is no 'auto_translate' or 'triggered' field in the response
        assert "auto_translate" not in resp.json()
        assert "triggered" not in resp.json()
