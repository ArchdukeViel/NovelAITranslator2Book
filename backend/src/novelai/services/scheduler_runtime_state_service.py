"""Scheduler runtime state persistence service (DEBT-036).

Persists scheduler cooldown, failure, exhausted, heartbeat, and next-eligible
state to the database so that scheduler health reflects real behavior and
state survives process restarts.

The existing file-based ``save_scheduler_state``/``load_scheduler_state`` in
``storage/traceability.py`` remains as an in-process cache for per-job model
state. This DB-backed service is the durable cross-restart store for
scheduler-level runtime state transitions.

Uses canonical identifiers: ``job_id``, ``source_key``, ``provider_key``,
``activity_id`` in metadata where applicable. No aliases are introduced.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.config.settings import settings
from novelai.db.models.scheduler_runtime_state import SchedulerRuntimeState

logger = logging.getLogger(__name__)

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_COOLDOWN = "cooldown"
STATE_EXHAUSTED = "exhausted"
STATE_FAILED = "failed"
STATE_DISABLED = "disabled"
STATE_STALE = "stale"
STATE_RECOVERED = "recovered"

_ACTIVE_STATES = frozenset({STATE_RUNNING, STATE_COOLDOWN, STATE_FAILED, STATE_DISABLED})


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SchedulerRuntimeStateService:
    """Durable scheduler runtime state persistence.

    All methods accept a SQLAlchemy ``Session`` for transactional safety.
    State writes are best-effort: failures are logged but must not crash
    user-facing jobs. Critical scheduler failures should still be persisted.
    """

    def __init__(self, session_scope_factory: Any | None = None) -> None:
        """Create the service.

        Args:
            session_scope_factory: A context manager that yields a SQLAlchemy
                ``Session``. If None, uses ``novelai.db.engine.session_scope``.
        """
        self._session_scope_factory = session_scope_factory

    def _session_scope(self):
        if self._session_scope_factory is not None:
            return self._session_scope_factory()
        from novelai.db.engine import session_scope
        return session_scope()

    def upsert_state(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
        state: str,
        reason: str | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
        cooldown_until: datetime | None = None,
        exhausted_until: datetime | None = None,
        next_eligible_at: datetime | None = None,
        locked_by: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert or update a runtime state record.

        Returns the persisted state as a dict.
        """
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=state,
                    reason=reason,
                    error_category=error_category,
                    error_message=error_message,
                    cooldown_until=cooldown_until,
                    exhausted_until=exhausted_until,
                    next_eligible_at=next_eligible_at,
                    heartbeat_at=now,
                    locked_by=locked_by,
                    metadata_json=json.dumps(metadata) if metadata else None,
                )
                session.add(existing)
            else:
                existing.state = state
                existing.reason = reason
                existing.error_category = error_category
                existing.error_message = error_message
                existing.cooldown_until = cooldown_until
                existing.exhausted_until = exhausted_until
                existing.next_eligible_at = next_eligible_at
                existing.heartbeat_at = now
                if locked_by is not None:
                    existing.locked_by = locked_by
                if metadata is not None:
                    existing.metadata_json = json.dumps(metadata)
            session.flush()
            return self._to_dict(existing)

    def mark_started(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
        locked_by: str | None = None,
    ) -> dict[str, Any]:
        """Record that a scheduler run has started."""
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=STATE_RUNNING,
                    last_started_at=now,
                    heartbeat_at=now,
                    locked_by=locked_by,
                )
                session.add(existing)
            else:
                existing.state = STATE_RUNNING
                existing.last_started_at = now
                existing.heartbeat_at = now
                if locked_by is not None:
                    existing.locked_by = locked_by
            session.flush()
            return self._to_dict(existing)

    def mark_success(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
    ) -> dict[str, Any]:
        """Record a successful scheduler run and clear active failure/cooldown state."""
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=STATE_IDLE,
                    last_success_at=now,
                    last_finished_at=now,
                    consecutive_failures=0,
                    heartbeat_at=now,
                )
                session.add(existing)
            else:
                existing.state = STATE_IDLE
                existing.last_success_at = now
                existing.last_finished_at = now
                existing.consecutive_failures = 0
                existing.error_category = None
                existing.error_message = None
                existing.cooldown_until = None
                existing.heartbeat_at = now
            session.flush()
            return self._to_dict(existing)

    def mark_failure(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
        error_category: str = "unknown",
        error_message: str | None = None,
        next_eligible_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Record a scheduler failure."""
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=STATE_FAILED,
                    error_category=error_category,
                    error_message=error_message,
                    failure_count=1,
                    consecutive_failures=1,
                    last_failure_at=now,
                    last_finished_at=now,
                    next_eligible_at=next_eligible_at,
                    heartbeat_at=now,
                )
                session.add(existing)
            else:
                existing.state = STATE_FAILED
                existing.error_category = error_category
                existing.error_message = error_message
                existing.failure_count = (existing.failure_count or 0) + 1
                existing.consecutive_failures = (existing.consecutive_failures or 0) + 1
                existing.last_failure_at = now
                existing.last_finished_at = now
                existing.next_eligible_at = next_eligible_at
                existing.heartbeat_at = now
            session.flush()
            return self._to_dict(existing)

    def mark_cooldown(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
        cooldown_until: datetime,
        reason: str | None = None,
        error_category: str | None = None,
    ) -> dict[str, Any]:
        """Record that a scope has entered cooldown."""
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=STATE_COOLDOWN,
                    reason=reason,
                    error_category=error_category,
                    cooldown_until=cooldown_until,
                    next_eligible_at=cooldown_until,
                    heartbeat_at=now,
                )
                session.add(existing)
            else:
                existing.state = STATE_COOLDOWN
                existing.reason = reason
                if error_category is not None:
                    existing.error_category = error_category
                existing.cooldown_until = cooldown_until
                existing.next_eligible_at = cooldown_until
                existing.heartbeat_at = now
            session.flush()
            return self._to_dict(existing)

    def mark_exhausted(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
        exhausted_until: datetime | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Record that a scope has no eligible work."""
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=STATE_EXHAUSTED,
                    reason=reason,
                    exhausted_until=exhausted_until,
                    next_eligible_at=exhausted_until,
                    heartbeat_at=now,
                )
                session.add(existing)
            else:
                existing.state = STATE_EXHAUSTED
                existing.reason = reason
                existing.exhausted_until = exhausted_until
                existing.next_eligible_at = exhausted_until
                existing.heartbeat_at = now
            session.flush()
            return self._to_dict(existing)

    def update_heartbeat(
        self,
        *,
        scheduler_key: str,
        scope_type: str,
        scope_key: str,
    ) -> dict[str, Any]:
        """Update the heartbeat timestamp for a scope."""
        with self._session_scope() as session:
            existing = self._find(session, scheduler_key, scope_type, scope_key)
            now = _utcnow()
            if existing is None:
                existing = SchedulerRuntimeState(
                    scheduler_key=scheduler_key,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    state=STATE_IDLE,
                    heartbeat_at=now,
                )
                session.add(existing)
            else:
                existing.heartbeat_at = now
            session.flush()
            return self._to_dict(existing)

    def list_runtime_states(
        self,
        *,
        scheduler_key: str | None = None,
        scope_type: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        """List runtime states with optional filters."""
        with self._session_scope() as session:
            stmt = select(SchedulerRuntimeState)
            if scheduler_key is not None:
                stmt = stmt.where(SchedulerRuntimeState.scheduler_key == scheduler_key)
            if scope_type is not None:
                stmt = stmt.where(SchedulerRuntimeState.scope_type == scope_type)
            if state is not None:
                stmt = stmt.where(SchedulerRuntimeState.state == state)
            stmt = stmt.order_by(SchedulerRuntimeState.updated_at.desc())
            results = session.execute(stmt).scalars().all()
            return [self._to_dict(r) for r in results]

    def get_scheduler_health_summary(self, *, scheduler_key: str | None = None) -> dict[str, Any]:
        """Return a health summary for scheduler health APIs.

        Computes stale state from heartbeat age. Does not expose secrets,
        stack traces, or raw error messages in the public-safe summary.
        """
        states = self.list_runtime_states(scheduler_key=scheduler_key)
        now = _utcnow()
        stale_threshold = timedelta(seconds=settings.SCHEDULER_STALE_AFTER_SECONDS)

        active_cooldowns = 0
        active_failures = 0
        exhausted_scopes = 0
        stale_scopes = 0
        runtime_states: list[dict[str, Any]] = []

        for s in states:
            heartbeat_at = s.get("heartbeat_at")
            is_stale = False
            if heartbeat_at is not None:
                hb = heartbeat_at
                if isinstance(hb, str):
                    pass
                else:
                    # Handle both offset-aware and offset-naive datetimes (SQLite).
                    now_cmp = now
                    if hb.tzinfo is None:
                        now_cmp = now.replace(tzinfo=None)
                    is_stale = (now_cmp - hb) > stale_threshold

            state_val = s.get("state", STATE_IDLE)
            if is_stale and state_val not in _ACTIVE_STATES:
                stale_scopes += 1
                state_val = STATE_STALE

            if state_val == STATE_COOLDOWN:
                active_cooldowns += 1
            elif state_val == STATE_FAILED:
                active_failures += 1
            elif state_val == STATE_EXHAUSTED:
                exhausted_scopes += 1

            runtime_states.append({
                "scheduler_key": s.get("scheduler_key"),
                "scope_type": s.get("scope_type"),
                "scope_key": s.get("scope_key"),
                "state": state_val,
                "reason": s.get("reason"),
                "error_category": s.get("error_category"),
                "next_eligible_at": _iso(s.get("next_eligible_at")),
                "consecutive_failures": s.get("consecutive_failures", 0),
                "last_attempt_at": _iso(s.get("last_attempt_at")),
                "heartbeat_at": _iso(s.get("heartbeat_at")),
            })

        if not states:
            overall = "unknown"
        elif active_failures > 0:
            overall = "unhealthy"
        elif stale_scopes > 0 or active_cooldowns > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "active_cooldowns": active_cooldowns,
            "active_failures": active_failures,
            "exhausted_scopes": exhausted_scopes,
            "stale_scopes": stale_scopes,
            "runtime_states": runtime_states,
        }

    def cleanup_expired_states(self, *, ttl_days: int | None = None) -> int:
        """Delete expired idle/recovered runtime states. Active states are preserved.

        Returns the count of deleted records.
        """
        ttl = ttl_days if ttl_days is not None else settings.SCHEDULER_RUNTIME_STATE_TTL_DAYS
        cutoff = _utcnow() - timedelta(days=ttl)
        with self._session_scope() as session:
            stmt = select(SchedulerRuntimeState).where(
                SchedulerRuntimeState.state.not_in(list(_ACTIVE_STATES)),
                SchedulerRuntimeState.updated_at < cutoff,
            )
            expired = session.execute(stmt).scalars().all()
            count = len(expired)
            for record in expired:
                session.delete(record)
            session.flush()
            if count > 0:
                logger.info("Cleanup: deleted %d expired scheduler runtime states (ttl=%dd).", count, ttl)
            return count

    def _find(self, session: Session, scheduler_key: str, scope_type: str, scope_key: str) -> SchedulerRuntimeState | None:
        stmt = select(SchedulerRuntimeState).where(
            SchedulerRuntimeState.scheduler_key == scheduler_key,
            SchedulerRuntimeState.scope_type == scope_type,
            SchedulerRuntimeState.scope_key == scope_key,
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _to_dict(record: SchedulerRuntimeState) -> dict[str, Any]:
        return {
            "id": record.id,
            "scheduler_key": record.scheduler_key,
            "scope_type": record.scope_type,
            "scope_key": record.scope_key,
            "state": record.state,
            "reason": record.reason,
            "error_category": record.error_category,
            "error_message": record.error_message,
            "failure_count": record.failure_count,
            "consecutive_failures": record.consecutive_failures,
            "last_attempt_at": record.last_attempt_at,
            "last_success_at": record.last_success_at,
            "last_failure_at": record.last_failure_at,
            "last_started_at": record.last_started_at,
            "last_finished_at": record.last_finished_at,
            "cooldown_until": record.cooldown_until,
            "exhausted_until": record.exhausted_until,
            "next_eligible_at": record.next_eligible_at,
            "heartbeat_at": record.heartbeat_at,
            "locked_by": record.locked_by,
            "metadata_json": record.metadata_json,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "expires_at": record.expires_at,
        }


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)
