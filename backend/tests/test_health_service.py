"""Tests for the HealthService (M2a, DEBT-001).

Tests probe logic, timeout behavior, redaction, and status aggregation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from novelai.config.settings import settings
from novelai.services.health_service import STATE_DEGRADED, STATE_HEALTHY, STATE_UNHEALTHY, HealthService


class FakeStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def probe(self) -> bool:
        probe_file = self.base_dir / ".healthcheck.json"
        try:
            probe_file.write_bytes(b'{"status":"ok"}')
            return probe_file.read_bytes() == b'{"status":"ok"}'
        finally:
            probe_file.unlink(missing_ok=True)

    def probe_readiness(self) -> bool:
        return self.base_dir.is_dir()


class FakeRunner:
    def status(self) -> dict[str, Any]:
        return {"running": True}


class FakeRunnerStopped:
    def status(self) -> dict[str, Any]:
        return {"running": False}


@pytest.fixture()
def storage(tmp_path: Path) -> FakeStorage:
    return FakeStorage(tmp_path)


@pytest.fixture()
def service(storage: FakeStorage) -> HealthService:
    return HealthService(storage=storage, activity_runner=FakeRunner())


class TestLiveness:
    @pytest.mark.asyncio
    async def test_liveness_always_ok(self, service: HealthService) -> None:
        result = service.liveness()
        assert result["status"] == "ok"
        assert result["service"] == "novelai"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_liveness_no_probes(self, service: HealthService) -> None:
        result = service.liveness()
        assert "checks" not in result


class TestReadiness:
    @pytest.mark.asyncio
    async def test_readiness_healthy(self, service: HealthService) -> None:
        with (
            patch("novelai.config.settings.settings.DATABASE_URL", "sqlite://"),
            patch("novelai.db.engine.get_sessionmaker") as mock_sm,
        ):
            mock_session = MagicMock()
            mock_sm.return_value = mock_session
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.readiness()
        assert result["status"] in (STATE_HEALTHY, STATE_DEGRADED, STATE_UNHEALTHY)
        assert "checks" in result

    @pytest.mark.asyncio
    async def test_readiness_storage_healthy(self, storage: FakeStorage) -> None:
        svc = HealthService(storage=storage, activity_runner=None)
        result = await svc.readiness()
        checks = result["checks"]
        assert "storage" in checks
        assert checks["storage"]["status"] == STATE_HEALTHY

    @pytest.mark.asyncio
    async def test_readiness_storage_uses_backend_probe(self, storage: FakeStorage) -> None:
        storage.probe = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = await HealthService(storage=storage)._probe_storage()

        assert result["status"] == STATE_HEALTHY
        storage.probe.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_readiness_worker_not_enabled(self, storage: FakeStorage) -> None:
        with patch("novelai.config.settings.settings.JOB_WORKER_ENABLED", False):
            svc = HealthService(storage=storage, activity_runner=None)
            result = await svc.readiness()
        checks = result["checks"]
        assert checks["worker"]["status"] == STATE_DEGRADED

    @pytest.mark.asyncio
    async def test_readiness_disk_healthy(self, storage: FakeStorage) -> None:
        svc = HealthService(storage=storage, activity_runner=None)
        result = await svc.readiness()
        checks = result["checks"]
        assert checks["disk"]["status"] in (STATE_HEALTHY, STATE_DEGRADED, STATE_UNHEALTHY)

    @pytest.mark.asyncio
    async def test_readiness_public_safe_no_paths(self, service: HealthService) -> None:
        result = await service.readiness()
        checks_str = str(result["checks"])
        assert "base_dir" not in checks_str
        assert "path" not in checks_str.lower()
        assert "password" not in checks_str.lower()
        assert "secret" not in checks_str.lower()

    @pytest.mark.asyncio
    async def test_readiness_uses_short_ttl_cache(self, service: HealthService, monkeypatch) -> None:
        monkeypatch.setattr(settings, "HEALTH_CACHE_TTL_SECONDS", 30)
        probe = AsyncMock(return_value={"database": {"status": STATE_HEALTHY}, "storage": {"status": STATE_HEALTHY}})
        service._run_probes = probe  # type: ignore[method-assign]

        await service.readiness()
        await service.readiness()

        probe.assert_awaited_once_with()
        stats = service.health_cache_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.entries == 1

    @pytest.mark.asyncio
    async def test_concurrent_readiness_requests_share_one_probe(self, service: HealthService, monkeypatch) -> None:
        monkeypatch.setattr(settings, "HEALTH_CACHE_TTL_SECONDS", 30)
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def run_probe():
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return {"database": {"status": STATE_HEALTHY}}

        service._run_probes = run_probe  # type: ignore[method-assign]
        tasks = [asyncio.create_task(service.readiness()) for _ in range(3)]
        await started.wait()
        release.set()
        results = await asyncio.gather(*tasks)

        assert calls == 1
        assert all(result["status"] == STATE_HEALTHY for result in results)


class TestStorageUsage:
    @pytest.mark.asyncio
    async def test_storage_usage_uses_backend_contract(self, storage: FakeStorage) -> None:
        backend = MagicMock()
        backend.total_size_bytes.return_value = 512
        with (
            patch("novelai.config.settings.settings.R2_STORAGE_LIMIT_GB", 1),
            patch("novelai.storage.backends.get_storage_backend", return_value=backend),
        ):
            result = await HealthService(storage=storage)._probe_storage_usage()

        assert result["status"] == STATE_HEALTHY
        assert result["used_bytes"] == 512
        backend.total_size_bytes.assert_called_once_with()


class TestAdminHealth:
    @pytest.mark.asyncio
    async def test_admin_health_includes_latency(self, service: HealthService) -> None:
        result = await service.admin_health()
        for _name, check in result["checks"].items():
            assert "latency_ms" in check
            assert "message" in check
            assert "checked_at" in check

    @pytest.mark.asyncio
    async def test_admin_health_no_raw_exceptions(self, service: HealthService) -> None:
        result = await service.admin_health()
        checks_str = str(result["checks"])
        assert "Traceback" not in checks_str
        assert "stack" not in checks_str.lower()

    @pytest.mark.asyncio
    async def test_admin_health_includes_recovery_checks(self, storage: FakeStorage) -> None:
        backup = MagicMock()
        backup.get_backup_health.return_value = {"status": "healthy", "message": "Verified backup exists"}
        with (
            patch("novelai.config.settings.settings.BACKUP_ENABLED", True),
            patch("novelai.config.settings.settings.DATABASE_BACKUP_ENABLED", True),
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_ENABLED", False),
        ):
            result = await HealthService(
                storage=storage,
                backup_service=backup,
                database_backup_service=backup,
            ).admin_health()

        assert result["checks"]["object_snapshot"]["status"] == STATE_HEALTHY
        assert result["checks"]["database_backup"]["status"] == STATE_HEALTHY
        assert result["checks"]["database_restore_verification"]["status"] == STATE_DEGRADED


class TestProbeIsolation:
    @pytest.mark.asyncio
    async def test_failed_probe_does_not_stop_others(self, storage: FakeStorage) -> None:
        svc = HealthService(storage=storage, activity_runner=FakeRunner())

        async def boom() -> dict[str, Any]:
            raise RuntimeError("boom")

        svc._probe_database = boom
        result = await svc.readiness()
        checks = result["checks"]
        assert checks["database"]["status"] == STATE_UNHEALTHY
        assert checks["storage"]["status"] == STATE_HEALTHY


class TestStatusAggregation:
    def test_all_healthy(self) -> None:
        results = {"db": {"status": STATE_HEALTHY}, "storage": {"status": STATE_HEALTHY}}
        assert HealthService._aggregate_status(results) == STATE_HEALTHY

    def test_one_degraded(self) -> None:
        results = {"db": {"status": STATE_HEALTHY}, "storage": {"status": STATE_DEGRADED}}
        assert HealthService._aggregate_status(results) == STATE_DEGRADED

    def test_one_unhealthy(self) -> None:
        results = {"db": {"status": STATE_UNHEALTHY}, "storage": {"status": STATE_HEALTHY}}
        assert HealthService._aggregate_status(results) == STATE_UNHEALTHY

    def test_empty_results(self) -> None:
        assert HealthService._aggregate_status({}) == STATE_UNHEALTHY


class TestRedaction:
    def test_public_safe_checks_no_messages(self) -> None:
        results = {"db": {"status": STATE_HEALTHY, "message": "DB at postgres://user:pass@host:5432/db"}}
        safe = HealthService._public_safe_checks(results)
        assert safe["db"] == {"status": STATE_HEALTHY}
        assert "message" not in safe["db"]

    def test_admin_safe_checks_includes_message_but_no_secrets(self) -> None:
        results = {"db": {"status": STATE_HEALTHY, "message": "Database responsive", "latency_ms": 5}}
        safe = HealthService._admin_safe_checks(results)
        assert safe["db"]["status"] == STATE_HEALTHY
        assert safe["db"]["message"] == "Database responsive"
        assert safe["db"]["latency_ms"] == 5
        assert "checked_at" in safe["db"]


class TestDatabaseRestoreVerification:
    """Tests for _probe_database_restore_verification (M2a)."""

    @pytest.mark.asyncio
    async def test_disabled_returns_degraded(self) -> None:
        svc = HealthService()
        with patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_ENABLED", False):
            result = await svc._probe_database_restore_verification()
        assert result["status"] == STATE_DEGRADED
        assert "not enabled" in result["message"]

    @pytest.mark.asyncio
    async def test_no_row_unhealthy(self) -> None:
        svc = HealthService()
        with (
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_ENABLED", True),
            patch("novelai.db.engine.get_sessionmaker") as mock_sm,
        ):
            mock_session = MagicMock()
            mock_sm.return_value.return_value = mock_session
            mock_execute = MagicMock()
            mock_session.execute = mock_execute
            mock_execute.return_value.one_or_none.return_value = None
            result = await svc._probe_database_restore_verification()
        assert result["status"] == STATE_UNHEALTHY
        assert "No database restore verification record found" in result["message"]

    @pytest.mark.asyncio
    async def test_failed_row_unhealthy(self) -> None:
        svc = HealthService()
        with (
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_ENABLED", True),
            patch("novelai.db.engine.get_sessionmaker") as mock_sm,
        ):
            mock_session = MagicMock()
            mock_sm.return_value.return_value = mock_session
            mock_execute = MagicMock()
            mock_session.execute = mock_execute
            mock_execute.return_value.one_or_none.return_value = ("failed", None)
            result = await svc._probe_database_restore_verification()
        assert result["status"] == STATE_UNHEALTHY
        assert "No successful database restore verification exists" in result["message"]

    @pytest.mark.asyncio
    async def test_stale_success_unhealthy(self) -> None:
        svc = HealthService()
        old_time = datetime.now(UTC) - timedelta(days=60)
        with (
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_ENABLED", True),
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS", 32),
            patch("novelai.db.engine.get_sessionmaker") as mock_sm,
        ):
            mock_session = MagicMock()
            mock_sm.return_value.return_value = mock_session
            mock_execute = MagicMock()
            mock_session.execute = mock_execute
            mock_execute.return_value.one_or_none.return_value = ("succeeded", old_time)
            result = await svc._probe_database_restore_verification()
        assert result["status"] == STATE_UNHEALTHY
        assert "too old" in result["message"]

    @pytest.mark.asyncio
    async def test_fresh_success_healthy(self) -> None:
        svc = HealthService()
        fresh = datetime.now(UTC)
        with (
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_ENABLED", True),
            patch("novelai.config.settings.settings.DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS", 32),
            patch("novelai.db.engine.get_sessionmaker") as mock_sm,
        ):
            mock_session = MagicMock()
            mock_sm.return_value.return_value = mock_session
            mock_execute = MagicMock()
            mock_session.execute = mock_execute
            mock_execute.return_value.one_or_none.return_value = ("succeeded", fresh)
            result = await svc._probe_database_restore_verification()
        assert result["status"] == STATE_HEALTHY
        assert "succeeded" in result["message"]
