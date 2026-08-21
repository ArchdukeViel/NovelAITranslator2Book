"""HTTP contract tests for authenticated contributor credential endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session
from novelai.api.routers.user_contributions import router
from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.contributor import ContributorCredential, ContributorUsageLedger
from novelai.db.models.users import User
from novelai.providers.gemini_provider import GeminiProvider


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine)()
    first = User(email="contributor-router@example.test", role="user")
    second = User(email="other-router@example.test", role="user")
    owner = User(email="owner-router@example.test", role="owner")
    db_session.add_all([first, second, owner])
    db_session.commit()

    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("router-test-encryption"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(settings, "CONTRIBUTOR_CREDENTIALS_ENABLED", True)

    current = {"user": SessionUser(user_id=None, email=None, role="guest")}
    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware, secret_key="router-test-session", https_only=False)
    test_app.include_router(auth_router)
    test_app.include_router(router)

    def db_override():
        yield db_session

    test_app.dependency_overrides[get_db_session] = db_override
    test_app.dependency_overrides[get_current_user] = lambda: current["user"]
    test_app.state.current = current
    test_app.state.users = {"first": first.id, "second": second.id, "owner": owner.id}
    test_app.state.db_session = db_session
    yield test_app
    db_session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/csrf").json()["csrf_token"]}


def _as_user(app: FastAPI, key: str) -> None:
    user_id = app.state.users[key]
    role = "owner" if key == "owner" else "user"
    app.state.current["user"] = SessionUser(user_id=user_id, email=f"{key}@example.test", role=role)


def _payload(client: TestClient, *, key: str = "router-secret-key") -> dict[str, object]:
    return {
        "provider_key": "gemini",
        "api_key": key,
        "consent_version": settings.CONTRIBUTOR_CONSENT_VERSION,
    }


def test_contribution_routes_require_user_and_csrf_for_mutations(app: FastAPI, client: TestClient) -> None:
    assert client.get("/api/user/contributions").status_code == 401
    assert client.put("/api/user/contributions", json=_payload(client)).status_code == 403

    _as_user(app, "first")
    assert client.put("/api/user/contributions", json=_payload(client)).status_code == 403
    assert client.patch("/api/user/contributions/missing", json={"status": "paused"}).status_code == 403
    assert client.delete("/api/user/contributions/missing").status_code == 403


def test_contribution_api_masks_key_and_enforces_ownership_and_lifecycle(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def valid_validate(self: GeminiProvider, model: str | None = None, **kwargs: object) -> tuple[bool, str]:
        del self, model, kwargs
        return True, "valid"

    monkeypatch.setattr(GeminiProvider, "validate_connection", valid_validate)
    _as_user(app, "first")
    headers = _csrf(client)
    response = client.put("/api/user/contributions", json=_payload(client), headers=headers)

    assert response.status_code == 200
    body = response.json()
    credential = body["credential"]
    credential_id = credential["credential_id"]
    assert body["validation_ok"] is True
    assert credential["status"] == "active"
    assert credential["last4"] == "-key"
    assert "api_key" not in body
    assert "encrypted_api_key" not in body
    assert "router-secret-key" not in response.text

    assert client.get("/api/user/contributions").json()["credentials"][0]["credential_id"] == credential_id

    _as_user(app, "second")
    assert client.get(f"/api/user/contributions/{credential_id}/usage").status_code == 404
    assert (
        client.patch(
            f"/api/user/contributions/{credential_id}",
            json={"status": "paused"},
            headers=_csrf(client),
        ).status_code
        == 404
    )
    assert client.delete(f"/api/user/contributions/{credential_id}", headers=_csrf(client)).status_code == 404

    _as_user(app, "first")
    assert (
        client.patch(
            f"/api/user/contributions/{credential_id}",
            json={"status": "paused"},
            headers=_csrf(client),
        ).json()["status"]
        == "paused"
    )
    assert (
        client.patch(
            f"/api/user/contributions/{credential_id}",
            json={"status": "active"},
            headers=_csrf(client),
        ).json()["status"]
        == "active"
    )
    assert client.delete(f"/api/user/contributions/{credential_id}", headers=_csrf(client)).status_code == 204
    assert app.state.db_session.get(ContributorCredential, credential_id) is None
    assert app.state.db_session.query(ContributorUsageLedger).count() == 1


def test_failed_validation_is_persisted_as_invalid_and_not_eligible(
    app: FastAPI, client: TestClient, monkeypatch
) -> None:
    async def invalid_validate(self: GeminiProvider, model: str | None = None, **kwargs: object) -> tuple[bool, str]:
        del self, model, kwargs
        return False, "invalid key"

    monkeypatch.setattr(GeminiProvider, "validate_connection", invalid_validate)
    _as_user(app, "first")
    response = client.put(
        "/api/user/contributions",
        json=_payload(client, key="bad-key"),
        headers=_csrf(client),
    )

    assert response.status_code == 200
    assert response.json()["validation_ok"] is False
    assert response.json()["credential"]["status"] == "invalid"
    assert response.json()["credential"]["validation_status"] == "failed"
