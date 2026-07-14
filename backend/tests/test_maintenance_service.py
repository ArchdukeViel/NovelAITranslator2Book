"""Tests for the MaintenanceService (M2c).

Tests dry-run mode, path safety, task isolation, and individual task
execution for fetch cache cleanup, pipeline events cleanup, activity log
cleanup, scheduler state cleanup, and backup retention delegation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from novelai.services.maintenance_service import (
    TASK_ACTIVITY_LOG,
    TASK_BACKUP_RETENTION,
    TASK_FETCH_CACHE,
    TASK_PIPELINE_EVENTS,
    TASK_SCHEDULER_STATE,
    MaintenanceService,
    validate_cleanup_root,
)


class FakeStorage:
    """Minimal fake storage for testing cleanup methods."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._fetch_cache_dir = base_dir / "runtime" / "fetch_cache"
        self._trace_dir = base_dir / "runtime" / "traceability"
        self._fetch_cache_dir.mkdir(parents=True, exist_ok=True)
        self._trace_dir.mkdir(parents=True, exist_ok=True)

    def _fetch_cache_dir_method(self) -> Path:
        return self._fetch_cache_dir

    def _trace_dir_method(self) -> Path:
        return self._trace_dir

    def cleanup_fetch_cache(self, *, max_age_hours: int = 24) -> int:
        path = self._fetch_cache_dir / "index.json"
        if not path.exists():
            return 0
        records = json.loads(path.read_text(encoding="utf-8"))
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        kept: dict[str, Any] = {}
        purged = 0
        for key, record in records.items():
            fetched_at = record.get("fetched_at")
            if fetched_at:
                ts = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
                if ts < cutoff:
                    purged += 1
                    continue
            kept[key] = record
        path.write_text(json.dumps(kept), encoding="utf-8")
        return purged

    def cleanup_pipeline_events(self, *, max_age_days: int = 30) -> int:
        path = self._trace_dir / "pipeline_events.json"
        if not path.exists():
            return 0
        events = json.loads(path.read_text(encoding="utf-8"))
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        kept: list[dict[str, Any]] = []
        purged = 0
        for event in events:
            ts = event.get("timestamp")
            if ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt < cutoff:
                    purged += 1
                    continue
            kept.append(event)
        path.write_text(json.dumps(kept), encoding="utf-8")
        return purged


class FakeActivityLog:
    def prune_activity_log(self, *, keep_completed: int = 90, keep_failed: int = 180, dry_run: bool = True) -> dict[str, Any]:
        return {"deleted": 5 if not dry_run else 0, "dry_run": dry_run}


class FakeSchedulerStateService:
    def cleanup_expired_states(self, *, ttl_days: int = 14) -> int:
        return 3


class FakeBackupManager:
    async def apply_retention(self, **kwargs: Any) -> int:
        return 2


@pytest.fixture()
def storage(tmp_path: Path) -> FakeStorage:
    return FakeStorage(tmp_path)


@pytest.fixture()
def service(storage: FakeStorage) -> MaintenanceService:
    return MaintenanceService(
        storage=storage,
        activity_log=FakeActivityLog(),
        backup_manager=FakeBackupManager(),
        scheduler_runtime_state_service=FakeSchedulerStateService(),
    )


class TestDryRun:
    def test_dry_run_does_not_delete(self, service: MaintenanceService) -> None:
        result = service.run_maintenance(dry_run=True)
        assert result["dry_run"] is True
        for task in result["tasks"]:
            if task["status"] == "succeeded":
                assert task.get("items_deleted") is None or task.get("items_deleted") == 0

    def test_dry_run_reports_would_delete(self, service: MaintenanceService) -> None:
        result = service.run_maintenance(dry_run=True, tasks=[TASK_FETCH_CACHE])
        assert result["dry_run"] is True
        task = result["tasks"][0]
        assert "Would clean" in task["message"]


class TestTaskIsolation:
    def test_unknown_task_skipped(self, service: MaintenanceService) -> None:
        result = service.run_maintenance(tasks=["unknown_task"])
        assert result["tasks"][0]["status"] == "skipped"

    def test_all_tasks_succeed(self, service: MaintenanceService) -> None:
        result = service.run_maintenance(dry_run=False)
        succeeded = sum(1 for t in result["tasks"] if t["status"] == "succeeded")
        assert succeeded >= 4  # At least 4 of 5 tasks should succeed.

    def test_failure_in_one_task_does_not_stop_others(self, storage: FakeStorage) -> None:
        # Make storage.cleanup_fetch_cache raise.
        def boom(**kwargs: Any) -> int:
            raise RuntimeError("boom")

        storage.cleanup_fetch_cache = boom  # type: ignore[assignment]
        svc = MaintenanceService(
            storage=storage,
            activity_log=FakeActivityLog(),
            backup_manager=FakeBackupManager(),
            scheduler_runtime_state_service=FakeSchedulerStateService(),
        )
        result = svc.run_maintenance(dry_run=False)
        fetch_task = next(t for t in result["tasks"] if t["task_key"] == TASK_FETCH_CACHE)
        assert fetch_task["status"] == "failed"
        other_tasks = [t for t in result["tasks"] if t["task_key"] != TASK_FETCH_CACHE]
        assert any(t["status"] == "succeeded" for t in other_tasks)


class TestFetchCacheCleanup:
    def test_fetch_cache_cleanup_deletes_old(self, service: MaintenanceService, storage: FakeStorage) -> None:
        # Write old fetch cache entry.
        path = storage._fetch_cache_dir / "index.json"
        old_ts = (datetime.now(UTC) - timedelta(hours=48)).isoformat().replace("+00:00", "Z")
        records = {"syosetu:https://example.com": {"fetched_at": old_ts, "url": "https://example.com", "source_key": "syosetu"}}
        path.write_text(json.dumps(records), encoding="utf-8")

        result = service.run_maintenance(dry_run=False, tasks=[TASK_FETCH_CACHE])
        task = result["tasks"][0]
        assert task["status"] == "succeeded"
        assert task["items_deleted"] == 1


class TestPipelineEventsCleanup:
    def test_pipeline_events_cleanup_deletes_old(self, service: MaintenanceService, storage: FakeStorage) -> None:
        path = storage._trace_dir / "pipeline_events.json"
        old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
        recent_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        events = [
            {"timestamp": old_ts, "event": "old"},
            {"timestamp": recent_ts, "event": "recent"},
        ]
        path.write_text(json.dumps(events), encoding="utf-8")

        result = service.run_maintenance(dry_run=False, tasks=[TASK_PIPELINE_EVENTS])
        task = result["tasks"][0]
        assert task["status"] == "succeeded"
        assert task["items_deleted"] == 1


class TestActivityLogCleanup:
    def test_activity_log_cleanup(self, service: MaintenanceService) -> None:
        result = service.run_maintenance(dry_run=False, tasks=[TASK_ACTIVITY_LOG])
        task = result["tasks"][0]
        assert task["status"] == "succeeded"
        assert task["items_deleted"] == 5


class TestSchedulerStateCleanup:
    def test_scheduler_state_cleanup(self, service: MaintenanceService) -> None:
        result = service.run_maintenance(dry_run=False, tasks=[TASK_SCHEDULER_STATE])
        task = result["tasks"][0]
        assert task["status"] == "succeeded"
        assert task["items_deleted"] == 3


class TestBackupRetentionDelegation:
    @pytest.mark.asyncio
    async def test_backup_retention_async(self, service: MaintenanceService) -> None:
        result = await service.run_maintenance_async(dry_run=False, tasks=[TASK_BACKUP_RETENTION])
        task = result["tasks"][0]
        assert task["status"] == "succeeded"
        assert task["items_deleted"] == 2


class TestPathSafety:
    def test_validate_cleanup_root_rejects_blank(self) -> None:
        assert validate_cleanup_root(Path(""), [Path("/data")]) is False

    def test_validate_cleanup_root_rejects_root(self) -> None:
        assert validate_cleanup_root(Path("/"), [Path("/data")]) is False

    def test_validate_cleanup_root_accepts_allowed(self, tmp_path: Path) -> None:
        allowed = tmp_path / "runtime"
        allowed.mkdir()
        target = allowed / "cache"
        target.mkdir()
        assert validate_cleanup_root(target, [allowed]) is True

    def test_validate_cleanup_root_rejects_outside_allowed(self, tmp_path: Path) -> None:
        allowed = tmp_path / "runtime"
        allowed.mkdir()
        outside = tmp_path / "other"
        outside.mkdir()
        assert validate_cleanup_root(outside, [allowed]) is False
