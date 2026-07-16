from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from novelai.services.scheduler_service import SchedulerService


class StubBackupService:
    def __init__(self, status: str) -> None:
        self.status = status

    async def run_scheduled_backup(self) -> dict[str, str]:
        return {"status": self.status}

    def get_backup_health(self) -> dict[str, str]:
        return {
            "status": "healthy",
            "last_backup_at": (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        }


class StubAlerts:
    def __init__(self) -> None:
        self.codes: list[str] = []

    def send(self, *, code: str, message: str) -> bool:
        self.codes.append(code)
        return True

    def clear(self, code: str) -> None:
        self.codes = [existing for existing in self.codes if existing != code]


@pytest.mark.asyncio
async def test_scheduler_propagates_backup_success() -> None:
    service = SchedulerService(backup_service=StubBackupService("succeeded"))
    assert await service._run_backup() == "succeeded"


@pytest.mark.asyncio
async def test_scheduler_does_not_record_failure_as_success() -> None:
    service = SchedulerService(backup_service=StubBackupService("failed"))
    assert await service._run_backup() == "failed"


@pytest.mark.asyncio
async def test_scheduler_preserves_locked_status_for_retry() -> None:
    service = SchedulerService(backup_service=StubBackupService("skipped_locked"))
    assert await service._run_backup() == "skipped_locked"


@pytest.mark.asyncio
async def test_scheduler_alerts_when_snapshot_is_stale(monkeypatch) -> None:
    alerts = StubAlerts()
    monkeypatch.setattr("novelai.services.scheduler_service.settings.BACKUP_ENABLED", True)
    monkeypatch.setattr("novelai.services.scheduler_service.settings.OPERATOR_ALERT_STALE_BACKUP_HOURS", 36)
    service = SchedulerService(backup_service=StubBackupService("succeeded"), operator_alert_service=alerts)
    await service._check_backup_staleness()
    assert alerts.codes == ["r2_backup_stale"]
