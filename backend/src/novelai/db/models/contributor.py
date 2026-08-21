"""Contributor credential and usage-ledger ORM models.

Contributor keys are deliberately separate from owner-managed provider
credentials.  The ledger contains accounting and routing metadata only; it
never contains prompts, provider responses, authorization headers, or key
material.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _credential_id() -> str:
    return uuid4().hex


class ContributorCredential(Base):
    """One encrypted provider credential owned by one authenticated user."""

    __tablename__ = "contributor_credentials"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "provider_key", name="uq_contributor_credentials_owner_provider"),
        Index("ix_contributor_credentials_status_provider", "status", "provider_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_credential_id)
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last4: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="invalid", index=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unchecked")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
        return f"<ContributorCredential id={self.id!r} provider={self.provider_key!r} status={self.status!r}>"


class ContributorUsageLedger(Base):
    """Sanitized provider accounting for contributor-backed requests."""

    __tablename__ = "contributor_usage_ledger"
    __table_args__ = (
        Index("ix_contributor_usage_ledger_credential_created", "credential_id", "created_at"),
        Index("ix_contributor_usage_ledger_owner_created", "credential_owner_user_id", "created_at"),
        Index("ix_contributor_usage_ledger_requesting_created", "requesting_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Deliberately not a foreign key: a permanent credential deletion must not
    # erase or orphan the historical accounting identity in this ledger.
    credential_id: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
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
        return f"<ContributorUsageLedger id={self.id} credential_id={self.credential_id!r} status={self.status!r}>"
