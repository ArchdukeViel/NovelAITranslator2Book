"""System-level ORM models: audit logs and settings.

AuditLog records every dangerous owner action for accountability.
SystemSetting is a key/value store for runtime configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        default=_utcnow, onupdate=_utcnow
    )
    updated_by: Mapped[int | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<SystemSetting key={self.key!r}>"


class ProviderCredential(Base):
    """Encrypted owner-managed provider API credential.

    Full keys are stored only as encrypted ciphertext. API responses expose
    safe metadata such as fingerprint and last4 only.
    """

    __tablename__ = "provider_credentials"
    __table_args__ = (UniqueConstraint("provider", name="uq_provider_credentials_provider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last4: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unchecked")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ProviderCredential id={self.id} provider={self.provider!r} active={self.is_active}>"
