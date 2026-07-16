from __future__ import annotations

from pathlib import Path

import pytest

from novelai.config.settings import settings
from novelai.services.backup_manager import BackupManager
from novelai.services.backup_service import BackupService
from novelai.storage.snapshots import SnapshotResult


class StubSnapshotTarget:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.created = 0
        self.result = SnapshotResult(
            snapshot_id="backup-20260716T000000Z-deadbeef",
            created_at="2026-07-16T00:00:00Z",
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


@pytest.mark.asyncio
async def test_s3_backup_uses_committed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    target = StubSnapshotTarget()
    service = BackupService(BackupManager(tmp_path), snapshot_target=target)

    result = await service.run_scheduled_backup()

    assert result["status"] == "succeeded"
    assert result["backup_id"] == target.result.snapshot_id
    assert result["verified"] is True
    assert target.created == 1


@pytest.mark.asyncio
async def test_s3_backup_fails_when_snapshot_copy_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    service = BackupService(
        BackupManager(tmp_path),
        snapshot_target=StubSnapshotTarget(failure=RuntimeError("provider unavailable")),
    )

    result = await service.run_scheduled_backup()

    assert result["status"] == "failed"
    assert "provider unavailable" in result["error"]


def test_offsite_backup_health_uses_committed_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "BACKUP_ENABLED", True)
    target = StubSnapshotTarget()
    service = BackupService(BackupManager(tmp_path), snapshot_target=target)

    health = service.get_backup_health()

    assert health["status"] == "healthy"
    assert health["backup_id"] == target.result.snapshot_id
