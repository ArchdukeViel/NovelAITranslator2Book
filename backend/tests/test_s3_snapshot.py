from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from novelai.storage.backends.s3_snapshot import S3SnapshotTarget

boto3 = pytest.importorskip("boto3", reason="boto3 not installed")
pytest.importorskip("moto", reason="moto not installed")


@pytest.fixture
def snapshot_env() -> Generator[tuple[Any, S3SnapshotTarget]]:
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="source-bucket")
        client.create_bucket(Bucket="backup-bucket")
        client.put_object(Bucket="source-bucket", Key="app/novels/a.json", Body=b'{"a":1}')
        client.put_object(Bucket="source-bucket", Key="app/novels/sub/b.json", Body=b'{"b":2}')
        client.put_object(Bucket="source-bucket", Key="app/cache/disposable.json", Body=b"cache")
        target = S3SnapshotTarget(
            source_bucket="source-bucket",
            source_prefix="app",
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


def test_snapshot_copies_only_canonical_novel_objects(
    snapshot_env: tuple[Any, S3SnapshotTarget],
) -> None:
    client, target = snapshot_env

    result = target.create_snapshot()

    assert result.files_count == 2
    assert result.verified is True
    keys = [
        item["Key"]
        for item in client.list_objects_v2(Bucket="backup-bucket").get("Contents", [])
    ]
    assert any(key.endswith("/manifest.json") for key in keys)
    assert any(key.endswith("/objects/a.json") for key in keys)
    assert any(key.endswith("/objects/sub/b.json") for key in keys)
    assert not any("disposable" in key for key in keys)
    assert target.latest_snapshot() == result
    assert target.verify_snapshot(result.snapshot_id) == result


def test_snapshot_target_must_be_independent() -> None:
    with pytest.raises(ValueError, match="must differ"):
        S3SnapshotTarget(
            source_bucket="same-bucket",
            source_prefix="",
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


def test_incomplete_prefix_is_not_a_committed_snapshot(
    snapshot_env: tuple[Any, S3SnapshotTarget],
) -> None:
    client, target = snapshot_env
    client.put_object(
        Bucket="backup-bucket",
        Key="snapshots/backup-20990101T000000Z-deadbeef/objects/a.json",
        Body=b"partial",
    )

    assert target.latest_snapshot() is None


def test_copy_failure_never_commits_manifest(
    snapshot_env: tuple[Any, S3SnapshotTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, target = snapshot_env
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

    keys = [
        item["Key"]
        for item in client.list_objects_v2(Bucket="backup-bucket").get("Contents", [])
    ]
    assert not any(key.endswith("/manifest.json") for key in keys)
