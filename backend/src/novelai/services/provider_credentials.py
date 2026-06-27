from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.config.settings import settings
from novelai.db.models import ProviderCredential


def _utcnow() -> datetime:
    return datetime.now(UTC)


def secret_fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def secret_last4(secret: str) -> str:
    return secret[-4:] if len(secret) >= 4 else secret


class ProviderCredentialService:
    """Encrypted DB persistence for owner-managed provider credentials."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def encryption_available() -> bool:
        return settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY is not None

    @staticmethod
    def _fernet() -> Fernet:
        secret = settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY
        if secret is None or not secret.get_secret_value().strip():
            raise ValueError("PROVIDER_CREDENTIAL_ENCRYPTION_KEY is required for provider credential storage.")
        digest = hashlib.sha256(secret.get_secret_value().encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def encrypt_api_key(self, api_key: str) -> str:
        clean = api_key.strip()
        if not clean:
            raise ValueError("API key must not be empty")
        return self._fernet().encrypt(clean.encode("utf-8")).decode("utf-8")

    def decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return self._fernet().decrypt(credential.encrypted_api_key.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored provider credential cannot be decrypted with the configured key.") from exc

    def list_credentials(self) -> list[ProviderCredential]:
        return list(self.db.scalars(select(ProviderCredential).order_by(ProviderCredential.provider)))

    def get_by_provider(self, provider: str) -> ProviderCredential | None:
        return self.db.scalar(select(ProviderCredential).where(ProviderCredential.provider == provider))

    def get_by_id_or_provider(self, credential_id: str) -> ProviderCredential | None:
        clean = credential_id.strip()
        if clean.isdigit():
            found = self.db.get(ProviderCredential, int(clean))
            if found is not None:
                return found
        return self.get_by_provider(clean)

    def upsert_credential(
        self,
        *,
        provider: str,
        api_key: str,
        label: str,
        model: str | None,
        is_active: bool,
        notes: str | None,
        validation_status: str = "unchecked",
        validation_message: str | None = "Connection has not been checked in this server session.",
    ) -> ProviderCredential:
        clean_api_key = api_key.strip()
        encrypted = self.encrypt_api_key(clean_api_key)
        now = _utcnow()
        credential = self.get_by_provider(provider)
        if credential is None:
            credential = ProviderCredential(
                provider=provider,
                label=label,
                encrypted_api_key=encrypted,
                key_fingerprint=secret_fingerprint(clean_api_key),
                last4=secret_last4(clean_api_key),
                is_active=is_active,
                validation_status=validation_status,
                validation_message=validation_message,
                notes=notes,
                model=model,
                created_at=now,
                updated_at=now,
            )
            self.db.add(credential)
        else:
            credential.label = label
            credential.encrypted_api_key = encrypted
            credential.key_fingerprint = secret_fingerprint(clean_api_key)
            credential.last4 = secret_last4(clean_api_key)
            credential.is_active = is_active
            credential.validation_status = validation_status
            credential.validation_message = validation_message
            credential.notes = notes
            credential.model = model
            credential.updated_at = now
        self.db.flush()
        return credential

    def update_metadata(
        self,
        credential: ProviderCredential,
        *,
        label: str | None = None,
        model: str | None = None,
        is_active: bool | None = None,
        notes: str | None = None,
        validation_status: str | None = None,
        validation_message: str | None = None,
        last_validated_at: datetime | None = None,
    ) -> ProviderCredential:
        if label is not None:
            credential.label = label
        if model is not None:
            credential.model = model
        if is_active is not None:
            credential.is_active = is_active
        if notes is not None:
            credential.notes = notes
        if validation_status is not None:
            credential.validation_status = validation_status
        if validation_message is not None:
            credential.validation_message = validation_message
        if last_validated_at is not None:
            credential.last_validated_at = last_validated_at
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    @staticmethod
    def safe_response(credential: ProviderCredential) -> dict[str, Any]:
        return {
            "id": str(credential.provider),
            "db_id": credential.id,
            "provider": credential.provider,
            "label": credential.label,
            "is_active": credential.is_active,
            "configured": True,
            "last4": credential.last4,
            "fingerprint": credential.key_fingerprint,
            "model": credential.model,
            "provider_model": credential.model,
            "validation_status": credential.validation_status,
            "validation_message": credential.validation_message,
            "last_validated_at": credential.last_validated_at.isoformat().replace("+00:00", "Z")
            if credential.last_validated_at
            else None,
            "created_at": credential.created_at.isoformat().replace("+00:00", "Z") if credential.created_at else None,
            "updated_at": credential.updated_at.isoformat().replace("+00:00", "Z") if credential.updated_at else None,
            "notes": credential.notes,
        }
