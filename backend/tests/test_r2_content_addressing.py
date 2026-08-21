"""Focused R2-only storage and deterministic artifact contract tests."""

from __future__ import annotations

from collections.abc import Iterator

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
