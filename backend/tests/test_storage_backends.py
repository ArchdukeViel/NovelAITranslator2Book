"""Tests for explicit R2 storage and the canonical backend factory."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, cast

import pytest
from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.storage.backends import _reset_r2_storage, get_r2_storage
from novelai.storage.backends.base import R2StorageBackend
from novelai.storage.backends.r2 import InMemoryR2Storage, R2Storage


class TestInMemoryR2Storage:
    """Exercise the R2 contract without disk or an external service."""

    @pytest.fixture
    def store(self) -> InMemoryR2Storage:
        return InMemoryR2Storage()

    def test_save_and_load(self, store: InMemoryR2Storage) -> None:
        store.save("hello.txt", b"world")
        assert store.load("hello.txt") == b"world"

    def test_copy_object(self, store: InMemoryR2Storage) -> None:
        store.save("source.txt", b"payload")
        store.copy_object("source.txt", "nested/destination.txt")
        assert store.load("nested/destination.txt") == b"payload"

    def test_load_missing_raises(self, store: InMemoryR2Storage) -> None:
        with pytest.raises(FileNotFoundError):
            store.load("does-not-exist.txt")

    def test_overwrite_and_delete(self, store: InMemoryR2Storage) -> None:
        store.save("x.txt", b"one")
        store.save("x.txt", b"two")
        assert store.load("x.txt") == b"two"
        store.delete("x.txt")
        assert not store.exists("x.txt")

    def test_list_and_size(self, store: InMemoryR2Storage) -> None:
        store.save("a.txt", b"abc")
        store.save("nested/b.txt", b"12345")
        assert store.list_keys("", recursive=True) == ["a.txt", "nested/b.txt"]
        assert store.list_keys("nested") == ["nested/b.txt"]
        assert store.total_size_bytes() == 8

    def test_compare_and_swap(self, store: InMemoryR2Storage) -> None:
        assert store.compare_and_swap("x.txt", None, b"one") is True
        assert store.compare_and_swap("x.txt", b"wrong", b"two") is False
        assert store.compare_and_swap("x.txt", b"one", b"two") is True
        assert store.load("x.txt") == b"two"

    def test_mkdirs_is_virtual_noop(self, store: InMemoryR2Storage) -> None:
        store.mkdirs("some/path")
        assert not store.has_keys("some/path")

    def test_probe_readiness_uses_bucket_head(self, store: InMemoryR2Storage) -> None:
        assert store.probe_readiness() is True
        assert store.stats.operations == {"probe": 1}


pytest.importorskip("moto", reason="moto not installed")


class TestR2Storage:
    """Exercise the real S3-compatible client boundary against moto."""

    @pytest.fixture
    def s3(self) -> Generator[R2StorageBackend]:
        _reset_r2_storage()
        from moto import mock_aws

        with mock_aws():
            import boto3

            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket="test-bucket")
            yield R2Storage(bucket="test-bucket", region="us-east-1", endpoint_url=None, client=client)

    def test_save_and_load(self, s3: R2StorageBackend) -> None:
        s3.save("hello.txt", b"world")
        assert s3.load("hello.txt") == b"world"

    def test_provider_failures_propagate(self, s3: R2StorageBackend, monkeypatch: pytest.MonkeyPatch) -> None:
        from botocore.exceptions import ClientError

        def denied(**_kwargs: object) -> None:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "HeadObject")

        monkeypatch.setattr(cast(Any, s3)._client, "head_object", denied)
        with pytest.raises(ClientError):
            s3.exists("x.txt")

    def test_paginated_contract(self, s3: R2StorageBackend) -> None:
        s3.save("a.txt", b"1")
        s3.save("nested/b.txt", b"12345")
        assert "a.txt" in s3.list_keys("")
        assert "nested/b.txt" in s3.list_keys("nested")
        assert s3.total_size_bytes() == 6


class TestGetR2Storage:
    def test_factory_is_always_r2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_r2_storage()
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", SecretStr("test-access"))
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", SecretStr("test-secret"))
        assert isinstance(get_r2_storage(), R2Storage)

    def test_singleton_and_reset(self) -> None:
        _reset_r2_storage()
        first = get_r2_storage()
        assert first is get_r2_storage()
        _reset_r2_storage()
        assert first is not get_r2_storage()
