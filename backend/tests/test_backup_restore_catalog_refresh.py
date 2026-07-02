"""Tests for catalog refresh after backup restore (Task 9).

Verifies:
  - `safely_refresh_catalog_projection_after_storage_write` is called after restore
    when `storage` param is provided.
  - A failure in the refresh does not cause restore to fail.
  - Without `storage`, refresh is not called.
"""

from __future__ import annotations

import json
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import ANY, patch

import pytest

from novelai.services.backup_manager import BackupManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_tar(backup_path: Path, novel_id: str) -> None:
    """Create a minimal valid tar archive mimicking a backup."""
    with tarfile.open(backup_path, "w:gz") as tar:
        info = tarfile.TarInfo(name=novel_id)
        info.type = tarfile.DIRTYPE
        tar.addfile(info)


def _write_manifest(mgr: BackupManager, backup_id: str, novel_id: str) -> None:
    """Write a valid manifest with one entry directly to disk."""
    mgr._backup_manifest.parent.mkdir(parents=True, exist_ok=True)
    mgr._backup_manifest.write_text(
        json.dumps({
            backup_id: {
                "timestamp": "2025-01-01T00:00:00Z",
                "novel_id": novel_id,
                "size_bytes": 100,
                "compressed": True,
                "files_count": 1,
                "description": None,
            },
        }),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBackupRestoreCatalogRefresh:
    """Catalog refresh after restore."""

    @pytest.mark.asyncio
    async def test_refresh_called_when_storage_provided(
        self, tmp_path: Path,
    ) -> None:
        """Refresh function should be called after successful restore."""
        backup_id = "novel_a__20250101_000000"
        novel_id = "novel_a"
        target_dir = tmp_path / "restore"

        mgr = BackupManager(tmp_path, storage=object(), session_scope_factory=lambda: contextmanager(lambda: iter([None]))())  # type: ignore[arg-type]
        _write_manifest(mgr, backup_id, novel_id)
        _create_tar(mgr._get_backup_path(backup_id), novel_id)

        with patch(
            "novelai.services.backup_manager.safely_refresh_catalog_projection_after_storage_write",
        ) as mock_refresh:
            result = await mgr.restore_backup(backup_id, target_dir, overwrite=True)

        assert result is True
        mock_refresh.assert_called_once_with(
            novel_id,
            mgr._storage,
            context="backup_restore",
            session_scope_factory=mgr._session_scope_factory,
        )

    @pytest.mark.asyncio
    async def test_refresh_failure_does_not_fail_restore(
        self, tmp_path: Path,
    ) -> None:
        """Restore should return True even if catalog refresh fails."""
        backup_id = "novel_b__20250101_000000"
        novel_id = "novel_b"
        target_dir = tmp_path / "restore"

        mgr = BackupManager(tmp_path, storage=object())
        _write_manifest(mgr, backup_id, novel_id)
        _create_tar(mgr._get_backup_path(backup_id), novel_id)

        with patch(
            "novelai.services.backup_manager.safely_refresh_catalog_projection_after_storage_write",
            side_effect=RuntimeError("DB unavailable"),
        ):
            result = await mgr.restore_backup(backup_id, target_dir, overwrite=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_refresh_not_called_without_storage(
        self, tmp_path: Path,
    ) -> None:
        """Without storage param, refresh should not be called."""
        backup_id = "novel_c__20250101_000000"
        novel_id = "novel_c"
        target_dir = tmp_path / "restore"

        mgr = BackupManager(tmp_path)  # no storage
        _write_manifest(mgr, backup_id, novel_id)
        _create_tar(mgr._get_backup_path(backup_id), novel_id)

        with patch(
            "novelai.services.backup_manager.safely_refresh_catalog_projection_after_storage_write",
        ) as mock_refresh:
            result = await mgr.restore_backup(backup_id, target_dir, overwrite=True)

        assert result is True
        mock_refresh.assert_not_called()
