from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypedDict

from novelai.core.errors import StorageError

_UNSET = object()


class UnsupportedStorageSchemaVersionError(StorageError):
    """Raised when a persisted artifact cannot be read by this application version."""


def validate_storage_schema_version(
    payload: dict[str, Any],
    *,
    current_version: int,
    artifact_type: str,
) -> int:
    """Require the exact storage schema supported by the current application."""
    version = payload.get("schema_version")
    if version is None:
        raise UnsupportedStorageSchemaVersionError(f"{artifact_type} is missing the required storage schema version.")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise UnsupportedStorageSchemaVersionError(f"{artifact_type} has an invalid storage schema version.")
    if version != current_version:
        raise UnsupportedStorageSchemaVersionError(
            f"{artifact_type} schema version {version} does not match required version {current_version}."
        )
    return version


class CheckpointInfo(TypedDict):
    """Validated checkpoint metadata returned from storage."""

    filename: str
    timestamp: str
    checkpoint_name: str


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return _utc_now().isoformat().replace("+00:00", "Z")
