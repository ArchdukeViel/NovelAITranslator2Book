"""Contributor credential isolation, masking, and lifecycle coverage."""

from __future__ import annotations

import asyncio
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
from novelai.providers.gemini_provider import GeminiProvider
from novelai.services import provider_credentials as provider_credentials_module
from novelai.services.gemini_request_control import GeminiQuotaController
from novelai.services.provider_credentials import ProviderCredentialService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_contributor_credential_lifecycle_is_encrypted_masked_and_owner_scoped(
    db_session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("test-contributor-encryption"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)

    owner = User(email="contributor@example.test", role="user")
    other_user = User(email="other@example.test", role="user")
    db_session.add_all([owner, other_user])
    db_session.commit()

    service = ProviderCredentialService(db_session)
    credential, submitted_key = service.replace_unvalidated(
        owner_user_id=owner.id,
        provider_key="gemini",
        api_key="sk-live-contributor-key",
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )

    assert submitted_key == "sk-live-contributor-key"
    assert credential.encrypted_api_key != submitted_key
    assert submitted_key not in credential.encrypted_api_key
    assert service.get_owned(owner.id, credential.id) is credential
    assert service.get_owned(other_user.id, credential.id) is None
    safe = service.safe_response(credential)
    assert safe["last4"] == "-key"
    assert safe["fingerprint"]
    assert "encrypted_api_key" not in safe
    assert "api_key" not in safe

    captured_keys: list[str | None] = []

    async def fake_validate(self: GeminiProvider, model: str | None = None, **kwargs: object) -> tuple[bool, str]:
        del model, kwargs
        captured_keys.append(self._explicit_api_key)
        return False, "provider rejected the key"

    monkeypatch.setattr(GeminiProvider, "validate_connection", fake_validate)
    ok, message = asyncio.run(service.validate_and_activate(credential, submitted_key))
    db_session.commit()
    assert not ok
    assert message == "provider rejected the key"
    assert captured_keys == [submitted_key]
    assert credential.status == "invalid"
    assert credential.validation_status == "failed"

    replacement, replacement_key = service.replace_unvalidated(
        owner_user_id=owner.id,
        provider_key="gemini",
        api_key="sk-valid-contributor-key",
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )

    async def valid_validate(self: GeminiProvider, model: str | None = None, **kwargs: object) -> tuple[bool, str]:
        del model, kwargs
        captured_keys.append(self._explicit_api_key)
        return True, "valid"

    monkeypatch.setattr(GeminiProvider, "validate_connection", valid_validate)
    ok, _ = asyncio.run(service.validate_and_activate(replacement, replacement_key))
    db_session.commit()
    assert ok
    assert replacement.id == credential.id
    assert replacement.status == "active"
    assert replacement.validation_status == "valid"
    assert captured_keys[-1] == replacement_key

    service.pause(replacement)
    assert replacement.status == "paused"
    service.resume(replacement)
    assert replacement.status == "active"
    service.revoke(replacement)
    with pytest.raises(ValueError, match="cannot be replaced"):
        service.replace_unvalidated(
            owner_user_id=owner.id,
            provider_key="gemini",
            api_key="sk-replacement-after-revoke",
            consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
        )

    service.delete(replacement)
    db_session.commit()
    assert service.get_any(replacement.id) is None
    assert db_session.query(ProviderUsageLedger).count() == 2


def test_contributor_consent_and_provider_key_contracts_are_enforced(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("test-contributor-encryption"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    user = User(email="contract@example.test", role="user")
    db_session.add(user)
    db_session.commit()
    service = ProviderCredentialService(db_session)

    with pytest.raises(ValueError, match="consent"):
        service.replace_unvalidated(
            owner_user_id=user.id,
            provider_key="gemini",
            api_key="sk-key",
            consent_version="old-version",
        )
    with pytest.raises(ValueError, match="Only Gemini"):
        service.replace_unvalidated(
            owner_user_id=user.id,
            provider_key="openai",
            api_key="sk-key",
            consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
        )

    provider = GeminiProvider(api_key="explicit-key")
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", SecretStr("owner-global-key"))
    assert provider._api_key_string() == "explicit-key"


def test_contributor_usage_cleanup_applies_configured_retention(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            ProviderUsageLedger(
                credential_id="deleted-credential",
                credential_owner_user_id=1,
                provider_key="gemini",
                provider_model="gemini-test",
                contribution_mode="contributor",
                status="completed",
                created_at=now - timedelta(days=31),
            ),
            ProviderUsageLedger(
                credential_id="active-credential",
                credential_owner_user_id=1,
                provider_key="gemini",
                provider_model="gemini-test",
                contribution_mode="contributor",
                status="completed",
                created_at=now,
            ),
        ]
    )
    db_session.commit()

    deleted = ProviderCredentialService(db_session).cleanup_old_usage(ttl_days=30)

    assert deleted == 1
    assert db_session.query(ProviderUsageLedger).count() == 1


def test_contributor_usage_summary_aggregates_beyond_recent_detail_limit(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            ProviderUsageLedger(
                credential_id="busy-credential",
                credential_owner_user_id=1,
                provider_key="gemini",
                provider_model="gemini-test",
                contribution_mode="contributor",
                status="completed",
                total_tokens=2,
                created_at=now,
            )
            for _ in range(101)
        ]
    )
    db_session.commit()

    summary = ProviderCredentialService(db_session).usage_summary("busy-credential")

    assert summary["today"] == {"requests": 101, "tokens": 202}
    assert summary["current_minute"] == {"requests": 101, "tokens": 202}
    assert len(summary["recent"]) == 100


def test_runtime_lease_pools_active_valid_keys_and_never_reads_owner_key(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("lease-test-encryption"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", SecretStr("owner-global-key"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(settings, "ENV", "test")
    monkeypatch.setattr(settings, "CONTRIBUTOR_CREDENTIALS_ENABLED", True)

    owner = User(email="lease-owner@example.test", role="owner")
    first_user = User(email="lease-first@example.test", role="user")
    second_user = User(email="lease-second@example.test", role="user")
    db_session.add_all([owner, first_user, second_user])
    db_session.commit()
    service = ProviderCredentialService(db_session)
    owner_credential, owner_key = service.import_environment_credential(owner_user_id=owner.id)
    assert owner_credential.source == "env_bootstrap"
    assert owner_credential.owner_job_eligible is True
    assert owner_credential.contributor_pool_eligible is False
    assert owner_key == "owner-global-key"
    first, first_key = service.replace_unvalidated(
        owner_user_id=first_user.id,
        provider_key="gemini",
        api_key="contributor-first-key",
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )
    second, second_key = service.replace_unvalidated(
        owner_user_id=second_user.id,
        provider_key="gemini",
        api_key="contributor-second-key",
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )
    first.status = second.status = "active"
    first.is_active = second.is_active = True
    first.contributor_pool_eligible = second.contributor_pool_eligible = True
    first.validation_status = second.validation_status = "valid"
    now = datetime.now(UTC)
    first.last_used_at = now - timedelta(minutes=2)
    second.last_used_at = now - timedelta(minutes=1)
    db_session.commit()

    @contextmanager
    def fake_session_scope():
        yield db_session

    monkeypatch.setattr("novelai.db.engine.session_scope", fake_session_scope)
    leases = [
        ProviderCredentialService.acquire_runtime_lease(
            provider_key="gemini",
            provider_model="gemini-3.5-flash-lite",
            requesting_user_id=999,
        )
        for _ in range(3)
    ]

    assert [lease.credential_id if lease is not None else None for lease in leases] == [
        str(first.id),
        str(second.id),
        str(first.id),
    ]
    assert [lease.api_key if lease is not None else None for lease in leases] == [first_key, second_key, first_key]
    assert all(lease is not None and lease.api_key != "owner-global-key" for lease in leases)


def test_owner_and_user_credentials_share_registry_without_cross_eligibility(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("shared-registry-encryption"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", SecretStr("owner-registry-key"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    owner = User(email="shared-owner@example.test", role="owner")
    contributor = User(email="shared-contributor@example.test", role="user")
    db_session.add_all([owner, contributor])
    db_session.commit()
    service = ProviderCredentialService(db_session)

    owner_credential, _ = service.import_environment_credential(owner_user_id=owner.id)
    user_credential, user_key = service.replace_unvalidated(
        owner_user_id=contributor.id,
        provider_key="gemini",
        api_key="shared-user-key",
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )

    async def valid_validate(self: GeminiProvider, model: str | None = None, **kwargs: object) -> tuple[bool, str]:
        del self, model, kwargs
        return True, "valid"

    monkeypatch.setattr(GeminiProvider, "validate_connection", valid_validate)
    ok, _ = asyncio.run(service.validate_and_activate(user_credential, user_key))
    db_session.commit()

    assert ok is True
    assert owner_credential.id != user_credential.id
    assert owner_credential.credential_owner_user_id == owner.id
    assert owner_credential.source == "env_bootstrap"
    assert owner_credential.owner_job_eligible is True
    assert owner_credential.contributor_pool_eligible is False
    assert user_credential.credential_owner_user_id == contributor.id
    assert user_credential.source == "user_contribution"
    assert user_credential.owner_job_eligible is False
    assert user_credential.contributor_pool_eligible is True
    assert service.decrypt_api_key(owner_credential) == "owner-registry-key"
    assert service.decrypt_api_key(user_credential) == user_key
    safe_owner = service.safe_response(owner_credential)
    safe_user = service.safe_response(user_credential)
    assert "owner-registry-key" not in str(safe_owner)
    assert "shared-user-key" not in str(safe_user)


def test_failed_owner_environment_validation_clears_runtime_fallback(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("owner-failure-encryption"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", SecretStr("owner-invalid-key"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    owner = User(email="owner-failure@example.test", role="owner")
    db_session.add(owner)
    db_session.commit()
    service = ProviderCredentialService(db_session)
    credential, submitted_key = service.import_environment_credential(owner_user_id=owner.id)

    async def invalid_validate(self: GeminiProvider, model: str | None = None, **kwargs: object) -> tuple[bool, str]:
        del self, model, kwargs
        return False, "provider rejected the owner key"

    monkeypatch.setattr(GeminiProvider, "validate_connection", invalid_validate)
    ok, message = asyncio.run(service.validate_and_activate(credential, submitted_key))

    assert ok is False
    assert message == "provider rejected the owner key"
    assert credential.status == "invalid"
    assert credential.owner_job_eligible is True
    assert credential.contributor_pool_eligible is False
    assert settings.PROVIDER_GEMINI_API_KEY is None


def test_production_contributor_quota_includes_per_credential_concurrency_limit(db_session, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class CapturingRedisQuotaController(GeminiQuotaController):
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://quota-test")
    monkeypatch.setattr(
        provider_credentials_module,
        "RedisGeminiQuotaController",
        CapturingRedisQuotaController,
    )

    controller = ProviderCredentialService(db_session)._quota_controller("credential-for-quota-test")

    assert isinstance(controller, CapturingRedisQuotaController)
    assert captured["concurrency_limit"] == settings.CONTRIBUTOR_CONCURRENCY_LIMIT


def test_validation_cannot_activate_a_key_replaced_while_provider_call_was_in_flight(
    db_session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("replacement-test-encryption"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    user = User(email="replacement@example.test", role="user")
    db_session.add(user)
    db_session.commit()
    service = ProviderCredentialService(db_session)
    credential, old_key = service.replace_unvalidated(
        owner_user_id=user.id,
        provider_key="gemini",
        api_key="old-contributor-key",
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
    )

    async def replace_during_validation(
        self: GeminiProvider, model: str | None = None, **kwargs: object
    ) -> tuple[bool, str]:
        del self, model, kwargs
        service.replace_unvalidated(
            owner_user_id=user.id,
            provider_key="gemini",
            api_key="new-contributor-key",
            consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
        )
        return True, "valid"

    monkeypatch.setattr(GeminiProvider, "validate_connection", replace_during_validation)
    ok, message = asyncio.run(service.validate_and_activate(credential, old_key))

    assert not ok
    assert "replaced" in message
    assert credential.status == "invalid"
    assert credential.validation_status == "unchecked"
    assert db_session.query(ProviderUsageLedger).count() == 0
