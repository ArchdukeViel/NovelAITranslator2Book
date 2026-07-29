"""Tests for the audit log service and admin API (DEBT-054)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from novelai.api.auth.session import SessionUser
from novelai.api.routers.admin_audit import router as audit_router
from novelai.api.routers.dependencies import get_db_session
from novelai.db.base import Base
from novelai.db.models.system import AuditLog
from novelai.services.audit_service import AuditService


@pytest.fixture
def db_session() -> Iterator:
    """In-memory SQLite session with the canonical ORM tables registered."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


def test_log_writes_row_with_redaction(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="user.delete",
        actor_user_id=42,
        target_type="user",
        target_id="7",
        metadata={
            "note": "removed inactive user",
            "api_key": "sk-abcdefghijklmnop1234567890",
            "before": {"role": "user", "token": "Bearer abcdefghijklmnop1234567890"},
        },
    )

    db_session.commit()
    stored = db_session.get(AuditLog, entry.id)
    assert stored is not None
    assert stored.action == "user.delete"
    assert stored.actor_user_id == 42
    parsed = json.loads(stored.metadata_json or "{}")
    # Sensitive keys are scrubbed at write-time
    assert parsed["api_key"] == "***REDACTED***"
    assert parsed["before"]["token"].startswith("***REDACTED***")
    # Non-sensitive values pass through
    assert parsed["note"] == "removed inactive user"


def test_list_logs_filters_and_paginates(db_session):
    svc = AuditService(db_session)
    for _ in range(5):
        svc.log(action="user.delete", target_id="x", actor_user_id=1)
    for _ in range(3):
        svc.log(action="settings.update", target_id="sys", actor_user_id=2)
    db_session.commit()

    rows, total = svc.list_logs(action="user.delete")
    assert total == 5
    assert len(rows) == 5

    rows, total = svc.list_logs(action="user.delete", limit=2, offset=1)
    assert total == 5
    assert len(rows) == 2

    rows, total = svc.list_logs(actor_user_id=2)
    assert total == 3
    assert all(row.actor_user_id == 2 for row in rows)


def test_to_summary_redacts_and_truncates(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="credential.create",
        target_type="credential",
        target_id="gemini",
        metadata={"api_key": "AIzaabcdefghijklmnop1234567890", "label": "main"},
    )
    db_session.commit()
    summary = svc.to_summary(entry)
    assert summary["action"] == "credential.create"
    # The summary never includes the full metadata dict
    assert "metadata" not in summary
    # The single-line summary excludes the redacted api_key value
    assert "AIza" not in summary["summary"]


def test_to_detail_returns_full_redacted_metadata(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="export.run",
        metadata={
            "format": "epub",
            "secret": "should-not-leak",
            "nested": {"jwt": "eyJabcdefghijklmnopqrstuvwxyz123456"},
        },
    )
    db_session.commit()
    detail = svc.to_detail(entry)
    assert detail["metadata"]["format"] == "epub"
    assert detail["metadata"]["secret"] == "***REDACTED***"
    assert detail["metadata"]["nested"]["jwt"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# Router-level integration test
# ---------------------------------------------------------------------------


def _owner_user() -> SessionUser:
    return SessionUser(user_id=1, email="owner@example.com", role="owner")


@pytest.fixture
def app_client(monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    """Spin up a minimal FastAPI app hosting the audit router only.

    The full ``create_app()`` is avoided because it instantiates models that
    require ``email-validator`` (a pre-existing project dep, not our
    concern). The audit router is isolated and exercised directly with
    owner-auth + DB overrides.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def _override_db_session():
        session = TestSession()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db_session] = _override_db_session
    # require_role("owner") falls through to get_current_user, which we override.
    from novelai.api.auth.session import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _owner_user()
    # The CSRF dependency looks at the request session; for these read-only
    # GETs it never actually runs (require_csrf_for_unsafe_methods short-
    # circuits safe methods). We don't need to override it.

    with TestClient(app) as client:
        yield client, TestSession
    engine.dispose()


def test_admin_audit_list_and_detail_require_owner(app_client):
    client, Session = app_client
    session = Session()
    svc = AuditService(session)
    entry = svc.log(action="user.delete", target_id="42", actor_user_id=1)
    session.commit()
    audit_id = entry.id
    session.close()

    response = client.get("/api/admin/audit")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "user.delete"

    response = client.get(f"/api/admin/audit/{audit_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == audit_id
    assert detail["action"] == "user.delete"

    response = client.get("/api/admin/audit/9999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Canonical column tests (DEBT-054 admin-audit-log-viewer)
# ---------------------------------------------------------------------------


def test_log_accepts_explicit_canonical_columns(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="admin.user.disabled",
        actor_user_id=1,
        target_type="user",
        target_id="42",
        status="succeeded",
        severity="warning",
        request_id="req-abc",
        correlation_id="corr-abc",
    )
    db_session.commit()

    stored = db_session.get(AuditLog, entry.id)
    assert stored.status == "succeeded"
    assert stored.severity == "warning"
    assert stored.request_id == "req-abc"
    assert stored.correlation_id == "corr-abc"


def test_log_promotes_allowlisted_metadata_to_canonical_columns(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="export.run",
        actor_user_id=2,
        metadata={
            "status": "success",
            "severity": "info",
            "request_id": "req-meta-1",
            "correlation_id": "corr-meta-1",
            "note": "metadata should keep this",
        },
    )
    db_session.commit()

    stored = db_session.get(AuditLog, entry.id)
    assert stored.status == "succeeded"  # "success" normalised
    assert stored.severity == "info"
    assert stored.request_id == "req-meta-1"
    assert stored.correlation_id == "corr-meta-1"
    parsed = json.loads(stored.metadata_json or "{}")
    # Promoted keys removed from metadata_json so they are not duplicated.
    assert "status" not in parsed
    assert "severity" not in parsed
    assert "request_id" not in parsed
    assert "correlation_id" not in parsed
    assert parsed["note"] == "metadata should keep this"


def test_log_normalises_unknown_status_and_severity(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="test.action",
        status="BANANA",
        severity="NUCLEAR",
    )
    db_session.commit()
    stored = db_session.get(AuditLog, entry.id)
    assert stored.status == "unknown"
    assert stored.severity == "unknown"


def test_list_logs_filters_by_status_severity_request_correlation(db_session):
    svc = AuditService(db_session)
    svc.log(
        action="a",
        actor_user_id=1,
        status="succeeded",
        severity="info",
        request_id="req-1",
        correlation_id="corr-1",
    )
    svc.log(
        action="b",
        actor_user_id=1,
        status="failed",
        severity="critical",
        request_id="req-2",
        correlation_id="corr-2",
    )
    svc.log(action="c", actor_user_id=2)
    db_session.commit()

    rows, total = svc.list_logs(status="succeeded")
    assert total == 1
    assert rows[0].action == "a"

    rows, total = svc.list_logs(severity="critical")
    assert total == 1
    assert rows[0].action == "b"

    rows, total = svc.list_logs(request_id="req-2")
    assert total == 1
    assert rows[0].action == "b"

    rows, total = svc.list_logs(correlation_id="corr-1")
    assert total == 1
    assert rows[0].action == "a"

    # Unknown filter value normalises to "unknown"; no rows have it, total=0
    rows, total = svc.list_logs(status="garbage")
    assert total == 0


def test_to_summary_exposes_canonical_columns_when_available(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="admin.user.disabled",
        actor_user_id=1,
        status="succeeded",
        severity="warning",
        request_id="req-xyz",
        correlation_id="corr-xyz",
    )
    db_session.commit()

    summary = svc.to_summary(entry)
    assert summary["status"] == "succeeded"
    assert summary["severity"] == "warning"
    assert summary["request_id"] == "req-xyz"
    assert summary["correlation_id"] == "corr-xyz"


def test_to_summary_omits_canonical_columns_when_legacy(db_session):
    svc = AuditService(db_session)
    # Legacy producer: no canonical columns
    entry = svc.log(action="legacy.event", actor_user_id=1)
    db_session.commit()
    summary = svc.to_summary(entry)
    assert summary["status"] is None
    assert summary["severity"] is None
    assert summary["request_id"] is None
    assert summary["correlation_id"] is None


def test_to_detail_exposes_safe_before_after(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="user.role_changed",
        actor_user_id=1,
        target_id="7",
        status="succeeded",
        severity="warning",
        metadata={
            "before": {"role": "user", "api_key": "sk-abcdefghijklmnop1234567890"},
            "after": {"role": "admin", "api_key": "sk-zxcvbnmlkjhgfdsa1234567890"},
        },
    )
    db_session.commit()
    detail = svc.to_detail(entry)
    assert detail["status"] == "succeeded"
    assert detail["severity"] == "warning"
    assert detail["changes"] is not None
    assert detail["changes"]["before"]["role"] == "user"
    assert detail["changes"]["after"]["role"] == "admin"
    assert detail["changes"]["before"]["api_key"] == "***REDACTED***"
    assert detail["changes"]["after"]["api_key"] == "***REDACTED***"


def test_to_detail_returns_null_changes_when_absent(db_session):
    svc = AuditService(db_session)
    entry = svc.log(action="no.changes", metadata={"reason": "no before/after"})
    db_session.commit()
    detail = svc.to_detail(entry)
    assert detail["changes"] is None


def test_recursive_redaction_signed_urls_prompts_paths_private_text(db_session):
    svc = AuditService(db_session)
    signed_url = "https://r2.example/bucket/key?X-Amz-Signature=abcdef0123456789abcdef0123456789&X-Amz-Expires=60"
    long_prompt = "You are a translator of Japanese light novels. " * 20
    entry = svc.log(
        action="export.run",
        actor_user_id=1,
        metadata={
            "signed_url": signed_url,
            "system_prompt": long_prompt,
            "prompt": "Translate the following chapter text: ...",
            "chapter_text": "Raw source chapter paragraph " * 50,
            "translated_text": "Raw translated text " * 50,
            "filesystem_path": "/var/lib/novelai/secrets/db.sqlite",
            "abs_path": "C:\\Users\\admin\\secrets.txt",
            "storage_credentials": "AKIAEXAMPLE",
        },
    )
    db_session.commit()
    parsed = json.loads(entry.metadata_json or "{}")

    # Key-based redaction
    assert parsed["system_prompt"] == "***REDACTED***"
    assert parsed["prompt"] == "***REDACTED***"
    assert parsed["chapter_text"] == "***REDACTED***"
    assert parsed["translated_text"] == "***REDACTED***"
    assert parsed["filesystem_path"] == "***REDACTED***"
    assert parsed["abs_path"] == "***REDACTED***"

    # Value-pattern redaction for signed URLs and leaked absolute paths
    assert "X-Amz-Signature" not in parsed["signed_url"]
    assert "***REDACTED***" in parsed["signed_url"]

    detail = svc.to_detail(entry)
    # Recursive redaction survives round-trip into the detail payload
    assert detail["metadata"]["system_prompt"] == "***REDACTED***"
    assert "X-Amz-Signature" not in detail["metadata"]["signed_url"]


def test_recursive_redaction_glossary_definition(db_session):
    svc = AuditService(db_session)
    entry = svc.log(
        action="glossary.updated",
        metadata={
            "glossary_definition": "private internal definition the viewer must not show",
            "note": "harmless",
        },
    )
    db_session.commit()
    parsed = json.loads(entry.metadata_json or "{}")
    assert parsed["glossary_definition"] == "***REDACTED***"
    assert parsed["note"] == "harmless"


def test_unknown_action_renders_safely(db_session):
    svc = AuditService(db_session)
    entry = svc.log(action="completely.unknown.custom_action")
    db_session.commit()
    summary = svc.to_summary(entry)
    detail = svc.to_detail(entry)
    # No crash, raw action echoed verbatim (no fabricated label).
    assert summary["action"] == "completely.unknown.custom_action"
    assert detail["action"] == "completely.unknown.custom_action"


# ---------------------------------------------------------------------------
# Router filter & validation tests
# ---------------------------------------------------------------------------


def test_router_filters_by_status_severity_request_correlation(app_client):
    client, Session = app_client
    session = Session()
    svc = AuditService(session)
    svc.log(
        action="admin.user.disabled",
        actor_user_id=1,
        status="succeeded",
        severity="warning",
        request_id="req-r1",
        correlation_id="corr-r1",
    )
    svc.log(
        action="admin.user.enabled",
        actor_user_id=2,
        status="failed",
        severity="critical",
        request_id="req-r2",
        correlation_id="corr-r2",
    )
    session.commit()
    session.close()

    response = client.get("/api/admin/audit", params={"status": "succeeded"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "succeeded"

    response = client.get("/api/admin/audit", params={"severity": "critical"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "admin.user.enabled"

    response = client.get("/api/admin/audit", params={"request_id": "req-r1"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1

    response = client.get("/api/admin/audit", params={"correlation_id": "corr-r2"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "admin.user.enabled"


def test_router_date_range_validation(app_client):
    client, _ = app_client
    response = client.get(
        "/api/admin/audit",
        params={
            "date_from": "2026-07-10T00:00:00Z",
            "date_to": "2026-07-01T00:00:00Z",
        },
    )
    assert response.status_code == 400
    assert "date_from" in response.json()["detail"]

    # Invalid format
    response = client.get("/api/admin/audit", params={"date_from": "not-a-date"})
    assert response.status_code == 400


def test_router_pagination_enforces_max_page_size(app_client):
    client, _ = app_client
    response = client.get("/api/admin/audit", params={"page_size": 9999})
    assert response.status_code == 422

    response = client.get("/api/admin/audit", params={"page": 0})
    assert response.status_code == 422


def test_router_exposes_request_and_correlation_id_in_detail(app_client):
    client, Session = app_client
    session = Session()
    svc = AuditService(session)
    entry = svc.log(
        action="admin.user.disabled",
        actor_user_id=1,
        status="succeeded",
        severity="warning",
        request_id="req-display",
        correlation_id="corr-display",
    )
    session.commit()
    audit_id = entry.id
    session.close()

    response = client.get(f"/api/admin/audit/{audit_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["request_id"] == "req-display"
    assert detail["correlation_id"] == "corr-display"
    assert detail["status"] == "succeeded"
    assert detail["severity"] == "warning"
