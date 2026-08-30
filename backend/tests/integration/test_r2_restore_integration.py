"""Opt-in isolated R2 restore verification through the dedicated Worker."""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest

from novelai.storage.backends.r2_gateway import R2GatewayStorage
from novelai.storage.r2_backup import R2IncrementalBackupTarget

pytestmark = pytest.mark.slow


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


@pytest.mark.integration
def test_r2_restore_isolated_under_test_prefix() -> None:
    gateway_url = _required("TEST_R2_GATEWAY_URL")
    source_bucket = _required("TEST_R2_BUCKET")
    target_bucket = _required("TEST_R2_BACKUP_BUCKET")
    client_id = _required("TEST_R2_RECOVERY_CLIENT_ID")
    client_secret = _required("TEST_R2_RECOVERY_CLIENT_SECRET")
    if source_bucket != "test-dokushodo" or target_bucket != "test-dokushodo-backup":
        pytest.fail("R2 restore integration requires the exact dedicated test buckets")

    source = R2GatewayStorage(
        bucket=source_bucket,
        bucket_class="app",
        gateway_url=gateway_url,
        client_id=client_id,
        client_secret=client_secret,
    )
    target = R2GatewayStorage(
        bucket=target_bucket,
        bucket_class="backup",
        gateway_url=gateway_url,
        client_id=client_id,
        client_secret=client_secret,
    )
    source_key = f"novels/recovery-{uuid.uuid4().hex}/metadata.json"
    restore_key = f"objects/recovery-{uuid.uuid4().hex}/metadata.json"
    payload = b'{"integration":true,"restore":"isolated"}'
    source.save(source_key, payload, content_type="application/json")
    snapshot_id: str | None = None
    backup_key: str | None = None
    try:
        backup = R2IncrementalBackupTarget(source_backend=source, target_backend=target)
        result = backup.create_snapshot()
        snapshot_id = result.snapshot_id
        manifest = backup._load_manifest(snapshot_id)
        entry = next(candidate for candidate in manifest["objects"] if candidate["key"] == source_key)
        backup_key = str(entry["backup_key"])
        restored = target.load(backup_key)
        assert len(restored) == int(entry["size_bytes"])
        assert hashlib.sha256(restored).hexdigest() == str(entry["sha256"])
        target.save(restore_key, restored, content_type="application/json")
        assert target.load(restore_key) == payload
    finally:
        source.delete(source_key)
        target.delete(restore_key)
        if snapshot_id is not None:
            target.delete(f"snapshots/{snapshot_id}/manifest.json")
        if backup_key is not None:
            target.delete(backup_key)
        source.close()
        target.close()
