"""Contract tests for session-scoped notification API."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session, get_notification_persistence_service
from novelai.api.routers.notifications import router
from novelai.db.base import Base
from novelai.db.models.users import User
from novelai.services.notification_service import NoopNotificationBackend, NotificationPersistenceService


@pytest.fixture()
def app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine)()
    first = User(email="first@example.test", role="user")
    second = User(email="second@example.test", role="user")
    owner = User(email="owner@example.test", role="owner")
    db_session.add_all([first, second, owner])
    db_session.commit()
    current = {"user": SessionUser(user_id=None, email=None, role="guest")}
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    app.include_router(auth_router)
    app.include_router(router)

    def db_override():
        yield db_session

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[get_notification_persistence_service] = lambda: NotificationPersistenceService(
        db_session, NoopNotificationBackend()
    )
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.state.db_session = db_session
    app.state.users = {"first": first.id, "second": second.id, "owner": owner.id}
    app.state.current = current
    yield app
    db_session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/csrf").json()["csrf_token"]}


def _set_user(app: FastAPI, key: str) -> None:
    user_id = app.state.users[key]
    role = "owner" if key == "owner" else "user"
    app.state.current["user"] = SessionUser(user_id=user_id, email=f"{key}@example.test", role=role)


def _create(app: FastAPI, key: str, dedupe_key: str, event_type: str = "translation.completed") -> int:
    result = NotificationPersistenceService(app.state.db_session, NoopNotificationBackend()).create(
        recipient_user_id=app.state.users[key],
        event_type=event_type,
        title="Ready",
        body="Private body",
        severity="success",
        dedupe_key=dedupe_key,
    )
    assert result is not None
    return result["id"]  # type: ignore[return-value]


def test_guest_blocked_and_mutations_require_csrf(app: FastAPI, client: TestClient) -> None:
    assert client.get("/api/user/notifications").status_code == 401
    assert client.post("/api/user/notifications/read-all").status_code == 403
    _set_user(app, "first")
    assert client.post("/api/user/notifications/read-all").status_code == 403


def test_list_filters_pagination_and_unread_count(app: FastAPI, client: TestClient) -> None:
    _create(app, "first", "first-1")
    _create(app, "first", "first-2", "translation.failed")
    _create(app, "second", "second-1")
    _set_user(app, "first")

    response = client.get("/api/user/notifications?page=1&page_size=1&event_type=translation.completed&channel=in_app")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1
    assert client.get("/api/user/notifications/unread-count").json() == {"unread_count": 2}
    assert client.get("/api/user/notifications?page=0").status_code == 422
    assert client.get("/api/user/notifications?event_type=bad").status_code == 422


def test_read_archive_and_read_all_hide_other_user_ids(app: FastAPI, client: TestClient) -> None:
    first_id = _create(app, "first", "first-1")
    second_id = _create(app, "second", "second-1")
    _set_user(app, "first")
    headers = _csrf(client)

    assert client.post(f"/api/user/notifications/{second_id}/read", headers=headers).status_code == 404
    assert client.post(f"/api/user/notifications/{first_id}/read", headers=headers).status_code == 204
    assert client.post(f"/api/user/notifications/{first_id}/archive", headers=headers).status_code == 204
    assert client.post("/api/user/notifications/read-all", headers=headers).json() == {"updated": 0}


def test_preferences_accept_owner_session_and_validate_payload(app: FastAPI, client: TestClient) -> None:
    _set_user(app, "owner")
    assert len(client.get("/api/user/notifications/preferences").json()) == 6
    headers = _csrf(client)
    response = client.put(
        "/api/user/notifications/preferences",
        headers=headers,
        json={"event_type": "translation.completed", "channel": "email", "enabled": True},
    )
    assert response.status_code == 200
    assert response.json() == {"event_type": "translation.completed", "channel": "email", "enabled": True}
    assert (
        client.put(
            "/api/user/notifications/preferences",
            headers=headers,
            json={"event_type": "bad", "channel": "email", "enabled": True},
        ).status_code
        == 422
    )
