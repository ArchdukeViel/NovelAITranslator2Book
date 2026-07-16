"""Opt-in real-R2 snapshot verification with isolated prefixes and cleanup."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from novelai.storage.backends.s3_snapshot import S3SnapshotTarget


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


@pytest.mark.integration
def test_real_r2_snapshot_credential_split() -> None:
    boto3 = pytest.importorskip("boto3")
    from botocore.exceptions import ClientError
    endpoint = _required("TEST_R2_ENDPOINT")
    source_bucket = _required("TEST_R2_SOURCE_BUCKET")
    target_bucket = _required("TEST_R2_TARGET_BUCKET")
    source_prefix = f"_integration_test_{int(time.time())}_{os.urandom(4).hex()}"
    target_prefix = f"_integration_test/{source_prefix}"

    def client(access_name: str, secret_name: str) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=os.environ.get("TEST_R2_REGION", "auto"),
            aws_access_key_id=_required(access_name),
            aws_secret_access_key=_required(secret_name),
        )

    application_client = client("TEST_R2_APP_ACCESS_KEY", "TEST_R2_APP_SECRET_KEY")
    source_client = client("TEST_R2_SNAPSHOT_SOURCE_ACCESS_KEY", "TEST_R2_SNAPSHOT_SOURCE_SECRET_KEY")
    target_client = client("TEST_R2_BACKUP_ACCESS_KEY", "TEST_R2_BACKUP_SECRET_KEY")
    source_key = f"{source_prefix}/novels/integration/metadata.json"
    application_client.put_object(Bucket=source_bucket, Key=source_key, Body=b'{"integration":true}')
    snapshot = S3SnapshotTarget(
        source_bucket=source_bucket,
        source_prefix=source_prefix,
        target_bucket=target_bucket,
        target_prefix=target_prefix,
        endpoint_url=endpoint,
        region=os.environ.get("TEST_R2_REGION", "auto"),
        source_access_key_id=None,
        source_secret_access_key=None,
        target_access_key_id=None,
        target_secret_access_key=None,
        source_client=source_client,
        target_client=target_client,
    )
    try:
        result = snapshot.create_snapshot()
        assert result.verified is True
        assert result.files_count == 1
        assert snapshot.verify_snapshot(result.snapshot_id).verified is True
        with pytest.raises(ClientError):
            source_client.put_object(Bucket=source_bucket, Key=f"{source_prefix}/forbidden", Body=b"x")
        with pytest.raises(ClientError):
            target_client.get_object(Bucket=source_bucket, Key=source_key)
    finally:
        application_client.delete_object(Bucket=source_bucket, Key=source_key)
        paginator = target_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=target_bucket, Prefix=f"{target_prefix}/"):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                target_client.delete_objects(Bucket=target_bucket, Delete={"Objects": objects})
