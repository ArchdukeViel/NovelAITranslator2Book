"""Multi-process file locking primitive.

Provides ``InterProcessFileLock`` — a cross-platform advisory lock backed by an
atomic-rename lockfile.  Works on Windows (no ``fcntl``/``msvcrt`` dependency)
and POSIX systems.  Retries are bounded and stale locks from crashed processes
are reclaimed via PID liveness checks.

Usage::

    with InterProcessFileLock(lock_path) as lock:
        if lock.acquired:
            ...  # exclusive work

The context manager blocks until the lock is acquired or the retry budget is
exhausted, at which point it raises ``TimeoutError``.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
import uuid
from pathlib import Path

from novelai.config.settings import settings

logger = logging.getLogger(__name__)


def _is_pid_alive(pid: int) -> bool:
    """Return True if a process with *pid* is currently running.

    On POSIX, uses ``os.kill(pid, 0)`` which raises ``ProcessLookupError`` if
    the process does not exist. On Windows, uses ``ctypes`` to call
    ``OpenProcess`` since ``os.kill`` does not support signal 0 on Windows.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class InterProcessFileLock:
    """Cross-platform advisory file lock using atomic rename.

    Acquisition writes a temp file then ``os.replace``s it onto the lockfile
    path.  If the rename succeeds, the lock is held.  If it fails because
    another process holds the lock, we retry up to ``retry_count`` times with
    ``retry_delay`` backoff.  Stale lockfiles (whose PID is no longer alive)
    are reclaimed.
    """

    def __init__(
        self,
        lock_path: Path,
        *,
        retry_count: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        self.lock_path = Path(lock_path)
        self.retry_count = retry_count if retry_count is not None else settings.FILE_LOCK_RETRY_COUNT
        self.retry_delay = retry_delay if retry_delay is not None else settings.FILE_LOCK_RETRY_DELAY_SECONDS
        self._acquired = False
        self._owner_id = f"{os.getpid()}:{uuid.uuid4().hex}"

    @property
    def acquired(self) -> bool:
        return self._acquired

    def acquire(self) -> bool:
        """Attempt to acquire the lock, retrying within the configured budget.

        Uses ``O_CREAT | O_EXCL`` to atomically create the lockfile. If the
        file already exists, the creation fails and we retry after checking
        for stale locks.

        Returns ``True`` on success.
        Raises ``TimeoutError`` if the lock cannot be acquired after all retries.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"owner": self._owner_id, "pid": os.getpid(), "ts": time.time()}).encode("utf-8")
        attempts = max(1, self.retry_count)
        for attempt in range(attempts):
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                # Lock is held by someone. Check if stale, then retry.
                if self._reclaim_stale_if_possible():
                    continue
                if attempt < attempts - 1:
                    time.sleep(self.retry_delay)
                continue
            except OSError:
                if attempt < attempts - 1:
                    time.sleep(self.retry_delay)
                continue
            try:
                os.write(fd, payload)
                os.fsync(fd)
            finally:
                os.close(fd)
            self._acquired = True
            return True
        raise TimeoutError(f"Could not acquire file lock after {attempts} attempts: {self.lock_path}")

    def _reclaim_stale_if_possible(self) -> bool:
        """If the lockfile exists but its PID is dead, remove it. Returns True if reclaimed."""
        try:
            data = self.lock_path.read_text(encoding="utf-8")
            info = json.loads(data)
            pid = int(info.get("pid", 0))
            if pid > 0 and not _is_pid_alive(pid):
                with contextlib.suppress(OSError):
                    self.lock_path.unlink(missing_ok=True)
                logger.warning("Reclaimed stale file lock from dead PID %s at %s", pid, self.lock_path)
                return True
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        return False

    def release(self) -> None:
        """Release the lock by removing the lockfile."""
        if self._acquired:
            with contextlib.suppress(OSError):
                self.lock_path.unlink(missing_ok=True)
            self._acquired = False

    def __enter__(self) -> InterProcessFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.release()

    def __del__(self) -> None:
        """Best-effort cleanup if the lock is still held."""
        try:
            if self._acquired:
                self.release()
        except Exception:
            pass
