"""Durable activity records used by crawl and translation workers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ActivityRecord(Base):
    """One durable unit of work and its renewable worker lease.

    ``metadata_json`` contains sanitized activity progress and result data.
    Provider prompts, raw credentials, authorization headers, and provider
    responses must never be placed in it.
    """

    __tablename__ = "activity_records"
    __table_args__ = (
        Index("ix_activity_records_status_type_created", "status", "type", "created_at"),
        Index("ix_activity_records_novel_status_created", "novel_id", "status", "created_at"),
        Index("ix_activity_records_lease_expires", "lease_expires_at"),
        Index("ix_activity_records_idempotency_status", "idempotency_key", "status"),
        UniqueConstraint("idempotency_key", name="uq_activity_records_idempotency_key"),
    )

    activity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    novel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chapters: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )
    lease_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ActivityRecord id={self.activity_id!r} type={self.type!r} status={self.status!r}>"
