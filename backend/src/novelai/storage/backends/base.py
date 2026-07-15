"""Abstract storage backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Abstract interface for all storage backends.

    All paths are relative (e.g. ``novels/my-novel/metadata.json``).
    The backend is responsible for resolving them against its root.
    """

    @abstractmethod
    def save(self, path: str | Path, data: bytes) -> None:
        """Write *data* to *path*, overwriting if it exists.
        Must be atomic (no partial writes visible to readers).
        """

    @abstractmethod
    def load(self, path: str | Path) -> bytes:
        """Return the bytes stored at *path*.
        Raises ``FileNotFoundError`` if it does not exist.
        """

    @abstractmethod
    def delete(self, path: str | Path) -> None:
        """Remove the object at *path*.
        Do NOT raise if *path* does not exist.
        """

    @abstractmethod
    def exists(self, path: str | Path) -> bool:
        """Return True if *path* exists in storage."""

    @abstractmethod
    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        """Return all keys under *prefix*.

        When *recursive* is True, return keys at any depth (default: False)."""

    @abstractmethod
    def has_keys(self, prefix: str | Path) -> bool:
        """Return True when at least one key exists under *prefix*.

        Implementations should retrieve at most one matching descendant.
        Used for logical-directory presence checks on remote backends.
        """

    @abstractmethod
    def mkdirs(self, path: str | Path) -> None:
        """Ensure *path* (a directory) exists, creating parents if needed.
        No-op for flat backends (S3).
        """
