"""Tests for the BackupManager."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.services.backup_manager import (
    BackupInfo,
    BackupManager,
    BackupManifestEntry,
    _parse_manifest_entry,
)

_TMP = Path(__file__).resolve().parent / ".tmp" / "backups"


@pytest.fixture()
def backup_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def source_dir(backup_dir: Path) -> Path:
    src = backup_dir / "source_novel"
    src.mkdir()
    (src / "metadata.json").write_text('{"title":"test"}', encoding="utf-8")
    (src / "chapter1.txt").write_text("Chapter content", encoding="utf-8")
    return src


class TestParseManifestEntry:
    def test_valid_entry(self) -> None:
        result = _parse_manifest_entry({
            "timestamp": "2025-01-01T00:00:00Z",
            "novel_id": "n1",
            "size_bytes": 1024,
            "compressed": True,
            "files_count": 5,
            "description": "test",
        })
        assert result is not None
        assert result["novel_id"] == "n1"
        assert result["size_bytes"] == 1024

    def test_missing_fields_default(self) -> None:
        result = _parse_manifest_entry({
            "timestamp": "2025-01-01T00:00:00Z",
            "novel_id": "n1",
        })
        assert result is not None
        assert result["size_bytes"] == 0
        assert result["compressed"] is False

    def test_non_dict_returns_none(self) -> None:
        assert _parse_manifest_entry("string") is None

    def test_missing_required_returns_none(self) -> None:
        assert _parse_manifest_entry({"timestamp": "ts"}) is None


class TestBackupManager:
    def test_load_manifest_empty(self, backup_dir: Path) -> None:
        mgr = BackupManager(backup_dir)
        assert mgr._load_manifest() == {}

    def test_load_manifest_corrupted(self, backup_dir: Path) -> None:
        mgr = BackupManager(backup_dir)
        mgr._backup_manifest.write_text("NOT JSON", encoding="utf-8")
        assert mgr._load_manifest() == {}

    def test_save_and_load_manifest(self, backup_dir: Path) -> None:
        mgr = BackupManager(backup_dir)
        manifest: dict[str, BackupManifestEntry] = {
            "backup1": BackupManifestEntry(
                timestamp="2025-01-01T00:00:00Z",
                novel_id="n1",
                size_bytes=100,
                compressed=True,
                files_count=2,
                description=None,
            )
        }
        mgr._save_manifest(manifest)
        loaded = mgr._load_manifest()
        assert "backup1" in loaded
        assert loaded["backup1"]["novel_id"] == "n1"

    @pytest.mark.asyncio
    async def test_create_full_backup(self, backup_dir: Path, source_dir: Path) -> None:
        mgr = BackupManager(backup_dir)
        info = await mgr.create_full_backup("test_novel", source_dir, description="test")
        assert isinstance(info, BackupInfo)
        assert info.novel_id == "test_novel"
        assert info.files_count > 0
        assert info.size_bytes > 0
        assert info.compressed is True
        # Check manifest was updated
        assert info.backup_id in mgr._load_manifest()

    @pytest.mark.asyncio
    async def test_list_backups(self, backup_dir: Path, source_dir: Path) -> None:
        mgr = BackupManager(backup_dir)
        await mgr.create_full_backup("novel_a", source_dir)
        backups = mgr.list_backups("novel_a")
        assert len(backups) >= 1
        assert backups[0].novel_id == "novel_a"

    @pytest.mark.asyncio
    async def test_list_backups_filters_by_novel_id(self, backup_dir: Path, source_dir: Path) -> None:
        mgr = BackupManager(backup_dir)
        await mgr.create_full_backup("novel_a", source_dir)
        assert mgr.list_backups("novel_b") == []

    def test_collect_changed_files(self, source_dir: Path) -> None:
        from datetime import datetime
        old = datetime(2000, 1, 1, tzinfo=UTC)
        changed = BackupManager._collect_changed_files(source_dir, old)
        assert len(changed) >= 2  # metadata.json + chapter1.txt
