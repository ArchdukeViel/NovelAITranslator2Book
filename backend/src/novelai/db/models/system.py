"""System-level ORM models and the unified provider credential ledger.

AuditLog records every dangerous owner action for accountability.
SystemSetting is a key/value store for runtime configuration.
ProviderCredential and ProviderUsageLedger form the single credential and
accounting boundary for owner-managed and user-contributed provider keys.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    """An immutable audit record for owner/user actions.

    Written for every dangerous operation: content delete/unpublish,
    settings change, user management, credential actions.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} actor={self.actor_user_id}"
            f" action={self.action!r} target={self.target_type}/{self.target_id}>"
        )


class SystemSetting(Base):
    """A key/value store for runtime system configuration.

    Values are stored as JSON strings. Only the owner may write settings.
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )
    updated_by: Mapped[int | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<SystemSetting key={self.key!r}>"


class ScheduledJobLease(Base):
    """Expiring cross-process ownership record for scheduled work."""

    __tablename__ = "scheduled_job_leases"

    job_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    holder_id: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ProviderCredential(Base):
    """Unified encrypted provider credential registry.

    Every credential is stored once, tied to its authenticated owner when
    known, and carries independent owner-job and contributor-pool eligibility.
    Full keys are stored only as encrypted ciphertext. API responses expose
    safe metadata such as fingerprint and last4 only.
    """

    __tablename__ = "provider_credentials"
    __table_args__ = (
        Index("ix_provider_credentials_owner_provider", "credential_owner_user_id", "provider"),
        Index(
            "ix_provider_credentials_pool_status",
            "provider",
            "contributor_pool_eligible",
            "status",
            "last_used_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last4: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unchecked")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="owner_admin")
    owner_job_eligible: Mapped[bool] = mapped_column(nullable=False, default=True)
    contributor_pool_eligible: Mapped[bool] = mapped_column(nullable=False, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ProviderCredential id={self.id} provider={self.provider!r} "
            f"owner={self.credential_owner_user_id} status={self.status!r}>"
        )


class ProviderUsageLedger(Base):
    """Sanitized accounting for every credential-backed provider request."""

    __tablename__ = "contributor_usage_ledger"
    __table_args__ = (
        Index("ix_contributor_usage_ledger_credential_created", "credential_id", "created_at"),
        Index("ix_contributor_usage_ledger_owner_created", "credential_owner_user_id", "created_at"),
        Index("ix_contributor_usage_ledger_requesting_created", "requesting_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Deliberately not a foreign key: permanent credential deletion preserves
    # the historical accounting identity in this ledger.
    credential_id: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requesting_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contribution_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="contributor")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ProviderUsageLedger id={self.id} credential_id={self.credential_id!r} status={self.status!r}>"
