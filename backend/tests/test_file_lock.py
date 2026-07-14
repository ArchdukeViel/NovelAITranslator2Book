"""Tests for the multi-process InterProcessFileLock primitive."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from novelai.storage.file_lock import InterProcessFileLock, _is_pid_alive


class TestIsPidAlive:
    def test_current_pid_is_alive(self) -> None:
        assert _is_pid_alive(os.getpid()) is True

    def test_dead_pid_is_not_alive(self) -> None:
        # PID 999999 is extremely unlikely to exist.
        assert _is_pid_alive(999999) is False

    def test_zero_pid_is_not_alive(self) -> None:
        assert _is_pid_alive(0) is False


class TestInterProcessFileLock:
    def test_acquire_and_release(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        lock = InterProcessFileLock(lock_path, retry_count=1, retry_delay=0.01)
        assert lock.acquired is False
        lock.acquire()
        assert lock.acquired is True
        assert lock_path.exists()
        lock.release()
        assert lock.acquired is False
        assert not lock_path.exists()

    def test_context_manager(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "ctx.lock"
        with InterProcessFileLock(lock_path, retry_count=1, retry_delay=0.01) as lock:
            assert lock.acquired is True
            assert lock_path.exists()
        assert not lock_path.exists()

    def test_second_lock_waits_then_acquires(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "multi.lock"
        lock1 = InterProcessFileLock(lock_path, retry_count=5, retry_delay=0.05)
        lock1.acquire()
        assert lock1.acquired is True

        # Second lock should fail initially but succeed after lock1 is released.
        lock2 = InterProcessFileLock(lock_path, retry_count=20, retry_delay=0.05)

        # Release lock1 in a separate thread after a short delay.
        import threading

        def release_after_delay():
            time.sleep(0.1)
            lock1.release()

        thread = threading.Thread(target=release_after_delay, daemon=True)
        thread.start()
        lock2.acquire()
        thread.join()
        assert lock2.acquired is True
        lock2.release()

    def test_stale_lock_reclaimed(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "stale.lock"
        # Write a stale lockfile with a dead PID.
        stale_payload = json.dumps({"owner": "dead:abc", "pid": 999999, "ts": time.time()})
        lock_path.write_text(stale_payload, encoding="utf-8")
        lock = InterProcessFileLock(lock_path, retry_count=3, retry_delay=0.01)
        lock.acquire()
        assert lock.acquired is True
        lock.release()

    def test_timeout_raises(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "timeout.lock"
        lock1 = InterProcessFileLock(lock_path, retry_count=1, retry_delay=0.01)
        lock1.acquire()

        lock2 = InterProcessFileLock(lock_path, retry_count=2, retry_delay=0.01)
        with pytest.raises(TimeoutError, match="Could not acquire file lock"):
            lock2.acquire()
        lock1.release()

    def test_lockfile_contains_pid(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "info.lock"
        with InterProcessFileLock(lock_path, retry_count=1, retry_delay=0.01):
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            assert data["pid"] == os.getpid()
            assert "owner" in data
            assert "ts" in data

    def test_release_is_idempotent(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "idem.lock"
        lock = InterProcessFileLock(lock_path, retry_count=1, retry_delay=0.01)
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise.
        assert lock.acquired is False

    def test_del_releases_lock(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "del.lock"
        lock = InterProcessFileLock(lock_path, retry_count=1, retry_delay=0.01)
        lock.acquire()
        assert lock_path.exists()
        del lock
        assert not lock_path.exists()
