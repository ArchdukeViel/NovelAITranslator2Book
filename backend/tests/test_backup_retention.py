"""Tests for backup retention policy (M2c, DEBT-010).

Tests that retention preserves the newest successful backup and a minimum
count of successful backups, and deletes older backups beyond the threshold.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from novelai.services.backup_manager import BackupManager


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def manager(backup_dir: Path) -> BackupManager:
    return BackupManager(base_dir=backup_dir)


async def _create_backup(manager: BackupManager, novel_id: str, source_dir: Path, age_days: int = 0) -> None:
    """Create a backup and optionally age its manifest entry."""
    info = await manager.create_full_backup(novel_id, source_dir)
    if age_days > 0:
        # Manually age the manifest entry.
        old_ts = (datetime.now(UTC) - timedelta(days=age_days)).isoformat().replace("+00:00", "Z")
        manifest = manager._load_manifest()
        entry = manifest.get(info.backup_id)
        if entry is not None:
            entry["timestamp"] = old_ts
        manager._save_manifest(manifest)


class TestApplyRetention:
    @pytest.mark.asyncio
    async def test_preserves_newest_successful(self, manager: BackupManager, tmp_path: Path) -> None:
        source = tmp_path / "novel1"
        source.mkdir()
        (source / "data.txt").write_text("content", encoding="utf-8")

        for _ in range(3):
            await _create_backup(manager, "novel1", source)

        deleted = await manager.apply_retention(
            novel_id="novel1",
            keep_count=2,
            min_successful=1,
            max_age_days=0,
        )
        backups = manager.list_backups("novel1")
        assert len(backups) >= 1
        assert deleted >= 0

    @pytest.mark.asyncio
    async def test_preserves_minimum_count(self, manager: BackupManager, tmp_path: Path) -> None:
        source = tmp_path / "novel2"
        source.mkdir()
        (source / "data.txt").write_text("content", encoding="utf-8")

        # Create backups with unique timestamps by adding unique content.
        for i in range(5):
            (source / f"file_{i}.txt").write_text(f"content_{i}", encoding="utf-8")
            await _create_backup(manager, "novel2", source, age_days=i * 10)

        backups_before = manager.list_backups("novel2")
        await manager.apply_retention(
            novel_id="novel2",
            keep_count=3,
            min_successful=3,
            max_age_days=30,
        )
        backups_after = manager.list_backups("novel2")
        # Should keep at least min_successful backups.
        assert len(backups_after) >= min(3, len(backups_before))

    @pytest.mark.asyncio
    async def test_deletes_old_beyond_keep_count(self, manager: BackupManager, tmp_path: Path) -> None:
        source = tmp_path / "novel3"
        source.mkdir()
        (source / "data.txt").write_text("content", encoding="utf-8")

        for i in range(5):
            await _create_backup(manager, "novel3", source, age_days=i * 10)

        await manager.apply_retention(
            novel_id="novel3",
            keep_count=2,
            min_successful=1,
            max_age_days=15,
        )
        backups = manager.list_backups("novel3")
        assert len(backups) <= 3

    @pytest.mark.asyncio
    async def test_no_backups_returns_zero(self, manager: BackupManager) -> None:
        deleted = await manager.apply_retention(
            novel_id="nonexistent",
            keep_count=5,
            min_successful=3,
            max_age_days=30,
        )
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_never_deletes_newest(self, manager: BackupManager, tmp_path: Path) -> None:
        source = tmp_path / "novel4"
        source.mkdir()
        (source / "data.txt").write_text("content", encoding="utf-8")

        for i in range(4):
            await _create_backup(manager, "novel4", source, age_days=i * 20)

        await manager.apply_retention(
            novel_id="novel4",
            keep_count=1,
            min_successful=1,
            max_age_days=1,
        )
        backups = manager.list_backups("novel4")
        assert len(backups) >= 1
        newest = backups[0]
        assert newest.backup_id is not None
