"""Backup scheduling and status service (M2c, DEBT-010).

Wraps BackupManager with scheduling integration, lock-based concurrency
prevention, verified offsite snapshots, and status reporting.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from novelai.config.settings import settings
from novelai.services.backup_manager import BackupManager
from novelai.storage.file_lock import InterProcessFileLock
from novelai.storage.snapshots import SnapshotTarget

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class BackupService:
    """High-level backup orchestration service.

    Provides scheduled backup execution, retention enforcement, and status
    reporting for health integration. Uses a multi-process file lock to
    prevent overlapping backup runs.
    """

    def __init__(
        self,
        backup_manager: BackupManager,
        snapshot_target: SnapshotTarget | None = None,
    ) -> None:
        self._backup_manager = backup_manager
        self._snapshot_target = snapshot_target
        self._lock_path = backup_manager.backups_dir / ".backup.lock"

    async def run_scheduled_backup(self, novel_id: str | None = None) -> dict[str, Any]:
        """Run a scheduled backup with lock-based concurrency prevention.

        Args:
            novel_id: If provided, back up only this novel. If None, backs up
                all novels with stored data.

        Returns:
            Summary dict with backup status.
        """
        lock = InterProcessFileLock(self._lock_path, retry_count=1, retry_delay=0.1)
        try:
            lock.acquire()
        except TimeoutError:
            logger.info("Scheduled backup skipped: another backup is already running.")
            return {
                "status": "skipped_locked",
                "timestamp": _utc_now_iso(),
            }

        started_at = _utc_now_iso()
        try:
            if settings.STORAGE_BACKEND.strip().lower() == "s3":
                if self._snapshot_target is None:
                    raise RuntimeError("Independent S3 snapshot target is not configured")
                snapshot = await asyncio.to_thread(self._snapshot_target.create_snapshot)
                return {
                    "status": "succeeded",
                    "backup_id": snapshot.snapshot_id,
                    "timestamp": snapshot.created_at,
                    "size_bytes": snapshot.size_bytes,
                    "files_count": snapshot.files_count,
                    "offsite": True,
                    "verified": snapshot.verified,
                    "started_at": started_at,
                    "finished_at": _utc_now_iso(),
                }

            # Resolve source directory from storage base.
            source_dir = self._backup_manager.base_dir / "novels"
            if novel_id and novel_id != "all":
                source_dir = source_dir / novel_id
            backup_info = await self._backup_manager.create_full_backup(
                novel_id or "all",
                source_dir,
            )
            result = {
                "status": "succeeded",
                "backup_id": backup_info.backup_id,
                "timestamp": backup_info.timestamp,
                "size_bytes": backup_info.size_bytes,
                "files_count": backup_info.files_count,
                "started_at": started_at,
                "finished_at": _utc_now_iso(),
            }

            # Run retention after successful backup.
            try:
                deleted = await self._backup_manager.apply_retention(
                    keep_count=settings.BACKUP_RETENTION_COUNT,
                    min_successful=settings.BACKUP_MIN_SUCCESSFUL_TO_KEEP,
                    max_age_days=settings.BACKUP_MAX_AGE_DAYS,
                )
                result["retention_deleted"] = deleted
            except Exception as exc:
                logger.warning("Backup retention cleanup failed: %s", exc)
                result["retention_error"] = str(exc)[:200]

            return result
        except Exception as exc:
            logger.error("Scheduled backup failed: %s", exc)
            return {
                "status": "failed",
                "error": str(exc)[:200],
                "started_at": started_at,
                "finished_at": _utc_now_iso(),
            }
        finally:
            lock.release()

    def get_status(self) -> dict[str, Any]:
        """Return backup status for health integration.

        Does not expose secrets, raw filesystem paths, or credentials.
        """
        return {
            "enabled": settings.BACKUP_ENABLED,
            "schedule": settings.BACKUP_SCHEDULE_CRON,
            "timezone": settings.BACKUP_TIMEZONE,
            "retention_count": settings.BACKUP_RETENTION_COUNT,
            "min_successful_to_keep": settings.BACKUP_MIN_SUCCESSFUL_TO_KEEP,
            "max_age_days": settings.BACKUP_MAX_AGE_DAYS,
            "offsite_enabled": self._snapshot_target is not None,
        }

    def get_backup_health(self) -> dict[str, Any]:
        """Return backup health signal for health probes.

        Returns:
            Dict with ``status`` (healthy/degraded/unhealthy), ``message``,
            and ``last_backup_at`` if available.
        """
        if not settings.BACKUP_ENABLED:
            return {
                "status": "degraded",
                "message": "Backups are not enabled",
            }

        if settings.STORAGE_BACKEND.strip().lower() == "s3":
            if self._snapshot_target is None:
                return {
                    "status": "unhealthy",
                    "message": "Independent S3 snapshot target is not configured",
                }
            try:
                latest = self._snapshot_target.latest_snapshot()
                if latest is None:
                    return {
                        "status": "unhealthy",
                        "message": "No committed offsite snapshot exists",
                    }
                return {
                    "status": "healthy" if latest.verified else "degraded",
                    "message": "Verified offsite snapshot exists",
                    "last_backup_at": latest.created_at,
                    "backup_id": latest.snapshot_id,
                }
            except Exception:
                return {
                    "status": "degraded",
                    "message": "Unable to determine offsite backup status",
                }

        try:
            backups = self._backup_manager.list_backups(None)
            if not backups:
                return {
                    "status": "unhealthy",
                    "message": "No successful backup exists",
                }

            newest = backups[0]
            return {
                "status": "healthy",
                "message": "Recent backup exists",
                "last_backup_at": newest.timestamp,
                "backup_id": newest.backup_id,
            }
        except Exception:
            return {
                "status": "degraded",
                "message": "Unable to determine backup status",
            }
