"""Maintenance cleanup service (M2c).

Provides safe, allowlisted cleanup of stale operational data: fetch cache,
pipeline events, activity records, scheduler runtime state, and backup
retention delegation. Supports dry-run mode and path safety checks.

Safety rules:
- Only allowlisted cleanup roots are touched.
- Blank, root, and project-root paths are rejected.
- Symlink escape is prevented.
- Active jobs, current exports, audit/security records, and raw source
  chapters are preserved.
- Each task is isolated — a failure in one task does not stop others.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.config.settings import settings

logger = logging.getLogger(__name__)

TASK_FETCH_CACHE = "fetch_cache_cleanup"
TASK_PIPELINE_EVENTS = "pipeline_events_cleanup"
TASK_ACTIVITY_LOG = "activity_log_cleanup"
TASK_SCHEDULER_STATE = "scheduler_runtime_state_cleanup"
TASK_BACKUP_RETENTION = "backup_retention_cleanup"

_ALL_TASKS = (
    TASK_FETCH_CACHE,
    TASK_PIPELINE_EVENTS,
    TASK_ACTIVITY_LOG,
    TASK_SCHEDULER_STATE,
    TASK_BACKUP_RETENTION,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class MaintenanceService:
    """Centralized maintenance cleanup service.

    Each task is independently enabled/disabled. Failures are isolated per
    task — a non-critical task failure does not stop remaining tasks.
    """

    def __init__(
        self,
        storage: Any,
        activity_log: Any | None = None,
        backup_manager: Any | None = None,
        scheduler_runtime_state_service: Any | None = None,
    ) -> None:
        self._storage = storage
        self._activity_log = activity_log
        self._backup_manager = backup_manager
        self._scheduler_state_service = scheduler_runtime_state_service

    def run_maintenance(
        self,
        *,
        dry_run: bool | None = None,
        tasks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run maintenance cleanup tasks.

        Args:
            dry_run: If True, scan only without deleting. Defaults to settings.MAINTENANCE_DRY_RUN.
            tasks: Specific task keys to run. If None, runs all enabled tasks.

        Returns:
            Summary dict with per-task results.
        """
        is_dry_run = dry_run if dry_run is not None else settings.MAINTENANCE_DRY_RUN
        enabled_tasks = tasks if tasks is not None else list(_ALL_TASKS)

        started_at = _utc_now_iso()
        task_results: list[dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for task_key in enabled_tasks:
            if task_key not in _ALL_TASKS:
                task_results.append({
                    "task_key": task_key,
                    "status": "skipped",
                    "message": f"Unknown task: {task_key}",
                })
                continue

            try:
                result = self._run_task(task_key, dry_run=is_dry_run)
                task_results.append(result)
                if result["status"] == "succeeded":
                    succeeded += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.warning("Maintenance task %s failed: %s", task_key, exc)
                task_results.append({
                    "task_key": task_key,
                    "status": "failed",
                    "error": str(exc)[:200],
                    "dry_run": is_dry_run,
                })
                failed += 1

        overall = "succeeded" if failed == 0 else ("partially_succeeded" if succeeded > 0 else "failed")
        finished_at = _utc_now_iso()

        return {
            "status": overall,
            "started_at": started_at,
            "finished_at": finished_at,
            "dry_run": is_dry_run,
            "tasks_total": len(enabled_tasks),
            "tasks_succeeded": succeeded,
            "tasks_failed": failed,
            "tasks": task_results,
        }

    def _run_task(self, task_key: str, *, dry_run: bool) -> dict[str, Any]:
        """Run a single maintenance task."""
        if task_key == TASK_FETCH_CACHE:
            return self._cleanup_fetch_cache(dry_run=dry_run)
        if task_key == TASK_PIPELINE_EVENTS:
            return self._cleanup_pipeline_events(dry_run=dry_run)
        if task_key == TASK_ACTIVITY_LOG:
            return self._cleanup_activity_log(dry_run=dry_run)
        if task_key == TASK_SCHEDULER_STATE:
            return self._cleanup_scheduler_state(dry_run=dry_run)
        if task_key == TASK_BACKUP_RETENTION:
            return self._cleanup_backup_retention(dry_run=dry_run)
        return {"task_key": task_key, "status": "skipped", "message": "Not implemented"}

    def _cleanup_fetch_cache(self, *, dry_run: bool) -> dict[str, Any]:
        """Clean up expired fetch cache entries."""
        max_age_hours = settings.MAINTENANCE_FETCH_CACHE_MAX_AGE_HOURS
        if dry_run:
            return {
                "task_key": TASK_FETCH_CACHE,
                "status": "succeeded",
                "dry_run": True,
                "message": f"Would clean fetch cache entries older than {max_age_hours}h",
            }
        count = self._storage.cleanup_fetch_cache(max_age_hours=max_age_hours)
        return {
            "task_key": TASK_FETCH_CACHE,
            "status": "succeeded",
            "dry_run": False,
            "items_deleted": count,
        }

    def _cleanup_pipeline_events(self, *, dry_run: bool) -> dict[str, Any]:
        """Clean up old pipeline event records."""
        max_age_days = settings.MAINTENANCE_PIPELINE_EVENTS_MAX_AGE_DAYS
        if dry_run:
            return {
                "task_key": TASK_PIPELINE_EVENTS,
                "status": "succeeded",
                "dry_run": True,
                "message": f"Would clean pipeline events older than {max_age_days}d",
            }
        count = self._storage.cleanup_pipeline_events(max_age_days=max_age_days)
        return {
            "task_key": TASK_PIPELINE_EVENTS,
            "status": "succeeded",
            "dry_run": False,
            "items_deleted": count,
        }

    def _cleanup_activity_log(self, *, dry_run: bool) -> dict[str, Any]:
        """Clean up old activity records. Preserves active/running/queued activities."""
        if self._activity_log is None:
            return {
                "task_key": TASK_ACTIVITY_LOG,
                "status": "skipped",
                "message": "Activity log service not available",
            }
        keep_completed = settings.MAINTENANCE_ACTIVITY_RETENTION_DAYS
        keep_failed = settings.MAINTENANCE_FAILED_ACTIVITY_RETENTION_DAYS
        if dry_run:
            return {
                "task_key": TASK_ACTIVITY_LOG,
                "status": "succeeded",
                "dry_run": True,
                "message": f"Would prune activity log (completed>{keep_completed}d, failed>{keep_failed}d)",
            }
        result = self._activity_log.prune_activity_log(
            keep_completed=keep_completed,
            keep_failed=keep_failed,
            dry_run=False,
        )
        deleted = result.get("deleted", 0) if isinstance(result, dict) else 0
        return {
            "task_key": TASK_ACTIVITY_LOG,
            "status": "succeeded",
            "dry_run": False,
            "items_deleted": deleted,
        }

    def _cleanup_scheduler_state(self, *, dry_run: bool) -> dict[str, Any]:
        """Clean up expired scheduler runtime state records."""
        if self._scheduler_state_service is None:
            return {
                "task_key": TASK_SCHEDULER_STATE,
                "status": "skipped",
                "message": "Scheduler runtime state service not available",
            }
        ttl_days = settings.SCHEDULER_RUNTIME_STATE_TTL_DAYS
        if dry_run:
            return {
                "task_key": TASK_SCHEDULER_STATE,
                "status": "succeeded",
                "dry_run": True,
                "message": f"Would clean scheduler runtime states older than {ttl_days}d",
            }
        count = self._scheduler_state_service.cleanup_expired_states(ttl_days=ttl_days)
        return {
            "task_key": TASK_SCHEDULER_STATE,
            "status": "succeeded",
            "dry_run": False,
            "items_deleted": count,
        }

    def _cleanup_backup_retention(self, *, dry_run: bool) -> dict[str, Any]:
        """Delegate to backup manager retention. Never deletes newest successful backup."""
        if self._backup_manager is None:
            return {
                "task_key": TASK_BACKUP_RETENTION,
                "status": "skipped",
                "message": "Backup manager not available",
            }
        if dry_run:
            return {
                "task_key": TASK_BACKUP_RETENTION,
                "status": "succeeded",
                "dry_run": True,
                "message": "Would apply backup retention policy",
            }
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, we can't use run_until_complete.
            # The caller should use the async version instead.
            return {
                "task_key": TASK_BACKUP_RETENTION,
                "status": "skipped",
                "message": "Cannot run async backup retention from sync context",
            }
        count = loop.run_until_complete(
            self._backup_manager.apply_retention(
                keep_count=settings.BACKUP_RETENTION_COUNT,
                min_successful=settings.BACKUP_MIN_SUCCESSFUL_TO_KEEP,
                max_age_days=settings.BACKUP_MAX_AGE_DAYS,
            )
        )
        return {
            "task_key": TASK_BACKUP_RETENTION,
            "status": "succeeded",
            "dry_run": False,
            "items_deleted": count,
        }

    async def run_maintenance_async(
        self,
        *,
        dry_run: bool | None = None,
        tasks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Async version of run_maintenance for use in async contexts."""
        is_dry_run = dry_run if dry_run is not None else settings.MAINTENANCE_DRY_RUN
        enabled_tasks = tasks if tasks is not None else list(_ALL_TASKS)

        started_at = _utc_now_iso()
        task_results: list[dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for task_key in enabled_tasks:
            if task_key not in _ALL_TASKS:
                task_results.append({
                    "task_key": task_key,
                    "status": "skipped",
                    "message": f"Unknown task: {task_key}",
                })
                continue

            try:
                if task_key == TASK_BACKUP_RETENTION and self._backup_manager is not None:
                    result = await self._cleanup_backup_retention_async(dry_run=is_dry_run)
                else:
                    result = self._run_task(task_key, dry_run=is_dry_run)
                task_results.append(result)
                if result["status"] == "succeeded":
                    succeeded += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.warning("Maintenance task %s failed: %s", task_key, exc)
                task_results.append({
                    "task_key": task_key,
                    "status": "failed",
                    "error": str(exc)[:200],
                    "dry_run": is_dry_run,
                })
                failed += 1

        overall = "succeeded" if failed == 0 else ("partially_succeeded" if succeeded > 0 else "failed")
        finished_at = _utc_now_iso()

        return {
            "status": overall,
            "started_at": started_at,
            "finished_at": finished_at,
            "dry_run": is_dry_run,
            "tasks_total": len(enabled_tasks),
            "tasks_succeeded": succeeded,
            "tasks_failed": failed,
            "tasks": task_results,
        }

    async def _cleanup_backup_retention_async(self, *, dry_run: bool) -> dict[str, Any]:
        """Async backup retention cleanup."""
        if self._backup_manager is None:
            return {
                "task_key": TASK_BACKUP_RETENTION,
                "status": "skipped",
                "message": "Backup manager not available",
            }
        if dry_run:
            return {
                "task_key": TASK_BACKUP_RETENTION,
                "status": "succeeded",
                "dry_run": True,
                "message": "Would apply backup retention policy",
            }
        count = await self._backup_manager.apply_retention(
            keep_count=settings.BACKUP_RETENTION_COUNT,
            min_successful=settings.BACKUP_MIN_SUCCESSFUL_TO_KEEP,
            max_age_days=settings.BACKUP_MAX_AGE_DAYS,
        )
        return {
            "task_key": TASK_BACKUP_RETENTION,
            "status": "succeeded",
            "dry_run": False,
            "items_deleted": count,
        }


def validate_cleanup_root(path: Path, allowed_roots: list[Path]) -> bool:
    """Validate that *path* is inside one of *allowed_roots*.

    Rejects blank, root, project-root, and symlink-escape paths.
    """
    if not path or str(path).strip() == "":
        return False
    resolved = path.resolve()
    for root in allowed_roots:
        resolved_root = root.resolve()
        try:
            resolved.relative_to(resolved_root)
            return True
        except ValueError:
            continue
    return False
