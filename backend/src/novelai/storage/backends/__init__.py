"""Storage backend abstraction layer.

Use `get_storage_backend()` to obtain the configured backend singleton.
Backend selection is controlled by the `STORAGE_BACKEND` env var.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from novelai.config.settings import settings

if TYPE_CHECKING:
    from novelai.storage.backends.base import StorageBackend

_BACKEND: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend singleton.

    Selection:
      - ``STORAGE_BACKEND=filesystem`` or unset → ``FilesystemBackend``
      - ``STORAGE_BACKEND=s3`` → ``S3Backend`` (raises if boto3 not installed)
    """
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    choice = (os.environ.get("STORAGE_BACKEND") or settings.STORAGE_BACKEND).strip().lower()

    if choice == "filesystem":
        from novelai.storage.backends.filesystem import FilesystemBackend

        _BACKEND = FilesystemBackend(base_dir=settings.NOVEL_LIBRARY_DIR)
    elif choice == "s3":
        _BACKEND = _build_s3_backend()
    else:
        raise RuntimeError(
            f"Unknown STORAGE_BACKEND={choice!r}. Expected 'filesystem' or 's3'."
        )

    return _BACKEND


def _build_s3_backend() -> StorageBackend:
    """Validate S3 config and build an S3Backend."""
    try:
        from novelai.storage.backends.s3 import S3Backend
    except ImportError as exc:
        raise RuntimeError(
            "S3 backend selected but boto3 is not installed. "
            "Install with: pip install novelai[s3]"
        ) from exc

    if not settings.S3_BUCKET:
        raise RuntimeError(
            "S3_BUCKET is required when STORAGE_BACKEND=s3."
        )

    access_key = (
        settings.S3_ACCESS_KEY_ID.get_secret_value()
        if settings.S3_ACCESS_KEY_ID
        else None
    )
    secret_key = (
        settings.S3_SECRET_ACCESS_KEY.get_secret_value()
        if settings.S3_SECRET_ACCESS_KEY
        else None
    )

    return S3Backend(
        bucket=settings.S3_BUCKET,
        region=settings.S3_REGION,
        key_prefix=settings.S3_KEY_PREFIX,
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _reset_backend() -> None:
    """Reset the cached backend singleton (for testing only)."""
    global _BACKEND
    _BACKEND = None
