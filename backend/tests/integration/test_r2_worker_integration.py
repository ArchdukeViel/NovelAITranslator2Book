"""Opt-in integration tests for the dedicated non-production R2 Worker."""

from __future__ import annotations

import os
import uuid

import pytest

from novelai.storage.backends.r2_gateway import R2GatewayStorage

pytestmark = pytest.mark.slow


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


@pytest.mark.integration
def test_dedicated_r2_worker_exact_object_lifecycle() -> None:
    gateway_url = _required("TEST_R2_GATEWAY_URL")
    bucket = _required("TEST_R2_BUCKET")
    backup_bucket = _required("TEST_R2_BACKUP_BUCKET")
    app_client_id = _required("TEST_R2_APP_CLIENT_ID")
    app_client_secret = _required("TEST_R2_APP_CLIENT_SECRET")
    if bucket != "test-dokushodo" or backup_bucket != "test-dokushodo-backup":
        pytest.fail("R2 Worker integration requires the exact dedicated test bucket classes")
    backend = R2GatewayStorage(
        bucket=bucket,
        bucket_class="app",
        gateway_url=gateway_url,
        client_id=app_client_id,
        client_secret=app_client_secret,
    )
    key = f"novels/integration-{uuid.uuid4().hex}/metadata.json"
    payload = b'{"integration":true}'
    try:
        backend.save(key, payload, content_type="application/json")
        assert backend.head(key).size_bytes == len(payload)
        assert backend.load(key) == payload
        assert backend.probe_readiness() is True
    finally:
        backend.delete(key)
        assert backend.exists(key) is False
        backend.close()
