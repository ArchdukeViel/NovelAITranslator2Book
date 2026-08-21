"""Authenticated contributor credential lifecycle and accounting service.

This service intentionally does not call ``ProviderCredentialService``.  Owner
credentials are global control-plane configuration; contributor credentials
are user-owned, provider-isolated, and eligible only for explicitly marked
contributor translation work.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
from novelai.db.models.contributor import ContributorCredential, ContributorUsageLedger
from novelai.providers.gemini_provider import GeminiProvider
from novelai.services.gemini_request_control import GeminiQuotaController, RedisGeminiQuotaController
from novelai.utils.hashing import digest32, hexdigest

logger = logging.getLogger(__name__)

CONTRIBUTOR_PROVIDER = "gemini"
VALID_STATUSES = frozenset({"active", "paused", "invalid", "revoked"})


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _bounded(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean[:limit] or None


def secret_fingerprint(secret: str) -> str:
    return hexdigest(secret, length=12)


def secret_last4(secret: str) -> str:
    return secret[-4:] if len(secret) >= 4 else secret


@dataclass(frozen=True)
class ContributorCredentialLease:
    """Runtime-only decrypted credential lease.

    The object must never be placed in pipeline metadata or serialized state.
    ``api_key`` exists only for the duration of a provider call.
    """

    credential_id: str
    credential_owner_user_id: int
    provider_key: str
    provider_model: str
    api_key: str
    quota_controller: GeminiQuotaController


class ContributorCredentialService:
    """Manage user-owned encrypted contributor credentials."""

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
            raise ValueError("PROVIDER_CREDENTIAL_ENCRYPTION_KEY is required for contributor credential storage.")
        return Fernet(base64.urlsafe_b64encode(digest32(secret.get_secret_value())))

    def _encrypt(self, api_key: str) -> str:
        clean = api_key.strip()
        if not clean:
            raise ValueError("API key must not be empty")
        if len(clean) > 4096:
            raise ValueError("API key is too long")
        return self._fernet().encrypt(clean.encode("utf-8")).decode("utf-8")

    def _decrypt(self, credential: ContributorCredential) -> str:
        if not credential.encrypted_api_key:
            raise ValueError("Contributor credential has no usable encrypted key.")
        try:
            return self._fernet().decrypt(credential.encrypted_api_key.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored contributor credential cannot be decrypted with the configured key.") from exc

    def list_for_user(self, owner_user_id: int) -> list[ContributorCredential]:
        return list(
            self.db.scalars(
                select(ContributorCredential)
                .where(ContributorCredential.owner_user_id == owner_user_id)
                .order_by(ContributorCredential.created_at)
            )
        )

    def list_all(self) -> list[ContributorCredential]:
        """List credentials for owner-only emergency review."""
        return list(self.db.scalars(select(ContributorCredential).order_by(ContributorCredential.created_at)))

    def get_owned(self, owner_user_id: int, credential_id: str) -> ContributorCredential | None:
        return self.db.scalar(
            select(ContributorCredential).where(
                ContributorCredential.id == credential_id,
                ContributorCredential.owner_user_id == owner_user_id,
            )
        )

    def get_any(self, credential_id: str) -> ContributorCredential | None:
        return self.db.get(ContributorCredential, credential_id)

    def replace_unvalidated(
        self,
        *,
        owner_user_id: int,
        provider_key: str,
        api_key: str,
        consent_version: str,
    ) -> tuple[ContributorCredential, str]:
        if not self.enabled():
            raise RuntimeError("Contributor credentials are disabled.")
        if provider_key != CONTRIBUTOR_PROVIDER:
            raise ValueError("Only Gemini contributor credentials are supported.")
        if consent_version != settings.CONTRIBUTOR_CONSENT_VERSION:
            raise ValueError("The current contributor consent version must be accepted.")
        clean = api_key.strip()
        encrypted = self._encrypt(clean)
        now = _utcnow()
        credential = self.db.scalar(
            select(ContributorCredential).where(
                ContributorCredential.owner_user_id == owner_user_id,
                ContributorCredential.provider_key == provider_key,
            )
        )
        if credential is not None and credential.status == "revoked":
            raise ValueError("Revoked contributor credentials cannot be replaced.")
        if credential is None:
            credential = ContributorCredential(
                owner_user_id=owner_user_id,
                provider_key=provider_key,
                provider_model=GEMINI_DEFAULT_MODEL,
                encrypted_api_key=encrypted,
                key_fingerprint=secret_fingerprint(clean),
                last4=secret_last4(clean),
                status="invalid",
                validation_status="unchecked",
                validation_message="Key validation is in progress.",
                consent_version=consent_version,
                created_at=now,
                updated_at=now,
            )
            self.db.add(credential)
        else:
            credential.provider_model = GEMINI_DEFAULT_MODEL
            credential.encrypted_api_key = encrypted
            credential.key_fingerprint = secret_fingerprint(clean)
            credential.last4 = secret_last4(clean)
            credential.status = "invalid"
            credential.validation_status = "unchecked"
            credential.validation_message = "Key validation is in progress."
            credential.consent_version = consent_version
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
            )
        quota_dir = settings.RUNTIME_DIR / "contributor_quota" / credential_id
        return GeminiQuotaController(
            quota_dir,
            rpm_limit=settings.CONTRIBUTOR_RPM_LIMIT,
            tpm_limit=settings.CONTRIBUTOR_TPM_LIMIT,
            rpd_limit=settings.CONTRIBUTOR_RPD_LIMIT,
            concurrency_limit=settings.CONTRIBUTOR_CONCURRENCY_LIMIT,
        )

    async def validate_and_activate(self, credential: ContributorCredential, api_key: str) -> tuple[bool, str]:
        """Validate a submitted key through Gemini without global hydration."""
        provider = GeminiProvider(
            api_key=api_key,
            quota_controller=self._quota_controller(credential.id),
        )
        ok, message = await provider.validate_connection(credential.provider_model)
        now = _utcnow()
        credential.last_validated_at = now
        credential.updated_at = now
        credential.validation_message = _bounded(message, 512)
        credential.validation_status = "valid" if ok else "failed"
        credential.status = "active" if ok else "invalid"
        if not ok:
            credential.failure_count += 1
            credential.last_failure_at = now
        self.db.add(
            ContributorUsageLedger(
                credential_id=credential.id,
                credential_owner_user_id=credential.owner_user_id,
                provider_key=credential.provider_key,
                provider_model=credential.provider_model,
                request_id=f"credential-validation:{credential.id}:{now.timestamp()}",
                contribution_mode="contributor_validation",
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

    def pause(self, credential: ContributorCredential) -> ContributorCredential:
        if credential.status == "revoked":
            raise ValueError("Revoked contributor credentials cannot be resumed.")
        credential.status = "paused"
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def resume(self, credential: ContributorCredential) -> ContributorCredential:
        if credential.status == "revoked":
            raise ValueError("Revoked contributor credentials cannot be resumed.")
        if credential.validation_status != "valid":
            raise ValueError("Only a successfully validated credential can be resumed.")
        credential.status = "active"
        credential.validation_message = "Credential is active and eligible for contributor translation work."
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def revoke(self, credential: ContributorCredential) -> ContributorCredential:
        credential.status = "revoked"
        credential.validation_status = "revoked"
        credential.validation_message = "Credential revoked by an owner."
        credential.revoked_at = _utcnow()
        credential.updated_at = _utcnow()
        self.db.flush()
        return credential

    def delete(self, credential: ContributorCredential) -> None:
        self.db.delete(credential)
        self.db.flush()

    def mark_unhealthy(self, credential_id: str, *, error_code: str) -> None:
        credential = self.get_any(credential_id)
        if credential is None or credential.status == "revoked":
            return
        credential.status = "paused"
        credential.validation_status = "failed"
        credential.validation_message = "Credential paused after a provider failure; validate it again before resuming."
        credential.failure_count += 1
        credential.last_failure_at = _utcnow()
        credential.updated_at = _utcnow()
        self.db.flush()
        logger.info("Contributor credential paused after provider failure code=%s", error_code)

    @staticmethod
    def mark_runtime_unhealthy(credential_id: str, *, error_code: str) -> None:
        """Pause a credential after a background provider failure."""
        try:
            from novelai.db.engine import session_scope

            with session_scope() as db:
                ContributorCredentialService(db).mark_unhealthy(credential_id, error_code=error_code)
        except Exception:
            logger.warning("Contributor credential health update failed", exc_info=True)

    @staticmethod
    def safe_response(credential: ContributorCredential) -> dict[str, Any]:
        return {
            "credential_id": credential.id,
            "provider": credential.provider_key,
            "provider_model": credential.provider_model,
            "last4": credential.last4,
            "fingerprint": credential.key_fingerprint,
            "status": credential.status if credential.status in VALID_STATUSES else "invalid",
            "validation_status": credential.validation_status,
            "validation_message": credential.validation_message,
            "consent_version": credential.consent_version,
            "created_at": _iso(credential.created_at),
            "updated_at": _iso(credential.updated_at),
            "last_validated_at": _iso(credential.last_validated_at),
            "last_used_at": _iso(credential.last_used_at),
            "failure_count": credential.failure_count,
        }

    @staticmethod
    def _usage_row(row: ContributorUsageLedger) -> dict[str, Any]:
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
        base = select(ContributorUsageLedger).where(ContributorUsageLedger.credential_id == credential_id)
        recent = list(
            self.db.scalars(
                base.where(ContributorUsageLedger.created_at >= day_cutoff)
                .order_by(ContributorUsageLedger.created_at.desc())
                .limit(100)
            )
        )
        minute_requests, minute_tokens = self.db.execute(
            select(
                func.count(ContributorUsageLedger.id),
                func.coalesce(func.sum(ContributorUsageLedger.total_tokens), 0),
            ).where(
                ContributorUsageLedger.credential_id == credential_id,
                ContributorUsageLedger.created_at >= minute_cutoff,
            )
        ).one()
        today_requests, today_tokens = self.db.execute(
            select(
                func.count(ContributorUsageLedger.id),
                func.coalesce(func.sum(ContributorUsageLedger.total_tokens), 0),
            ).where(
                ContributorUsageLedger.credential_id == credential_id,
                ContributorUsageLedger.created_at >= day_cutoff,
            )
        ).one()
        return {
            "credential_id": credential_id,
            "limits": {
                "requests_per_minute": settings.CONTRIBUTOR_RPM_LIMIT,
                "tokens_per_minute": settings.CONTRIBUTOR_TPM_LIMIT,
                "requests_per_day": settings.CONTRIBUTOR_RPD_LIMIT,
            },
            "current_minute": {
                "requests": int(minute_requests or 0),
                "tokens": int(minute_tokens or 0),
            },
            "today": {"requests": int(today_requests or 0), "tokens": int(today_tokens or 0)},
            "recent": [self._usage_row(row) for row in recent],
        }

    def cleanup_old_usage(
        self,
        *,
        ttl_days: int | None = None,
        batch_size: int = 500,
    ) -> int:
        """Delete expired sanitized ledger rows in bounded batches."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        cutoff = _utcnow() - timedelta(days=ttl_days or settings.CONTRIBUTOR_USAGE_RETENTION_DAYS)
        deleted = 0
        while True:
            ids = self.db.scalars(
                select(ContributorUsageLedger.id)
                .where(ContributorUsageLedger.created_at < cutoff)
                .order_by(ContributorUsageLedger.id)
                .limit(batch_size)
            ).all()
            if not ids:
                return deleted
            self.db.execute(delete(ContributorUsageLedger).where(ContributorUsageLedger.id.in_(ids)))
            self.db.flush()
            deleted += len(ids)

    @staticmethod
    def record_usage(
        *,
        credential_id: str,
        credential_owner_user_id: int,
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
    ) -> None:
        """Persist only sanitized accounting metadata in an isolated transaction."""
        try:
            from novelai.db.engine import session_scope

            total = total_tokens if isinstance(total_tokens, int) else None
            estimate_total = (estimated_input_tokens or 0) + (estimated_output_tokens or 0)
            with session_scope() as db:
                db.add(
                    ContributorUsageLedger(
                        credential_id=credential_id,
                        credential_owner_user_id=credential_owner_user_id,
                        requesting_user_id=requesting_user_id,
                        provider_key=provider_key,
                        provider_model=provider_model,
                        request_id=_bounded(request_id, 255),
                        job_id=_bounded(job_id, 255),
                        activity_id=_bounded(activity_id, 255),
                        contribution_mode="contributor",
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
            logger.warning("Contributor usage ledger write failed", exc_info=True)

    @staticmethod
    def acquire_runtime_lease(
        *,
        provider_key: str,
        provider_model: str | None,
        requesting_user_id: int | None,
    ) -> ContributorCredentialLease | None:
        """Select/decrypt one eligible credential for an explicit contributor run."""
        if not settings.CONTRIBUTOR_CREDENTIALS_ENABLED or provider_key != CONTRIBUTOR_PROVIDER:
            return None
        try:
            from novelai.db.engine import session_scope

            with session_scope() as db:
                service = ContributorCredentialService(db)
                credential = db.scalar(
                    select(ContributorCredential)
                    .where(
                        ContributorCredential.provider_key == provider_key,
                        ContributorCredential.status == "active",
                        ContributorCredential.validation_status == "valid",
                    )
                    .order_by(ContributorCredential.last_used_at.is_(None).desc(), ContributorCredential.last_used_at)
                )
                if credential is None:
                    return None
                api_key = service._decrypt(credential)
                credential.last_used_at = _utcnow()
                credential.updated_at = _utcnow()
                db.flush()
                return ContributorCredentialLease(
                    credential_id=credential.id,
                    credential_owner_user_id=credential.owner_user_id,
                    provider_key=credential.provider_key,
                    provider_model=provider_model or credential.provider_model,
                    api_key=api_key,
                    quota_controller=service._quota_controller(credential.id),
                )
        except Exception as exc:
            logger.warning("Contributor credential selection failed (%s)", type(exc).__name__)
            return None
