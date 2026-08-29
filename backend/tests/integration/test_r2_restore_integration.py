"""Opt-in real-R2 restore verification into an isolated prefix.

The workflow supplies dedicated source and target test buckets. This test is
never a production-bucket restore and does not claim hosted recovery success
until the workflow itself runs at the candidate revision.
"""

from __future__ import annotations

import hashlib
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
def test_real_r2_restore_into_isolated_prefix() -> None:
    boto3 = pytest.importorskip("boto3")
    from botocore.exceptions import ClientError

    endpoint = _required("TEST_R2_ENDPOINT")
    source_bucket = _required("TEST_R2_SOURCE_BUCKET")
    target_bucket = _required("TEST_R2_TARGET_BUCKET")
    if source_bucket == target_bucket or {source_bucket, target_bucket} & {"dokushodo", "dokushodo-backup"}:
        pytest.fail("Managed-services R2 integration requires dedicated non-production test buckets")
    token = f"integration-{int(time.time())}-{os.urandom(4).hex()}"
    payload = b'{"integration":true,"restore":"isolated-prefix"}'

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
    restore_key = f"restore-verification/{token}/metadata.json"
    backup_key = f"objects/{source_key}"
    source_created = False
    restore_created = False
    backup_preexisting = False
    snapshot_id: str | None = None

    try:
        application_client.put_object(Bucket=source_bucket, Key=source_key, Body=payload)
        source_created = True
        try:
            target_client.head_object(Bucket=target_bucket, Key=backup_key)
            backup_preexisting = True
        except ClientError:
            backup_preexisting = False

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
        entry = next(
            (candidate for candidate in manifest["objects"] if candidate.get("key") == source_key),
            None,
        )
        assert entry is not None
        assert result.verified is True
        assert backup.verify_snapshot(snapshot_id).verified is True

        response = target_client.get_object(Bucket=target_bucket, Key=str(entry["backup_key"]))
        body = response["Body"]
        try:
            restored_bytes = body.read()
        finally:
            body.close()
        assert len(restored_bytes) == int(entry["size_bytes"])
        assert hashlib.sha256(restored_bytes).hexdigest() == str(entry["sha256"])

        target_client.put_object(Bucket=target_bucket, Key=restore_key, Body=restored_bytes)
        restore_created = True
        restored_response = target_client.get_object(Bucket=target_bucket, Key=restore_key)
        restored_body = restored_response["Body"]
        try:
            assert restored_body.read() == payload
        finally:
            restored_body.close()
    finally:
        if restore_created:
            target_client.delete_object(Bucket=target_bucket, Key=restore_key)
        if snapshot_id is not None:
            target_client.delete_object(Bucket=target_bucket, Key=f"snapshots/{snapshot_id}/manifest.json")
        if not backup_preexisting:
            target_client.delete_object(Bucket=target_bucket, Key=backup_key)
        if source_created:
            application_client.delete_object(Bucket=source_bucket, Key=source_key)
