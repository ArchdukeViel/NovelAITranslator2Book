"""Tests for the HealthService (M2a, DEBT-001).

Tests probe logic, timeout behavior, redaction, and status aggregation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from novelai.config.settings import settings
from novelai.services.health_service import STATE_DEGRADED, STATE_HEALTHY, STATE_UNHEALTHY, HealthService


class FakeStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir


class FakeRunner:
    def status(self) -> dict[str, Any]:
        return {"running": True}


class FakeRunnerStopped:
    def status(self) -> dict[str, Any]:
        return {"running": False}


@pytest.fixture()
def storage(tmp_path: Path) -> FakeStorage:
    return FakeStorage(tmp_path)


@pytest.fixture(autouse=True)
def filesystem_storage_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "filesystem")


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
        with patch("novelai.config.settings.settings.DATABASE_URL", "sqlite://"), \
             patch("novelai.db.engine.get_sessionmaker") as mock_sm:
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


class TestStorageUsage:
    @pytest.mark.asyncio
    async def test_storage_usage_uses_backend_contract(self, storage: FakeStorage) -> None:
        backend = MagicMock()
        backend.total_size_bytes.return_value = 512
        with (
            patch("novelai.config.settings.settings.STORAGE_BACKEND", "s3"),
            patch("novelai.config.settings.settings.S3_STORAGE_LIMIT_GB", 1),
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
