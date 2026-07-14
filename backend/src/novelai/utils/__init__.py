"""Utility helpers for Novel AI."""

import contextlib
import os
import tempfile
from pathlib import Path


def format_usd(amount: float, decimals: int = 4) -> str:
    """Format a USD amount for human-readable display."""
    if decimals < 0:
        raise ValueError("decimals must be >= 0.")
    return f"${amount:,.{decimals}f}"


def atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically (write-to-temp then rename).

    Flushes and fsyncs the temp file before replacing the target so that
    readers never see a partial file. Best-effort fsyncs the parent directory.
    On Windows, retries the replace if the target is briefly locked.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, path)
            replaced = True
            _fsync_directory(path.parent)
        except PermissionError:
            # On Windows the target may be briefly locked; try to remove then replace.
            try:
                with contextlib.suppress(OSError):
                    os.remove(path)
                os.replace(tmp, path)
                replaced = True
                _fsync_directory(path.parent)
            except Exception:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
                raise
    except BaseException:
        if not replaced:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        raise


def _fsync_directory(directory: Path) -> None:
    """Best-effort fsync of *directory*. No-op on platforms that don't support it."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
