"""Utility helpers for Novel AI."""

import contextlib
import os
import tempfile
from pathlib import Path

from novelai.utils.filesystem import replace_with_retry


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
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


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
