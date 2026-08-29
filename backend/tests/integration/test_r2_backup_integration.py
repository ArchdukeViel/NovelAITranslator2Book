"""Opt-in real-R2 incremental backup verification with isolated test objects."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from novelai.storage.r2_backup import R2IncrementalBackupTarget

pytestmark = pytest.mark.slow


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


@pytest.mark.integration
def test_real_r2_backup_credential_split() -> None:
    boto3 = pytest.importorskip("boto3")
    from botocore.exceptions import ClientError

    endpoint = _required("TEST_R2_ENDPOINT")
    source_bucket = _required("TEST_R2_SOURCE_BUCKET")
    target_bucket = _required("TEST_R2_TARGET_BUCKET")
    if source_bucket == target_bucket or {source_bucket, target_bucket} & {"dokushodo", "dokushodo-backup"}:
        pytest.fail("Managed-services R2 integration requires dedicated non-production test buckets")
    token = f"integration-{int(time.time())}-{os.urandom(4).hex()}"

    def client(access_name: str, secret_name: str) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=os.environ.get("TEST_R2_REGION", "auto"),
            aws_access_key_id=_required(access_name),
            aws_secret_access_key=_required(secret_name),
        )

    application_client = client("TEST_R2_APP_ACCESS_KEY_ID", "TEST_R2_APP_SECRET_ACCESS_KEY")
    source_client = client(
        "TEST_R2_SNAPSHOT_SOURCE_ACCESS_KEY_ID",
        "TEST_R2_SNAPSHOT_SOURCE_SECRET_ACCESS_KEY",
    )
    target_client = client("TEST_R2_BACKUP_ACCESS_KEY_ID", "TEST_R2_BACKUP_SECRET_ACCESS_KEY")
    source_key = f"novels/{token}/metadata.json"
    application_client.put_object(Bucket=source_bucket, Key=source_key, Body=b'{"integration":true}')
    backup: R2IncrementalBackupTarget | None = None
    snapshot_id: str | None = None
    backup_key: str | None = None
    try:
        backup = R2IncrementalBackupTarget(
            source_bucket=source_bucket,
            target_bucket=target_bucket,
            target_prefix="snapshots",
            endpoint_url=endpoint,
            region=os.environ.get("TEST_R2_REGION", "auto"),
            source_access_key_id=None,
            source_secret_access_key=None,
            target_access_key_id=None,
            target_secret_access_key=None,
            source_client=source_client,
            target_client=target_client,
        )
        result = backup.create_snapshot()
        snapshot_id = result.snapshot_id
        manifest = backup._load_manifest(snapshot_id)
        backup_key = str(manifest["objects"][0]["backup_key"])
        assert result.verified is True
        assert result.files_count == 1
        assert backup.verify_snapshot(result.snapshot_id).verified is True
        with pytest.raises(ClientError):
            source_client.put_object(Bucket=source_bucket, Key=f"{source_key}.forbidden", Body=b"x")
        with pytest.raises(ClientError):
            target_client.get_object(Bucket=source_bucket, Key=source_key)
    finally:
        application_client.delete_object(Bucket=source_bucket, Key=source_key)
        if snapshot_id is not None:
            target_client.delete_object(Bucket=target_bucket, Key=f"snapshots/{snapshot_id}/manifest.json")
        if backup_key is not None:
            target_client.delete_object(Bucket=target_bucket, Key=backup_key)
