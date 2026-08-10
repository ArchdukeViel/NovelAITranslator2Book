"""Filesystem primitives and atomic operations for Novel AI."""

import os
import time
from pathlib import Path


def replace_with_retry(src: Path, dst: Path, *, attempts: int = 8) -> None:
    """os.replace with bounded retry for Windows WinError-5 transient locks.

    Windows can briefly hold a destination file open (antivirus scan,
    directory-watcher, a reader mid-stream); the atomic rename then fails
    with PermissionError. Retrying a bounded number of times with a tiny
    backoff makes the atomic replace deterministic without broad sleeps or
    unbounded loops. The retry budget is fixed (max ~1s total); a genuine
    permission problem still fails fast.
    """
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.02 * (attempt + 1))
