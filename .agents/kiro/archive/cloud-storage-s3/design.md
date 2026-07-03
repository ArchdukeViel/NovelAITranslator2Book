# Design: Cloud Storage Backend (S3)

## Overview

Introduce a `StorageBackend` abstract base class, refactor existing filesystem I/O into `FilesystemBackend`, and implement `S3Backend` using boto3. A factory function selects the backend based on `STORAGE_BACKEND`. All production code uses the interface; direct file I/O is removed from services.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/storage/backends/__init__.py` | New — backend package, factory |
| `backend/src/novelai/storage/backends/base.py` | New — `StorageBackend` abstract class |
| `backend/src/novelai/storage/backends/filesystem.py` | New — `FilesystemBackend` implementation |
| `backend/src/novelai/storage/backends/s3.py` | New — `S3Backend` implementation |
| `backend/src/novelai/storage/service.py` | Refactor — use `get_storage_backend()` instead of direct file I/O |
| Any service using direct `open()` | Refactor — use `StorageBackend` methods |
| `requirements.lock` / `pyproject.toml` | Update — add `boto3` as optional dependency |

### Files Not Touched

- DB models — no change
- API routers — no change
- Translation pipeline — no change
- Source adapters — no change
- File naming conventions — no change

## Component Design

### 1. `StorageBackend` Interface (`storage/backends/base.py`)

```python
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract storage backend for chapter content, metadata, and assets."""

    @abstractmethod
    async def save(self, key: str, data: bytes | str) -> None:
        """Save data at the given key. Creates parent path if needed."""
        ...

    @abstractmethod
    async def load(self, key: str) -> bytes:
        """Load data from the given key. Raises FileNotFoundError if missing."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data at the given key. No-op if key does not exist."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if key exists."""
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with the given prefix."""
        ...
```

### 2. `FilesystemBackend` (`storage/backends/filesystem.py`)

```python
import os
import tempfile
from pathlib import Path

from novelai.storage.backends.base import StorageBackend

STORAGE_PATH = Path(os.environ.get("STORAGE_PATH", "storage/novel_library"))


class FilesystemBackend(StorageBackend):
    def __init__(self, root: Path | None = None):
        self.root = root or STORAGE_PATH

    async def save(self, key: str, data: bytes | str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode("utf-8")
        # Atomic write: write to temp, then rename
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp_name, str(path))
        except Exception:
            os.unlink(tmp_name)
            raise

    async def load(self, key: str) -> bytes:
        path = self.root / key
        if not path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self.root / key
        path.unlink(missing_ok=True)

    async def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    async def list_keys(self, prefix: str = "") -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return [str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file()]
```

### 3. `S3Backend` (`storage/backends/s3.py`)

```python
import os
import asyncio
import logging

import boto3
from botocore.config import Config

from novelai.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

S3_CONFIG = {
    "endpoint_url": os.environ.get("S3_ENDPOINT_URL"),
    "bucket": os.environ["S3_BUCKET"],
    "prefix": os.environ.get("S3_PREFIX", "novel_library/"),
    "region": os.environ.get("S3_REGION", "us-east-1"),
}

RETRY_CONFIG = Config(retries={"max_attempts": 3, "mode": "standard"})


class S3Backend(StorageBackend):
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=S3_CONFIG["endpoint_url"],
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY"),
            region_name=S3_CONFIG["region"],
            config=RETRY_CONFIG,
        )
        self.bucket = S3_CONFIG["bucket"]
        self.prefix = S3_CONFIG["prefix"]

    def _full_key(self, key: str) -> str:
        return self.prefix + key

    async def save(self, key: str, data: bytes | str) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        full_key = self._full_key(key)
        size = len(data)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.put_object(
                Bucket=self.bucket, Key=full_key, Body=data
            ),
        )
        logger.debug("s3: PUT %s/%s (%d bytes)", self.bucket, full_key, size)

    async def load(self, key: str) -> bytes:
        full_key = self._full_key(key)
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_object(Bucket=self.bucket, Key=full_key),
            )
            return response["Body"].read()
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Key not found: {key}")
        except Exception as exc:
            if "NoSuchKey" in str(exc):
                raise FileNotFoundError(f"Key not found: {key}")
            raise

    async def delete(self, key: str) -> None:
        full_key = self._full_key(key)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.delete_object(Bucket=self.bucket, Key=full_key),
        )

    async def exists(self, key: str) -> bool:
        full_key = self._full_key(key)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self.client.head_object(Bucket=self.bucket, Key=full_key),
            )
            return True
        except Exception:
            return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        full_prefix = self._full_key(prefix)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=full_prefix
            ),
        )
        keys = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if key.startswith(self.prefix):
                keys.append(key[len(self.prefix) :])
        return keys
```

### 4. Factory and Configuration

```python
import os
import logging

from novelai.storage.backends.base import StorageBackend
from novelai.storage.backends.filesystem import FilesystemBackend

logger = logging.getLogger(__name__)

_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is not None:
        return _backend

    backend_type = os.environ.get("STORAGE_BACKEND", "filesystem")

    if backend_type == "filesystem":
        _backend = FilesystemBackend()
    elif backend_type == "s3":
        _validate_s3_config()
        from novelai.storage.backends.s3 import S3Backend
        _backend = S3Backend()
    else:
        raise ValueError(f"Unknown STORAGE_BACKEND: {backend_type}")

    logger.info("Storage backend initialized: %s", backend_type)
    return _backend


def _validate_s3_config() -> None:
    missing = []
    for var in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        raise RuntimeError(
            f"STORAGE_BACKEND=s3 requires environment variables: {', '.join(missing)}"
        )
```

## Migration and Backward Compatibility

- Default `STORAGE_BACKEND=filesystem` preserves current behavior.
- `FilesystemBackend` uses the same directory layout (`storage/novel_library/`).
- Atomic writes prevent corruption that previously could occur with direct writes.
- Existing tests continue to use the filesystem backend without changes.
- `boto3` is listed as an optional dependency (not required for filesystem mode).

## Acceptance Criteria

1. `STORAGE_BACKEND=filesystem` (default) — all existing operations work identically.
2. `STORAGE_BACKEND=s3` with valid config — save, load, delete, exists, list_keys all work against S3.
3. Missing S3 env vars at startup produce a clear error message.
4. Atomic file writes prevent partial data on the filesystem backend.
5. `FilesystemBackend.list_keys("chapters/")` returns correct relative paths.
6. All existing tests pass with the filesystem backend.
