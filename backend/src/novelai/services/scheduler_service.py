"""Durable cron scheduling for backup and maintenance jobs."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter

from novelai.config.settings import settings
from novelai.services.scheduled_job_lease_service import ScheduledJobLeaseService

logger = logging.getLogger(__name__)
_CHECK_INTERVAL = 300


class SchedulerService:
    """Run each due cron job once across all application instances."""

    def __init__(
        self,
        backup_service: Any | None = None,
        maintenance_service: Any | None = None,
        database_backup_service: Any | None = None,
        operator_alert_service: Any | None = None,
        db_session_scope_factory: Any | None = None,
    ) -> None:
        self._backup_service = backup_service
        self._maintenance_service = maintenance_service
        self._database_backup_service = database_backup_service
        self._operator_alert_service = operator_alert_service
        self._session_scope_factory = db_session_scope_factory
        self._lease_service = (
            ScheduledJobLeaseService(db_session_scope_factory) if db_session_scope_factory is not None else None
        )
        self._holder_id = uuid.uuid4().hex
        self._task: asyncio.Task[None] | None = None
        self._ev = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._ev.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("SchedulerService background loop started.")

    async def stop(self) -> None:
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
        while not self._ev.is_set():
            try:
                jobs: list[tuple[bool, str, str, str, Callable[[], Awaitable[str]]]] = [
                    (
                        settings.BACKUP_ENABLED and self._backup_service is not None,
                        "backup",
                        settings.BACKUP_SCHEDULE_CRON,
                        settings.BACKUP_TIMEZONE,
                        self._run_backup,
                    ),
                    (
                        settings.MAINTENANCE_ENABLED and self._maintenance_service is not None,
                        "maintenance",
                        settings.MAINTENANCE_SCHEDULE_CRON,
                        settings.MAINTENANCE_TIMEZONE,
                        self._run_maintenance,
                    ),
                    (
                        settings.DATABASE_BACKUP_ENABLED and self._database_backup_service is not None,
                        "database_backup",
                        settings.DATABASE_BACKUP_SCHEDULE_CRON,
                        settings.DATABASE_BACKUP_TIMEZONE,
                        self._run_database_backup,
                    ),
                    (
                        settings.DATABASE_RESTORE_VERIFICATION_ENABLED
                        and self._database_backup_service is not None,
                        "database_restore_verify",
                        settings.DATABASE_RESTORE_VERIFICATION_SCHEDULE_CRON,
                        settings.DATABASE_RESTORE_VERIFICATION_TIMEZONE,
                        self._run_database_restore_verification,
                    ),
                ]
                for enabled, job_name, expression, timezone_name, runner in jobs:
                    if enabled and await self._is_due(job_name, expression, timezone_name):
                        await self._run_with_lease(job_name, runner)
                await self._check_backup_staleness()
                await asyncio.sleep(_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Scheduler loop error type=%s", exc.__class__.__name__)
                await asyncio.sleep(30)

    async def _latest_success(self, job_name: str) -> datetime | None:
        if self._session_scope_factory is None:
            return None
        scope_factory = self._session_scope_factory

        def _query() -> datetime | None:
            from sqlalchemy import text

            with scope_factory() as session:
                return session.execute(
                    text(
                        "SELECT max(started_at) FROM scheduled_cron_log "
                        "WHERE job_name LIKE :pattern AND status = 'succeeded'"
                    ),
                    {"pattern": f"{job_name}-%"},
                ).scalar_one_or_none()

        return await asyncio.to_thread(_query)

    async def _is_due(self, job_name: str, expression: str, timezone_name: str) -> bool:
        timezone = ZoneInfo(timezone_name)
        now = datetime.now(timezone)
        last_success = await self._latest_success(job_name)
        if last_success is None:
            return croniter(expression, now).get_prev(datetime) <= now
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=UTC)
        next_due = croniter(expression, last_success.astimezone(timezone)).get_next(datetime)
        return next_due <= now

    async def _run_with_lease(self, job_name: str, runner: Callable[[], Awaitable[str]]) -> None:
        if self._lease_service is None:
            try:
                status = await runner()
            except Exception as exc:
                logger.error("Scheduled job failed job=%s type=%s", job_name, exc.__class__.__name__)
                status = "failed"
            await self._record_run_result(job_name, status)
            return
        acquired = await asyncio.to_thread(
            self._lease_service.acquire,
            job_name,
            self._holder_id,
            settings.SCHEDULED_JOB_LEASE_SECONDS,
        )
        if not acquired:
            logger.info("Scheduled job skipped because another instance holds the lease job=%s", job_name)
            return
        heartbeat = asyncio.create_task(self._heartbeat(job_name))
        try:
            try:
                status = await runner()
            except Exception as exc:
                logger.error("Scheduled job failed job=%s type=%s", job_name, exc.__class__.__name__)
                status = "failed"
            await self._record_run_result(job_name, status)
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
            await asyncio.to_thread(self._lease_service.release, job_name, self._holder_id)

    async def _record_run_result(self, job_name: str, status: str) -> None:
        await self._log_run(job_name, status)
        alert_code = f"scheduled_{job_name}_failed"
        if status not in {"succeeded", "skipped_locked"}:
            await self._alert(alert_code, f"Scheduled {job_name} failed")
        elif self._operator_alert_service is not None and hasattr(self._operator_alert_service, "clear"):
            self._operator_alert_service.clear(alert_code)

    async def _heartbeat(self, job_name: str) -> None:
        lease_service = self._lease_service
        if lease_service is None:
            return
        interval = max(20, settings.SCHEDULED_JOB_LEASE_SECONDS // 3)
        while True:
            await asyncio.sleep(interval)
            renewed = await asyncio.to_thread(
                lease_service.renew,
                job_name,
                self._holder_id,
                settings.SCHEDULED_JOB_LEASE_SECONDS,
            )
            if not renewed:
                logger.error("Scheduled job lease expired job=%s", job_name)
                await self._alert("scheduled_lease_expired", f"Lease expired for {job_name}")
                return

    async def _log_run(self, job_name: str, status: str) -> None:
        if self._session_scope_factory is None:
            return
        scope_factory = self._session_scope_factory

        def _insert() -> None:
            from sqlalchemy import text

            with scope_factory() as session:
                session.execute(
                    text("INSERT INTO scheduled_cron_log (job_name, status) VALUES (:job_name, :status)"),
                    {"job_name": f"{job_name}-{datetime.now(UTC).date().isoformat()}", "status": status},
                )

        await asyncio.to_thread(_insert)

    async def _run_backup(self) -> str:
        if self._backup_service is None:
            return "failed"
        result = await self._backup_service.run_scheduled_backup()
        status = str(result.get("status", "failed"))
        return status if status in {"succeeded", "skipped_locked"} else "failed"

    async def _run_maintenance(self) -> str:
        if self._maintenance_service is None:
            return "failed"
        try:
            result = await self._maintenance_service.run_maintenance_async()
            return "succeeded" if result.get("status") in {"succeeded", "completed"} else "failed"
        except Exception:
            logger.exception("Scheduled maintenance failed")
            return "failed"

    async def _run_database_backup(self) -> str:
        if self._database_backup_service is None:
            return "failed"
        result = await asyncio.to_thread(self._database_backup_service.create_backup)
        return "succeeded" if result.get("status") == "succeeded" else "failed"

    async def _run_database_restore_verification(self) -> str:
        if self._database_backup_service is None:
            return "failed"
        result = await asyncio.to_thread(self._database_backup_service.verify_latest_restore)
        return "succeeded" if result.get("status") == "succeeded" else "failed"

    async def _alert(self, code: str, message: str) -> None:
        if self._operator_alert_service is not None:
            await asyncio.to_thread(self._operator_alert_service.send, code=code, message=message)

    async def _check_backup_staleness(self) -> None:
        checks = (
            ("r2_backup_stale", self._backup_service if settings.BACKUP_ENABLED else None),
            (
                "database_backup_stale",
                self._database_backup_service if settings.DATABASE_BACKUP_ENABLED else None,
            ),
        )
        cutoff = datetime.now(UTC) - timedelta(hours=settings.OPERATOR_ALERT_STALE_BACKUP_HOURS)
        for code, service in checks:
            if service is None or not hasattr(service, "get_backup_health"):
                continue
            health = await asyncio.to_thread(service.get_backup_health)
            last_backup_at = health.get("last_backup_at")
            stale = health.get("status") == "unhealthy" or not last_backup_at
            if last_backup_at:
                parsed = datetime.fromisoformat(str(last_backup_at).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                stale = parsed.astimezone(UTC) < cutoff
            if stale:
                await self._alert(code, str(health.get("message", "Backup is stale")))
            elif self._operator_alert_service is not None and hasattr(self._operator_alert_service, "clear"):
                self._operator_alert_service.clear(code)
