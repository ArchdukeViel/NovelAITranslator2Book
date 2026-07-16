"""Committed snapshots between S3-compatible buckets."""

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


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_snapshot_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"backup-{timestamp}-{uuid.uuid4().hex[:8]}"


def _etag(value: object) -> str:
    return str(value or "").strip('"')


class S3SnapshotTarget:
    """Copies canonical storage into an independent S3-compatible bucket.

    The manifest is written last and is the commit marker. Prefixes without a
    valid manifest are incomplete and are ignored by status checks.
    """

    def __init__(
        self,
        *,
        source_bucket: str,
        source_prefix: str,
        target_bucket: str,
        target_prefix: str,
        endpoint_url: str | None,
        region: str,
        source_access_key_id: str | None,
        source_secret_access_key: str | None,
        target_access_key_id: str | None,
        target_secret_access_key: str | None,
        source_client: Any | None = None,
        target_client: Any | None = None,
    ) -> None:
        if source_bucket == target_bucket:
            raise ValueError("Snapshot target bucket must differ from the source bucket")
        normalized_target_prefix = target_prefix.strip("/")
        if not normalized_target_prefix:
            raise ValueError("Snapshot target prefix must not be blank or root")

        self._source_bucket = source_bucket
        self._source_prefix = source_prefix.strip("/")
        self._target_bucket = target_bucket
        self._target_prefix = normalized_target_prefix
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

    @property
    def _canonical_source_prefix(self) -> str:
        if self._source_prefix:
            return f"{self._source_prefix}/novels/"
        return "novels/"

    def _snapshot_root(self, snapshot_id: str) -> str:
        return f"{self._target_prefix}/{snapshot_id}"

    def _manifest_key(self, snapshot_id: str) -> str:
        return f"{self._snapshot_root(snapshot_id)}/manifest.json"

    def _list_source_objects(self) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        paginator = self._source_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self._source_bucket,
            Prefix=self._canonical_source_prefix,
        ):
            objects.extend(page.get("Contents", []))
        return sorted(objects, key=lambda item: str(item.get("Key", "")))

    def _read_target_object(self, *, key: str) -> bytes:
        response = self._target_client.get_object(Bucket=self._target_bucket, Key=key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def create_snapshot(self) -> SnapshotResult:
        snapshot_id = _new_snapshot_id()
        created_at = _utc_now_iso()
        snapshot_root = self._snapshot_root(snapshot_id)
        source_prefix = self._canonical_source_prefix
        copied_keys: list[str] = []
        entries: list[dict[str, Any]] = []
        total_bytes = 0

        try:
            for source in self._list_source_objects():
                source_key = str(source["Key"])
                relative_key = source_key[len(source_prefix):]
                if not relative_key:
                    continue
                destination_key = f"{snapshot_root}/objects/{relative_key}"
                source_etag_header = str(source.get("ETag") or "")
                source_etag = _etag(source_etag_header)
                read_args: dict[str, Any] = {"Bucket": self._source_bucket, "Key": source_key}
                if source_etag_header:
                    read_args["IfMatch"] = source_etag_header
                response = self._source_client.get_object(**read_args)
                source_body = response["Body"]
                digest_builder = hashlib.sha256()
                with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as staged:
                    try:
                        while chunk := source_body.read(1024 * 1024):
                            digest_builder.update(chunk)
                            staged.write(chunk)
                    finally:
                        source_body.close()
                    staged.seek(0)
                    self._target_client.upload_fileobj(staged, self._target_bucket, destination_key)
                copied_keys.append(destination_key)

                restored = self._read_target_object(key=destination_key)
                expected_size = int(source.get("Size", 0))
                if len(restored) != expected_size:
                    raise RuntimeError("Snapshot object size verification failed")
                digest = digest_builder.hexdigest()
                if hashlib.sha256(restored).hexdigest() != digest:
                    raise RuntimeError("Snapshot object checksum verification failed")
                entries.append(
                    {
                        "key": relative_key,
                        "size_bytes": expected_size,
                        "source_etag": source_etag,
                        "sha256": digest,
                    }
                )
                total_bytes += expected_size

            manifest = {
                "schema_version": 1,
                "snapshot_id": snapshot_id,
                "backup_type": "full",
                "status": "succeeded",
                "created_at": created_at,
                "source_prefix": source_prefix,
                "files_count": len(entries),
                "size_bytes": total_bytes,
                "objects": entries,
                "restore_verification": {"status": "succeeded", "verified_at": _utc_now_iso()},
            }
            manifest_body = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            self._target_client.put_object(
                Bucket=self._target_bucket,
                Key=self._manifest_key(snapshot_id),
                Body=manifest_body,
                ContentType="application/octet-stream",
            )
            copied_keys.append(self._manifest_key(snapshot_id))
            verified_manifest = json.loads(
                self._read_target_object(key=self._manifest_key(snapshot_id))
            )
            if verified_manifest != manifest:
                raise RuntimeError("Snapshot manifest verification failed")
            return SnapshotResult(
                snapshot_id=snapshot_id,
                created_at=created_at,
                files_count=len(entries),
                size_bytes=total_bytes,
                verified=True,
            )
        except Exception:
            for key in reversed(copied_keys):
                try:
                    self._target_client.delete_object(Bucket=self._target_bucket, Key=key)
                except Exception:
                    logger.warning("Could not clean incomplete snapshot object", exc_info=True)
            raise

    def _load_manifest(self, snapshot_id: str) -> dict[str, Any]:
        body = self._read_target_object(key=self._manifest_key(snapshot_id))
        manifest = json.loads(body)
        if not isinstance(manifest, dict) or manifest.get("snapshot_id") != snapshot_id:
            raise RuntimeError("Invalid snapshot manifest")
        return manifest

    def latest_snapshot(self) -> SnapshotResult | None:
        roots: list[str] = []
        paginator = self._target_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self._target_bucket,
            Prefix=f"{self._target_prefix}/",
            Delimiter="/",
        ):
            roots.extend(str(item["Prefix"]) for item in page.get("CommonPrefixes", []))

        for root in sorted(roots, reverse=True):
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
        snapshot_root = self._snapshot_root(snapshot_id)
        for entry in manifest.get("objects", []):
            key = f"{snapshot_root}/objects/{entry['key']}"
            restored = self._read_target_object(key=key)
            if len(restored) != int(entry["size_bytes"]):
                raise RuntimeError("Restore drill size verification failed")
            if hashlib.sha256(restored).hexdigest() != entry["sha256"]:
                raise RuntimeError("Restore drill checksum verification failed")
        return SnapshotResult(
            snapshot_id=snapshot_id,
            created_at=str(manifest.get("created_at", "")),
            files_count=int(manifest.get("files_count", 0)),
            size_bytes=int(manifest.get("size_bytes", 0)),
            verified=True,
        )
