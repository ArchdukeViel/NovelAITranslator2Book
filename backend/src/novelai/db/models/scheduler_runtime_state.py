"""Scheduler runtime state ORM model (DEBT-036).

Persists scheduler cooldown, failure, exhausted, heartbeat, and next-eligible
state so that scheduler health reflects real behavior and state survives
process restarts.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SchedulerRuntimeState(Base):
    """Durable scheduler runtime state for a scheduler/scope combination.

    Tracks cooldown, failure, exhausted, running, disabled, and recovered
    states so that scheduler health APIs report live behavior instead of only
    static configuration. State survives process restarts.

    Uses canonical identifiers: ``job_id``, ``source_key``, ``provider_key``,
    ``activity_id`` in the ``metadata_json`` field where applicable.
    """

    __tablename__ = "scheduler_runtime_states"
    __table_args__ = (
        UniqueConstraint("scheduler_key", "scope_type", "scope_key", name="uq_scheduler_runtime_states_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scheduler_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="idle", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exhausted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SchedulerRuntimeState id={self.id} scheduler={self.scheduler_key!r} scope={self.scope_type}:{self.scope_key!r} state={self.state!r}>"
