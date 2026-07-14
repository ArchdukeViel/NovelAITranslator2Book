"""Scheduling support for backup and maintenance jobs (M2c).

Uses a lightweight periodic asyncio loop to check ``scheduled_cron_log``
for pending work.  ``pg_cron`` handles DB-native cleanup (scheduler runtime
states).  This service handles backup and file-based maintenance, logging
results back to ``scheduled_cron_log`` for cross-restart observability.

Jobs are idempotent and use file locks to prevent overlapping execution.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from novelai.config.settings import settings

logger = logging.getLogger(__name__)

_CHECK_INTERVAL = 300  # seconds (5 minutes)


class SchedulerService:
    """Lightweight scheduler for backup and maintenance recurring jobs.

    A single background task periodically checks whether backup or maintenance
    should run, then fires them.  Scheduling decisions are durable: the
    ``scheduled_cron_log`` table in PostgreSQL tracks when each job last ran.
    """

    def __init__(
        self,
        backup_service: Any | None = None,
        maintenance_service: Any | None = None,
        db_session_scope_factory: Any | None = None,
    ) -> None:
        self._backup_service = backup_service
        self._maintenance_service = maintenance_service
        self._session_scope_factory = db_session_scope_factory
        self._task: asyncio.Task[None] | None = None
        self._ev = asyncio.Event()

    def start(self) -> None:
        """Start the background scheduling loop."""
        if self._task is not None:
            return
        self._ev.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("SchedulerService background loop started.")

    async def stop(self) -> None:
        """Stop the background scheduling loop."""
        if self._task is not None:
            self._ev.set()
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            logger.info("SchedulerService background loop stopped.")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        """Periodic loop: check if backup or maintenance should run."""
        _last_backup_check = ""
        _last_maintenance_check = ""
        while not self._ev.is_set():
            try:
                if settings.BACKUP_ENABLED and self._backup_service is not None:
                    today_key = datetime.now(UTC).strftime("%Y-%m-%d")
                    if _last_backup_check != today_key:
                        already_ran = await self._check_log("backup", today_key)
                        if not already_ran:
                            logger.info("Backup check: no backup found for %s — starting.", today_key)
                            await self._run_backup()
                            await self._log_run("backup", today_key, "succeeded")
                        else:
                            logger.debug("Backup check: already ran for %s.", today_key)
                        _last_backup_check = today_key

                if settings.MAINTENANCE_ENABLED and self._maintenance_service is not None:
                    today_key = datetime.now(UTC).strftime("%Y-%m-%d")
                    if _last_maintenance_check != today_key:
                        already_ran = await self._check_log("maintenance", today_key)
                        if not already_ran:
                            logger.info("Maintenance check: no run found for %s — starting.", today_key)
                            await self._run_maintenance()
                            await self._log_run("maintenance", today_key, "succeeded")
                        else:
                            logger.debug("Maintenance check: already ran for %s.", today_key)
                        _last_maintenance_check = today_key

                await asyncio.sleep(_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)
                await asyncio.sleep(30)

    async def _check_log(self, job_type: str, day_key: str) -> bool:
        """Check scheduled_cron_log for a successful run today."""
        if self._session_scope_factory is None:
            return False
        try:
            loop = asyncio.get_running_loop()
            scope_factory = self._session_scope_factory

            def _query() -> bool:
                assert scope_factory is not None  # pyright narrow
                with scope_factory() as session:
                    from sqlalchemy import text
                    stmt = text("""
                        SELECT 1 FROM scheduled_cron_log
                        WHERE job_name LIKE :pattern
                          AND status = 'succeeded'
                          AND started_at::date = CURRENT_DATE
                        LIMIT 1
                    """)
                    result = session.execute(stmt, {"pattern": f"{job_type}%"})
                    return result.scalar() is not None
            return await loop.run_in_executor(None, _query)
        except Exception:
            logger.warning("Could not check scheduled_cron_log (DB may be unavailable).")
            return False

    async def _log_run(self, job_type: str, day_key: str, status: str) -> None:
        """Record a run in scheduled_cron_log."""
        if self._session_scope_factory is None:
            return
        try:
            loop = asyncio.get_running_loop()
            scope_factory = self._session_scope_factory

            def _insert() -> None:
                assert scope_factory is not None  # pyright narrow
                with scope_factory() as session:
                    from sqlalchemy import text
                    session.execute(
                        text("""
                            INSERT INTO scheduled_cron_log (job_name, status)
                            VALUES (:job_name, :status)
                        """),
                        {"job_name": f"{job_type}-{day_key}", "status": status},
                    )
                    session.commit()
            await loop.run_in_executor(None, _insert)
        except Exception:
            logger.warning("Could not write to scheduled_cron_log.")

    async def _run_backup(self) -> None:
        """Execute a scheduled backup run."""
        if self._backup_service is None:
            return
        svc = self._backup_service
        try:
            result = await svc.run_scheduled_backup()
            logger.info("Scheduled backup result: %s", result.get("status", "unknown"))
        except Exception as exc:
            logger.error("Scheduled backup failed: %s", exc)

    async def _run_maintenance(self) -> None:
        """Execute a scheduled maintenance run."""
        if self._maintenance_service is None:
            return
        svc = self._maintenance_service
        try:
            result = await svc.run_maintenance_async()
            logger.info("Scheduled maintenance result: %s", result.get("status", "unknown"))
        except Exception as exc:
            logger.error("Scheduled maintenance failed: %s", exc)
