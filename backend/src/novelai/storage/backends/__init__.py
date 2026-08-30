"""Canonical Cloudflare R2 gateway storage factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from novelai.config.settings import settings

if TYPE_CHECKING:
    from novelai.storage.backends.base import R2StorageBackend

_R2_STORAGE: R2StorageBackend | None = None


def build_r2_storage() -> R2StorageBackend:
    """Build the application client with the application Access identity."""

    from novelai.storage.backends.r2_gateway import R2GatewayStorage

    if not settings.R2_GATEWAY_URL or not settings.R2_GATEWAY_CLIENT_ID or not settings.R2_GATEWAY_CLIENT_SECRET:
        raise RuntimeError("R2 application gateway identity is not configured")
    return R2GatewayStorage(
        bucket=settings.R2_BUCKET,
        bucket_class="app",
        gateway_url=settings.R2_GATEWAY_URL,
        client_id=settings.R2_GATEWAY_CLIENT_ID,
        client_secret=settings.R2_GATEWAY_CLIENT_SECRET.get_secret_value(),
    )


def build_r2_recovery_storage(*, bucket_class: str = "backup") -> R2StorageBackend:
    """Build a recovery client using the separate recovery Access identity."""

    from novelai.storage.backends.r2_gateway import R2GatewayStorage

    if bucket_class not in {"app", "backup"}:
        raise ValueError("R2 recovery bucket class is invalid")
    if (
        not settings.R2_RECOVERY_GATEWAY_URL
        or not settings.R2_RECOVERY_CLIENT_ID
        or not settings.R2_RECOVERY_CLIENT_SECRET
    ):
        raise RuntimeError("R2 recovery gateway identity is not configured")
    bucket = settings.R2_BUCKET if bucket_class == "app" else settings.R2_BACKUP_BUCKET
    return R2GatewayStorage(
        bucket=bucket,
        bucket_class=bucket_class,  # type: ignore[arg-type]
        gateway_url=settings.R2_RECOVERY_GATEWAY_URL,
        client_id=settings.R2_RECOVERY_CLIENT_ID,
        client_secret=settings.R2_RECOVERY_CLIENT_SECRET.get_secret_value(),
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
