from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from novelai.config.settings import settings
from novelai.services.backup_service import BackupService
from novelai.services.database_backup_service import DatabaseBackupService
from novelai.storage.backends.r2_gateway import InMemoryR2GatewayStorage
from novelai.storage.snapshots import SnapshotResult


def _recent_iso(hours: float = 0) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


class StubSnapshotTarget:
    def __init__(self, *, created_at: str | None = None, failure: Exception | None = None) -> None:
        self.failure = failure
        self.created = 0
        self.result = SnapshotResult(
            snapshot_id="backup-20260716T000000Z-deadbeef",
            created_at=created_at or _recent_iso(hours=-1),
            files_count=2,
            size_bytes=12,
            verified=True,
        )

    def create_snapshot(self) -> SnapshotResult:
        self.created += 1
        if self.failure is not None:
            raise self.failure
        return self.result

    def latest_snapshot(self) -> SnapshotResult | None:
        return self.result

    def verify_snapshot(self, snapshot_id: str) -> SnapshotResult:
        assert snapshot_id == self.result.snapshot_id
        return self.result

    def apply_retention(self, **_: object) -> int:
        return 0


@pytest.mark.asyncio
async def test_r2_backup_uses_committed_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = StubSnapshotTarget()
    service = BackupService(runtime_dir=tmp_path, snapshot_target=target)

    result = await service.run_scheduled_backup()

    assert result["status"] == "succeeded"
    assert result["backup_id"] == target.result.snapshot_id
    assert result["verified"] is True
    assert target.created == 1


@pytest.mark.asyncio
async def test_r2_backup_fails_when_snapshot_copy_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = BackupService(
        runtime_dir=tmp_path,
        snapshot_target=StubSnapshotTarget(failure=RuntimeError("provider unavailable")),
    )

    result = await service.run_scheduled_backup()

    assert result["status"] == "failed"
    assert "provider unavailable" in result["error"]


def test_offsite_backup_health_uses_committed_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BACKUP_ENABLED", True)
    target = StubSnapshotTarget()
    service = BackupService(runtime_dir=tmp_path, snapshot_target=target)

    health = service.get_backup_health()

    assert health["status"] == "healthy"
    assert health["backup_id"] == target.result.snapshot_id


@pytest.mark.parametrize(("hours", "status"), [(-1, "healthy"), (-37, "unhealthy")])
def test_offsite_backup_health_enforces_freshness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hours: int, status: str
) -> None:
    monkeypatch.setattr(settings, "BACKUP_ENABLED", True)
    target = StubSnapshotTarget(created_at=_recent_iso(hours=hours))

    assert BackupService(runtime_dir=tmp_path, snapshot_target=target).get_backup_health()["status"] == status


@pytest.mark.parametrize(("hours", "status"), [(-1, "healthy"), (-37, "unhealthy")])
def test_database_backup_health_enforces_freshness(hours: int, status: str) -> None:
    backend = InMemoryR2GatewayStorage("test-dokushodo-backup")
    backend.save("database/backup/manifest.json", b"{}")
    record = backend._objects["database/backup/manifest.json"]
    record.metadata = replace(record.metadata, last_modified=datetime.now(UTC) + timedelta(hours=hours))

    assert DatabaseBackupService(backend).get_backup_health()["status"] == status


def test_restore_target_prepares_all_application_policy_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = False
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr("novelai.services.database_backup_service.create_engine", lambda *_args, **_kwargs: engine)

    DatabaseBackupService._prepare_restore_target("postgresql+psycopg://restore:restore@127.0.0.1/novelai_restore")

    statements = [str(call.args[0]) for call in connection.exec_driver_sql.call_args_list]
    assert 'CREATE ROLE "novelai_app" NOLOGIN' in statements
