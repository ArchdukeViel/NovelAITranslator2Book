"""Incremental content-addressed R2 backup target."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from typing import Any

from novelai.storage.snapshots import SnapshotResult

logger = logging.getLogger(__name__)


def _snapshot_id() -> str:
    return f"backup-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _etag(value: object) -> str:
    return str(value or "").strip('"')


class R2IncrementalBackupTarget:
    """Store one shared object copy and immutable snapshot manifests.

    Application objects are copied to ``objects/novels/...`` once. Later
    snapshots reference the same backup object from
    ``snapshots/<snapshot_id>/manifest.json``.
    """

    def __init__(
        self,
        *,
        source_bucket: str,
        target_bucket: str,
        endpoint_url: str | None,
        region: str,
        source_access_key_id: str | None,
        source_secret_access_key: str | None,
        target_access_key_id: str | None,
        target_secret_access_key: str | None,
        target_prefix: str = "snapshots",
        source_client: Any | None = None,
        target_client: Any | None = None,
    ) -> None:
        if source_bucket == target_bucket:
            raise ValueError("R2 backup target bucket must differ from the application bucket")
        if target_prefix.strip("/") != "snapshots":
            raise ValueError("R2 snapshots must use the snapshots prefix")
        self._source_bucket = source_bucket
        self._target_bucket = target_bucket
        self._target_prefix = "snapshots"
        if source_client is None or target_client is None:
            import boto3

            base_kwargs: dict[str, Any] = {"region_name": region}
            if endpoint_url:
                base_kwargs["endpoint_url"] = endpoint_url
            if source_client is None:
                source_kwargs = dict(base_kwargs)
                if source_access_key_id:
                    source_kwargs["aws_access_key_id"] = source_access_key_id
                if source_secret_access_key:
                    source_kwargs["aws_secret_access_key"] = source_secret_access_key
                source_client = boto3.client("s3", **source_kwargs)
            if target_client is None:
                target_kwargs = dict(base_kwargs)
                if target_access_key_id:
                    target_kwargs["aws_access_key_id"] = target_access_key_id
                if target_secret_access_key:
                    target_kwargs["aws_secret_access_key"] = target_secret_access_key
                target_client = boto3.client("s3", **target_kwargs)
        self._source_client = source_client
        self._target_client = target_client

    @staticmethod
    def _read_body(response: dict[str, Any]) -> bytes:
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def _list_source_objects(self) -> list[dict[str, Any]]:
        paginator = self._source_client.get_paginator("list_objects_v2")
        objects: list[dict[str, Any]] = []
        for page in paginator.paginate(Bucket=self._source_bucket, Prefix="novels/"):
            objects.extend(page.get("Contents", []))
        return sorted(objects, key=lambda item: str(item.get("Key", "")))

    def _manifest_key(self, snapshot_id: str) -> str:
        return f"{self._target_prefix}/{snapshot_id}/manifest.json"

    def _read_target(self, key: str) -> bytes:
        return self._read_body(self._target_client.get_object(Bucket=self._target_bucket, Key=key))

    def _load_manifest(self, snapshot_id: str) -> dict[str, Any]:
        manifest = json.loads(self._read_target(self._manifest_key(snapshot_id)))
        if not isinstance(manifest, dict) or manifest.get("snapshot_id") != snapshot_id:
            raise RuntimeError("Invalid R2 backup manifest")
        return manifest

    def create_snapshot(self) -> SnapshotResult:
        snapshot_id = _snapshot_id()
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        copied: list[str] = []
        entries: list[dict[str, Any]] = []
        total_bytes = 0
        try:
            for source in self._list_source_objects():
                source_key = str(source["Key"])
                backup_key = f"objects/{source_key}"
                source_etag = _etag(source.get("ETag"))
                size_bytes = int(source.get("Size", 0))
                reused = False
                source_sha256: str
                try:
                    existing = self._target_client.head_object(Bucket=self._target_bucket, Key=backup_key)
                except Exception:
                    existing = None
                if (
                    existing is not None
                    and int(existing.get("ContentLength", -1)) == size_bytes
                    and str((existing.get("Metadata") or {}).get("source-etag", "")) == source_etag
                ):
                    reused = True
                    source_sha256 = str((existing.get("Metadata") or {}).get("sha256", ""))
                    if not source_sha256:
                        reused = False
                else:
                    source_sha256 = ""
                if not reused:
                    response = self._source_client.get_object(Bucket=self._source_bucket, Key=source_key)
                    body = response["Body"]
                    digest = hashlib.sha256()
                    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as staged:
                        try:
                            while chunk := body.read(1024 * 1024):
                                digest.update(chunk)
                                staged.write(chunk)
                        finally:
                            body.close()
                        staged.seek(0)
                        self._target_client.upload_fileobj(
                            staged,
                            self._target_bucket,
                            backup_key,
                            ExtraArgs={
                                "Metadata": {"source-etag": source_etag, "sha256": digest.hexdigest()},
                                "ContentType": str(response.get("ContentType") or "application/octet-stream"),
                            },
                        )
                    copied.append(backup_key)
                    restored = self._read_target(backup_key)
                    source_sha256 = digest.hexdigest()
                    if len(restored) != size_bytes or hashlib.sha256(restored).hexdigest() != source_sha256:
                        raise RuntimeError(f"R2 backup checksum verification failed: {source_key}")
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
                "source_bucket": self._source_bucket,
                "object_root": "objects/novels",
                "files_count": len(entries),
                "size_bytes": total_bytes,
                "objects": entries,
                "restore_verification": {"status": "succeeded", "verified_at": created_at},
            }
            manifest_key = self._manifest_key(snapshot_id)
            self._target_client.put_object(
                Bucket=self._target_bucket,
                Key=manifest_key,
                Body=json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                ContentType="application/json",
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
                    self._target_client.delete_object(Bucket=self._target_bucket, Key=key)
                except Exception:
                    logger.warning("Could not clean incomplete R2 backup object", exc_info=True)
            raise

    def latest_snapshot(self) -> SnapshotResult | None:
        roots: list[str] = []
        paginator = self._target_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self._target_bucket,
            Prefix="snapshots/",
            Delimiter="/",
        ):
            roots.extend(str(item["Prefix"]) for item in page.get("CommonPrefixes", []))
        for root in sorted(set(roots), reverse=True):
            snapshot_id = root.rstrip("/").rsplit("/", 1)[-1]
            try:
                manifest = self._load_manifest(snapshot_id)
            except Exception:
                continue
            return SnapshotResult(
                snapshot_id=snapshot_id,
                created_at=str(manifest.get("created_at", "")),
                files_count=int(manifest.get("files_count", 0)),
                size_bytes=int(manifest.get("size_bytes", 0)),
                verified=manifest.get("restore_verification", {}).get("status") == "succeeded",
            )
        return None

    def verify_snapshot(self, snapshot_id: str) -> SnapshotResult:
        manifest = self._load_manifest(snapshot_id)
        for entry in manifest.get("objects", []):
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
