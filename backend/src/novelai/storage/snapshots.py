"""Provider-neutral committed snapshot contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SnapshotResult:
    """Safe summary of a committed storage snapshot."""

    snapshot_id: str
    created_at: str
    files_count: int
    size_bytes: int
    verified: bool


class SnapshotTarget(Protocol):
    """Creates and inspects independently stored snapshots."""

    def create_snapshot(self) -> SnapshotResult:
        """Create and verify a committed snapshot."""
        ...

    def latest_snapshot(self) -> SnapshotResult | None:
        """Return the newest committed snapshot, if one exists."""
        ...

    def verify_snapshot(self, snapshot_id: str) -> SnapshotResult:
        """Download and verify every object in an isolated read-only drill."""
        ...
