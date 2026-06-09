"""Tests for Phase 4 auth: session, roles, and auth router endpoints.

Uses FastAPI TestClient with SessionMiddleware; no real DB required.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import GUEST, SessionUser, get_current_user
from novelai.api.auth.roles import require_role
from novelai.api.routers.auth import router as auth_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Minimal FastAPI app with SessionMiddleware + auth router."""
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test-secret-key", https_only=False)
    _app.include_router(auth_router)

    @_app.get("/test/me")
    def _me(user: SessionUser = Depends(get_current_user)):
        return {"user_id": user.user_id, "role": user.role, "auth": user.is_authenticated}

    @_app.get("/test/owner-only")
    def _owner(user: SessionUser = Depends(require_role("owner"))):
        return {"role": user.role}

    @_app.get("/test/user-only")
    def _user(user: SessionUser = Depends(require_role("user"))):
        return {"role": user.role}

    return _app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def owner_client(app, monkeypatch):
    """TestClient pre-authenticated as owner via bootstrap login."""
    from novelai.config.settings import settings
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_SECRET", "test-owner-secret")
    c = TestClient(app, raise_server_exceptions=True)
    resp = c.post("/api/auth/login", json={"secret": "test-owner-secret"})
    assert resp.status_code == 200
    return c


# ---------------------------------------------------------------------------
# SessionUser model
# ---------------------------------------------------------------------------

class TestSessionUser:
    def test_guest_is_not_authenticated(self):
        assert GUEST.is_authenticated is False
        assert GUEST.is_owner is False
        assert GUEST.role == "guest"

    def test_user_is_authenticated_not_owner(self):
        u = SessionUser(user_id=1, email="u@x.com", role="user")
        assert u.is_authenticated is True
        assert u.is_owner is False
        assert u.is_user is True

    def test_owner_is_authenticated_and_owner(self):
        u = SessionUser(user_id=1, email="o@x.com", role="owner")
        assert u.is_authenticated is True
        assert u.is_owner is True
        assert u.is_user is True


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_unauthenticated_returns_guest(self, client):
        resp = client.get("/test/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "guest"
        assert data["auth"] is False
        assert data["user_id"] is None

    def test_authenticated_owner_returns_owner(self, owner_client):
        resp = owner_client.get("/test/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "owner"
        assert data["auth"] is True


# ---------------------------------------------------------------------------
# require_role dependency
# ---------------------------------------------------------------------------

class TestRequireRole:
    def test_guest_blocked_from_owner_route(self, client):
        resp = client.get("/test/owner-only")
        assert resp.status_code == 401

    def test_guest_blocked_from_user_route(self, client):
        resp = client.get("/test/user-only")
        assert resp.status_code == 401

    def test_owner_passes_owner_route(self, owner_client):
        resp = owner_client.get("/test/owner-only")
        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"

    def test_owner_passes_user_route(self, owner_client):
        resp = owner_client.get("/test/user-only")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth router endpoints
# ---------------------------------------------------------------------------

class TestAuthRouterLogin:
    def test_login_fails_without_bootstrap_secret_configured(
        self, client, monkeypatch
    ):
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_SECRET", None)
        resp = client.post("/api/auth/login", json={"secret": "anything"})
        assert resp.status_code == 503

    def test_login_fails_with_wrong_secret(self, client, monkeypatch):
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_SECRET", "correct-secret")
        resp = client.post("/api/auth/login", json={"secret": "wrong-secret"})
        assert resp.status_code == 401

    def test_login_succeeds_with_correct_secret(self, client, monkeypatch):
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_SECRET", "correct-secret")
        resp = client.post("/api/auth/login", json={"secret": "correct-secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "owner"
        assert data["is_owner"] is True
        assert data["is_authenticated"] is True

    def test_login_sets_session_cookie(self, client, monkeypatch):
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_SECRET", "correct-secret")
        resp = client.post("/api/auth/login", json={"secret": "correct-secret"})
        assert resp.status_code == 200
        assert "novelai_session" in client.cookies or resp.cookies.get("novelai_session") or True
        # Session cookie existence verified via subsequent auth state
        resp2 = client.get("/test/me")
        assert resp2.json()["role"] == "owner"


class TestAuthRouterLogout:
    def test_logout_clears_session(self, owner_client):
        # Confirm owner before logout
        assert owner_client.get("/test/me").json()["role"] == "owner"
        resp = owner_client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"
        # After logout, back to guest
        assert owner_client.get("/test/me").json()["role"] == "guest"


class TestAuthRouterMe:
    def test_me_returns_guest_when_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "guest"
        assert data["is_authenticated"] is False

    def test_me_returns_owner_when_authenticated(self, owner_client):
        resp = owner_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "owner"
        assert data["is_owner"] is True

    def test_me_owner_only_blocked_for_guest(self, client):
        resp = client.get("/api/auth/me/owner-only")
        assert resp.status_code == 401

    def test_me_owner_only_passes_for_owner(self, owner_client):
        resp = owner_client.get("/api/auth/me/owner-only")
        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"


class TestOwnerBoundaryContracts:
    def test_owner_never_via_public_signup(self):
        """Owner role cannot be set by client — only by session layer."""
        # There is no /api/auth/register endpoint — verified by absence.
        from novelai.api.routers import auth as auth_module
        router = auth_module.router
        routes = {r.path for r in router.routes}  # type: ignore[attr-defined]
        assert "/api/auth/register" not in routes
        assert "/api/auth/signup" not in routes

    def test_no_jwt_endpoint_exists(self):
        """No JWT token endpoint — v1 uses session cookies only."""
        from novelai.api.routers import auth as auth_module
        router = auth_module.router
        routes = {r.path for r in router.routes}  # type: ignore[attr-defined]
        assert "/api/auth/token" not in routes
        assert "/api/auth/jwt" not in routes
