"""Incremental content-addressed backup through native R2 gateway clients."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from novelai.storage.snapshots import SnapshotResult

logger = logging.getLogger(__name__)


def _snapshot_id() -> str:
    return f"backup-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _etag(value: object) -> str:
    return str(value or "").strip('"')


def _pages(storage: Any, prefix: str, *, recursive: bool = True) -> Iterator[Any]:
    cursor: str | None = None
    while True:
        page = storage.list_objects(prefix, recursive=recursive, cursor=cursor)
        yield page
        if not page.truncated or not page.cursor:
            return
        cursor = page.cursor


class R2IncrementalBackupTarget:
    """Store shared application objects and immutable snapshot manifests."""

    def __init__(
        self,
        *,
        source_backend: Any,
        target_backend: Any,
        target_prefix: str = "snapshots",
    ) -> None:
        if source_backend.bucket == target_backend.bucket:
            raise ValueError("R2 backup target bucket must differ from the application bucket")
        if target_prefix.strip("/") != "snapshots":
            raise ValueError("R2 snapshots must use the snapshots prefix")
        self._source = source_backend
        self._target = target_backend
        self._target_prefix = "snapshots"

    def _list_source_objects(self) -> list[Any]:
        objects = [item for page in _pages(self._source, "novels", recursive=True) for item in page.objects]
        return sorted(objects, key=lambda item: str(item.key))

    def _manifest_key(self, snapshot_id: str) -> str:
        return f"{self._target_prefix}/{snapshot_id}/manifest.json"

    def _read_target(self, key: str) -> bytes:
        return self._target.load(key)

    def _load_manifest(self, snapshot_id: str) -> dict[str, Any]:
        try:
            manifest = json.loads(self._read_target(self._manifest_key(snapshot_id)))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("Invalid R2 backup manifest") from exc
        if not isinstance(manifest, dict) or manifest.get("snapshot_id") != snapshot_id:
            raise RuntimeError("Invalid R2 backup manifest")
        return manifest

    def _list_manifest_items(self) -> list[Any]:
        return [
            item
            for page in _pages(self._target, "snapshots", recursive=True)
            for item in page.objects
            if item.key.startswith("snapshots/") and item.key.endswith("/manifest.json")
        ]

    @staticmethod
    def _parse_timestamp(value: object) -> datetime | None:
        if isinstance(value, datetime):
            timestamp = value
        elif isinstance(value, str):
            try:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)

    @staticmethod
    def _manifest_references(manifest: dict[str, Any]) -> set[str]:
        references: set[str] = set()
        objects = manifest.get("objects")
        if not isinstance(objects, list):
            return references
        for entry in objects:
            if isinstance(entry, dict):
                backup_key = entry.get("backup_key")
                if isinstance(backup_key, str) and backup_key.startswith("objects/"):
                    references.add(backup_key)
        return references

    def create_snapshot(self) -> SnapshotResult:
        snapshot_id = _snapshot_id()
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        copied: list[str] = []
        entries: list[dict[str, Any]] = []
        total_bytes = 0
        try:
            for source in self._list_source_objects():
                source_key = str(source.key)
                backup_key = f"objects/{source_key}"
                source_etag = _etag(source.etag)
                size_bytes = int(source.size_bytes)
                existing = None
                with suppress(FileNotFoundError):
                    existing = self._target.head(backup_key)
                source_sha256 = ""
                reused = False
                if existing is not None and existing.size_bytes == size_bytes:
                    metadata = existing.metadata
                    if _etag(metadata.get("source-etag")) == source_etag:
                        source_sha256 = metadata.get("sha256", "")
                        reused = bool(source_sha256)
                if not reused:
                    data = self._source.load(source_key)
                    source_sha256 = hashlib.sha256(data).hexdigest()
                    if len(data) != size_bytes:
                        raise RuntimeError("R2 backup source length verification failed")
                    self._target.save(
                        backup_key,
                        data,
                        content_type=source.content_type,
                        content_encoding=source.content_encoding,
                        metadata={"source-etag": source_etag, "sha256": source_sha256},
                    )
                    copied.append(backup_key)
                    restored = self._target.load(backup_key)
                    if len(restored) != size_bytes or hashlib.sha256(restored).hexdigest() != source_sha256:
                        raise RuntimeError("R2 backup checksum verification failed")
                entries.append(
                    {
                        "key": source_key,
                        "backup_key": backup_key,
                        "size_bytes": size_bytes,
                        "source_etag": source_etag,
                        "sha256": source_sha256,
                        "reused": reused,
                    }
                )
                total_bytes += size_bytes

            manifest = {
                "schema_version": 2,
                "snapshot_id": snapshot_id,
                "backup_type": "incremental",
                "status": "succeeded",
                "created_at": created_at,
                "source_bucket": self._source.bucket,
                "object_root": "objects/novels",
                "files_count": len(entries),
                "size_bytes": total_bytes,
                "objects": entries,
                "restore_verification": {"status": "succeeded", "verified_at": created_at},
            }
            self._target.save(
                self._manifest_key(snapshot_id),
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                content_type="application/json",
            )
            return SnapshotResult(
                snapshot_id=snapshot_id,
                created_at=created_at,
                files_count=len(entries),
                size_bytes=total_bytes,
                verified=True,
            )
        except Exception:
            for key in reversed(copied):
                try:
                    self._target.delete(key)
                except Exception:
                    logger.warning("Could not clean incomplete R2 backup object", exc_info=True)
            raise

    def latest_snapshot(self) -> SnapshotResult | None:
        records: list[tuple[datetime, str, dict[str, Any]]] = []
        for item in self._list_manifest_items():
            snapshot_id = item.key[len("snapshots/") : -len("/manifest.json")]
            try:
                manifest = self._load_manifest(snapshot_id)
                created_at = self._parse_timestamp(manifest.get("created_at"))
                if created_at is None or manifest.get("status") != "succeeded":
                    continue
            except Exception:
                continue
            records.append((created_at, snapshot_id, manifest))
        if not records:
            return None
        _, snapshot_id, manifest = max(records, key=lambda record: record[0])
        verification = manifest.get("restore_verification")
        return SnapshotResult(
            snapshot_id=snapshot_id,
            created_at=str(manifest.get("created_at", "")),
            files_count=int(manifest.get("files_count", 0)),
            size_bytes=int(manifest.get("size_bytes", 0)),
            verified=isinstance(verification, dict) and verification.get("status") == "succeeded",
        )

    def verify_snapshot(self, snapshot_id: str) -> SnapshotResult:
        manifest = self._load_manifest(snapshot_id)
        for entry in manifest.get("objects", []):
            if not isinstance(entry, dict):
                raise RuntimeError("R2 restore drill manifest entry is invalid")
            restored = self._read_target(str(entry["backup_key"]))
            if len(restored) != int(entry["size_bytes"]):
                raise RuntimeError("R2 restore drill size verification failed")
            if hashlib.sha256(restored).hexdigest() != str(entry["sha256"]):
                raise RuntimeError("R2 restore drill checksum verification failed")
        return SnapshotResult(
            snapshot_id=snapshot_id,
            created_at=str(manifest.get("created_at", "")),
            files_count=int(manifest.get("files_count", 0)),
            size_bytes=int(manifest.get("size_bytes", 0)),
            verified=True,
        )

    def apply_retention(
        self,
        *,
        keep_count: int,
        min_successful: int,
        max_age_days: int,
        safety_grace_days: int,
        dry_run: bool = False,
    ) -> int:
        if min_successful < 0 or keep_count < 0 or max_age_days < 0 or safety_grace_days < 0:
            raise ValueError("Backup retention values must not be negative")
        now = datetime.now(UTC)
        valid_records: list[tuple[str, datetime, dict[str, Any]]] = []
        invalid_manifest_found = False
        for item in self._list_manifest_items():
            snapshot_id = item.key[len("snapshots/") : -len("/manifest.json")]
            try:
                manifest = self._load_manifest(snapshot_id)
                manifest_created_at = self._parse_timestamp(manifest.get("created_at"))
                created_at = item.last_modified or manifest_created_at
                if not snapshot_id or created_at is None or manifest.get("status") != "succeeded":
                    invalid_manifest_found = True
                    continue
            except Exception:
                invalid_manifest_found = True
                continue
            valid_records.append((snapshot_id, created_at, manifest))

        valid_records.sort(key=lambda record: record[1], reverse=True)
        protected_count = max(keep_count, min_successful)
        cutoff = now - timedelta(days=max_age_days)
        candidates = [
            record for index, record in enumerate(valid_records) if index >= protected_count and record[1] < cutoff
        ]
        candidate_ids = {record[0] for record in candidates}
        retained_records = [record for record in valid_records if record[0] not in candidate_ids]
        retained_references: set[str] = set()
        for _, _, manifest in retained_records:
            retained_references.update(self._manifest_references(manifest))

        deleted_count = len(candidates) if dry_run else 0
        if not dry_run:
            for snapshot_id, _, manifest in candidates:
                try:
                    self._target.delete(self._manifest_key(snapshot_id))
                    deleted_count += 1
                except Exception:
                    retained_references.update(self._manifest_references(manifest))
                    logger.warning("Could not delete expired R2 backup manifest", exc_info=True)

        if invalid_manifest_found:
            logger.warning("Skipping R2 backup object collection because an invalid snapshot manifest exists")
            return deleted_count

        object_cutoff = now - timedelta(days=safety_grace_days)
        for item in (object_ for page in _pages(self._target, "objects", recursive=True) for object_ in page.objects):
            if item.key in retained_references:
                continue
            if item.last_modified is None or item.last_modified >= object_cutoff:
                continue
            if dry_run:
                deleted_count += 1
                continue
            try:
                self._target.delete(item.key)
                deleted_count += 1
            except Exception:
                logger.warning("Could not delete unreferenced R2 backup object", exc_info=True)
        return deleted_count
