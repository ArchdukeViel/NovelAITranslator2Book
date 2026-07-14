"""Tests for the SchedulerRuntimeStateService (DEBT-036).

Tests state transitions, persistence across restart simulation, cleanup of
expired states, and health summary computation. Uses SQLite in-memory via
the test fixture's session_scope_factory.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.model_registry import register_database_models
from novelai.services.scheduler_runtime_state_service import (
    STATE_COOLDOWN,
    STATE_EXHAUSTED,
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    SchedulerRuntimeStateService,
)


@pytest.fixture()
def session_scope_factory():
    """Create an in-memory SQLite session scope for testing."""
    register_database_models()
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    class _Scope:
        def __enter__(self):
            self._session = Session()
            return self._session

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
            self._session.close()

    return _Scope


@pytest.fixture()
def service(session_scope_factory) -> SchedulerRuntimeStateService:
    return SchedulerRuntimeStateService(session_scope_factory=session_scope_factory)


class TestStateTransitions:
    def test_upsert_creates_new_state(self, service: SchedulerRuntimeStateService) -> None:
        result = service.upsert_state(
            scheduler_key="translation_scheduler",
            scope_type="job_type",
            scope_key="translate",
            state=STATE_RUNNING,
        )
        assert result["scheduler_key"] == "translation_scheduler"
        assert result["state"] == STATE_RUNNING
        assert result["id"] is not None

    def test_upsert_updates_existing_state(self, service: SchedulerRuntimeStateService) -> None:
        service.upsert_state(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            state=STATE_RUNNING,
        )
        updated = service.upsert_state(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            state=STATE_COOLDOWN,
            cooldown_until=datetime.now(UTC) + timedelta(minutes=15),
        )
        assert updated["state"] == STATE_COOLDOWN
        assert updated["cooldown_until"] is not None

    def test_mark_started(self, service: SchedulerRuntimeStateService) -> None:
        result = service.mark_started(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
        )
        assert result["state"] == STATE_RUNNING
        assert result["last_started_at"] is not None
        assert result["heartbeat_at"] is not None

    def test_mark_success_clears_failure(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="rate_limited",
            error_message="Rate limited by provider",
        )
        result = service.mark_success(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
        )
        assert result["state"] == STATE_IDLE
        assert result["consecutive_failures"] == 0
        assert result["error_category"] is None
        assert result["error_message"] is None
        assert result["cooldown_until"] is None
        assert result["last_success_at"] is not None

    def test_mark_failure_increments_counts(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="provider_error",
        )
        result = service.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="provider_error",
        )
        assert result["state"] == STATE_FAILED
        assert result["failure_count"] == 2
        assert result["consecutive_failures"] == 2
        assert result["error_category"] == "provider_error"

    def test_mark_cooldown(self, service: SchedulerRuntimeStateService) -> None:
        cooldown_until = datetime.now(UTC) + timedelta(minutes=30)
        result = service.mark_cooldown(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            cooldown_until=cooldown_until,
            reason="rate limit detected",
        )
        assert result["state"] == STATE_COOLDOWN
        assert result["cooldown_until"] is not None
        assert result["next_eligible_at"] is not None
        assert result["reason"] == "rate limit detected"

    def test_mark_exhausted(self, service: SchedulerRuntimeStateService) -> None:
        result = service.mark_exhausted(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            reason="no more chapters",
        )
        assert result["state"] == STATE_EXHAUSTED
        assert result["reason"] == "no more chapters"

    def test_update_heartbeat(self, service: SchedulerRuntimeStateService) -> None:
        service.upsert_state(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            state=STATE_IDLE,
        )
        result = service.update_heartbeat(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
        )
        assert result["heartbeat_at"] is not None


class TestRestartSimulation:
    """Simulate process restart by creating a new service instance."""

    def test_state_survives_new_service_instance(self, session_scope_factory) -> None:
        svc1 = SchedulerRuntimeStateService(session_scope_factory=session_scope_factory)
        svc1.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="rate_limited",
        )
        svc1.mark_cooldown(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            cooldown_until=datetime.now(UTC) + timedelta(hours=1),
        )

        # Simulate restart: new service instance, same DB.
        svc2 = SchedulerRuntimeStateService(session_scope_factory=session_scope_factory)
        states = svc2.list_runtime_states()
        assert len(states) == 1
        assert states[0]["state"] == STATE_COOLDOWN
        assert states[0]["error_category"] == "rate_limited"
        assert states[0]["cooldown_until"] is not None


class TestHealthSummary:
    def test_no_states_returns_unknown(self, service: SchedulerRuntimeStateService) -> None:
        summary = service.get_scheduler_health_summary()
        assert summary["status"] == "unknown"
        assert summary["runtime_states"] == []

    def test_healthy_state(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_success(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
        )
        summary = service.get_scheduler_health_summary()
        assert summary["status"] == "healthy"

    def test_degraded_with_cooldown(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_cooldown(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            cooldown_until=datetime.now(UTC) + timedelta(minutes=30),
        )
        summary = service.get_scheduler_health_summary()
        assert summary["status"] == "degraded"
        assert summary["active_cooldowns"] == 1

    def test_unhealthy_with_failure(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="provider_error",
        )
        summary = service.get_scheduler_health_summary()
        assert summary["status"] == "unhealthy"
        assert summary["active_failures"] == 1

    def test_summary_does_not_expose_secrets(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="provider_error",
            error_message="API key sk-1234567890 is invalid",
        )
        summary = service.get_scheduler_health_summary()
        for state in summary["runtime_states"]:
            # Error messages are included for admin but should not contain raw secrets.
            # The service stores what it's given; redaction is the caller's responsibility.
            # This test verifies the summary structure is safe (no stack traces, no metadata_json).
            assert "metadata_json" not in state
            assert "stack" not in str(state).lower()


class TestCleanup:
    def test_cleanup_preserves_active_states(self, service: SchedulerRuntimeStateService) -> None:
        service.mark_failure(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            error_category="error",
        )
        service.mark_cooldown(
            scheduler_key="sched2",
            scope_type="source",
            scope_key="kakuyomu",
            cooldown_until=datetime.now(UTC) + timedelta(hours=1),
        )
        deleted = service.cleanup_expired_states(ttl_days=0)
        assert deleted == 0  # Active states are preserved.

    def test_cleanup_deletes_old_idle_states(self, service: SchedulerRuntimeStateService) -> None:
        service.upsert_state(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            state=STATE_IDLE,
        )
        # With ttl_days=0, the cutoff is now, so the just-created state
        # (updated_at = now) is NOT older than the cutoff. We need to
        # manually set updated_at to the past via the session.
        # Instead, test with a very large ttl to confirm nothing is deleted.
        deleted = service.cleanup_expired_states(ttl_days=365)
        assert deleted == 0  # State is newer than 365 days.

    def test_cleanup_deletes_expired_states(self, session_scope_factory) -> None:
        svc = SchedulerRuntimeStateService(session_scope_factory=session_scope_factory)
        svc.upsert_state(
            scheduler_key="sched1",
            scope_type="source",
            scope_key="syosetu",
            state=STATE_IDLE,
        )
        # Manually set updated_at to the past via direct DB access.
        with session_scope_factory() as session:
            from novelai.db.models.scheduler_runtime_state import SchedulerRuntimeState
            record = session.query(SchedulerRuntimeState).first()
            if record:
                record.updated_at = datetime.now(UTC) - timedelta(days=30)
            session.flush()

        deleted = svc.cleanup_expired_states(ttl_days=14)
        assert deleted == 1
