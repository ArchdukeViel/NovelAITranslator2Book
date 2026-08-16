"""Tests for admin user management endpoints (DEBT-008) and session enforcement."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.admin_users import router as users_router
from novelai.api.routers.dependencies import get_db_session
from novelai.db.base import Base
from novelai.db.models.system import AuditLog
from novelai.db.models.users import User
from novelai.services.auth_service import AuthService

# ── fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_fk_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    yield TestSession
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client_owner(db_session: sessionmaker) -> Iterator[TestClient]:
    """Test client with owner authentication."""
    yield from _build_client(db_session, override_user=SessionUser(user_id=1, email="owner@test", role="owner"))


@pytest.fixture
def client_non_owner(db_session: sessionmaker) -> Iterator[TestClient]:
    """Test client with non-owner (user) authentication."""
    yield from _build_client(db_session, override_user=SessionUser(user_id=2, email="user@test", role="user"))


@pytest.fixture
def client_unauth(db_session: sessionmaker) -> Iterator[TestClient]:
    """Test client with NO authentication (guest)."""
    yield from _build_client(db_session, override_user=SessionUser(user_id=None, email=None, role="guest"))


def _build_client(db_session: sessionmaker, override_user: SessionUser) -> Iterator[TestClient]:
    """Build test app with given user override and DB session."""

    def _override_db():
        session = db_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = FastAPI()
    app.include_router(users_router)
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = lambda: override_user
    # Bypass CSRF — the dedicated CSRF suite covers its own behavior.
    app.dependency_overrides[require_csrf_for_unsafe_methods] = lambda: None

    with TestClient(app) as client:
        yield client


def _seed(db_session: sessionmaker) -> None:
    """Seed test users."""
    session = db_session()
    session.add(User(id=1, email="owner@test", role="owner", is_active=True, display_name="Owner"))
    session.add(User(id=2, email="alice@example.com", role="user", is_active=True, display_name="Alice"))
    session.add(User(id=3, email="bob@example.com", role="user", is_active=False, display_name="Bob"))
    session.add(User(id=4, email="carol@example.com", role="guest", is_active=True, display_name="Carol"))
    session.add(User(id=5, email="dave@example.com", role="user", is_active=True, display_name="Dave"))
    session.commit()
    session.close()


def _count_audit_logs(db_session: sessionmaker, action: str | None = None) -> int:
    session = db_session()
    try:
        q = session.query(AuditLog)
        if action:
            q = q.filter(AuditLog.action == action)
        return q.count()
    finally:
        session.close()


def _get_user(db_session: sessionmaker, user_id: int) -> User | None:
    session = db_session()
    try:
        return session.get(User, user_id)
    finally:
        session.close()


# ── auth guards ─────────────────────────────────────────────────────────────────


class TestAuthGuards:
    def test_unauth_gets_401_on_list(self, client_unauth):
        assert client_unauth.get("/api/admin/users").status_code == 401

    def test_unauth_gets_401_on_detail(self, client_unauth):
        assert client_unauth.get("/api/admin/users/1").status_code == 401

    def test_unauth_gets_401_on_disable(self, client_unauth):
        assert (
            client_unauth.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "test"}).status_code
            == 401
        )

    def test_unauth_gets_401_on_role(self, client_unauth):
        assert (
            client_unauth.patch("/api/admin/users/2/role", json={"role": "guest", "reason": "test"}).status_code == 401
        )

    def test_unauth_gets_401_on_revoke(self, client_unauth):
        assert client_unauth.post("/api/admin/users/2/revoke-sessions", json={"reason": "test"}).status_code == 401

    def test_non_owner_gets_403_on_list(self, client_non_owner):
        assert client_non_owner.get("/api/admin/users").status_code == 403

    def test_non_owner_gets_403_on_detail(self, client_non_owner):
        assert client_non_owner.get("/api/admin/users/1").status_code == 403

    def test_non_owner_gets_403_on_disable(self, client_non_owner):
        assert (
            client_non_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "test"}).status_code
            == 403
        )

    def test_non_owner_gets_403_on_role(self, client_non_owner):
        assert (
            client_non_owner.patch("/api/admin/users/2/role", json={"role": "guest", "reason": "test"}).status_code
            == 403
        )

    def test_non_owner_gets_403_on_revoke(self, client_non_owner):
        assert client_non_owner.post("/api/admin/users/2/revoke-sessions", json={"reason": "test"}).status_code == 403


# ── list / detail ───────────────────────────────────────────────────────────────


class TestListUsers:
    def test_list_paginates(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 5
        assert len(body["items"]) == 5
        assert body["page"] == 1
        assert body["page_size"] == 50

    def test_list_page_size(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?page=1&page_size=2")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page_size"] == 2

    def test_list_page_two(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?page=2&page_size=2")
        body = response.json()
        assert len(body["items"]) == 2
        assert body["page"] == 2

    def test_list_filter_by_role_user(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?role=user")
        body = response.json()
        assert body["total"] == 3  # Alice (active), Bob (inactive), Dave
        emails = {item["email"] for item in body["items"]}
        assert emails == {"alice@example.com", "bob@example.com", "dave@example.com"}

    def test_list_filter_by_role_guest(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?role=guest")
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "carol@example.com"

    def test_list_filter_by_is_active_false(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?is_active=false")
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "bob@example.com"

    def test_list_filter_by_is_active_true(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?is_active=true")
        body = response.json()
        assert body["total"] == 4

    def test_list_search_by_email(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?search=ali")
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "alice@example.com"

    def test_list_search_by_display_name(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?search=Dave")
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "dave@example.com"

    def test_list_search_no_match(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users?search=zzzzz")
        body = response.json()
        assert body["total"] == 0
        assert len(body["items"]) == 0

    def test_list_safe_fields(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users")
        item = response.json()["items"][0]
        # Must NOT expose sensitive fields
        assert "password_hash" not in item
        assert "disabled_at" not in item  # safe list omits admin fields
        assert "session_revoked_at" not in item
        # Has expected safe fields
        assert "id" in item
        assert "email" in item
        assert "display_name" in item
        assert "role" in item
        assert "is_active" in item
        assert "has_password" in item


class TestGetUserDetail:
    def test_detail_includes_disabled_fields(self, client_owner, db_session):
        _seed(db_session)
        # Disable Alice first
        client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "spam"})

        response = client_owner.get("/api/admin/users/2")
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "alice@example.com"
        assert body["is_active"] is False
        assert body["disabled_at"] is not None
        assert body["disabled_reason"] == "spam"
        assert body["disabled_by_user_id"] == 1
        assert body["session_revoked_at"] is not None
        # Also has safe fields
        assert "has_password" in body

    def test_detail_user_not_found(self, client_owner):
        response = client_owner.get("/api/admin/users/9999")
        assert response.status_code == 404

    def test_detail_shows_active_user_no_disabled(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.get("/api/admin/users/2")
        body = response.json()
        assert body["is_active"] is True
        assert body["disabled_at"] is None
        assert body["disabled_reason"] is None
        assert body["session_revoked_at"] is None


# ── disable / enable ────────────────────────────────────────────────────────────


class TestDisableUser:
    def test_disable_user(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch(
            "/api/admin/users/2/active", json={"is_active": False, "reason": "Abusive behavior"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is False

        # Verify DB state
        u = _get_user(db_session, 2)
        assert u is not None
        assert u.is_active is False
        assert u.disabled_at is not None
        assert u.disabled_reason == "Abusive behavior"
        assert u.disabled_by_user_id == 1
        assert u.session_revoked_at is not None

    def test_disable_owner_returns_409(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/1/active", json={"is_active": False, "reason": "test"})
        assert response.status_code == 409
        assert "owner" in response.json()["detail"].lower()

    def test_disable_self_returns_409(self, client_owner, db_session):
        _seed(db_session)
        # The owner can't disable themselves (id=1=actor, user_id=1)
        response = client_owner.patch("/api/admin/users/1/active", json={"is_active": False, "reason": "test"})
        assert response.status_code == 409

    def test_disable_nonexistent_user(self, client_owner):
        response = client_owner.patch("/api/admin/users/9999/active", json={"is_active": False, "reason": "test"})
        assert response.status_code == 404

    def test_disable_missing_reason(self, client_owner):
        response = client_owner.patch("/api/admin/users/2/active", json={"is_active": False})
        assert response.status_code == 422  # Pydantic validation

    def test_disable_empty_reason(self, client_owner):
        response = client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": ""})
        assert response.status_code == 422  # Pydantic min_length

    def test_disable_reason_too_long(self, client_owner):
        response = client_owner.patch(
            "/api/admin/users/2/active",
            json={"is_active": False, "reason": "x" * 501},
        )
        assert response.status_code == 422  # Pydantic max_length


class TestEnableUser:
    def test_enable_user(self, client_owner, db_session):
        _seed(db_session)
        # Disable first
        client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "spam"})
        # Enable
        response = client_owner.patch(
            "/api/admin/users/2/active", json={"is_active": True, "reason": "appeal approved"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is True

        # Verify DB state
        u = _get_user(db_session, 2)
        assert u is not None
        assert u.is_active is True
        assert u.disabled_at is None
        assert u.disabled_reason is None
        assert u.disabled_by_user_id is None
        # session_revoked_at stays from the disable (only cleared on login)
        # Enable does NOT clear session_revoked_at
        assert u.session_revoked_at is not None

    def test_enable_owner_returns_409(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/1/active", json={"is_active": True, "reason": "test"})
        assert response.status_code == 409

    def test_enable_nonexistent_user(self, client_owner):
        response = client_owner.patch("/api/admin/users/9999/active", json={"is_active": True, "reason": "test"})
        assert response.status_code == 404

    def test_enable_requires_reason(self, client_owner):
        response = client_owner.patch("/api/admin/users/2/active", json={"is_active": True})
        assert response.status_code == 422


# ── role changes ────────────────────────────────────────────────────────────────


class TestRoleChanges:
    def test_change_user_to_guest(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/2/role", json={"role": "guest", "reason": "downgrade"})
        assert response.status_code == 200
        assert response.json()["role"] == "guest"

        u = _get_user(db_session, 2)
        assert u is not None
        assert u.role == "guest"
        assert u.session_revoked_at is not None  # role change revokes sessions

    def test_change_guest_to_user(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/4/role", json={"role": "user", "reason": "upgrade"})
        assert response.status_code == 200
        assert response.json()["role"] == "user"

    def test_change_role_owner_returns_409(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/1/role", json={"role": "user", "reason": "test"})
        assert response.status_code == 409

    def test_change_role_to_owner_returns_400(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/2/role", json={"role": "owner", "reason": "test"})
        assert response.status_code == 400

    def test_change_role_invalid_role(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/2/role", json={"role": "admin", "reason": "test"})
        assert response.status_code == 400

    def test_change_role_nonexistent_user(self, client_owner):
        response = client_owner.patch("/api/admin/users/9999/role", json={"role": "guest", "reason": "test"})
        assert response.status_code == 404

    def test_change_role_requires_reason(self, client_owner):
        response = client_owner.patch("/api/admin/users/2/role", json={"role": "guest"})
        assert response.status_code == 422

    def test_change_role_reason_too_long(self, client_owner):
        response = client_owner.patch(
            "/api/admin/users/2/role",
            json={"role": "guest", "reason": "x" * 501},
        )
        assert response.status_code == 422


# ── session revocation ─────────────────────────────────────────────────────────


class TestRevokeSessions:
    def test_revoke_sessions(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.post("/api/admin/users/2/revoke-sessions", json={"reason": "security concern"})
        assert response.status_code == 200
        body = response.json()
        assert body["session_revoked_at"] is not None

        u = _get_user(db_session, 2)
        assert u is not None
        assert u.session_revoked_at is not None

    def test_revoke_owner_returns_409(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.post("/api/admin/users/1/revoke-sessions", json={"reason": "test"})
        assert response.status_code == 409

    def test_revoke_nonexistent_user(self, client_owner):
        response = client_owner.post("/api/admin/users/9999/revoke-sessions", json={"reason": "test"})
        assert response.status_code == 404

    def test_revoke_requires_reason(self, client_owner):
        response = client_owner.post("/api/admin/users/2/revoke-sessions", json={})
        assert response.status_code == 422


# ── audit entries ───────────────────────────────────────────────────────────────


class TestAuditEntries:
    def test_disable_creates_audit_log(self, client_owner, db_session):
        _seed(db_session)
        count_before = _count_audit_logs(db_session, "user.disabled")
        client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "spam"})
        count_after = _count_audit_logs(db_session, "user.disabled")
        assert count_after == count_before + 1

    def test_enable_creates_audit_log(self, client_owner, db_session):
        _seed(db_session)
        client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "spam"})
        count_before = _count_audit_logs(db_session, "user.enabled")
        client_owner.patch("/api/admin/users/2/active", json={"is_active": True, "reason": "appeal"})
        count_after = _count_audit_logs(db_session, "user.enabled")
        assert count_after == count_before + 1

    def test_role_change_creates_audit_log(self, client_owner, db_session):
        _seed(db_session)
        count_before = _count_audit_logs(db_session, "user.role_changed")
        client_owner.patch("/api/admin/users/2/role", json={"role": "guest", "reason": "downgrade"})
        count_after = _count_audit_logs(db_session, "user.role_changed")
        assert count_after == count_before + 1

    def test_revoke_sessions_creates_audit_log(self, client_owner, db_session):
        _seed(db_session)
        count_before = _count_audit_logs(db_session, "user.sessions_revoked")
        client_owner.post("/api/admin/users/2/revoke-sessions", json={"reason": "security"})
        count_after = _count_audit_logs(db_session, "user.sessions_revoked")
        assert count_after == count_before + 1

    def test_audit_has_before_and_after(self, client_owner, db_session):
        _seed(db_session)
        client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "spam"})

        s = db_session()
        try:
            log = s.query(AuditLog).filter(AuditLog.action == "user.disabled").order_by(AuditLog.id.desc()).first()
            assert log is not None
            assert log.actor_user_id == 1
            assert log.target_type == "user"
            assert log.target_id == "2"
            import json

            meta = json.loads(log.metadata_json or "{}")
            assert "before" in meta
            assert "after" in meta
            assert meta["before"]["is_active"] is True
            assert meta["after"]["is_active"] is False
        finally:
            s.close()


# ── session enforcement (integration) ───────────────────────────────────────────


class TestSessionEnforcement:
    """Test that disabled/revoked accounts are rejected at the service and DB level.

    Full HTTP-level session enforcement is tested via the auth middleware integration
    suite. Here we verify the underlying service invariants.
    """

    def test_disabled_user_state(self, db_session: sessionmaker) -> None:
        s = db_session()
        try:
            s.add(User(id=1, email="owner@test", role="owner", is_active=True))
            s.add(User(id=2, email="alice@example.com", role="user", is_active=True))
            s.commit()

            svc = AuthService(db_session=s)
            svc.disable_user(2, reason="policy violation", by_user_id=1)
            s.commit()

            u = s.get(User, 2)
            assert u is not None
            assert u.is_active is False
            assert u.disabled_at is not None
        finally:
            s.close()

    def test_revoked_session_state(self, db_session: sessionmaker) -> None:
        s = db_session()
        try:
            s.add(User(id=1, email="owner@test", role="owner", is_active=True))
            s.add(User(id=2, email="alice@example.com", role="user", is_active=True))
            s.commit()

            svc = AuthService(db_session=s)
            svc.revoke_sessions(2)
            s.commit()

            u = s.get(User, 2)
            assert u is not None
            assert u.session_revoked_at is not None
        finally:
            s.close()

    def test_enable_clears_disabled_fields(self, db_session: sessionmaker) -> None:
        s = db_session()
        try:
            s.add(User(id=1, email="owner@test", role="owner", is_active=True))
            s.add(User(id=2, email="alice@example.com", role="user", is_active=True))
            s.commit()

            svc = AuthService(db_session=s)
            svc.disable_user(2, reason="spam", by_user_id=1)
            s.commit()
            svc.enable_user(2)
            s.commit()

            u = s.get(User, 2)
            assert u is not None
            assert u.is_active is True
            assert u.disabled_at is None
            assert u.disabled_reason is None
            assert u.disabled_by_user_id is None
        finally:
            s.close()

    def test_owner_cannot_be_disabled(self, db_session: sessionmaker) -> None:
        s = db_session()
        try:
            s.add(User(id=1, email="owner@test", role="owner", is_active=True))
            s.commit()

            svc = AuthService(db_session=s)
            with pytest.raises(PermissionError, match="owner_account_protected"):
                svc.disable_user(1, reason="test", by_user_id=1)
        finally:
            s.close()

    def test_owner_sessions_cannot_be_revoked(self, db_session: sessionmaker) -> None:
        s = db_session()
        try:
            s.add(User(id=42, email="owner@test", role="owner", is_active=True))
            s.commit()

            svc = AuthService(db_session=s)
            with pytest.raises(PermissionError, match="owner_session_protected"):
                svc.revoke_sessions(42)
        finally:
            s.close()

    def test_self_disable_raises(self, db_session: sessionmaker) -> None:
        s = db_session()
        try:
            s.add(User(id=2, email="alice@example.com", role="user", is_active=True))
            s.commit()

            svc = AuthService(db_session=s)
            with pytest.raises(PermissionError, match="self_disable_protected"):
                svc.disable_user(2, reason="test", by_user_id=2)
        finally:
            s.close()


# ── reason validation edge cases ────────────────────────────────────────────────


class TestReasonValidation:
    def test_reason_exactly_one_char(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "x"})
        assert response.status_code == 200

    def test_reason_exactly_500_chars(self, client_owner, db_session):
        _seed(db_session)
        response = client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "x" * 500})
        assert response.status_code == 200

    def test_reason_whitespace_only(self, client_owner):
        response = client_owner.patch("/api/admin/users/2/active", json={"is_active": False, "reason": "   "})
        assert response.status_code == 400  # validate_reason rejects whitespace-only


class TestExistingBehaviorPreserved:
    """Verify that existing tests from the original file still pass."""

    def test_active_flag_updates_user(self, client_owner, db_session):
        _seed(db_session)
        # Bob is inactive, enable him
        response = client_owner.patch("/api/admin/users/3/active", json={"is_active": True, "reason": "reinstated"})
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_get_user_returns_404_for_missing(self, client_owner):
        response = client_owner.get("/api/admin/users/9999")
        assert response.status_code == 404
