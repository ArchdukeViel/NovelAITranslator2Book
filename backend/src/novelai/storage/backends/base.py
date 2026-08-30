"""R2 object-storage contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO


class R2StorageBackend(ABC):
    """Abstract contract for the canonical Cloudflare R2 object store.

    All keys are relative to the configured object namespace (for example,
    ``novels/<novel_id>/chapters/<chapter_id>/<hash>.json.gz``).
    """

    @property
    @abstractmethod
    def bucket(self) -> str:
        """Return the fixed R2 bucket name represented by this client."""

        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        path: str | Path,
        data: bytes,
        *,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Write *data* to *path*, overwriting if it exists.

        Readers must not observe partial bytes. R2 implementations may provide atomic
        replacement or last-write-wins object semantics; multi-object
        transactions are outside this contract.
        """

    def save_stream(
        self,
        path: str | Path,
        source: BinaryIO,
        *,
        content_length: int | None = None,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> int:
        """Write a bounded stream through the canonical R2 object contract."""

        data = source.read()
        if content_length is not None and len(data) != content_length:
            raise ValueError("R2 gateway stream length mismatch")
        self.save(
            path,
            data,
            content_type=content_type,
            content_encoding=content_encoding,
            metadata=metadata,
        )
        return len(data)

    def head(self, path: str | Path) -> Any:
        """Return metadata for one exact key."""

        raise NotImplementedError

    def put_immutable(
        self,
        path: str | Path,
        data: bytes,
        *,
        logical_sha256: str,
        content_type: str = "application/json",
        content_encoding: str | None = "gzip",
    ) -> Any:
        """Write an immutable content-addressed object."""

        raise NotImplementedError

    def list_objects(
        self,
        prefix: str | Path = "",
        *,
        recursive: bool = False,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> Any:
        """Return one bounded, optionally paginated R2 listing page."""

        raise NotImplementedError

    def delete_prefix(self, prefix: str | Path) -> int:
        """Delete only exact descendants of a virtual R2 prefix."""

        keys = self.list_keys(prefix, recursive=True)
        for key in keys:
            self.delete(key)
        return len(keys)

    def compare_and_swap(self, path: str | Path, expected: bytes | None, new_value: bytes) -> bool:
        """Atomically replace the object at *path* only when it currently
        equals *expected* (``None`` means the object is absent).

        Returns ``True`` when the swap happened, ``False`` when the current
        content differed (the caller must treat that as a lost race and not
        retry blindly). Backends that cannot provide a true atomic
        conditional write implement compare-then-write and document the
        residual race window; the per-novel crawl lock covers same-novel
        writers in practice.
        """
        current = None
        try:
            current = self.load(path)
        except FileNotFoundError:
            current = None
        if current != expected:
            return False
        self.save(path, new_value)
        return True

    def copy_object(self, source: str | Path, destination: str | Path) -> None:
        """Copy one immutable object without changing its bytes.

        R2 implementations with a native object-copy primitive should override this
        method.  The load/save fallback keeps custom and test backends
        compatible while preserving the same staging semantics.
        """
        self.save(destination, self.load(source))

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
    def total_size_bytes(self) -> int:
        """Return the total bytes stored by this backend."""

    @abstractmethod
    def mkdirs(self, path: str | Path) -> None:
        """Ensure *path* (a directory) exists, creating parents if needed.
        No-op for the flat R2 object store.
        """

    def probe_readiness(self) -> bool:
        """Check backend reachability without mutating or enumerating deeply."""
        self.list_keys("", recursive=False)
        return True
