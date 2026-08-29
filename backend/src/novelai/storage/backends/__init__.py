"""Canonical R2 storage factory.

There is deliberately no filesystem/S3 backend selection. The S3 protocol is
only the transport used by the explicit Cloudflare R2 client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from novelai.config.settings import settings

if TYPE_CHECKING:
    from novelai.storage.backends.base import R2StorageBackend

_R2_STORAGE: R2StorageBackend | None = None


def build_r2_storage() -> R2StorageBackend:
    """Build a fresh R2 client for an explicitly supplied dependency scope."""

    try:
        from novelai.storage.backends.r2 import R2Storage
    except ImportError as exc:
        raise RuntimeError("R2 storage requires boto3. Install with: pip install novelai[s3]") from exc

    access_key = settings.R2_ACCESS_KEY_ID.get_secret_value() if settings.R2_ACCESS_KEY_ID else None
    secret_key = settings.R2_SECRET_ACCESS_KEY.get_secret_value() if settings.R2_SECRET_ACCESS_KEY else None
    return R2Storage(
        bucket=settings.R2_BUCKET,
        region=settings.R2_REGION,
        endpoint_url=settings.R2_ENDPOINT,
        access_key_id=access_key,
        secret_access_key=secret_key,
    )


def get_r2_storage() -> R2StorageBackend:
    """Return the singleton for the canonical application R2 bucket."""

    global _R2_STORAGE
    if _R2_STORAGE is None:
        _R2_STORAGE = build_r2_storage()
    return _R2_STORAGE


def _reset_r2_storage() -> None:
    """Reset the cached R2 client for isolated test processes."""

    global _R2_STORAGE
    _R2_STORAGE = None
