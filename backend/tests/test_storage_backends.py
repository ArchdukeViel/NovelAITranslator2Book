"""Tests for storage backends (filesystem + S3 + factory)."""

from __future__ import annotations

from pathlib import Path

import pytest

from novelai.storage.backends import _reset_backend, get_storage_backend
from novelai.storage.backends.base import StorageBackend
from novelai.storage.backends.filesystem import FilesystemBackend, _try_unlink

# ── FilesystemBackend ────────────────────────────────────────────────

class TestFilesystemBackend:
    """Real filesystem I/O against a temp directory."""

    @pytest.fixture
    def fs(self, tmp_path: Path) -> FilesystemBackend:
        return FilesystemBackend(base_dir=tmp_path)

    def test_save_and_load(self, fs: FilesystemBackend, tmp_path: Path) -> None:
        fs.save("hello.txt", b"world")
        assert fs.load("hello.txt") == b"world"
        assert (tmp_path / "hello.txt").read_bytes() == b"world"

    def test_load_missing_raises(self, fs: FilesystemBackend) -> None:
        with pytest.raises(FileNotFoundError):
            fs.load("does-not-exist.txt")

    def test_overwrite(self, fs: FilesystemBackend) -> None:
        fs.save("x.txt", b"one")
        fs.save("x.txt", b"two")
        assert fs.load("x.txt") == b"two"

    def test_delete(self, fs: FilesystemBackend) -> None:
        fs.save("x.txt", b"data")
        fs.delete("x.txt")
        assert not fs.exists("x.txt")

    def test_delete_missing_is_noop(self, fs: FilesystemBackend) -> None:
        fs.delete("nope.txt")

    def test_exists(self, fs: FilesystemBackend) -> None:
        assert not fs.exists("x.txt")
        fs.save("x.txt", b"")
        assert fs.exists("x.txt")

    def test_list_keys_empty(self, fs: FilesystemBackend) -> None:
        assert fs.list_keys("") == []

    def test_list_keys(self, fs: FilesystemBackend) -> None:
        fs.save("a.txt", b"1")
        fs.save("b.txt", b"2")
        keys = fs.list_keys("")
        assert "a.txt" in keys
        assert "b.txt" in keys

    def test_list_keys_nested(self, fs: FilesystemBackend) -> None:
        fs.save("sub/x.txt", b"1")
        fs.save("sub/y.txt", b"2")
        keys = fs.list_keys("sub")
        assert "sub/x.txt" in keys
        assert "sub/y.txt" in keys

    def test_mkdirs(self, fs: FilesystemBackend, tmp_path: Path) -> None:
        p = tmp_path / "a" / "b" / "c"
        fs.mkdirs(p)
        assert p.parent.exists()

    def test_absolute_path(self, fs: FilesystemBackend, tmp_path: Path) -> None:
        outside = tmp_path / "outside.txt"
        fs.save(outside, b"data")
        assert outside.exists()

    def test_atomic_write_no_partial(self, fs: FilesystemBackend, tmp_path: Path) -> None:
        fs.save("atomic.txt", b"final")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert not tmp_files


# ── S3Backend (moto mock) ───────────────────────────────────────────

pytest.importorskip("moto", reason="moto not installed")


class TestS3Backend:
    """S3 backend tested against a moto mock."""

    @pytest.fixture
    def s3(self) -> StorageBackend:
        _reset_backend()
        from moto import mock_aws

        with mock_aws():
            from novelai.storage.backends.s3 import S3Backend

            backend = S3Backend(bucket="test-bucket", region="us-east-1")
            import boto3

            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket="test-bucket")
            yield backend

    def test_save_and_load(self, s3: StorageBackend) -> None:
        s3.save("hello.txt", b"world")
        assert s3.load("hello.txt") == b"world"

    def test_load_missing_raises(self, s3: StorageBackend) -> None:
        with pytest.raises(Exception):
            s3.load("does-not-exist.txt")

    def test_overwrite(self, s3: StorageBackend) -> None:
        s3.save("x.txt", b"one")
        s3.save("x.txt", b"two")
        assert s3.load("x.txt") == b"two"

    def test_delete(self, s3: StorageBackend) -> None:
        s3.save("x.txt", b"data")
        s3.delete("x.txt")
        assert not s3.exists("x.txt")

    def test_delete_missing_is_noop(self, s3: StorageBackend) -> None:
        s3.delete("nope.txt")

    def test_exists(self, s3: StorageBackend) -> None:
        assert not s3.exists("x.txt")
        s3.save("x.txt", b"")
        assert s3.exists("x.txt")

    def test_list_keys(self, s3: StorageBackend) -> None:
        s3.save("a.txt", b"1")
        s3.save("b.txt", b"2")
        keys = s3.list_keys("")
        assert "a.txt" in keys
        assert "b.txt" in keys

    def test_list_keys_nested(self, s3: StorageBackend) -> None:
        s3.save("sub/x.txt", b"1")
        s3.save("sub/y.txt", b"2")
        keys = s3.list_keys("sub")
        assert "sub/x.txt" in keys

    def test_mkdirs_is_noop(self, s3: StorageBackend) -> None:
        s3.mkdirs("some/path")

    def test_key_prefix(self) -> None:
        from novelai.storage.backends.s3 import S3Backend

        backend = S3Backend(bucket="b", key_prefix="myapp/data")
        assert backend._key("hello.txt") == "myapp/data/hello.txt"
        assert backend._key("sub/file.txt") == "myapp/data/sub/file.txt"


# ── Factory / singleton ──────────────────────────────────────────────

class TestGetStorageBackend:
    """Factory behaviour — does not test I/O."""

    def test_default_is_filesystem(self) -> None:
        _reset_backend()
        backend = get_storage_backend()
        assert isinstance(backend, FilesystemBackend)

    def test_singleton(self) -> None:
        _reset_backend()
        a = get_storage_backend()
        b = get_storage_backend()
        assert a is b

    def test_reset(self) -> None:
        _reset_backend()
        a = get_storage_backend()
        _reset_backend()
        b = get_storage_backend()
        assert a is not b

    def test_unknown_choice_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_backend()
        monkeypatch.setenv("STORAGE_BACKEND", "nfs")
        with pytest.raises(RuntimeError, match="Unknown STORAGE_BACKEND"):
            get_storage_backend()


# ── _try_unlink helper ──────────────────────────────────────────────

class TestTryUnlink:
    def test_missing_file(self, tmp_path: Path) -> None:
        _try_unlink(tmp_path / "nope")

    def test_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.write_text("hi")
        _try_unlink(p)
        assert not p.exists()
