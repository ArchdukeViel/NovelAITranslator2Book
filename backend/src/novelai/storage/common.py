from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

_UNSET = object()


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
