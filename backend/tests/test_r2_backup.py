from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from novelai.storage.r2_backup import R2IncrementalBackupTarget

boto3 = pytest.importorskip("boto3", reason="boto3 not installed")
pytest.importorskip("moto", reason="moto not installed")


@pytest.fixture
def backup_env() -> Generator[tuple[Any, R2IncrementalBackupTarget]]:
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="source-bucket")
        client.create_bucket(Bucket="backup-bucket")
        client.put_object(Bucket="source-bucket", Key="novels/a.json", Body=b'{"a":1}')
        client.put_object(Bucket="source-bucket", Key="novels/sub/b.json", Body=b'{"b":2}')
        client.put_object(Bucket="source-bucket", Key="runtime/disposable.json", Body=b"cache")
        target = R2IncrementalBackupTarget(
            source_bucket="source-bucket",
            target_bucket="backup-bucket",
            target_prefix="snapshots",
            endpoint_url=None,
            region="us-east-1",
            source_access_key_id=None,
            source_secret_access_key=None,
            target_access_key_id=None,
            target_secret_access_key=None,
            source_client=client,
            target_client=client,
        )
        yield client, target


def test_backup_copies_only_canonical_novel_objects(
    backup_env: tuple[Any, R2IncrementalBackupTarget],
) -> None:
    client, target = backup_env

    result = target.create_snapshot()

    assert result.files_count == 2
    assert result.verified is True
    keys = [item["Key"] for item in client.list_objects_v2(Bucket="backup-bucket").get("Contents", [])]
    assert any(key.endswith("/manifest.json") for key in keys)
    assert "objects/novels/a.json" in keys
    assert "objects/novels/sub/b.json" in keys
    assert not any("disposable" in key for key in keys)
    assert target.latest_snapshot() == result
    assert target.verify_snapshot(result.snapshot_id) == result


def test_backup_target_must_be_independent() -> None:
    with pytest.raises(ValueError, match="must differ"):
        R2IncrementalBackupTarget(
            source_bucket="same-bucket",
            target_bucket="same-bucket",
            target_prefix="snapshots",
            endpoint_url=None,
            region="us-east-1",
            source_access_key_id=None,
            source_secret_access_key=None,
            target_access_key_id=None,
            target_secret_access_key=None,
            source_client=object(),
            target_client=object(),
        )


def test_incomplete_prefix_is_not_a_committed_backup(
    backup_env: tuple[Any, R2IncrementalBackupTarget],
) -> None:
    client, target = backup_env
    client.put_object(
        Bucket="backup-bucket",
        Key="snapshots/backup-20990101T000000Z-deadbeef/objects/novels/a.json",
        Body=b"partial",
    )

    assert target.latest_snapshot() is None


def test_copy_failure_never_commits_manifest(
    backup_env: tuple[Any, R2IncrementalBackupTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, target = backup_env
    original_upload = client.upload_fileobj
    calls = 0

    def fail_second_copy(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("copy failed")
        return original_upload(*args, **kwargs)

    monkeypatch.setattr(client, "upload_fileobj", fail_second_copy)

    with pytest.raises(RuntimeError, match="copy failed"):
        target.create_snapshot()

    keys = [item["Key"] for item in client.list_objects_v2(Bucket="backup-bucket").get("Contents", [])]
    assert not any(key.endswith("/manifest.json") for key in keys)
    assert not any(key.startswith("objects/") for key in keys)
