from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from novelai.storage.backends.r2_gateway import InMemoryR2GatewayStorage
from novelai.storage.r2_backup import R2IncrementalBackupTarget


@pytest.fixture
def backup_env() -> tuple[InMemoryR2GatewayStorage, InMemoryR2GatewayStorage, R2IncrementalBackupTarget]:
    source = InMemoryR2GatewayStorage("test-dokushodo")
    target = InMemoryR2GatewayStorage("test-dokushodo-backup")
    source.save("novels/a.json", b'{"a":1}')
    source.save("novels/sub/b.json", b'{"b":2}')
    source.save("runtime/disposable.json", b"cache")
    return source, target, R2IncrementalBackupTarget(source_backend=source, target_backend=target)


def test_backup_copies_only_canonical_novel_objects(
    backup_env: tuple[InMemoryR2GatewayStorage, InMemoryR2GatewayStorage, R2IncrementalBackupTarget],
) -> None:
    _source, target, backup = backup_env

    result = backup.create_snapshot()

    assert result.files_count == 2
    assert result.verified is True
    keys = target.list_keys("", recursive=True)
    assert any(key.endswith("/manifest.json") for key in keys)
    assert "objects/novels/a.json" in keys
    assert "objects/novels/sub/b.json" in keys
    assert not any("disposable" in key for key in keys)
    assert backup.latest_snapshot() == result
    assert backup.verify_snapshot(result.snapshot_id) == result


def test_backup_target_must_be_independent() -> None:
    same = InMemoryR2GatewayStorage("same-bucket")
    with pytest.raises(ValueError, match="must differ"):
        R2IncrementalBackupTarget(source_backend=same, target_backend=same)


def test_incomplete_prefix_is_not_a_committed_backup(
    backup_env: tuple[InMemoryR2GatewayStorage, InMemoryR2GatewayStorage, R2IncrementalBackupTarget],
) -> None:
    _source, target, backup = backup_env
    target.save("snapshots/backup-20990101T000000Z-deadbeef/objects/novels/a.json", b"partial")

    assert backup.latest_snapshot() is None


def test_copy_failure_never_commits_manifest(
    backup_env: tuple[InMemoryR2GatewayStorage, InMemoryR2GatewayStorage, R2IncrementalBackupTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, target, backup = backup_env
    original_save = target.save

    def fail_second_copy(path: str, data: bytes, **kwargs: Any) -> None:
        if path.endswith("sub/b.json"):
            raise RuntimeError("copy failed")
        original_save(path, data, **kwargs)

    monkeypatch.setattr(target, "save", fail_second_copy)

    with pytest.raises(RuntimeError, match="copy failed"):
        backup.create_snapshot()

    keys = target.list_keys("", recursive=True)
    assert not any(key.endswith("/manifest.json") for key in keys)
    assert not any(key.startswith("objects/") for key in keys)


def test_retention_preserves_references_and_collects_old_orphans(
    backup_env: tuple[InMemoryR2GatewayStorage, InMemoryR2GatewayStorage, R2IncrementalBackupTarget],
) -> None:
    source, target, backup = backup_env
    first = backup.create_snapshot()
    source.delete("novels/sub/b.json")
    second = backup.create_snapshot()
    manifest_key = f"snapshots/{first.snapshot_id}/manifest.json"
    record = target._objects[manifest_key]
    record.metadata = replace(record.metadata, last_modified=datetime(2020, 1, 1, tzinfo=UTC))

    deleted = backup.apply_retention(
        keep_count=1,
        min_successful=1,
        max_age_days=1,
        safety_grace_days=0,
    )

    assert deleted >= 2
    latest = backup.latest_snapshot()
    assert latest is not None
    assert latest.snapshot_id == second.snapshot_id
    assert target.exists("objects/novels/a.json")
    assert not target.exists("objects/novels/sub/b.json")
