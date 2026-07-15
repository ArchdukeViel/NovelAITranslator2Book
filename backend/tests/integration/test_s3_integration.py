"""S3 storage backend real integration test.

Prerequisites:
  - A running S3-compatible endpoint (MinIO, AWS S3, etc.)
  - Environment variables:
      TEST_S3_ENDPOINT=http://localhost:9000
      TEST_S3_ACCESS_KEY=minioadmin
      TEST_S3_SECRET_KEY=minioadmin
      TEST_S3_BUCKET=novelai-test
      (TEST_S3_REGION=us-east-1  # optional, default)

Usage:
  pytest backend/tests/integration/test_s3_integration.py -v -m integration

Safety:
  Uses an isolated test prefix (_integration_test_TIMESTAMP/) that is
  cleaned up after the test, regardless of pass/fail.
  NEVER point TEST_S3_BUCKET to a production bucket.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

import pytest

from novelai.storage.backends.s3 import S3Backend


def _env_or_skip(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} not set; skipping real S3 integration test")
    return value


@pytest.fixture(scope="module")
def s3_backend() -> Iterator[tuple[S3Backend, str]]:
    """Create an S3Backend pointed at the configured test endpoint, with
    an isolated test prefix that is cleaned up after the module runs."""
    endpoint = _env_or_skip("TEST_S3_ENDPOINT")
    access_key = _env_or_skip("TEST_S3_ACCESS_KEY")
    secret_key = _env_or_skip("TEST_S3_SECRET_KEY")
    bucket = _env_or_skip("TEST_S3_BUCKET")
    region = os.environ.get("TEST_S3_REGION", "us-east-1")

    test_prefix = f"_integration_test_{int(time.time())}_{os.urandom(4).hex()}"

    import boto3

    raw_client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    # Verify bucket exists and is accessible. Skip if not (bucket must be pre-created).
    try:
        raw_client.head_bucket(Bucket=bucket)
    except raw_client.exceptions.ClientError as exc:
        pytest.skip(f"Bucket {bucket!r} not accessible: {exc}")

    backend = S3Backend(
        bucket=bucket,
        region=region,
        key_prefix=test_prefix,
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    yield backend, test_prefix

    # Cleanup: delete everything under the test prefix
    try:
        resp = raw_client.list_objects_v2(Bucket=bucket, Prefix=test_prefix)
        objects = resp.get("Contents", [])
        while objects:
            keys = [{"Key": obj["Key"]} for obj in objects]
            raw_client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            if resp.get("IsTruncated"):
                resp = raw_client.list_objects_v2(
                    Bucket=bucket, Prefix=test_prefix,
                    ContinuationToken=resp.get("NextContinuationToken"),
                )
                objects = resp.get("Contents", [])
            else:
                objects = []
    except Exception:
        pass  # best-effort cleanup


@pytest.mark.integration
class TestS3Integration:
    """Real S3 backend integration tests. Requires TEST_S3_* env vars."""

    def test_save_and_exists(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        path = "hello.txt"
        backend.save(path, b"world")
        assert backend.exists(path)

    def test_load_returns_saved_bytes(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        path = "data.bin"
        backend.save(path, b"\x00\x01\x02\xff")
        assert backend.load(path) == b"\x00\x01\x02\xff"

    def test_overwrite(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        path = "overwrite.txt"
        backend.save(path, b"v1")
        backend.save(path, b"v2")
        assert backend.load(path) == b"v2"

    def test_delete(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        path = "delete_me.txt"
        backend.save(path, b"bye")
        assert backend.exists(path)
        backend.delete(path)
        assert not backend.exists(path)

    def test_delete_nonexistent_no_error(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.delete("does_not_exist.txt")  # should not raise

    def test_load_nonexistent_raises(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        with pytest.raises(FileNotFoundError):
            backend.load("impossible/file.txt")

    def test_list_keys(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("a.txt", b"1")
        backend.save("b.txt", b"2")
        keys = backend.list_keys("")
        assert "a.txt" in keys
        assert "b.txt" in keys
        assert "c.txt" not in keys

    def test_list_keys_with_subdir(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("sub/x.txt", b"x")
        backend.save("sub/y.txt", b"y")
        keys = backend.list_keys("sub/")
        assert "sub/x.txt" in keys
        assert "sub/y.txt" in keys

    # ---- has_keys (logical-prefix presence) ----

    def test_has_keys_returns_true_with_descendants(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, prefix = s3_backend
        backend.save("novels/novel-a/chapters/0001.json", b"chapter")
        backend.save("novels/novel-a/metadata.json", b"meta")
        backend.save("novels/novel-a/chapters/assets/x.txt", b"asset")

        assert backend.has_keys("novels/novel-a/chapters") is True
        assert backend.has_keys("novels/novel-a") is True

    def test_has_keys_returns_false_for_absent_prefix(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        assert backend.has_keys("novels/nonexistent") is False

    def test_has_keys_boundary_separates_prefixes(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("novels/n1/chapters/0001.json", b"c1")
        backend.save("novels/n10/chapters/0001.json", b"c10")

        assert backend.has_keys("novels/n1") is True
        assert backend.has_keys("novels/n10") is True
        assert backend.has_keys("novels/n100") is False

    def test_has_keys_not_fooled_by_partial_prefix(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("novels/something/metadata.json", b"meta")

        assert backend.has_keys("novels/some") is False

    # ---- padded chapter listing ----

    def test_padded_chapter_listing_is_deterministic(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("novels/padded/chapters/0002.json", b'{"id":"2","raw":{"text":"ch2"}}')
        backend.save("novels/padded/chapters/0001.json", b'{"id":"1","raw":{"text":"ch1"}}')
        backend.save("novels/padded/chapters/0010.json", b'{"id":"10","raw":{"text":"ch10"}}')

        keys = backend.list_keys("novels/padded/chapters")
        assert keys == [
            "novels/padded/chapters/0001.json",
            "novels/padded/chapters/0002.json",
            "novels/padded/chapters/0010.json",
        ]

    def test_padded_listing_recursive(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("novels/padded-rec/chapters/0001.json", b'{"raw":{"text":"a"}}')
        backend.save("novels/padded-rec/chapters/assets/imgs/a.png", b"image")

        all_keys = backend.list_keys("novels/padded-rec/chapters", recursive=True)
        rec_key = "novels/padded-rec/chapters/assets/imgs/a.png"
        assert rec_key in all_keys

        flat_keys = backend.list_keys("novels/padded-rec/chapters")
        assert rec_key not in flat_keys

    # ---- recursive deletion ----

    def test_recursive_delete_prefix_confined(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("novels/alpha/chapters/0001.json", b'{"raw":{"text":"a"}}')
        backend.save("novels/beta/chapters/0001.json", b'{"raw":{"text":"b"}}')
        backend.save("novels/alpha/metadata.json", b'{"novel_id":"alpha"}')

        keys_alpha = backend.list_keys("novels/alpha", recursive=True)
        for key in keys_alpha:
            backend.delete(key)

        # alpha should be gone
        assert backend.has_keys("novels/alpha") is False
        # beta should survive
        assert backend.has_keys("novels/beta") is True

    def test_absence_after_recursive_delete(self, s3_backend: tuple[S3Backend, str]) -> None:
        backend, _ = s3_backend
        backend.save("novels/gone/chapters/0001.json", b'del')
        backend.delete("novels/gone/chapters/0001.json")
        assert backend.has_keys("novels/gone") is False
