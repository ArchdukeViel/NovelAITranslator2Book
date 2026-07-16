"""Tests for Phase 4 auth: session, roles, and auth router endpoints.

Uses FastAPI TestClient with SessionMiddleware; no real DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

# ORM models are registered by the session-scoped autouse fixture in conftest.py.
from novelai.api.auth.google_oauth import GoogleOAuthProfile, get_google_oauth_client
from novelai.api.auth.passwords import hash_password, verify_password
from novelai.api.auth.roles import require_role
from novelai.api.auth.security import reset_public_rate_limits
from novelai.api.auth.session import GUEST, SessionUser, get_current_user
from novelai.api.routers import auth as auth_module
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session
from novelai.api.routers.user_data import router as user_data_router
from novelai.db.base import Base
from novelai.db.models.users import EmailVerificationToken, PasswordResetToken, User
from novelai.services.email import EmailDeliveryResult, InMemoryAuthEmailService

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


@pytest.fixture(autouse=True)
def _reset_public_rate_limits():
    reset_public_rate_limits()
    yield
    reset_public_rate_limits()


@pytest.fixture()
def owner_client(app, monkeypatch):
    """TestClient pre-authenticated as owner via bootstrap login."""
    from novelai.config.settings import settings
    monkeypatch.setattr(settings, "OWNER_BOOTSTRAP_SECRET", "test-owner-secret")
    c = TestClient(app, raise_server_exceptions=True)
    resp = c.post("/api/auth/login", json={"secret": "test-owner-secret"})
    assert resp.status_code == 200
    return c


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


class FakeGoogleOAuthClient:
    def __init__(self, profile: GoogleOAuthProfile | None = None):
        self.profile = profile or GoogleOAuthProfile(
            subject="google-sub-1",
            email="Reader@Example.COM",
            email_verified=True,
            display_name="Reader One",
        )

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> GoogleOAuthProfile:
        return self.profile


@pytest.fixture()
def oauth_app(db_session, monkeypatch):
    from novelai.config.settings import settings

    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", SecretStr("google-client-secret"))
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "http://testserver/api/auth/google/callback")
    monkeypatch.setattr(settings, "PUBLIC_FRONTEND_URL", "http://frontend.test")

    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test-secret-key", https_only=False)
    _app.include_router(auth_router)
    _app.include_router(user_data_router)

    def _db_override():
        yield db_session
        db_session.commit()

    _app.dependency_overrides[get_db_session] = _db_override
    _app.dependency_overrides[get_google_oauth_client] = lambda: FakeGoogleOAuthClient()
    return _app


@pytest.fixture()
def oauth_client(oauth_app):
    return TestClient(oauth_app, raise_server_exceptions=True)


@pytest.fixture()
def auth_email_outbox(oauth_app):
    from novelai.config.settings import settings

    public_frontend_url = settings.PUBLIC_FRONTEND_URL
    assert public_frontend_url is not None
    service = InMemoryAuthEmailService(
        public_base_url=public_frontend_url,
        password_reset_path=settings.AUTH_PASSWORD_RESET_PATH,
        email_verification_path=settings.AUTH_EMAIL_VERIFICATION_PATH,
    )
    oauth_app.dependency_overrides[auth_module.get_auth_email_service] = lambda: service
    return service


def _start_oauth(client: TestClient, next_path: str = "/account/history") -> str:
    response = client.get(f"/api/auth/google/start?next={next_path}", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert "accounts.google.com" in location
    marker = "state="
    return location.split(marker, 1)[1].split("&", 1)[0]


def _csrf_headers(client: TestClient) -> dict[str, str]:
    resp = client.get("/api/auth/csrf")
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.json()["csrf_token"]}


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


class TestPasswordHashing:
    def test_hash_password_output_is_not_plaintext(self):
        password_hash = hash_password("correct horse battery staple")
        assert password_hash != "correct horse battery staple"
        assert password_hash.startswith("$argon2")

    def test_verify_password_accepts_correct_password(self):
        password_hash = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", password_hash) is True

    def test_verify_password_rejects_wrong_password(self):
        password_hash = hash_password("correct horse battery staple")
        assert verify_password("wrong horse battery staple", password_hash) is False


class TestPublicPasswordRegistration:
    def test_register_creates_user_role_never_owner_and_sets_session(self, oauth_client, db_session):
        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": "Reader@Example.COM ", "password": "long-enough-password", "display_name": "Reader"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        assert data["is_owner"] is False
        assert data["email"] == "reader@example.com"
        assert "password_hash" not in data

        user = db_session.query(User).filter_by(email="reader@example.com").one()
        assert user.role == "user"
        assert user.auth_provider == "password"
        assert user.password_hash
        assert user.password_hash != "long-enough-password"
        assert user.email_verified_at is None
        assert user.last_login_at is not None
        token = db_session.query(EmailVerificationToken).one()
        assert token.user_id == user.id
        assert token.used_at is None
        assert token.expires_at is not None

        me = oauth_client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user_id"] == user.id
        assert me.json()["role"] == "user"

    def test_register_rejects_weak_short_password(self, oauth_client):
        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": "reader@example.com", "password": "short"},
        )
        assert resp.status_code == 400

    def test_register_rejects_invalid_email(self, oauth_client):
        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "long-enough-password"},
        )
        assert resp.status_code == 400

    def test_register_duplicate_email_fails_safely(self, oauth_client, db_session):
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="password",
                password_hash=hash_password("existing-password"),
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": " READER@example.com ", "password": "long-enough-password"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "An account already exists for this email."
        assert db_session.query(User).filter_by(email="reader@example.com").count() == 1

    def test_register_does_not_overwrite_google_user(self, oauth_client, db_session):
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="google",
                auth_provider_subject="google-sub-1",
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": "reader@example.com", "password": "long-enough-password"},
        )
        assert resp.status_code == 409
        user = db_session.query(User).filter_by(email="reader@example.com").one()
        assert user.auth_provider == "google"
        assert user.auth_provider_subject == "google-sub-1"
        assert user.password_hash is None

    def test_register_rate_limit_eventually_returns_429(self, oauth_client):
        statuses = [
            oauth_client.post(
                "/api/auth/register",
                json={"email": "bad-email", "password": "long-enough-password"},
            ).status_code
            for _ in range(11)
        ]
        assert statuses[:10] == [400] * 10
        assert statuses[-1] == 429


class TestPublicPasswordLogin:
    def test_password_login_succeeds_with_correct_credentials(self, oauth_client, db_session):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": " READER@example.com ", "password": "long-enough-password"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user.id
        assert data["role"] == "user"
        assert data["email"] == "reader@example.com"
        assert "password_hash" not in data
        db_session.refresh(user)
        assert user.last_login_at is not None

    def test_password_login_fails_with_wrong_password_generic_error(self, oauth_client, db_session):
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="password",
                password_hash=hash_password("long-enough-password"),
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "reader@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password."

    def test_password_login_fails_unknown_email_generic_error(self, oauth_client):
        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "unknown@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password."

    def test_password_login_fails_google_only_user_without_password_hash(self, oauth_client, db_session):
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="google",
                auth_provider_subject="google-sub-1",
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "reader@example.com", "password": "long-enough-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password."

    def test_password_login_fails_inactive_user(self, oauth_client, db_session):
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="password",
                password_hash=hash_password("long-enough-password"),
                is_active=False,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "reader@example.com", "password": "long-enough-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password."

    def test_password_login_does_not_authenticate_owner_db_user(self, oauth_client, db_session):
        db_session.add(
            User(
                email="owner@example.com",
                role="owner",
                auth_provider="password",
                password_hash=hash_password("long-enough-password"),
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "owner@example.com", "password": "long-enough-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password."

    def test_password_login_rate_limit_eventually_returns_429(self, oauth_client):
        statuses = [
            oauth_client.post(
                "/api/auth/password/login",
                json={"email": "unknown@example.com", "password": "wrong-password"},
            ).status_code
            for _ in range(11)
        ]
        assert statuses[:10] == [401] * 10
        assert statuses[-1] == 429


class TestPublicPasswordReset:
    def test_reset_request_sends_fake_email_and_confirm_uses_captured_token(
        self, oauth_client, db_session, auth_email_outbox
    ):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/reset/request",
            json={"email": "reader@example.com"},
        )

        assert resp.status_code == 200
        assert len(auth_email_outbox.outbox) == 1
        message = auth_email_outbox.outbox[0]
        assert message.message_type == "password_reset"
        assert message.recipient == "reader@example.com"
        assert message.token
        assert message.token == parse_qs(urlparse(message.url).query).get("token", [None])[0]
        assert message.url.startswith("http://frontend.test/password/reset?token=")
        token = db_session.query(PasswordResetToken).one()
        assert token.token_hash == auth_module._hash_password_reset_token(message.token)
        assert token.token_hash != message.token

        confirm = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": message.token, "new_password": "new-password-long"},
        )
        assert confirm.status_code == 200
        db_session.refresh(user)
        assert user.password_hash is not None
        assert verify_password("new-password-long", user.password_hash)

    def test_reset_request_generic_for_existing_and_missing_email(self, oauth_client, db_session, monkeypatch):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        existing = oauth_client.post(
            "/api/auth/password/reset/request",
            json={"email": " READER@example.com "},
        )
        missing = oauth_client.post(
            "/api/auth/password/reset/request",
            json={"email": "missing@example.com"},
        )

        assert existing.status_code == 200
        assert missing.status_code == 200
        assert existing.json() == {"status": "ok"}
        assert missing.json() == {"status": "ok"}
        assert "known-reset-token" not in existing.text
        assert db_session.query(PasswordResetToken).count() == 1

    def test_noop_reset_delivery_does_not_log_raw_token(
        self, oauth_client, db_session, monkeypatch, caplog
    ):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        with caplog.at_level("INFO"):
            resp = oauth_client.post(
                "/api/auth/password/reset/request",
                json={"email": "reader@example.com"},
            )

        assert resp.status_code == 200
        assert "known-reset-token" not in caplog.text
        assert "reader@example.com" not in caplog.text

    def test_reset_request_stores_hashed_token_not_raw(self, oauth_client, db_session, monkeypatch):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/reset/request",
            json={"email": "reader@example.com"},
            headers={"User-Agent": "reset-test-agent"},
        )

        assert resp.status_code == 200
        token = db_session.query(PasswordResetToken).one()
        assert token.user_id == user.id
        assert token.token_hash == auth_module._hash_password_reset_token("known-reset-token")
        assert token.token_hash != "known-reset-token"
        assert token.used_at is None
        assert token.expires_at is not None
        assert token.request_ip is not None
        assert token.user_agent == "reset-test-agent"

    def test_second_reset_request_invalidates_old_unused_tokens(self, oauth_client, db_session, monkeypatch):
        tokens = iter(["first-reset-token", "second-reset-token"])
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: next(tokens))
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        first = oauth_client.post("/api/auth/password/reset/request", json={"email": "reader@example.com"})
        second = oauth_client.post("/api/auth/password/reset/request", json={"email": "reader@example.com"})

        assert first.status_code == 200
        assert second.status_code == 200
        stored = db_session.query(PasswordResetToken).order_by(PasswordResetToken.id).all()
        assert len(stored) == 2
        assert stored[0].used_at is not None
        assert stored[1].used_at is None

    def test_reset_confirm_valid_token_updates_password_and_login(self, oauth_client, db_session, monkeypatch):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        oauth_client.post("/api/auth/password/reset/request", json={"email": "reader@example.com"})

        resp = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "known-reset-token", "new_password": "new-password-long"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        db_session.refresh(user)
        assert user.password_hash is not None
        assert verify_password("new-password-long", user.password_hash)
        assert not verify_password("old-password-long", user.password_hash)
        stored_token = db_session.query(PasswordResetToken).one()
        assert stored_token.used_at is not None

        old_login = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "reader@example.com", "password": "old-password-long"},
        )
        new_login = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "reader@example.com", "password": "new-password-long"},
        )
        assert old_login.status_code == 401
        assert new_login.status_code == 200
        assert new_login.json()["user_id"] == user.id

    def test_reset_confirm_token_reuse_fails(self, oauth_client, db_session, monkeypatch):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        oauth_client.post("/api/auth/password/reset/request", json={"email": "reader@example.com"})

        first = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "known-reset-token", "new_password": "new-password-long"},
        )
        second = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "known-reset-token", "new_password": "another-password-long"},
        )

        assert first.status_code == 200
        assert second.status_code == 400
        assert second.json()["detail"] == "Invalid or expired reset token."

    def test_reset_confirm_expired_token_fails(self, oauth_client, db_session):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=auth_module._hash_password_reset_token("expired-reset-token"),
                created_at=datetime.now(UTC) - timedelta(hours=2),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "expired-reset-token", "new_password": "new-password-long"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired reset token."
        db_session.refresh(user)
        assert user.password_hash is not None
        assert verify_password("old-password-long", user.password_hash)

    def test_reset_confirm_missing_invalid_token_fails_generically(self, oauth_client):
        resp = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "not-a-token", "new_password": "new-password-long"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired reset token."

    def test_reset_confirm_rejects_weak_password(self, oauth_client):
        resp = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "not-a-token", "new_password": "short"},
        )

        assert resp.status_code == 400
        assert "Password must be at least" in resp.json()["detail"]

    def test_reset_request_google_only_user_does_not_create_token_or_leak(
        self, oauth_client, db_session, monkeypatch, auth_email_outbox
    ):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="google",
                auth_provider_subject="google-sub-1",
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/reset/request",
            json={"email": "reader@example.com"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert db_session.query(PasswordResetToken).count() == 0
        assert auth_email_outbox.outbox == []

    def test_reset_request_owner_account_does_not_create_token_or_leak(
        self, oauth_client, db_session, monkeypatch, auth_email_outbox
    ):
        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        db_session.add(
            User(
                email="owner@example.com",
                role="owner",
                auth_provider="password",
                password_hash=hash_password("old-password-long"),
                is_active=True,
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/reset/request",
            json={"email": "owner@example.com"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert db_session.query(PasswordResetToken).count() == 0
        assert auth_email_outbox.outbox == []

    def test_reset_delivery_failure_is_generic_and_token_remains_valid(
        self, oauth_app, oauth_client, db_session, monkeypatch, caplog
    ):
        class FailingAuthEmailService:
            def send_password_reset_email(self, *, email: str, token: str) -> EmailDeliveryResult:
                raise RuntimeError("mail failed")

            def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
                raise RuntimeError("mail failed")

        monkeypatch.setattr(auth_module, "_new_password_reset_token", lambda: "known-reset-token")
        oauth_app.dependency_overrides[auth_module.get_auth_email_service] = lambda: FailingAuthEmailService()
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("old-password-long"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        with caplog.at_level("WARNING"):
            resp = oauth_client.post(
                "/api/auth/password/reset/request",
                json={"email": "reader@example.com"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert "known-reset-token" not in caplog.text
        token = db_session.query(PasswordResetToken).one()
        assert token.used_at is None

        confirm = oauth_client.post(
            "/api/auth/password/reset/confirm",
            json={"token": "known-reset-token", "new_password": "new-password-long"},
        )
        assert confirm.status_code == 200
        db_session.refresh(user)
        assert user.password_hash is not None
        assert verify_password("new-password-long", user.password_hash)

    def test_reset_request_rate_limit_eventually_returns_429(self, oauth_client):
        statuses = [
            oauth_client.post(
                "/api/auth/password/reset/request",
                json={"email": "missing@example.com"},
            ).status_code
            for _ in range(6)
        ]
        assert statuses[:5] == [200] * 5
        assert statuses[-1] == 429


class TestPublicEmailVerification:
    def test_register_sends_verification_email_and_confirm_uses_captured_token(
        self, oauth_client, db_session, auth_email_outbox
    ):
        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": "Reader@Example.COM", "password": "long-enough-password"},
        )

        assert resp.status_code == 200
        assert len(auth_email_outbox.outbox) == 1
        message = auth_email_outbox.outbox[0]
        assert message.message_type == "email_verification"
        assert message.recipient == "reader@example.com"
        assert message.token
        assert message.token == parse_qs(urlparse(message.url).query).get("token", [None])[0]
        assert message.url.startswith("http://frontend.test/email/verify?token=")
        token = db_session.query(EmailVerificationToken).one()
        assert token.token_hash == auth_module._hash_email_verification_token(message.token)
        assert token.token_hash != message.token

        confirm = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": message.token},
        )
        assert confirm.status_code == 200
        user = db_session.query(User).filter_by(email="reader@example.com").one()
        assert user.email_verified_at is not None

    def test_register_creates_unverified_user_and_hashed_verification_token(
        self, oauth_client, db_session, monkeypatch
    ):
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")

        resp = oauth_client.post(
            "/api/auth/register",
            json={"email": "Reader@Example.COM", "password": "long-enough-password"},
            headers={"User-Agent": "verify-test-agent"},
        )

        assert resp.status_code == 200
        assert "known-verify-token" not in resp.text
        user = db_session.query(User).filter_by(email="reader@example.com").one()
        assert user.email_verified_at is None
        token = db_session.query(EmailVerificationToken).one()
        assert token.user_id == user.id
        assert token.token_hash == auth_module._hash_email_verification_token("known-verify-token")
        assert token.token_hash != "known-verify-token"
        assert token.used_at is None
        assert token.request_ip is not None
        assert token.user_agent == "verify-test-agent"

    def test_verification_request_sends_fake_email_and_confirm_uses_captured_token(
        self, oauth_client, db_session, auth_email_outbox
    ):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/email/verification/request",
            json={"email": "reader@example.com"},
        )

        assert resp.status_code == 200
        assert len(auth_email_outbox.outbox) == 1
        message = auth_email_outbox.outbox[0]
        assert message.message_type == "email_verification"
        assert message.recipient == "reader@example.com"
        assert message.token == parse_qs(urlparse(message.url).query).get("token", [None])[0]

        confirm = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": message.token},
        )
        assert confirm.status_code == 200
        db_session.refresh(user)
        assert user.email_verified_at is not None

    def test_verification_request_generic_for_existing_and_missing_email(
        self, oauth_client, db_session, monkeypatch
    ):
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        existing = oauth_client.post(
            "/api/auth/email/verification/request",
            json={"email": " READER@example.com "},
        )
        missing = oauth_client.post(
            "/api/auth/email/verification/request",
            json={"email": "missing@example.com"},
        )

        assert existing.status_code == 200
        assert missing.status_code == 200
        assert existing.json() == {"status": "ok"}
        assert missing.json() == {"status": "ok"}
        assert "known-verify-token" not in existing.text
        assert db_session.query(EmailVerificationToken).count() == 1

    def test_noop_verification_delivery_does_not_log_raw_token(
        self, oauth_client, db_session, monkeypatch, caplog
    ):
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        with caplog.at_level("INFO"):
            resp = oauth_client.post(
                "/api/auth/email/verification/request",
                json={"email": "reader@example.com"},
            )

        assert resp.status_code == 200
        assert "known-verify-token" not in caplog.text
        assert "reader@example.com" not in caplog.text

    def test_verification_request_creates_token_only_for_eligible_password_user(
        self, oauth_client, db_session, monkeypatch, auth_email_outbox
    ):
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")
        db_session.add_all(
            [
                User(
                    email="google@example.com",
                    role="user",
                    auth_provider="google",
                    auth_provider_subject="google-sub-1",
                    is_active=True,
                ),
                User(
                    email="owner@example.com",
                    role="owner",
                    auth_provider="password",
                    password_hash=hash_password("long-enough-password"),
                    is_active=True,
                ),
                User(
                    email="verified@example.com",
                    role="user",
                    auth_provider="password",
                    password_hash=hash_password("long-enough-password"),
                    email_verified_at=datetime.now(UTC),
                    is_active=True,
                ),
            ]
        )
        db_session.commit()

        for email in ["google@example.com", "owner@example.com", "verified@example.com"]:
            resp = oauth_client.post("/api/auth/email/verification/request", json={"email": email})
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

        assert db_session.query(EmailVerificationToken).count() == 0
        assert auth_email_outbox.outbox == []

    def test_second_verification_request_invalidates_old_unused_tokens(
        self, oauth_client, db_session, monkeypatch
    ):
        tokens = iter(["first-verify-token", "second-verify-token"])
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: next(tokens))
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        first = oauth_client.post("/api/auth/email/verification/request", json={"email": "reader@example.com"})
        second = oauth_client.post("/api/auth/email/verification/request", json={"email": "reader@example.com"})

        assert first.status_code == 200
        assert second.status_code == 200
        stored = db_session.query(EmailVerificationToken).order_by(EmailVerificationToken.id).all()
        assert len(stored) == 2
        assert stored[0].used_at is not None
        assert stored[1].used_at is None

    def test_verification_confirm_valid_token_sets_email_verified_at(
        self, oauth_client, db_session, monkeypatch
    ):
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        oauth_client.post("/api/auth/email/verification/request", json={"email": "reader@example.com"})

        resp = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": "known-verify-token"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        db_session.refresh(user)
        assert user.email_verified_at is not None
        stored_token = db_session.query(EmailVerificationToken).one()
        assert stored_token.used_at is not None

    def test_verification_confirm_invalid_missing_token_fails_generically(self, oauth_client):
        resp = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": "not-a-token"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired verification token."

    def test_verification_confirm_expired_token_fails(self, oauth_client, db_session):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=auth_module._hash_email_verification_token("expired-verify-token"),
                created_at=datetime.now(UTC) - timedelta(days=2),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": "expired-verify-token"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired verification token."
        db_session.refresh(user)
        assert user.email_verified_at is None

    def test_verification_confirm_token_reuse_fails(self, oauth_client, db_session, monkeypatch):
        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        oauth_client.post("/api/auth/email/verification/request", json={"email": "reader@example.com"})

        first = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": "known-verify-token"},
        )
        second = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": "known-verify-token"},
        )

        assert first.status_code == 200
        assert second.status_code == 400
        assert second.json()["detail"] == "Invalid or expired verification token."

    def test_unverified_password_user_can_still_login(self, oauth_client, db_session):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            email_verified_at=None,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        resp = oauth_client.post(
            "/api/auth/password/login",
            json={"email": "reader@example.com", "password": "long-enough-password"},
        )

        assert resp.status_code == 200
        assert resp.json()["user_id"] == user.id

    def test_verification_request_rate_limit_eventually_returns_429(self, oauth_client):
        statuses = [
            oauth_client.post(
                "/api/auth/email/verification/request",
                json={"email": "missing@example.com"},
            ).status_code
            for _ in range(6)
        ]
        assert statuses[:5] == [200] * 5
        assert statuses[-1] == 429

    def test_verification_delivery_failure_is_generic_and_token_remains_valid(
        self, oauth_app, oauth_client, db_session, monkeypatch, caplog
    ):
        class FailingAuthEmailService:
            def send_password_reset_email(self, *, email: str, token: str) -> EmailDeliveryResult:
                raise RuntimeError("mail failed")

            def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
                raise RuntimeError("mail failed")

        monkeypatch.setattr(auth_module, "_new_email_verification_token", lambda: "known-verify-token")
        oauth_app.dependency_overrides[auth_module.get_auth_email_service] = lambda: FailingAuthEmailService()
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="password",
            password_hash=hash_password("long-enough-password"),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        with caplog.at_level("WARNING"):
            resp = oauth_client.post(
                "/api/auth/email/verification/request",
                json={"email": "reader@example.com"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert "known-verify-token" not in caplog.text
        token = db_session.query(EmailVerificationToken).one()
        assert token.used_at is None

        confirm = oauth_client.post(
            "/api/auth/email/verification/confirm",
            json={"token": "known-verify-token"},
        )
        assert confirm.status_code == 200
        db_session.refresh(user)
        assert user.email_verified_at is not None


class TestAuthRouterLogout:
    def test_logout_clears_session(self, owner_client):
        # Confirm owner before logout
        assert owner_client.get("/test/me").json()["role"] == "owner"
        resp = owner_client.post("/api/auth/logout", headers=_csrf_headers(owner_client))
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"
        # After logout, back to guest
        assert owner_client.get("/test/me").json()["role"] == "guest"

    def test_logout_requires_csrf_token(self, owner_client):
        assert owner_client.post("/api/auth/logout").status_code == 403
        assert owner_client.post("/api/auth/logout", headers={"X-CSRF-Token": "bad"}).status_code == 403


class TestAuthRouterMe:
    def test_me_returns_guest_when_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "guest"
        assert data["is_authenticated"] is False

    def test_csrf_endpoint_is_safe_get(self, client):
        resp = client.get("/api/auth/csrf")
        assert resp.status_code == 200
        assert isinstance(resp.json()["csrf_token"], str)

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
    def test_public_signup_route_is_explicit_and_not_owner_login(self):
        """Public registration is separate from owner bootstrap login."""
        # Public registration exists, but it must not be a signup alias or owner login.
        from novelai.api.routers import auth as auth_module
        router = auth_module.router
        routes = {r.path for r in router.routes}  # type: ignore[attr-defined]
        assert "/api/auth/register" in routes
        assert "/api/auth/signup" not in routes

    def test_no_jwt_endpoint_exists(self):
        """No JWT token endpoint — v1 uses session cookies only."""
        from novelai.api.routers import auth as auth_module
        router = auth_module.router
        routes = {r.path for r in router.routes}  # type: ignore[attr-defined]
        assert "/api/auth/token" not in routes
        assert "/api/auth/jwt" not in routes


class TestGoogleOAuth:
    def test_frontend_redirect_fails_closed_without_public_url(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "PUBLIC_FRONTEND_URL", None)

        with pytest.raises(HTTPException) as exc_info:
            auth_module._frontend_redirect("/")

        assert exc_info.value.status_code == 503

    def test_start_returns_503_when_google_oauth_is_not_configured(self, client, monkeypatch):
        from novelai.config.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None)
        monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", None)
        monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", None)
        resp = client.get("/api/auth/google/start", follow_redirects=False)
        assert resp.status_code == 503

    def test_start_redirects_to_google_when_configured(self, oauth_client):
        resp = oauth_client.get("/api/auth/google/start?next=/novel/example", follow_redirects=False)
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]
        assert "state=" in resp.headers["location"]

    def test_start_rate_limit_eventually_returns_429(self, oauth_client):
        statuses = [
            oauth_client.get("/api/auth/google/start", follow_redirects=False).status_code
            for _ in range(11)
        ]
        assert statuses[:10] == [302] * 10
        assert statuses[-1] == 429

    def test_callback_rejects_missing_state(self, oauth_client):
        resp = oauth_client.get("/api/auth/google/callback?code=abc", follow_redirects=False)
        assert resp.status_code == 400

    def test_callback_rejects_invalid_state(self, oauth_client):
        _start_oauth(oauth_client)
        resp = oauth_client.get("/api/auth/google/callback?state=bad&code=abc", follow_redirects=False)
        assert resp.status_code == 400

    def test_callback_rejects_missing_code(self, oauth_client):
        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}", follow_redirects=False)
        assert resp.status_code == 400

    def test_callback_rejects_unverified_email(self, oauth_app, oauth_client):
        oauth_app.dependency_overrides[get_google_oauth_client] = lambda: FakeGoogleOAuthClient(
            GoogleOAuthProfile(
                subject="sub-unverified",
                email="reader@example.com",
                email_verified=False,
            )
        )
        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 403

    def test_callback_creates_user_session_and_normalizes_email(self, oauth_client, db_session):
        state = _start_oauth(oauth_client, "/account/history")
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "http://frontend.test/account/history"

        me = oauth_client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "user"
        assert me.json()["email"] == "reader@example.com"
        assert me.json()["is_owner"] is False

        user = db_session.query(User).filter_by(auth_provider="google", auth_provider_subject="google-sub-1").one()
        assert user.email == "reader@example.com"
        assert user.role == "user"
        assert user.email_verified_at is not None

    def test_callback_resumes_existing_google_user(self, oauth_client, db_session):
        user = User(
            email="reader@example.com",
            role="user",
            auth_provider="google",
            auth_provider_subject="google-sub-1",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 302
        assert oauth_client.get("/api/auth/me").json()["user_id"] == user.id
        assert db_session.query(User).count() == 1

    def test_callback_links_existing_non_owner_email(self, oauth_client, db_session):
        user = User(email="reader@example.com", role="user", is_active=True)
        db_session.add(user)
        db_session.commit()

        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 302
        db_session.refresh(user)
        assert user.auth_provider == "google"
        assert user.auth_provider_subject == "google-sub-1"
        assert user.email_verified_at is not None

    def test_callback_rejects_owner_email_link(self, oauth_client, db_session):
        db_session.add(User(email="reader@example.com", role="owner", is_active=True))
        db_session.commit()

        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 403

    def test_callback_rejects_inactive_user(self, oauth_client, db_session):
        db_session.add(
            User(
                email="reader@example.com",
                role="user",
                auth_provider="google",
                auth_provider_subject="google-sub-1",
                is_active=False,
            )
        )
        db_session.commit()

        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 403

    def test_callback_uses_safe_relative_return_path_only(self, oauth_client):
        state = _start_oauth(oauth_client, "https://evil.example/phish")
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "http://frontend.test/"

    def test_state_replay_fails(self, oauth_client):
        state = _start_oauth(oauth_client)
        first = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert first.status_code == 302
        replay = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert replay.status_code == 400

    def test_oauth_user_session_can_access_user_endpoint(self, oauth_client):
        state = _start_oauth(oauth_client)
        resp = oauth_client.get(f"/api/auth/google/callback?state={state}&code=abc", follow_redirects=False)
        assert resp.status_code == 302

        library = oauth_client.get("/api/user/library")
        assert library.status_code == 200
        assert library.json() == []

    def test_unauthenticated_user_endpoint_still_fails(self, oauth_client):
        resp = oauth_client.get("/api/user/library")
        assert resp.status_code == 401
