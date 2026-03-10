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
    """Write *content* to *path* atomically (write-to-temp then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
