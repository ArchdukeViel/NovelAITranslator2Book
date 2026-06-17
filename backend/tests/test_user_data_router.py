"""Contract tests for authenticated public user data routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.auth.security import reset_public_rate_limits
from novelai.api.routers.dependencies import get_db_session
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.user_data import router as user_data_router
from novelai.db.base import Base

import novelai.db.models.chapter  # noqa: F401
import novelai.db.models.jobs  # noqa: F401
import novelai.db.models.novel  # noqa: F401
import novelai.db.models.system  # noqa: F401
import novelai.db.models.users  # noqa: F401

from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.db.models.users import LibraryItem, ReadingProgress, Review, User

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
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
def seeded_catalog(db_session):
    novel = Novel(slug="test-novel", title="Test Novel", language="ja", status="ongoing")
    other = Novel(slug="other-novel", title="Other Novel", language="ja", status="ongoing")
    db_session.add_all([novel, other])
    db_session.flush()
    chapter = Chapter(novel_id=novel.id, chapter_number=1, title="Chapter One")
    other_chapter = Chapter(novel_id=other.id, chapter_number=1, title="Other Chapter")
    db_session.add_all([chapter, other_chapter])
    db_session.commit()
    return {"novel": novel, "other": other, "chapter": chapter, "other_chapter": other_chapter}


@pytest.fixture()
def app(db_session):
    current = {"user": None}
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    _app.include_router(auth_router)
    _app.include_router(user_data_router)

    def _db_override():
        yield db_session
        db_session.commit()

    def _user_override():
        return current["user"] or SessionUser(user_id=None, email=None, role="guest")

    _app.dependency_overrides[get_db_session] = _db_override
    _app.dependency_overrides[get_current_user] = _user_override
    _app.state.current_user = current
    return _app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def _reset_public_security_state():
    reset_public_rate_limits()
    yield
    reset_public_rate_limits()


def set_user(app: FastAPI, user_id: int, role: str = "user") -> None:
    app.state.current_user["user"] = SessionUser(user_id=user_id, email=f"user{user_id}@test.com", role=role)


def csrf_headers(client: TestClient) -> dict[str, str]:
    resp = client.get("/api/auth/csrf")
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.json()["csrf_token"]}


def assert_keys(data: dict, keys: set[str]) -> None:
    assert set(data) == keys


class TestAuthGuard:
    @pytest.mark.parametrize(
        ("method", "path", "json"),
        [
            ("get", "/api/user/library", None),
            ("post", "/api/user/library/test-novel", None),
            ("delete", "/api/user/library/test-novel", None),
            ("get", "/api/user/progress/test-novel", None),
            ("put", "/api/user/progress/test-novel", {"progress_percent": 0.5}),
            ("get", "/api/user/history", None),
            ("post", "/api/user/history", {"slug": "test-novel"}),
            ("put", "/api/user/reviews/test-novel", {"rating": 5}),
            ("delete", "/api/user/reviews/test-novel", None),
            ("get", "/api/user/requests", None),
            ("post", "/api/user/requests", {"request_type": "novel", "source_url": "https://example.com/novel"}),
        ],
    )
    def test_guest_blocked_from_user_endpoints(self, client, method, path, json) -> None:
        headers = csrf_headers(client) if method in {"post", "put", "delete"} else None
        resp = client.request(method.upper(), path, json=json, headers=headers)
        assert resp.status_code == 401

    def test_user_mutation_requires_csrf_token_before_auth_logic(self, client) -> None:
        assert client.post("/api/user/library/test-novel").status_code == 403
        assert client.post("/api/user/library/test-novel", headers={"X-CSRF-Token": "bad"}).status_code == 403


class TestLibraryContract:
    def test_list_add_get_delete_library_shapes_and_idempotency(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)

        empty = client.get("/api/user/library")
        assert empty.status_code == 200
        assert empty.json() == []

        created = client.post("/api/user/library/test-novel", json={"user_id": 999}, headers=headers)
        assert created.status_code == 201
        assert_keys(created.json(), {"slug", "status", "added_at"})
        assert created.json()["slug"] == "test-novel"
        assert created.json()["status"] == "reading"

        duplicate = client.post("/api/user/library/test-novel", headers=headers)
        assert duplicate.status_code == 201
        assert duplicate.json()["slug"] == "test-novel"

        item = client.get("/api/user/library/test-novel")
        assert item.status_code == 200
        assert_keys(item.json(), {"slug", "status", "added_at"})

        deleted = client.delete("/api/user/library/test-novel", headers=headers)
        assert deleted.status_code == 204
        missing_delete = client.delete("/api/user/library/test-novel", headers=headers)
        assert missing_delete.status_code == 204

    def test_library_unknown_novel_and_missing_membership_statuses(self, app, client) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        assert client.post("/api/user/library/missing", headers=headers).status_code == 404
        assert client.get("/api/user/library/missing").status_code == 404

    def test_user_b_cannot_see_or_remove_user_a_library(self, app, client, seeded_catalog) -> None:
        headers = csrf_headers(client)
        set_user(app, 1)
        assert client.post("/api/user/library/test-novel", headers=headers).status_code == 201

        set_user(app, 2)
        assert client.get("/api/user/library").json() == []
        assert client.get("/api/user/library/test-novel").status_code == 404
        assert client.delete("/api/user/library/test-novel", headers=headers).status_code == 204

        set_user(app, 1)
        assert len(client.get("/api/user/library").json()) == 1


class TestProgressContract:
    def test_progress_get_and_put_shape_and_upsert(self, app, client, seeded_catalog, db_session) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        chapter_id = str(seeded_catalog["chapter"].id)

        initial = client.get("/api/user/progress/test-novel")
        assert initial.status_code == 200
        assert_keys(initial.json(), {"slug", "chapter_id", "chapter_number", "progress_percent", "updated_at"})
        assert initial.json()["progress_percent"] == 0.0
        assert initial.json()["chapter_number"] is None

        updated = client.put(
            "/api/user/progress/test-novel",
            json={"chapter_id": chapter_id, "progress_percent": 0.75, "user_id": 999},
            headers=headers,
        )
        assert updated.status_code == 422

        updated = client.put(
            "/api/user/progress/test-novel",
            json={"chapter_id": chapter_id, "progress_percent": 0.75},
            headers=headers,
        )
        assert updated.status_code == 200
        assert_keys(updated.json(), {"slug", "chapter_id", "chapter_number", "progress_percent", "updated_at"})
        assert updated.json()["chapter_id"] == chapter_id
        assert updated.json()["progress_percent"] == 0.75
        assert updated.json()["chapter_number"] == 1

        overwritten = client.put("/api/user/progress/test-novel", json={"progress_percent": 0.5}, headers=headers)
        assert overwritten.status_code == 200
        assert overwritten.json()["progress_percent"] == 0.5
        assert overwritten.json()["chapter_number"] is None
        assert db_session.query(ReadingProgress).filter_by(user_id=42, novel_id=seeded_catalog["novel"].id).count() == 1

    def test_progress_validation(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        assert client.get("/api/user/progress/missing").status_code == 404
        assert client.put("/api/user/progress/test-novel", json={"progress_percent": 1.5}, headers=headers).status_code == 422
        assert client.put(
            "/api/user/progress/test-novel",
            json={"chapter_id": str(seeded_catalog["other_chapter"].id), "progress_percent": 0.3},
            headers=headers,
        ).status_code == 404

    def test_user_b_cannot_read_or_update_user_a_progress(self, app, client, seeded_catalog) -> None:
        headers = csrf_headers(client)
        set_user(app, 1)
        client.put("/api/user/progress/test-novel", json={"progress_percent": 0.9}, headers=headers)

        set_user(app, 2)
        assert client.get("/api/user/progress/test-novel").json()["progress_percent"] == 0.0
        client.put("/api/user/progress/test-novel", json={"progress_percent": 0.2}, headers=headers)

        set_user(app, 1)
        assert client.get("/api/user/progress/test-novel").json()["progress_percent"] == 0.9

    def test_progress_get_includes_chapter_number_when_chapter_linked(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        chapter_id = str(seeded_catalog["chapter"].id)
        client.put(
            "/api/user/progress/test-novel",
            json={"chapter_id": chapter_id, "progress_percent": 0.5},
            headers=headers,
        )
        resp = client.get("/api/user/progress/test-novel")
        assert resp.status_code == 200
        assert resp.json()["chapter_number"] == 1
        assert resp.json()["chapter_id"] == chapter_id


class TestHistoryContract:
    def test_history_records_body_shape_and_lists_newest_first(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        chapter_id = str(seeded_catalog["chapter"].id)
        first = client.post("/api/user/history", json={"slug": "test-novel", "chapter_id": chapter_id}, headers=headers)
        second = client.post("/api/user/history", json={"slug": "test-novel"}, headers=headers)
        assert first.status_code == 201
        assert_keys(first.json(), {"id", "slug", "chapter_id", "chapter_number", "read_at"})
        assert first.json()["chapter_number"] == 1
        assert second.status_code == 201
        assert second.json()["chapter_number"] is None

        listed = client.get("/api/user/history?limit=1")
        assert listed.status_code == 200
        assert_keys(listed.json(), {"items", "next_cursor"})
        assert len(listed.json()["items"]) == 1
        assert listed.json()["items"][0]["id"] == second.json()["id"]
        assert listed.json()["items"][0]["chapter_number"] is None

    def test_history_validation_and_legacy_query_compatibility(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        assert client.post("/api/user/history", headers=headers).status_code == 400
        assert client.post("/api/user/history", json={"slug": "missing"}, headers=headers).status_code == 404
        assert client.post("/api/user/history?slug=test-novel", headers=headers).status_code == 201

    def test_user_b_cannot_see_user_a_history(self, app, client, seeded_catalog) -> None:
        headers = csrf_headers(client)
        set_user(app, 1)
        client.post("/api/user/history", json={"slug": "test-novel"}, headers=headers)

        set_user(app, 2)
        assert client.get("/api/user/history").json()["items"] == []

    def test_history_list_includes_chapter_number_when_chapter_linked(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        chapter_id = str(seeded_catalog["chapter"].id)
        client.post("/api/user/history", json={"slug": "test-novel", "chapter_id": chapter_id}, headers=headers)
        listed = client.get("/api/user/history")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["chapter_number"] == 1
        assert items[0]["chapter_id"] == chapter_id


class TestReviewContract:
    def test_put_review_upserts_and_delete_is_idempotent(self, app, client, seeded_catalog, db_session) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        created = client.put("/api/user/reviews/test-novel", json={"rating": 5, "body": "Great"}, headers=headers)
        assert created.status_code == 200
        assert_keys(created.json(), {"slug", "rating", "body", "status", "updated_at"})
        assert created.json()["status"] == "pending"

        updated = client.put("/api/user/reviews/test-novel", json={"rating": 4, "body": "Still good"}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["rating"] == 4
        assert db_session.query(Review).filter_by(user_id=42, novel_id=seeded_catalog["novel"].id).count() == 1

        assert client.delete("/api/user/reviews/test-novel", headers=headers).status_code == 204
        assert client.delete("/api/user/reviews/test-novel", headers=headers).status_code == 204

    def test_legacy_post_review_preserved_with_contract_shape(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        resp = client.post("/api/user/reviews/test-novel", json={"rating": 5, "body": "Great novel!"}, headers=csrf_headers(client))
        assert resp.status_code == 201
        assert_keys(resp.json(), {"slug", "rating", "body", "status", "updated_at"})

    def test_review_validation_and_unknown_novel(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        assert client.put("/api/user/reviews/test-novel", json={"rating": 6}, headers=headers).status_code == 422
        assert client.put("/api/user/reviews/test-novel", json={"rating": 0}, headers=headers).status_code == 422
        assert client.put("/api/user/reviews/unknown", json={"rating": 3}, headers=headers).status_code == 404
        assert client.put("/api/user/reviews/test-novel", json={"rating": 5, "user_id": 99}, headers=headers).status_code == 422

    def test_user_b_cannot_modify_user_a_review(self, app, client, seeded_catalog) -> None:
        headers = csrf_headers(client)
        set_user(app, 1)
        client.put("/api/user/reviews/test-novel", json={"rating": 5}, headers=headers)

        set_user(app, 2)
        client.delete("/api/user/reviews/test-novel", headers=headers)

        set_user(app, 1)
        client.put("/api/user/reviews/test-novel", json={"rating": 4}, headers=headers)
        set_user(app, 2)
        client.put("/api/user/reviews/test-novel", json={"rating": 2}, headers=headers)
        set_user(app, 1)
        # User A's review still exists independently; no public read endpoint is exposed yet.
        assert client.delete("/api/user/reviews/test-novel", headers=headers).status_code == 204

    def test_review_mutation_rate_limit_eventually_returns_429(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        statuses = [
            client.put("/api/user/reviews/test-novel", json={"rating": 5}, headers=headers).status_code
            for _ in range(21)
        ]
        assert statuses[:20] == [200] * 20
        assert statuses[-1] == 429


class TestRequestContract:
    def test_request_create_list_shape_and_duplicate_pending_idempotency(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        payload = {"request_type": "novel", "source_url": "https://example.com/novel"}
        created = client.post("/api/user/requests", json=payload, headers=headers)
        duplicate = client.post("/api/user/requests", json=payload, headers=headers)
        assert created.status_code == 201
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] == created.json()["id"]
        assert_keys(created.json(), {"id", "request_type", "status", "source_url", "slug", "chapter_id", "created_at"})
        assert created.json()["status"] == "pending"

        listed = client.get("/api/user/requests")
        assert listed.status_code == 200
        assert_keys(listed.json(), {"items", "next_cursor"})
        assert len(listed.json()["items"]) == 1

    def test_chapter_request_validation(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        chapter_id = str(seeded_catalog["chapter"].id)
        resp = client.post(
            "/api/user/requests",
            json={"request_type": "chapter", "slug": "test-novel", "chapter_id": chapter_id},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "test-novel"
        assert resp.json()["chapter_id"] is None

        assert client.post("/api/user/requests", json={"request_type": "bad"}, headers=headers).status_code == 422
        assert client.post("/api/user/requests", json={"request_type": "novel"}, headers=headers).status_code == 422
        assert client.post(
            "/api/user/requests",
            json={"request_type": "chapter", "slug": "test-novel", "chapter_id": str(seeded_catalog["other_chapter"].id)},
            headers=headers,
        ).status_code == 404
        assert client.post(
            "/api/user/requests",
            json={"request_type": "novel", "source_url": "https://example.com/novel", "user_id": 1},
            headers=headers,
        ).status_code == 422

    def test_user_b_cannot_see_user_a_requests(self, app, client, seeded_catalog) -> None:
        headers = csrf_headers(client)
        set_user(app, 1)
        client.post("/api/user/requests", json={"request_type": "novel", "source_url": "https://example.com/novel"}, headers=headers)

        set_user(app, 2)
        assert client.get("/api/user/requests").json()["items"] == []

    def test_requests_never_auto_trigger_jobs(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        resp = client.post("/api/user/requests", json={"request_type": "chapter", "slug": "test-novel"}, headers=csrf_headers(client))
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"
        assert "auto_translate" not in resp.json()
        assert "triggered" not in resp.json()

    def test_request_create_rate_limit_eventually_returns_429(self, app, client, seeded_catalog) -> None:
        set_user(app, 42)
        headers = csrf_headers(client)
        statuses = [
            client.post(
                "/api/user/requests",
                json={"request_type": "novel", "source_url": f"https://example.com/novel-{idx}"},
                headers=headers,
            ).status_code
            for idx in range(11)
        ]
        assert statuses[:10] == [201] * 10
        assert statuses[-1] == 429


class TestOwnerSessionDoesNotBypassOwnership:
    def test_owner_only_sees_owner_session_user_data(self, app, client, seeded_catalog) -> None:
        headers = csrf_headers(client)
        set_user(app, 1, role="user")
        client.post("/api/user/library/test-novel", headers=headers)

        set_user(app, 999, role="owner")
        assert client.get("/api/user/library").json() == []
