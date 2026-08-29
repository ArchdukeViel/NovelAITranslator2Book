"""Unified encrypted provider credentials and sanitized usage accounting.

Owner-managed keys and user-contributed keys share one database registry. A
credential's owner, source, owner-job eligibility, and contributor-pool
eligibility are explicit row properties; selecting a contributor key never
falls back to the owner environment key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
from novelai.db.models.system import ProviderCredential, ProviderUsageLedger
from novelai.providers.gemini_provider import GeminiProvider
from novelai.services.gemini_request_control import (
    CompositeGeminiQuotaController,
    GeminiQuotaController,
    RedisGeminiQuotaController,
)
from novelai.services.preferences_service import PreferencesService
from novelai.utils.hashing import digest32, hexdigest

logger = logging.getLogger(__name__)

CONTRIBUTOR_PROVIDER = "gemini"
VALID_STATUSES = frozenset({"active", "paused", "invalid", "revoked"})
CONTRIBUTOR_SOURCE = "user_contribution"
OWNER_SOURCES = frozenset({"owner_admin", "env_bootstrap", "owner_legacy"})


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _bounded(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean[:limit] or None


def _safe_validation_message(message: str | None, secret: str) -> str | None:
    """Bound provider feedback without allowing a submitted key to echo back."""
    if message is None:
        return None
    redacted = message.replace(secret, "[redacted]") if secret else message
    return _bounded(redacted, 512)


def secret_fingerprint(secret: str) -> str:
    """Return a short server-keyed fingerprint for safe operator comparison."""
    encryption_key = settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY
    if encryption_key is None or not encryption_key.get_secret_value().strip():
        return hexdigest(secret, length=12)
    digest = hmac.new(
        digest32(encryption_key.get_secret_value()),
        secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:12]


def secret_last4(secret: str) -> str:
    return secret[-4:] if len(secret) >= 4 else secret


@dataclass(frozen=True)
class ProviderCredentialLease:
    """Runtime-only decrypted credential lease."""

    credential_id: str
    credential_owner_user_id: int | None
    provider_key: str
    provider_model: str
    api_key: str
    quota_controller: GeminiQuotaController | None


class ProviderCredentialService:
    """Manage the unified encrypted provider credential registry."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def enabled() -> bool:
        return settings.CONTRIBUTOR_CREDENTIALS_ENABLED

    @staticmethod
    def encryption_available() -> bool:
        key = settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY
        return key is not None and bool(key.get_secret_value().strip())

    @staticmethod
    def _fernet() -> Fernet:
        secret = settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY
        if secret is None or not secret.get_secret_value().strip():
            raise ValueError("PROVIDER_CREDENTIAL_ENCRYPTION_KEY is required for provider credential storage.")
        return Fernet(base64.urlsafe_b64encode(digest32(secret.get_secret_value())))

    def encrypt_api_key(self, api_key: str) -> str:
        clean = api_key.strip()
        if not clean:
            raise ValueError("API key must not be empty")
        if len(clean) > 4096:
            raise ValueError("API key is too long")
        return self._fernet().encrypt(clean.encode("utf-8")).decode("utf-8")

    def decrypt_api_key(self, credential: ProviderCredential) -> str:
        if not credential.encrypted_api_key:
            raise ValueError("Provider credential has no usable encrypted key.")
        try:
            return self._fernet().decrypt(credential.encrypted_api_key.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored provider credential cannot be decrypted with the configured key.") from exc

    def list_credentials(self) -> list[ProviderCredential]:
        return list(
            self.db.scalars(
                select(ProviderCredential).order_by(
                    ProviderCredential.provider,
                    ProviderCredential.owner_job_eligible.desc(),
                    ProviderCredential.created_at,
                    ProviderCredential.id,
                )
            )
        )

    def list_for_user(self, owner_user_id: int) -> list[ProviderCredential]:
        return list(
            self.db.scalars(
                select(ProviderCredential)
                .where(
                    ProviderCredential.credential_owner_user_id == owner_user_id,
                    ProviderCredential.source == CONTRIBUTOR_SOURCE,
                )
                .order_by(ProviderCredential.created_at, ProviderCredential.id)
            )
        )

    def list_all(self) -> list[ProviderCredential]:
        """List all credentials for owner-only emergency review."""
        return self.list_credentials()

    def get_owned(self, owner_user_id: int, credential_id: str | int) -> ProviderCredential | None:
        clean = str(credential_id).strip()
        if not clean.isdigit():
            return None
        return self.db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.id == int(clean),
                ProviderCredential.credential_owner_user_id == owner_user_id,
                ProviderCredential.source == CONTRIBUTOR_SOURCE,
            )
        )

    def get_any(self, credential_id: str | int) -> ProviderCredential | None:
        clean = str(credential_id).strip()
        if not clean.isdigit():
            return None
        return self.db.get(ProviderCredential, int(clean))

    def get_by_provider(self, provider: str) -> ProviderCredential | None:
        """Return the deterministic owner-job credential for a provider."""
        return self.db.scalar(
            select(ProviderCredential)
            .where(
                ProviderCredential.provider == provider,
                ProviderCredential.owner_job_eligible.is_(True),
            )
            .order_by(
                ProviderCredential.is_active.desc(),
                ProviderCredential.status == "active",
                ProviderCredential.created_at.desc(),
                ProviderCredential.id.desc(),
            )
        )

    def get_by_id_or_provider(self, credential_id: str | int) -> ProviderCredential | None:
        found = self.get_any(credential_id)
        return found if found is not None else self.get_by_provider(str(credential_id).strip())

    def _get_owner_candidate(self, provider: str) -> ProviderCredential | None:
        return self.db.scalar(
            select(ProviderCredential)
            .where(
                ProviderCredential.provider == provider,
                ProviderCredential.source.in_(OWNER_SOURCES),
            )
            .order_by(ProviderCredential.created_at.desc(), ProviderCredential.id.desc())
        )

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
        credential_owner_user_id: int | None = None,
        source: str = "owner_admin",
    ) -> ProviderCredential:
        """Create or replace an owner-managed row without touching user rows."""
        clean_api_key = api_key.strip()
        encrypted = self.encrypt_api_key(clean_api_key)
        now = _utcnow()
        credential = self._get_owner_candidate(provider)
        if credential is None:
            credential = ProviderCredential(
                provider=provider,
                label=label,
                encrypted_api_key=encrypted,
                key_fingerprint=secret_fingerprint(clean_api_key),
                last4=secret_last4(clean_api_key),
                is_active=is_active,
                status="active" if is_active else "paused",
                validation_status=validation_status,
                validation_message=validation_message,
                notes=notes,
                model=model,
                credential_owner_user_id=credential_owner_user_id,
                source=source,
                owner_job_eligible=True,
                contributor_pool_eligible=False,
                failure_count=0,
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
            credential.status = "active" if is_active else "paused"
            credential.validation_status = validation_status
            credential.validation_message = validation_message
            credential.notes = notes
            credential.model = model
            credential.credential_owner_user_id = credential_owner_user_id or credential.credential_owner_user_id
            credential.source = source
            credential.owner_job_eligible = True
            credential.contributor_pool_eligible = False
            credential.consent_revoked_at = _utcnow() if credential.consent_version else None
            credential.updated_at = now
        self.db.flush()
        return credential

    def import_environment_credential(
        self,
        *,
        owner_user_id: int,
        provider: str = CONTRIBUTOR_PROVIDER,
        model: str | None = None,
    ) -> tuple[ProviderCredential, str]:
        """Explicitly import the configured environment key into the registry.

        Startup never calls this method. The caller must be an authenticated
        owner or a tightly controlled operator command.
        """
        if provider != CONTRIBUTOR_PROVIDER:
            raise ValueError("Only Gemini environment credentials are supported.")
        configured = settings.PROVIDER_GEMINI_API_KEY
        if configured is None or not configured.get_secret_value().strip():
            raise ValueError("PROVIDER_GEMINI_API_KEY is not configured for import.")
        clean = configured.get_secret_value().strip()
        credential = self._get_owner_candidate(provider)
        now = _utcnow()
        if credential is None:
            credential = ProviderCredential(
                provider=provider,
                label="Owner Gemini (environment import)",
                encrypted_api_key=self.encrypt_api_key(clean),
                key_fingerprint=secret_fingerprint(clean),
                last4=secret_last4(clean),
                is_active=True,
                status="invalid",
                validation_status="unchecked",
                validation_message="Imported from the configured environment; validation is required.",
                model=model or GEMINI_DEFAULT_MODEL,
                credential_owner_user_id=owner_user_id,
                source="env_bootstrap",
                owner_job_eligible=True,
                contributor_pool_eligible=False,
                created_at=now,
                updated_at=now,
            )
            self.db.add(credential)
        else:
            credential.encrypted_api_key = self.encrypt_api_key(clean)
            credential.key_fingerprint = secret_fingerprint(clean)
            credential.last4 = secret_last4(clean)
            credential.is_active = True
            credential.status = "invalid"
            credential.validation_status = "unchecked"
            credential.validation_message = "Imported from the configured environment; validation is required."
            credential.model = model or credential.model or GEMINI_DEFAULT_MODEL
            credential.credential_owner_user_id = owner_user_id
            credential.source = "env_bootstrap"
            credential.owner_job_eligible = True
            credential.contributor_pool_eligible = False
            credential.consent_version = None
            credential.consent_at = None
            credential.consent_revoked_at = None
            credential.revoked_at = None
            credential.failure_count = 0
            credential.last_validated_at = None
            credential.last_failure_at = None
            credential.updated_at = now
        self.db.flush()
        return credential, clean

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
        owner_job_eligible: bool | None = None,
        contributor_pool_eligible: bool | None = None,
    ) -> ProviderCredential:
        if label is not None:
            credential.label = label
        if model is not None:
            credential.model = model
        if is_active is not None:
            credential.is_active = is_active
            if not is_active and credential.status == "active":
                credential.status = "paused"
            elif is_active and credential.status == "paused" and credential.validation_status != "failed":
                credential.status = "active"
        if notes is not None:
            credential.notes = notes
        if validation_status is not None:
            credential.validation_status = validation_status
        if validation_message is not None:
            credential.validation_message = validation_message
        if last_validated_at is not None:
            credential.last_validated_at = last_validated_at
        if owner_job_eligible is not None:
            credential.owner_job_eligible = owner_job_eligible
        if contributor_pool_eligible is not None:
            if contributor_pool_eligible and (credential.status != "active" or credential.validation_status != "valid"):
                raise ValueError("Only an active, successfully validated credential can enter the contributor pool.")
            credential.contributor_pool_eligible = contributor_pool_eligible
            if contributor_pool_eligible:
                credential.consent_version = credential.consent_version or settings.CONTRIBUTOR_CONSENT_VERSION
                credential.consent_at = credential.consent_at or _utcnow()
                credential.consent_revoked_at = None
            else:
                credential.consent_revoked_at = _utcnow()
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def replace_unvalidated(
        self,
        *,
        owner_user_id: int,
        provider_key: str,
        api_key: str,
        consent_version: str,
    ) -> tuple[ProviderCredential, str]:
        if not self.enabled():
            raise RuntimeError("Contributor credentials are disabled.")
        if provider_key != CONTRIBUTOR_PROVIDER:
            raise ValueError("Only Gemini contributor credentials are supported.")
        if consent_version != settings.CONTRIBUTOR_CONSENT_VERSION:
            raise ValueError("The current contributor consent version must be accepted.")
        clean = api_key.strip()
        encrypted = self.encrypt_api_key(clean)
        now = _utcnow()
        credential = self.db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.credential_owner_user_id == owner_user_id,
                ProviderCredential.provider == provider_key,
                ProviderCredential.source == CONTRIBUTOR_SOURCE,
            )
        )
        if credential is not None and credential.status == "revoked":
            raise ValueError("Revoked contributor credentials cannot be replaced.")
        if credential is None:
            credential = ProviderCredential(
                provider=provider_key,
                label="User contributor Gemini",
                encrypted_api_key=encrypted,
                key_fingerprint=secret_fingerprint(clean),
                last4=secret_last4(clean),
                is_active=False,
                status="invalid",
                validation_status="unchecked",
                validation_message="Key validation is in progress.",
                consent_version=consent_version,
                consent_at=now,
                model=GEMINI_DEFAULT_MODEL,
                credential_owner_user_id=owner_user_id,
                source=CONTRIBUTOR_SOURCE,
                owner_job_eligible=False,
                contributor_pool_eligible=False,
                failure_count=0,
                created_at=now,
                updated_at=now,
            )
            self.db.add(credential)
        else:
            credential.encrypted_api_key = encrypted
            credential.key_fingerprint = secret_fingerprint(clean)
            credential.last4 = secret_last4(clean)
            credential.is_active = False
            credential.status = "invalid"
            credential.validation_status = "unchecked"
            credential.validation_message = "Key validation is in progress."
            credential.consent_version = consent_version
            credential.consent_at = now
            credential.consent_revoked_at = None
            credential.owner_job_eligible = False
            credential.contributor_pool_eligible = False
            credential.failure_count = 0
            credential.last_validated_at = None
            credential.last_failure_at = None
            credential.revoked_at = None
            credential.updated_at = now
        self.db.flush()
        return credential, clean

    def _quota_controller(self, credential_id: str) -> GeminiQuotaController:
        if settings.ENV != "test":
            return RedisGeminiQuotaController(
                namespace=f"contributor:{credential_id}",
                rpm_limit=settings.CONTRIBUTOR_RPM_LIMIT,
                tpm_limit=settings.CONTRIBUTOR_TPM_LIMIT,
                rpd_limit=settings.CONTRIBUTOR_RPD_LIMIT,
                concurrency_limit=settings.CONTRIBUTOR_CONCURRENCY_LIMIT,
            )
        quota_dir = settings.RUNTIME_DIR / "contributor_quota" / credential_id
        return GeminiQuotaController(
            quota_dir,
            rpm_limit=settings.CONTRIBUTOR_RPM_LIMIT,
            tpm_limit=settings.CONTRIBUTOR_TPM_LIMIT,
            rpd_limit=settings.CONTRIBUTOR_RPD_LIMIT,
            concurrency_limit=settings.CONTRIBUTOR_CONCURRENCY_LIMIT,
        )

    @staticmethod
    def _project_quota_controller() -> GeminiQuotaController:
        """Return one shared provider-project budget for all contributor keys."""

        if settings.ENV != "test":
            return RedisGeminiQuotaController(
                namespace="contributors:project",
                rpm_limit=settings.GEMINI_RPM_LIMIT,
                tpm_limit=settings.GEMINI_TPM_LIMIT,
                rpd_limit=settings.GEMINI_RPD_LIMIT,
                concurrency_limit=settings.GEMINI_CONCURRENCY_LIMIT,
            )
        return GeminiQuotaController(
            settings.RUNTIME_DIR / "contributor_project_quota",
            rpm_limit=settings.GEMINI_RPM_LIMIT,
            tpm_limit=settings.GEMINI_TPM_LIMIT,
            rpd_limit=settings.GEMINI_RPD_LIMIT,
            concurrency_limit=settings.GEMINI_CONCURRENCY_LIMIT,
        )

    def contributor_pool_capacity_snapshot(self, provider_key: str = CONTRIBUTOR_PROVIDER) -> dict[str, Any]:
        """Return aggregate capacity without exposing credential identifiers."""

        credentials = list(
            self.db.scalars(
                select(ProviderCredential).where(
                    ProviderCredential.provider == provider_key,
                    ProviderCredential.source == CONTRIBUTOR_SOURCE,
                )
            )
        )
        eligible = [
            credential
            for credential in credentials
            if credential.status == "active"
            and credential.is_active
            and credential.validation_status == "valid"
            and credential.contributor_pool_eligible
        ]
        return {
            "provider_key": provider_key,
            "pool_size": len(credentials),
            "eligible_credential_count": len(eligible),
            "quota_domain_count": 1 if credentials else 0,
            "verified_independent_quota_domain_count": 0,
            "quota_domain_assumption": "shared_project_unverified",
            "project_rpm_limit": settings.GEMINI_RPM_LIMIT,
            "project_tpm_limit": settings.GEMINI_TPM_LIMIT,
            "project_rpd_limit": settings.GEMINI_RPD_LIMIT,
            "project_concurrency_limit": settings.GEMINI_CONCURRENCY_LIMIT,
            "per_credential_rpm_limit": settings.CONTRIBUTOR_RPM_LIMIT,
            "per_credential_tpm_limit": settings.CONTRIBUTOR_TPM_LIMIT,
            "per_credential_rpd_limit": settings.CONTRIBUTOR_RPD_LIMIT,
            "per_credential_concurrency_limit": settings.CONTRIBUTOR_CONCURRENCY_LIMIT,
            "reader_http_rps_is_separate": True,
        }

    def _combined_quota_controller(self, credential_id: str) -> CompositeGeminiQuotaController:
        return CompositeGeminiQuotaController((self._project_quota_controller(), self._quota_controller(credential_id)))

    async def validate_and_activate(self, credential: ProviderCredential, api_key: str) -> tuple[bool, str]:
        """Validate one explicit key without copying it into global settings."""
        is_contributor = credential.source == CONTRIBUTOR_SOURCE
        provider = GeminiProvider(
            api_key=api_key,
            quota_controller=self._quota_controller(str(credential.id)) if is_contributor else None,
        )
        ok, message = await provider.validate_connection(credential.model or GEMINI_DEFAULT_MODEL)
        self.db.refresh(credential)
        if credential.key_fingerprint != secret_fingerprint(api_key):
            return False, "Credential was replaced while validation was in progress."
        now = _utcnow()
        credential.last_validated_at = now
        credential.updated_at = now
        credential.validation_message = _safe_validation_message(message, api_key)
        credential.validation_status = "valid" if ok else "failed"
        credential.status = "active" if ok else "invalid"
        credential.is_active = ok
        if is_contributor:
            credential.contributor_pool_eligible = ok
        if not ok:
            credential.failure_count += 1
            credential.last_failure_at = now
            credential.contributor_pool_eligible = False
            if not is_contributor and credential.source == "env_bootstrap":
                # An explicitly imported environment key must not remain
                # usable through the in-memory preference fallback after
                # provider validation fails.
                settings.PROVIDER_GEMINI_API_KEY = None
        self.db.add(
            ProviderUsageLedger(
                credential_id=str(credential.id),
                credential_owner_user_id=credential.credential_owner_user_id,
                provider_key=credential.provider,
                provider_model=credential.model or GEMINI_DEFAULT_MODEL,
                request_id=f"credential-validation:{credential.id}:{now.timestamp()}",
                contribution_mode="contributor_validation" if is_contributor else "owner_validation",
                status="validated" if ok else "validation_failed",
                estimated_input_tokens=1,
                estimated_output_tokens=32,
                estimated_cost_usd=32 * settings.COST_PER_TOKEN_USD,
                error_code=None if ok else "validation_failed",
                created_at=now,
                completed_at=now,
            )
        )
        self.db.flush()
        return ok, message

    def pause(self, credential: ProviderCredential) -> ProviderCredential:
        if credential.status == "revoked":
            raise ValueError("Revoked credentials cannot be resumed.")
        credential.status = "paused"
        credential.is_active = False
        credential.contributor_pool_eligible = False
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def resume(self, credential: ProviderCredential) -> ProviderCredential:
        if credential.status == "revoked":
            raise ValueError("Revoked credentials cannot be resumed.")
        if credential.validation_status != "valid":
            raise ValueError("Only a successfully validated credential can be resumed.")
        credential.status = "active"
        credential.is_active = True
        if credential.source == CONTRIBUTOR_SOURCE:
            credential.contributor_pool_eligible = True
            credential.validation_message = "Credential is active and eligible for contributor translation work."
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def revoke(self, credential: ProviderCredential) -> ProviderCredential:
        credential.status = "revoked"
        credential.is_active = False
        credential.validation_status = "revoked"
        credential.validation_message = "Credential revoked by an owner."
        credential.owner_job_eligible = False
        credential.contributor_pool_eligible = False
        credential.revoked_at = _utcnow()
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def delete(self, credential: ProviderCredential) -> None:
        self.db.delete(credential)
        self.db.flush()

    def set_pool_eligibility(self, credential: ProviderCredential, eligible: bool) -> ProviderCredential:
        return self.update_metadata(credential, contributor_pool_eligible=eligible)

    def mark_unhealthy(self, credential_id: str, *, error_code: str) -> None:
        credential = self.get_any(credential_id)
        if credential is None or credential.status == "revoked":
            return
        credential.status = "paused"
        credential.is_active = False
        credential.validation_status = "failed"
        credential.validation_message = "Credential paused after a provider failure; validate it again before resuming."
        credential.contributor_pool_eligible = False
        credential.failure_count += 1
        credential.last_failure_at = _utcnow()
        credential.updated_at = _utcnow()
        self.db.flush()
        logger.info("Provider credential paused after provider failure code=%s", error_code)

    @staticmethod
    def mark_runtime_unhealthy(credential_id: str, *, error_code: str) -> None:
        try:
            from novelai.db.engine import session_scope

            with session_scope() as db:
                ProviderCredentialService(db).mark_unhealthy(credential_id, error_code=error_code)
        except Exception:
            logger.warning("Provider credential health update failed", exc_info=True)

    @staticmethod
    def safe_response(credential: ProviderCredential) -> dict[str, Any]:
        return {
            "id": credential.id,
            "db_id": credential.id,
            "credential_id": str(credential.id),
            "provider_key": str(credential.provider),
            "provider": str(credential.provider),
            "provider_model": credential.model,
            "model": credential.model,
            "label": credential.label,
            "is_active": credential.is_active,
            "status": credential.status if credential.status in VALID_STATUSES else "invalid",
            "configured": True,
            "last4": credential.last4,
            "fingerprint": credential.key_fingerprint,
            "validation_status": credential.validation_status,
            "validation_message": credential.validation_message,
            "last_validated_at": _iso(credential.last_validated_at),
            "created_at": _iso(credential.created_at),
            "updated_at": _iso(credential.updated_at),
            "last_used_at": _iso(credential.last_used_at),
            "last_failure_at": _iso(credential.last_failure_at),
            "failure_count": credential.failure_count,
            "notes": credential.notes,
            "credential_owner_user_id": credential.credential_owner_user_id,
            "source": credential.source,
            "owner_job_eligible": credential.owner_job_eligible,
            "contributor_pool_eligible": credential.contributor_pool_eligible,
            "consent_version": credential.consent_version,
            "consent_at": _iso(credential.consent_at),
            "consent_revoked_at": _iso(credential.consent_revoked_at),
            "revoked_at": _iso(credential.revoked_at),
        }

    @staticmethod
    def _usage_row(row: ProviderUsageLedger) -> dict[str, Any]:
        return {
            "id": row.id,
            "status": row.status,
            "provider": row.provider_key,
            "provider_model": row.provider_model,
            "request_id": row.request_id,
            "job_id": row.job_id,
            "activity_id": row.activity_id,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "total_tokens": row.total_tokens,
            "estimated_cost_usd": row.estimated_cost_usd,
            "error_code": row.error_code,
            "created_at": _iso(row.created_at),
            "completed_at": _iso(row.completed_at),
        }

    def usage_summary(self, credential_id: str) -> dict[str, Any]:
        now = _utcnow()
        minute_cutoff = now - timedelta(minutes=1)
        day_cutoff = now - timedelta(days=1)
        base = select(ProviderUsageLedger).where(ProviderUsageLedger.credential_id == credential_id)
        recent = list(
            self.db.scalars(
                base.where(ProviderUsageLedger.created_at >= day_cutoff)
                .order_by(ProviderUsageLedger.created_at.desc())
                .limit(100)
            )
        )
        minute_requests, minute_tokens = self.db.execute(
            select(
                func.count(ProviderUsageLedger.id),
                func.coalesce(func.sum(ProviderUsageLedger.total_tokens), 0),
            ).where(
                ProviderUsageLedger.credential_id == credential_id,
                ProviderUsageLedger.created_at >= minute_cutoff,
            )
        ).one()
        today_requests, today_tokens = self.db.execute(
            select(
                func.count(ProviderUsageLedger.id),
                func.coalesce(func.sum(ProviderUsageLedger.total_tokens), 0),
            ).where(
                ProviderUsageLedger.credential_id == credential_id,
                ProviderUsageLedger.created_at >= day_cutoff,
            )
        ).one()
        return {
            "credential_id": credential_id,
            "limits": {
                "requests_per_minute": settings.CONTRIBUTOR_RPM_LIMIT,
                "tokens_per_minute": settings.CONTRIBUTOR_TPM_LIMIT,
                "requests_per_day": settings.CONTRIBUTOR_RPD_LIMIT,
            },
            "current_minute": {"requests": int(minute_requests or 0), "tokens": int(minute_tokens or 0)},
            "today": {"requests": int(today_requests or 0), "tokens": int(today_tokens or 0)},
            "recent": [self._usage_row(row) for row in recent],
        }

    def cleanup_old_usage(self, *, ttl_days: int | None = None, batch_size: int = 500) -> int:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        cutoff = _utcnow() - timedelta(days=ttl_days or settings.CONTRIBUTOR_USAGE_RETENTION_DAYS)
        deleted = 0
        while True:
            ids = self.db.scalars(
                select(ProviderUsageLedger.id)
                .where(ProviderUsageLedger.created_at < cutoff)
                .order_by(ProviderUsageLedger.id)
                .limit(batch_size)
            ).all()
            if not ids:
                return deleted
            self.db.execute(delete(ProviderUsageLedger).where(ProviderUsageLedger.id.in_(ids)))
            self.db.flush()
            deleted += len(ids)

    @staticmethod
    def record_usage(
        *,
        credential_id: str,
        credential_owner_user_id: int | None,
        requesting_user_id: int | None,
        provider_key: str,
        provider_model: str,
        request_id: str | None,
        job_id: str | None,
        activity_id: str | None,
        status: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        estimated_input_tokens: int | None,
        estimated_output_tokens: int | None,
        error_code: str | None = None,
        contribution_mode: str = "contributor",
    ) -> None:
        """Persist sanitized accounting metadata in a short transaction."""
        try:
            from novelai.db.engine import session_scope

            total = total_tokens if isinstance(total_tokens, int) else None
            estimate_total = (estimated_input_tokens or 0) + (estimated_output_tokens or 0)
            with session_scope() as db:
                db.add(
                    ProviderUsageLedger(
                        credential_id=_bounded(credential_id, 64) or "unknown",
                        credential_owner_user_id=credential_owner_user_id,
                        requesting_user_id=requesting_user_id,
                        provider_key=_bounded(provider_key, 64) or "unknown",
                        provider_model=_bounded(provider_model, 255) or GEMINI_DEFAULT_MODEL,
                        request_id=_bounded(request_id, 255),
                        job_id=_bounded(job_id, 255),
                        activity_id=_bounded(activity_id, 255),
                        contribution_mode=_bounded(contribution_mode, 64) or "owner",
                        status=_bounded(status, 32) or "failed",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total,
                        estimated_input_tokens=estimated_input_tokens,
                        estimated_output_tokens=estimated_output_tokens,
                        estimated_cost_usd=(total or estimate_total) * settings.COST_PER_TOKEN_USD,
                        error_code=_bounded(error_code, 64),
                        created_at=_utcnow(),
                        completed_at=_utcnow(),
                    )
                )
        except Exception:
            logger.warning("Provider usage ledger write failed", exc_info=True)

    @staticmethod
    def acquire_runtime_lease(
        *,
        provider_key: str,
        provider_model: str | None,
        requesting_user_id: int | None,
    ) -> ProviderCredentialLease | None:
        """Select/decrypt one explicitly eligible contributor credential."""
        del requesting_user_id
        if not settings.CONTRIBUTOR_CREDENTIALS_ENABLED or provider_key != CONTRIBUTOR_PROVIDER:
            return None
        try:
            from novelai.db.engine import session_scope

            with session_scope() as db:
                service = ProviderCredentialService(db)
                credential = db.scalar(
                    select(ProviderCredential)
                    .where(
                        ProviderCredential.provider == provider_key,
                        ProviderCredential.status == "active",
                        ProviderCredential.is_active.is_(True),
                        ProviderCredential.validation_status == "valid",
                        ProviderCredential.contributor_pool_eligible.is_(True),
                    )
                    .order_by(
                        ProviderCredential.last_used_at.is_(None).desc(),
                        ProviderCredential.last_used_at,
                        ProviderCredential.id,
                    )
                    .with_for_update(skip_locked=True)
                )
                if credential is None:
                    return None
                api_key = service.decrypt_api_key(credential)
                credential.last_used_at = _utcnow()
                credential.updated_at = _utcnow()
                db.flush()
                return ProviderCredentialLease(
                    credential_id=str(credential.id),
                    credential_owner_user_id=credential.credential_owner_user_id,
                    provider_key=credential.provider,
                    provider_model=provider_model or credential.model or GEMINI_DEFAULT_MODEL,
                    api_key=api_key,
                    quota_controller=service._combined_quota_controller(str(credential.id)),
                )
        except Exception as exc:
            logger.warning("Contributor credential selection failed (%s)", type(exc).__name__)
            return None

    @staticmethod
    def owner_runtime_identity(provider_key: str) -> dict[str, Any] | None:
        """Return safe identity metadata for the owner-selected runtime row."""
        try:
            from novelai.db.engine import session_scope

            with session_scope() as db:
                credential = db.scalar(
                    select(ProviderCredential)
                    .where(
                        ProviderCredential.provider == provider_key,
                        ProviderCredential.owner_job_eligible.is_(True),
                        ProviderCredential.is_active.is_(True),
                        ProviderCredential.status == "active",
                        ProviderCredential.validation_status != "failed",
                    )
                    .order_by(ProviderCredential.created_at.desc(), ProviderCredential.id.desc())
                )
                if credential is None:
                    return None
                return {
                    "credential_id": str(credential.id),
                    "credential_owner_user_id": credential.credential_owner_user_id,
                    "credential_scope": "owner",
                    "contribution_mode": "owner",
                }
        except Exception as exc:
            logger.debug("Owner credential identity lookup unavailable (%s)", type(exc).__name__)
            return None


def _production_like() -> bool:
    return settings.ENV.strip().lower() not in {"development", "dev", "test", "testing", "local"}


def hydrate_active_provider_credentials(
    *,
    db: Session,
    preferences: PreferencesService,
    require_encryption_key: bool | None = None,
) -> list[dict[str, Any]]:
    """Hydrate only owner-job-eligible rows into runtime provider settings."""
    credential_service = ProviderCredentialService(db)
    credentials = credential_service.list_credentials()
    require_key = _production_like() if require_encryption_key is None else bool(require_encryption_key)
    diagnostics: list[dict[str, Any]] = []
    hydrated_providers: set[str] = set()
    for credential in credentials:
        diagnostic = {
            "provider": credential.provider,
            "credential_id": str(credential.provider),
            "db_id": credential.id,
            "label": credential.label,
            "hydrated": False,
            "reason": None,
        }
        if not credential.owner_job_eligible:
            diagnostic["reason"] = "not_owner_eligible"
            diagnostics.append(diagnostic)
            continue
        if credential.provider in hydrated_providers:
            diagnostic["reason"] = "owner_credential_already_selected"
            diagnostics.append(diagnostic)
            continue
        if not credential.is_active or credential.status in {"paused", "revoked", "invalid"}:
            preferences.clear_api_key(credential.provider)
            diagnostic["reason"] = "disabled"
            diagnostics.append(diagnostic)
            continue
        if credential.validation_status == "failed":
            preferences.clear_api_key(credential.provider)
            diagnostic["reason"] = "credential_invalid"
            diagnostics.append(diagnostic)
            continue
        if not ProviderCredentialService.encryption_available():
            diagnostic["reason"] = "encryption_key_missing"
            diagnostics.append(diagnostic)
            if require_key:
                raise ValueError(
                    "PROVIDER_CREDENTIAL_ENCRYPTION_KEY is required to hydrate active provider credentials."
                )
            continue
        try:
            api_key = credential_service.decrypt_api_key(credential)
        except ValueError:
            diagnostic["reason"] = "decrypt_failed"
            diagnostics.append(diagnostic)
            if require_key:
                raise
            continue

        preferences.set_api_key(api_key, provider_key=credential.provider)
        hydrated_providers.add(credential.provider)
        diagnostic["hydrated"] = True
        diagnostic["reason"] = "active"
        diagnostics.append(diagnostic)

    for item in diagnostics:
        logger.info(
            "Provider credential hydration provider=%s credential_id=%s label=%s hydrated=%s reason=%s",
            item["provider"],
            item["credential_id"],
            item["label"],
            item["hydrated"],
            item["reason"],
        )
    return diagnostics
