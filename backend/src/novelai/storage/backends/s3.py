"""S3-backed storage backend using boto3."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from novelai.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


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
        key = self._key(path)
        logger.debug("S3 save: bucket=%s key=%s size=%d", self._bucket, key, len(data))
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def load(self, path: str | Path) -> bytes:
        key = self._key(path)
        logger.debug("S3 load: bucket=%s key=%s", self._bucket, key)
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(f"S3 key not found: {key}") from exc
        body = resp["Body"].read()
        resp["Body"].close()
        return body

    def delete(self, path: str | Path) -> None:
        key = self._key(path)
        logger.debug("S3 delete: bucket=%s key=%s", self._bucket, key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            pass
        except Exception:
            pass

    def exists(self, path: str | Path) -> bool:
        key = self._key(path)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def list_keys(self, prefix: str | Path) -> list[str]:
        key = self._key(prefix)
        # delimiter listing for subdir grouping; empty prefix lists root
        prefix_str = key if not key or key.endswith("/") else f"{key}/"
        logger.debug("S3 list_keys: bucket=%s prefix=%s", self._bucket, prefix_str)
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
