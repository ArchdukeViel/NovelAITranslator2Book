"""Capacity and isolation checks for the bounded contributor credential pool."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.system import ProviderUsageLedger
from novelai.db.models.users import User
from novelai.services.gemini_request_control import (
    CompositeGeminiQuotaController,
    GeminiQuotaController,
    QuotaRejection,
)
from novelai.services.provider_credentials import ProviderCredentialService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _eligible_contributor(service: ProviderCredentialService, owner_user_id: int, key: str):
    credential, _submitted_key = service.replace_unvalidated(
        owner_user_id=owner_user_id,
        provider_key="gemini",
        api_key=key,
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )
    credential.status = "active"
    credential.is_active = True
    credential.validation_status = "valid"
    credential.contributor_pool_eligible = True
    return credential


def test_pool_selection_is_eligible_fair_and_shared_project_bounded(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "ENV", "test")
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("pool-capacity-encryption"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", SecretStr("owner-key-not-in-pool"))

    first_user = User(email="pool-first@example.test", role="user")
    second_user = User(email="pool-second@example.test", role="user")
    owner_user = User(email="pool-owner@example.test", role="owner")
    db_session.add_all([first_user, second_user, owner_user])
    db_session.commit()
    service = ProviderCredentialService(db_session)
    owner_credential, _owner_key = service.import_environment_credential(owner_user_id=owner_user.id)
    first = _eligible_contributor(service, first_user.id, "first-contributor-key")
    second = _eligible_contributor(service, second_user.id, "second-contributor-key")
    db_session.commit()

    @contextmanager
    def fake_session_scope():
        yield db_session

    monkeypatch.setattr("novelai.db.engine.session_scope", fake_session_scope)
    snapshot = service.contributor_pool_capacity_snapshot()
    leases = [
        ProviderCredentialService.acquire_runtime_lease(
            provider_key="gemini",
            provider_model="gemini-3.5-flash-lite",
            requesting_user_id=first_user.id,
        )
        for _ in range(3)
    ]

    assert owner_credential.owner_job_eligible is True
    assert owner_credential.contributor_pool_eligible is False
    assert snapshot["pool_size"] == 2
    assert snapshot["eligible_credential_count"] == 2
    assert snapshot["quota_domain_count"] == 1
    assert snapshot["verified_independent_quota_domain_count"] == 0
    assert snapshot["reader_http_rps_is_separate"] is True
    assert [lease.credential_id if lease is not None else None for lease in leases] == [
        str(first.id),
        str(second.id),
        str(first.id),
    ]
    assert all(lease is not None for lease in leases)
    assert all(isinstance(lease.quota_controller, CompositeGeminiQuotaController) for lease in leases if lease)
    assert "first-contributor-key" not in str(snapshot)
    assert "owner-key-not-in-pool" not in str(snapshot)


def test_composite_quota_reconciles_project_and_credential_reservations(tmp_path) -> None:
    project = GeminiQuotaController(
        tmp_path / "project",
        rpm_limit=10,
        tpm_limit=100,
        rpd_limit=10,
        concurrency_limit=1,
    )
    credential = GeminiQuotaController(
        tmp_path / "credential",
        rpm_limit=10,
        tpm_limit=100,
        rpd_limit=10,
        concurrency_limit=1,
    )
    controller = CompositeGeminiQuotaController((project, credential))

    reservation = controller.reserve(
        purpose="capacity-test",
        model="gemini-test",
        estimated_input_tokens=10,
        estimated_output_tokens=10,
    )
    assert not isinstance(reservation, QuotaRejection)
    blocked = controller.reserve(
        purpose="capacity-test",
        model="gemini-test",
        estimated_input_tokens=10,
        estimated_output_tokens=10,
    )
    assert isinstance(blocked, QuotaRejection)
    assert blocked.dimension == "concurrency"
    assert project.snapshot()["in_flight"] == 1
    assert credential.snapshot()["in_flight"] == 1

    controller.reconcile(
        reservation,
        input_tokens=8,
        output_tokens=6,
        total_tokens=14,
        success=False,
    )
    assert project.snapshot()["in_flight"] == 0
    assert credential.snapshot()["in_flight"] == 0


def test_composite_quota_expiry_releases_stale_reservation(tmp_path) -> None:
    now = datetime.now(UTC)
    clock_value = [now]

    def clock() -> datetime:
        return clock_value[0]

    project = GeminiQuotaController(
        tmp_path / "project",
        clock=clock,
        rpm_limit=10,
        tpm_limit=100,
        rpd_limit=10,
        concurrency_limit=1,
    )
    credential = GeminiQuotaController(
        tmp_path / "credential",
        clock=clock,
        rpm_limit=10,
        tpm_limit=100,
        rpd_limit=10,
        concurrency_limit=1,
    )
    controller = CompositeGeminiQuotaController((project, credential))
    reservation = controller.reserve(
        purpose="expiry-test",
        model="gemini-test",
        estimated_input_tokens=1,
        estimated_output_tokens=1,
    )
    assert not isinstance(reservation, QuotaRejection)

    clock_value[0] = now + timedelta(seconds=settings.PROVIDER_RESERVATION_TTL_SECONDS + 1)
    assert project.snapshot()["in_flight"] == 0
    assert credential.snapshot()["in_flight"] == 0


def test_usage_ledger_records_safe_attribution_without_key_material(db_session, monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    @contextmanager
    def fake_session_scope():
        yield db_session

    monkeypatch.setattr("novelai.db.engine.session_scope", fake_session_scope)
    ProviderCredentialService.record_usage(
        credential_id="credential-opaque",
        credential_owner_user_id=10,
        requesting_user_id=20,
        provider_key="gemini",
        provider_model="gemini-test",
        request_id="request-opaque",
        job_id="job-opaque",
        activity_id="activity-opaque",
        status="cancelled",
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        estimated_input_tokens=10,
        estimated_output_tokens=10,
        error_code="cancelled",
        contribution_mode="contributor",
    )
    row = db_session.query(ProviderUsageLedger).one()
    captured.append(
        {
            "credential_id": row.credential_id,
            "credential_owner_user_id": row.credential_owner_user_id,
            "requesting_user_id": row.requesting_user_id,
            "status": row.status,
            "error_code": row.error_code,
        }
    )

    assert captured == [
        {
            "credential_id": "credential-opaque",
            "credential_owner_user_id": 10,
            "requesting_user_id": 20,
            "status": "cancelled",
            "error_code": "cancelled",
        }
    ]
    assert "api_key" not in str(captured)
    assert "authorization" not in str(captured).lower()
