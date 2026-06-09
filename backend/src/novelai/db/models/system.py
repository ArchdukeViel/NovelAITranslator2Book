"""System-level ORM models: audit logs and settings.

AuditLog records every dangerous owner action for accountability.
SystemSetting is a key/value store for runtime configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, func
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
