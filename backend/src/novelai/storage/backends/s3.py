"""S3-backed storage backend using boto3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from novelai.storage.backends.base import StorageBackend


class S3Backend(StorageBackend):
    """Stores objects in an S3-compatible bucket.

    Paths are stored as S3 object keys (forward-slash separated).
    Atomic writes are not guaranteed by the S3 API; callers that
    need strict atomicity should use a separate coordination layer.
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        key_prefix: str = "",
        endpoint_url: str | None = None,
    ) -> None:
        import boto3

        self._bucket = bucket
        self._key_prefix = key_prefix.strip("/")
        self._client: Any = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)

    # ── helpers ──────────────────────────────────────────────────────

    def _key(self, path: str | Path) -> str:
        """Build the full S3 object key from a relative path."""
        key = str(path).replace("\\", "/")
        if self._key_prefix:
            return f"{self._key_prefix}/{key}"
        return key

    # ── interface ────────────────────────────────────────────────────

    def save(self, path: str | Path, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=self._key(path), Body=data)

    def load(self, path: str | Path) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=self._key(path))
        body = resp["Body"].read()
        resp["Body"].close()
        return body

    def delete(self, path: str | Path) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._key(path))
        except self._client.exceptions.NoSuchKey:
            pass
        except Exception:
            # boto3 has per-service exceptions; swallow broadly for idempotency
            pass

    def exists(self, path: str | Path) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._key(path))
            return True
        except Exception:
            return False

    def list_keys(self, prefix: str | Path) -> list[str]:
        key = self._key(prefix)
        # delimiter listing: trailing slash groups subdirs; empty prefix lists root
        prefix_str = key if not key or key.endswith("/") else f"{key}/"
        resp = self._client.list_objects_v2(
            Bucket=self._bucket, Prefix=prefix_str, Delimiter="/"
        )
        keys: list[str] = []
        # CommonPrefixes for "directory" entries
        for cp in resp.get("CommonPrefixes", []):
            k: str = cp["Prefix"]
            # Strip key_prefix from returned keys
            if self._key_prefix and k.startswith(self._key_prefix + "/"):
                k = k[len(self._key_prefix) + 1:]
            keys.append(k)
        # Object keys for files
        for obj in resp.get("Contents", []):
            k: str = obj["Key"]
            # Strip key_prefix
            if self._key_prefix and k.startswith(self._key_prefix + "/"):
                k = k[len(self._key_prefix) + 1:]
            keys.append(k)
        return sorted(keys)

    def mkdirs(self, path: str | Path) -> None:
        pass  # S3 has no directories; objects are created implicitly
