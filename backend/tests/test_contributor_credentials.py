"""Contributor credential isolation, masking, and lifecycle coverage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.contributor import ContributorUsageLedger
from novelai.db.models.users import User
from novelai.providers.gemini_provider import GeminiProvider
from novelai.services.contributor_credentials import ContributorCredentialService


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

    service = ContributorCredentialService(db_session)
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
    assert db_session.query(ContributorUsageLedger).count() == 2


def test_contributor_consent_and_provider_key_contracts_are_enforced(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("test-contributor-encryption"))
    monkeypatch.setattr(settings, "RUNTIME_DIR", tmp_path)
    user = User(email="contract@example.test", role="user")
    db_session.add(user)
    db_session.commit()
    service = ContributorCredentialService(db_session)

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
            ContributorUsageLedger(
                credential_id="deleted-credential",
                credential_owner_user_id=1,
                provider_key="gemini",
                provider_model="gemini-test",
                contribution_mode="contributor",
                status="completed",
                created_at=now - timedelta(days=31),
            ),
            ContributorUsageLedger(
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

    deleted = ContributorCredentialService(db_session).cleanup_old_usage(ttl_days=30)

    assert deleted == 1
    assert db_session.query(ContributorUsageLedger).count() == 1


def test_contributor_usage_summary_aggregates_beyond_recent_detail_limit(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            ContributorUsageLedger(
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

    summary = ContributorCredentialService(db_session).usage_summary("busy-credential")

    assert summary["today"] == {"requests": 101, "tokens": 202}
    assert summary["current_minute"] == {"requests": 101, "tokens": 202}
    assert len(summary["recent"]) == 100
