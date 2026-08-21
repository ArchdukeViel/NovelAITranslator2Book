"""Real R2 integration tests against an S3-compatible endpoint.

The test uses a unique namespace wrapper because the application R2 client
does not support a configurable production key prefix. The configured test
bucket must never be a production bucket.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from novelai.storage.backends.base import StorageBackend
from novelai.storage.backends.r2 import R2Storage

pytestmark = pytest.mark.slow


def _env_or_skip(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} not set; skipping real R2 integration test")
    return value


class _IsolatedR2Store(StorageBackend):
    """Test-only namespace view over the explicit R2 implementation."""

    def __init__(self, backend: R2Storage, prefix: str) -> None:
        self._backend = backend
        self._prefix = prefix.strip("/")

    def _key(self, path: str | Path) -> str:
        relative = str(path).replace("\\", "/").strip("/")
        return f"{self._prefix}/{relative}" if relative else self._prefix

    def _strip(self, key: str) -> str:
        return key[len(self._prefix) + 1 :] if key.startswith(self._prefix + "/") else key

    def save(self, path: str | Path, data: bytes) -> None:
        self._backend.save(self._key(path), data)

    def load(self, path: str | Path) -> bytes:
        return self._backend.load(self._key(path))

    def delete(self, path: str | Path) -> None:
        self._backend.delete(self._key(path))

    def exists(self, path: str | Path) -> bool:
        return self._backend.exists(self._key(path))

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        return [self._strip(key) for key in self._backend.list_keys(self._key(prefix), recursive=recursive)]

    def has_keys(self, prefix: str | Path) -> bool:
        return self._backend.has_keys(self._key(prefix))

    def total_size_bytes(self) -> int:
        return sum(self._backend.head(key).size_bytes for key in self._backend.list_keys(self._prefix, recursive=True))

    def mkdirs(self, path: str | Path) -> None:
        self._backend.mkdirs(self._key(path))


@pytest.fixture(scope="module")
def r2_backend() -> Iterator[tuple[_IsolatedR2Store, str]]:
    endpoint = _env_or_skip("TEST_R2_ENDPOINT")
    access_key = _env_or_skip("TEST_R2_ACCESS_KEY")
    secret_key = _env_or_skip("TEST_R2_SECRET_KEY")
    bucket = _env_or_skip("TEST_R2_BUCKET")
    region = os.environ.get("TEST_R2_REGION", "auto")
    prefix = f"_integration_test_{int(time.time())}_{os.urandom(4).hex()}"

    import boto3

    raw_client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    try:
        raw_client.head_bucket(Bucket=bucket)
    except raw_client.exceptions.ClientError as exc:
        pytest.skip(f"Configured R2 test bucket is not accessible: {exc}")

    backend = R2Storage(
        bucket=bucket,
        region=region,
        endpoint_url=endpoint,
        access_key_id=access_key,
        secret_access_key=secret_key,
    )
    isolated = _IsolatedR2Store(backend, prefix)
    try:
        yield isolated, prefix
    finally:
        try:
            response = raw_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            while True:
                objects = response.get("Contents", [])
                if objects:
                    raw_client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                    )
                if not response.get("IsTruncated"):
                    break
                response = raw_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=prefix,
                    ContinuationToken=response.get("NextContinuationToken"),
                )
        except Exception:
            pass


@pytest.mark.integration
class TestR2Integration:
    def test_save_and_exists(self, r2_backend: tuple[_IsolatedR2Store, str]) -> None:
        backend, _ = r2_backend
        backend.save("hello.txt", b"world")
        assert backend.exists("hello.txt")

    def test_load_and_overwrite(self, r2_backend: tuple[_IsolatedR2Store, str]) -> None:
        backend, _ = r2_backend
        backend.save("data.bin", b"v1")
        backend.save("data.bin", b"v2")
        assert backend.load("data.bin") == b"v2"

    def test_delete_and_missing(self, r2_backend: tuple[_IsolatedR2Store, str]) -> None:
        backend, _ = r2_backend
        backend.delete("does_not_exist.txt")
        backend.save("delete_me.txt", b"bye")
        backend.delete("delete_me.txt")
        assert not backend.exists("delete_me.txt")
        with pytest.raises(FileNotFoundError):
            backend.load("impossible/file.txt")

    def test_list_and_prefix_presence(self, r2_backend: tuple[_IsolatedR2Store, str]) -> None:
        backend, _ = r2_backend
        backend.save("novels/novel-a/chapters/0001.json", b"chapter")
        backend.save("novels/novel-a/metadata.json", b"meta")
        backend.save("novels/novel-a/chapters/assets/x.txt", b"asset")
        assert backend.has_keys("novels/novel-a/chapters")
        assert not backend.has_keys("novels/nonexistent")
        assert backend.has_keys("novels/novel-a")

    def test_prefix_boundaries_and_recursive_listing(self, r2_backend: tuple[_IsolatedR2Store, str]) -> None:
        backend, _ = r2_backend
        backend.save("novels/n1/chapters/0001.json", b"c1")
        backend.save("novels/n10/chapters/0001.json", b"c10")
        assert backend.has_keys("novels/n1")
        assert backend.has_keys("novels/n10")
        assert not backend.has_keys("novels/n100")
        assert "novels/n1/chapters/0001.json" in backend.list_keys("novels/n1", recursive=True)

    def test_recursive_delete_is_confined(self, r2_backend: tuple[_IsolatedR2Store, str]) -> None:
        backend, _ = r2_backend
        backend.save("novels/alpha/chapters/0001.json", b"a")
        backend.save("novels/beta/chapters/0001.json", b"b")
        for key in backend.list_keys("novels/alpha", recursive=True):
            backend.delete(key)
        assert not backend.has_keys("novels/alpha")
        assert backend.has_keys("novels/beta")
