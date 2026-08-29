"""Safe inventory, reset, and garbage-collection controls for R2 cutover."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from novelai.storage.backends.r2 import R2ObjectMetadata, R2Storage

APPLICATION_BUCKET = "dokushodo"
BACKUP_BUCKET = "dokushodo-backup"
RESET_CONFIRMATION = "RESET-DOKUSHODO-AND-DOKUSHODO-BACKUP"


@dataclass(frozen=True, slots=True)
class R2Inventory:
    bucket: str
    object_count: int
    bytes_total: int
    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class R2ResetResult:
    dry_run: bool
    application_objects: int
    backup_objects: int
    deleted_application_objects: int
    deleted_backup_objects: int


@dataclass(frozen=True, slots=True)
class R2GarbageCollectionResult:
    dry_run: bool
    candidates: tuple[str, ...]
    deleted: tuple[str, ...]


def inventory_bucket(storage: R2Storage) -> R2Inventory:
    """Inventory every object, including all paginated list results."""

    keys = tuple(storage.list_keys("", recursive=True))
    total = 0
    for key in keys:
        total += storage.head(key).size_bytes
    return R2Inventory(
        bucket=storage.bucket,
        object_count=len(keys),
        bytes_total=total,
        keys=keys,
    )


class R2CutoverService:
    """Plan or execute the explicitly-confirmed two-bucket clean cutover."""

    def __init__(self, *, application: R2Storage, backup: R2Storage) -> None:
        self.application = application
        self.backup = backup
        if application.bucket != APPLICATION_BUCKET or backup.bucket != BACKUP_BUCKET:
            raise ValueError("R2 cutover requires the dokushodo and dokushodo-backup buckets")

    def inventory(self) -> tuple[R2Inventory, R2Inventory]:
        return inventory_bucket(self.application), inventory_bucket(self.backup)

    def reset(
        self,
        *,
        writers_frozen: bool,
        identities_verified: bool,
        confirmation: str | None,
        dry_run: bool = True,
    ) -> R2ResetResult:
        app_inventory, backup_inventory = self.inventory()
        if dry_run:
            return R2ResetResult(
                dry_run=True,
                application_objects=app_inventory.object_count,
                backup_objects=backup_inventory.object_count,
                deleted_application_objects=0,
                deleted_backup_objects=0,
            )
        if not writers_frozen:
            raise PermissionError("Writers must be frozen before an R2 reset")
        if not identities_verified:
            raise PermissionError("Novel identities must be inventoried and verified before an R2 reset")
        if confirmation != RESET_CONFIRMATION:
            raise PermissionError("The exact R2 reset confirmation token is required")
        deleted_backup = self.backup.delete_prefix("")
        deleted_application = self.application.delete_prefix("")
        return R2ResetResult(
            dry_run=False,
            application_objects=app_inventory.object_count,
            backup_objects=backup_inventory.object_count,
            deleted_application_objects=deleted_application,
            deleted_backup_objects=deleted_backup,
        )


class R2GarbageCollector:
    """Mark-and-sweep immutable objects with a mandatory grace period."""

    def __init__(self, storage: R2Storage) -> None:
        self.storage = storage

    def collect(
        self,
        *,
        referenced_keys: Iterable[str],
        protected_keys: Iterable[str],
        now: datetime | None = None,
        grace_period: timedelta = timedelta(days=7),
        dry_run: bool = True,
    ) -> R2GarbageCollectionResult:
        if grace_period < timedelta(0):
            raise ValueError("GC grace period cannot be negative")
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        keep = set(referenced_keys) | set(protected_keys)
        cutoff = current_time - grace_period
        candidates: list[str] = []
        for key in self.storage.list_keys("novels", recursive=True):
            if key in keep:
                continue
            metadata: R2ObjectMetadata = self.storage.head(key)
            last_modified = metadata.last_modified
            if last_modified is None:
                continue
            if last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=UTC)
            if last_modified <= cutoff:
                candidates.append(key)
        deleted: list[str] = []
        if not dry_run:
            for key in candidates:
                self.storage.delete(key)
                deleted.append(key)
        return R2GarbageCollectionResult(
            dry_run=dry_run,
            candidates=tuple(sorted(candidates)),
            deleted=tuple(sorted(deleted)),
        )
