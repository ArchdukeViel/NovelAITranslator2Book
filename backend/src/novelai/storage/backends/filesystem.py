"""Filesystem-backed storage backend."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from novelai.storage.backends.base import StorageBackend


class FilesystemBackend(StorageBackend):
    """Stores files on the local filesystem under *base_dir*.

    Atomic writes via ``mkstemp`` + ``os.replace``.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._root = Path(base_dir).resolve()

    # ── helpers ──────────────────────────────────────────────────────

    def _resolve(self, path: str | Path) -> Path:
        """Resolve a relative path under the root directory."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self._root / p

    # ── interface ────────────────────────────────────────────────────

    def save(self, path: str | Path, data: bytes) -> None:
        dest = self._resolve(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
        except BaseException:
            _try_unlink(Path(tmp))
            raise

    def load(self, path: str | Path) -> bytes:
        return self._resolve(path).read_bytes()

    def delete(self, path: str | Path) -> None:
        dest = self._resolve(path)
        _try_unlink(dest)

    def exists(self, path: str | Path) -> bool:
        return self._resolve(path).exists()

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        resolved = self._resolve(prefix)
        if not resolved.exists() or not resolved.is_dir():
            return []
        keys: list[str] = []
        if recursive:
            for child in resolved.rglob("*"):
                if child.is_dir():
                    continue
                rel = child.relative_to(self._root)
                keys.append(str(rel.as_posix()))
        else:
            for child in resolved.iterdir():
                rel = child.relative_to(self._root)
                keys.append(str(rel.as_posix()))
        return sorted(keys)

    def has_keys(self, prefix: str | Path) -> bool:
        resolved = self._resolve(prefix)
        if not resolved.exists() or not resolved.is_dir():
            return False
        try:
            next(iter(resolved.iterdir()))
            return True
        except StopIteration:
            return False

    def total_size_bytes(self) -> int:
        if not self._root.exists():
            return 0
        return sum(child.stat().st_size for child in self._root.rglob("*") if child.is_file())

    def mkdirs(self, path: str | Path) -> None:
        self._resolve(path).mkdir(parents=True, exist_ok=True)


def _try_unlink(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)
