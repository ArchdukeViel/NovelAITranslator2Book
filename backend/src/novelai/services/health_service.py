"""Health probe service (M2a, DEBT-001).

Provides bounded, redacted health probes for database, storage, worker,
disk, and migrations. Probes are isolated — a failed probe does not stop
unrelated probes. Public responses never expose credentials, hostnames,
paths, stack traces, raw exceptions, bucket names, or signed URLs.

Probe states: ``healthy``, ``degraded``, ``unhealthy``.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.config.settings import settings

logger = logging.getLogger(__name__)

STATE_HEALTHY = "healthy"
STATE_DEGRADED = "degraded"
STATE_UNHEALTHY = "unhealthy"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class HealthService:
    """Bounded health probe service for liveness, readiness, and admin diagnostics.

    All probes are bounded by ``HEALTH_PROBE_TIMEOUT_MS`` per probe and
    ``HEALTH_TOTAL_TIMEOUT_MS`` for the total request. Probe failures are
    isolated — a failed probe returns ``unhealthy`` but does not stop other
    probes from running.
    """

    def __init__(
        self,
        storage: Any | None = None,
        activity_runner: Any | None = None,
        db_session_factory: Any | None = None,
        backup_service: Any | None = None,
        database_backup_service: Any | None = None,
        operator_alert_service: Any | None = None,
    ) -> None:
        self._storage = storage
        self._activity_runner = activity_runner
        self._db_session_factory = db_session_factory
        self._backup_service = backup_service
        self._database_backup_service = database_backup_service
        self._operator_alert_service = operator_alert_service
        self._cache: dict[str, Any] = {}
        self._cache_timestamp: float = 0.0

    def liveness(self) -> dict[str, Any]:
        """Process-only liveness check. No DB/storage/worker calls.

        Always returns 200 with status, service, and timestamp.
        """
        return {
            "status": "ok",
            "service": "novelai",
            "timestamp": _utc_now_iso(),
        }

    async def readiness(self) -> dict[str, Any]:
        """Public-safe readiness check. Probes DB, storage, worker, disk.

        Returns 200 if all probes are healthy or degraded.
        Returns 503 if any probe is unhealthy.
        Never exposes credentials, paths, hostnames, or stack traces.
        """
        results = await self._run_probes()
        overall = self._aggregate_status(results)

        return {
            "status": overall,
            "service": "novelai",
            "timestamp": _utc_now_iso(),
            "checks": self._public_safe_checks(results),
        }

    async def admin_health(self) -> dict[str, Any]:
        """Owner-only detailed health diagnostics. Still redacted.

        Includes probe status, latency, safe messages, and checked timestamp.
        Does not expose raw exceptions, stack traces, credentials, or paths.
        """
        results = await self._run_probes(include_recovery=True)
        overall = self._aggregate_status(results)

        return {
            "status": overall,
            "service": "novelai",
            "timestamp": _utc_now_iso(),
            "checks": self._admin_safe_checks(results),
        }

    async def _run_probes(self, *, include_recovery: bool = False) -> dict[str, dict[str, Any]]:
        """Run all probes with per-probe and total timeout bounds."""
        probe_timeout = settings.HEALTH_PROBE_TIMEOUT_MS / 1000.0
        total_timeout = settings.HEALTH_TOTAL_TIMEOUT_MS / 1000.0

        probes = {
            "database": self._probe_database,
            "storage": self._probe_storage,
            "worker": self._probe_worker,
            "disk": self._probe_disk,
            "storage_usage": self._probe_storage_usage,
        }
        if include_recovery:
            probes.update(
                {
                    "object_snapshot": self._probe_object_snapshot,
                    "database_backup": self._probe_database_backup,
                    "database_restore_verification": self._probe_database_restore_verification,
                }
            )

        results: dict[str, dict[str, Any]] = {}

        async def run_probe(name: str, probe: Any) -> tuple[str, dict[str, Any]]:
            try:
                result = await asyncio.wait_for(probe(), timeout=probe_timeout)
                return name, result
            except TimeoutError:
                return name, {
                    "status": STATE_UNHEALTHY,
                    "message": "Probe timed out",
                    "latency_ms": int(probe_timeout * 1000),
                }
            except Exception as exc:
                logger.debug("Health probe %s failed: %s", name, exc)
                return name, {
                    "status": STATE_UNHEALTHY,
                    "message": "Probe failed",
                    "error_type": type(exc).__name__,
                    "latency_ms": 0,
                }

        try:
            completed = await asyncio.wait_for(
                asyncio.gather(*[run_probe(name, probe) for name, probe in probes.items()]),
                timeout=total_timeout,
            )
            for name, result in completed:
                results[name] = result
        except TimeoutError:
            for name in probes:
                if name not in results:
                    results[name] = {
                        "status": STATE_UNHEALTHY,
                        "message": "Total timeout exceeded",
                    }

        return results

    async def _probe_database(self) -> dict[str, Any]:
        """Probe database connectivity with SELECT 1."""
        start = time.monotonic()
        if not settings.DATABASE_URL:
            return {
                "status": STATE_DEGRADED,
                "message": "Database not configured",
                "latency_ms": 0,
            }
        try:
            if self._db_session_factory is not None:
                session = self._db_session_factory()
                try:
                    session.execute(
                        type(session).bind.text("SELECT 1") if hasattr(type(session).bind, "text") else None
                    )
                finally:
                    session.close()
            else:
                from sqlalchemy import text

                from novelai.db.engine import get_sessionmaker

                SM = get_sessionmaker()
                session = SM()
                try:
                    session.execute(text("SELECT 1"))
                    session.commit()
                finally:
                    session.close()
            latency = int((time.monotonic() - start) * 1000)
            if self._operator_alert_service is not None:
                self._operator_alert_service.clear("database_connectivity_failed")
                self._operator_alert_service.clear("database_pool_timeout")
            return {
                "status": STATE_HEALTHY,
                "message": "Database responsive",
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            if self._operator_alert_service is not None:
                code = (
                    "database_pool_timeout"
                    if exc.__class__.__name__ == "TimeoutError"
                    else "database_connectivity_failed"
                )
                await asyncio.to_thread(
                    self._operator_alert_service.send,
                    code=code,
                    message="Database readiness probe failed",
                )
            return {
                "status": STATE_UNHEALTHY,
                "message": "Database probe failed",
                "error_type": type(exc).__name__,
                "latency_ms": latency,
            }

    async def _probe_storage(self) -> dict[str, Any]:
        """Probe configured storage with bounded write/read/delete."""
        start = time.monotonic()
        if self._storage is None:
            return {
                "status": STATE_DEGRADED,
                "message": "Storage service not available",
                "latency_ms": 0,
            }
        try:
            responsive = await asyncio.to_thread(self._storage.probe)
            latency = int((time.monotonic() - start) * 1000)
            if responsive:
                return {
                    "status": STATE_HEALTHY,
                    "message": "Storage responsive",
                    "latency_ms": latency,
                }
            return {
                "status": STATE_UNHEALTHY,
                "message": "Storage probe returned unexpected content",
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return {
                "status": STATE_UNHEALTHY,
                "message": "Storage probe failed",
                "error_type": type(exc).__name__,
                "latency_ms": latency,
            }

    async def _probe_worker(self) -> dict[str, Any]:
        """Probe worker/queue backend status."""
        start = time.monotonic()
        if not settings.JOB_WORKER_ENABLED:
            return {
                "status": STATE_DEGRADED,
                "message": "Worker not enabled",
                "latency_ms": 0,
            }
        if self._activity_runner is None:
            return {
                "status": STATE_DEGRADED,
                "message": "Activity runner not available",
                "latency_ms": 0,
            }
        try:
            status = self._activity_runner.status()
            latency = int((time.monotonic() - start) * 1000)
            running = bool(status.get("running", False))
            if running:
                return {
                    "status": STATE_HEALTHY,
                    "message": "Worker running",
                    "latency_ms": latency,
                }
            return {
                "status": STATE_DEGRADED,
                "message": "Worker not running",
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return {
                "status": STATE_UNHEALTHY,
                "message": "Worker probe failed",
                "error_type": type(exc).__name__,
                "latency_ms": latency,
            }

    async def _probe_disk(self) -> dict[str, Any]:
        """Probe disk space at the storage root."""
        start = time.monotonic()
        try:
            if self._storage is not None:
                path = Path(self._storage.base_dir)
            else:
                path = Path(settings.NOVEL_LIBRARY_DIR)
            usage = shutil.disk_usage(str(path))
            total = usage.total
            free = usage.free
            free_percent = int((free / total) * 100) if total > 0 else 0
            latency = int((time.monotonic() - start) * 1000)

            if free_percent < settings.HEALTH_DISK_CRITICAL_FREE_PERCENT:
                return {
                    "status": STATE_UNHEALTHY,
                    "message": "Disk space critical",
                    "free_percent": free_percent,
                    "latency_ms": latency,
                }
            if free_percent < settings.HEALTH_DISK_WARNING_FREE_PERCENT:
                return {
                    "status": STATE_DEGRADED,
                    "message": "Disk space low",
                    "free_percent": free_percent,
                    "latency_ms": latency,
                }
            return {
                "status": STATE_HEALTHY,
                "message": "Disk space sufficient",
                "free_percent": free_percent,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return {
                "status": STATE_UNHEALTHY,
                "message": "Disk probe failed",
                "error_type": type(exc).__name__,
                "latency_ms": latency,
            }

    async def _probe_storage_usage(self) -> dict[str, Any]:
        """Probe S3/R2 storage usage against soft limit (S3_STORAGE_LIMIT_GB).

        For filesystem backend, this probe is skipped (disk probe covers it).
        Always redacted — never exposes bucket name, credentials, or raw paths.
        """
        start = time.monotonic()
        if settings.STORAGE_BACKEND != "s3":
            return {
                "status": STATE_HEALTHY,
                "message": "Filesystem backend; use disk probe",
                "latency_ms": 0,
            }
        try:
            from novelai.storage.backends import get_storage_backend as _gsb

            backend = _gsb()
            used_bytes = backend.total_size_bytes()

            limit_bytes = int(settings.S3_STORAGE_LIMIT_GB * 1024**3)
            used_percent = int(used_bytes / limit_bytes * 100) if limit_bytes > 0 else 0
            free_bytes = max(0, limit_bytes - used_bytes)
            latency = int((time.monotonic() - start) * 1000)

            if used_percent >= 95:
                return {
                    "status": STATE_UNHEALTHY,
                    "message": "Storage usage critical",
                    "used_bytes": used_bytes,
                    "limit_bytes": limit_bytes,
                    "free_bytes": free_bytes,
                    "used_percent": used_percent,
                    "latency_ms": latency,
                }
            if used_percent >= 90:
                return {
                    "status": STATE_DEGRADED,
                    "message": "Storage usage warning",
                    "used_bytes": used_bytes,
                    "limit_bytes": limit_bytes,
                    "free_bytes": free_bytes,
                    "used_percent": used_percent,
                    "latency_ms": latency,
                }
            return {
                "status": STATE_HEALTHY,
                "message": "Storage usage within limits",
                "used_bytes": used_bytes,
                "limit_bytes": limit_bytes,
                "free_bytes": free_bytes,
                "used_percent": used_percent,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return {
                "status": STATE_UNHEALTHY,
                "message": "Storage usage probe failed",
                "error_type": type(exc).__name__,
                "latency_ms": latency,
            }

    async def _probe_object_snapshot(self) -> dict[str, Any]:
        return await self._probe_backup_service(
            self._backup_service,
            enabled=settings.BACKUP_ENABLED,
            disabled_message="Object snapshots are not enabled",
        )

    async def _probe_database_backup(self) -> dict[str, Any]:
        return await self._probe_backup_service(
            self._database_backup_service,
            enabled=settings.DATABASE_BACKUP_ENABLED,
            disabled_message="Database backups are not enabled",
        )

    @staticmethod
    async def _probe_backup_service(service: Any | None, *, enabled: bool, disabled_message: str) -> dict[str, Any]:
        start = time.monotonic()
        if not enabled:
            return {"status": STATE_DEGRADED, "message": disabled_message, "latency_ms": 0}
        if service is None:
            return {"status": STATE_UNHEALTHY, "message": "Backup service unavailable", "latency_ms": 0}
        result = await asyncio.to_thread(service.get_backup_health)
        return {
            "status": result.get("status", STATE_UNHEALTHY),
            "message": result.get("message", "Backup health unavailable"),
            "latency_ms": int((time.monotonic() - start) * 1000),
        }

    async def _probe_database_restore_verification(self) -> dict[str, Any]:
        start = time.monotonic()
        if not settings.DATABASE_RESTORE_VERIFICATION_ENABLED:
            return {
                "status": STATE_DEGRADED,
                "message": "Database restore verification is not enabled",
                "latency_ms": 0,
            }
        try:
            from sqlalchemy import text

            from novelai.db.engine import get_sessionmaker

            session = get_sessionmaker()()
            try:
                row = session.execute(
                    text(
                        "SELECT status, started_at FROM scheduled_cron_log "
                        "WHERE job_name LIKE 'database_restore_verify-%' "
                        "ORDER BY started_at DESC LIMIT 1"
                    )
                ).one_or_none()
            finally:
                session.close()

            if row is None:
                return {
                    "status": STATE_UNHEALTHY,
                    "message": "No database restore verification record found",
                    "latency_ms": int((time.monotonic() - start) * 1000),
                }
            status, started_at = row
            if status != "succeeded" or started_at is None:
                return {
                    "status": STATE_UNHEALTHY,
                    "message": "No successful database restore verification exists",
                    "latency_ms": int((time.monotonic() - start) * 1000),
                }
            max_age = settings.DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS
            cutoff = datetime.now(UTC).timestamp() - max_age * 86400
            if isinstance(started_at, datetime):
                started_ts = (
                    started_at.replace(tzinfo=UTC).timestamp() if started_at.tzinfo is None else started_at.timestamp()
                )
            else:
                started_ts = None
            if started_ts is None or started_ts < cutoff:
                return {
                    "status": STATE_UNHEALTHY,
                    "message": "Latest successful database restore verification is too old",
                    "latency_ms": int((time.monotonic() - start) * 1000),
                }
            return {
                "status": STATE_HEALTHY,
                "message": "Latest database restore verification succeeded",
                "latency_ms": int((time.monotonic() - start) * 1000),
            }
        except Exception as exc:
            return {
                "status": STATE_UNHEALTHY,
                "message": "Database restore verification probe failed",
                "error_type": type(exc).__name__,
                "latency_ms": int((time.monotonic() - start) * 1000),
            }

    @staticmethod
    def _aggregate_status(results: dict[str, dict[str, Any]]) -> str:
        """Aggregate probe results into an overall status."""
        statuses = [r.get("status", STATE_UNHEALTHY) for r in results.values()]
        if not statuses:
            return STATE_UNHEALTHY
        if any(s == STATE_UNHEALTHY for s in statuses):
            return STATE_UNHEALTHY
        if any(s == STATE_DEGRADED for s in statuses):
            return STATE_DEGRADED
        return STATE_HEALTHY

    @staticmethod
    def _public_safe_checks(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Redact probe results for public consumption.

        Never exposes: paths, hostnames, credentials, stack traces, raw exceptions,
        bucket names, signed URLs, or error details.
        """
        safe: dict[str, Any] = {}
        for name, result in results.items():
            safe[name] = {
                "status": result.get("status", STATE_UNHEALTHY),
            }
        return safe

    @staticmethod
    def _admin_safe_checks(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Redact probe results for admin consumption.

        Includes status, latency, safe message, and checked timestamp.
        Does not expose raw exceptions, stack traces, credentials, or paths.
        """
        safe: dict[str, Any] = {}
        for name, result in results.items():
            safe[name] = {
                "status": result.get("status", STATE_UNHEALTHY),
                "message": result.get("message", ""),
                "latency_ms": result.get("latency_ms", 0),
                "checked_at": _utc_now_iso(),
            }
            if "free_percent" in result:
                safe[name]["free_percent"] = result["free_percent"]
            if "used_bytes" in result:
                safe[name]["used_bytes"] = result["used_bytes"]
            if "used_percent" in result:
                safe[name]["used_percent"] = result["used_percent"]
            if "free_bytes" in result:
                safe[name]["free_bytes"] = result["free_bytes"]
            if "error_type" in result:
                safe[name]["error_type"] = result["error_type"]
        return safe
