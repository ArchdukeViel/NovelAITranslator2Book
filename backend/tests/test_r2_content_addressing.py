"""Focused R2-only storage and deterministic artifact contract tests."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from typing import Any
from unittest.mock import patch

import pytest

from novelai.storage.backends.r2 import R2Storage
from novelai.storage.content_addressing import (
    ArtifactConflictError,
    artifact_key,
    deterministic_gzip,
    prepare_json_artifact,
)


def test_logical_hash_excludes_volatile_timestamps_and_normalizes_text() -> None:
    first = prepare_json_artifact(
        {"text": "line\r\nnext", "updated_at": "2026-01-01T00:00:00Z"},
        novel_id="n1",
        kind="chapters",
        identity="1",
    )
    second = prepare_json_artifact(
        {"updated_at": "2027-01-01T00:00:00Z", "text": "line\nnext"},
        novel_id="n1",
        kind="chapters",
        identity="1",
    )
    assert first.logical_hash == second.logical_hash
    assert first.compressed_bytes == second.compressed_bytes
    assert first.key == "novels/n1/chapters/1/" + first.logical_hash + ".json.gz"
    assert deterministic_gzip(first.logical_bytes) == first.compressed_bytes


def test_application_keys_have_no_legacy_prefix() -> None:
    key = artifact_key("n1", "translations", "chapter:1", "a" * 64)
    assert key == "novels/n1/translations/chapter:1/" + "a" * 64 + ".json.gz"
    assert not key.startswith("storage/")
    assert "v1/" not in key


@pytest.fixture()
def r2() -> Iterator[R2Storage]:
    pytest.importorskip("moto")
    from moto import mock_aws

    with mock_aws():
        import boto3

        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="dokushodo")
        yield R2Storage(bucket="dokushodo", region="auto", endpoint_url=None, client=client)


def test_immutable_write_is_idempotent_and_rejects_changed_bytes(r2: R2Storage) -> None:
    artifact = prepare_json_artifact(
        {"chapter_id": "1", "text": "hello"},
        novel_id="n1",
        kind="chapters",
        identity="1",
    )
    first = r2.put_immutable(artifact.key, artifact.compressed_bytes, logical_sha256=artifact.logical_hash)
    second = r2.put_immutable(artifact.key, artifact.compressed_bytes, logical_sha256=artifact.logical_hash)
    assert first.created is True
    assert second.created is False
    with pytest.raises(ArtifactConflictError):
        r2.put_immutable(artifact.key, b"different", logical_sha256=artifact.logical_hash)


def test_recursive_and_nonrecursive_listing_are_paginated(r2: R2Storage) -> None:
    for index in range(1105):
        r2.save(f"novels/n1/chapters/{index}/body.json.gz", b"x")
    recursive = r2.list_keys("novels/n1", recursive=True)
    assert len(recursive) == 1105
    immediate = r2.list_keys("novels/n1", recursive=False)
    assert len(immediate) == 1
    assert immediate == ["novels/n1/chapters/"]


def test_delete_prefix_removes_all_pages(r2: R2Storage) -> None:
    for index in range(1105):
        r2.save(f"novels/n1/assets/{index}.jpg", b"x")
    assert r2.delete_prefix("novels/n1/assets") == 1105
    assert r2.list_keys("novels/n1/assets", recursive=True) == []


def test_delete_prefix_snapshots_keys_before_mutating_listing(r2: R2Storage) -> None:
    for index in range(1105):
        r2.save(f"novels/n1/assets/{index}.jpg", b"x")
    all_keys = [f"novels/n1/assets/{index}.jpg" for index in range(1105)]
    state = {"delete_started": False}
    original_delete_objects = r2._client.delete_objects

    class MutatingPaginator:
        def paginate(self, **_: Any) -> Iterator[dict[str, Any]]:
            yield {"Contents": [{"Key": key} for key in all_keys[:1000]]}
            remaining = [] if state["delete_started"] else all_keys[1000:]
            yield {"Contents": [{"Key": key} for key in remaining]}

    def delete_objects(*args: Any, **kwargs: Any) -> Any:
        state["delete_started"] = True
        return original_delete_objects(*args, **kwargs)

    with (
        patch.object(r2._client, "get_paginator", return_value=MutatingPaginator()),
        patch.object(r2._client, "delete_objects", side_effect=delete_objects),
    ):
        assert r2.delete_prefix("novels/n1/assets") == 1105
    assert r2.list_keys("novels/n1/assets", recursive=True) == []


def test_stream_upload_uses_multipart_transfer_and_provider_checksum(r2: R2Storage) -> None:
    data = b"streamed-artifact" * 600_000
    with (
        patch.object(r2._client, "create_multipart_upload", wraps=r2._client.create_multipart_upload) as multipart,
        patch.object(r2._client, "upload_fileobj", wraps=r2._client.upload_fileobj) as upload,
    ):
        written = r2.save_stream(
            "novels/n1/assets/large.bin",
            BytesIO(data),
            content_length=len(data),
            content_type="application/octet-stream",
        )

    assert written == len(data)
    assert multipart.called
    assert upload.call_args is not None
    assert upload.call_args.kwargs["ExtraArgs"]["ChecksumAlgorithm"] == "SHA256"
    assert upload.call_args.kwargs["Config"].multipart_threshold == R2Storage._MULTIPART_THRESHOLD_BYTES
    assert r2.head("novels/n1/assets/large.bin").size_bytes == len(data)


def test_stream_upload_cleans_object_when_declared_length_is_wrong(r2: R2Storage) -> None:
    with pytest.raises(ValueError, match="stream length mismatch"):
        r2.save_stream("novels/n1/assets/wrong.bin", BytesIO(b"three"), content_length=2)

    assert not r2.exists("novels/n1/assets/wrong.bin")
