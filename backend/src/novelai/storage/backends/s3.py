"""S3-backed storage backend using boto3."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from novelai.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}


def _is_not_found_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error")
    if not isinstance(error, dict):
        return False
    return str(error.get("Code", "")) in _NOT_FOUND_CODES


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
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        import boto3

        self._BACKING: str = "s3"
        self._bucket = bucket
        self._key_prefix = key_prefix.strip("/")
        client_kwargs: dict[str, Any] = {"region_name": region}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if aws_access_key_id:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key
        self._client: Any = boto3.client("s3", **client_kwargs)

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
        except Exception as exc:
            if _is_not_found_error(exc):
                raise FileNotFoundError(f"S3 key not found: {key}") from exc
            raise
        body = resp["Body"].read()
        resp["Body"].close()
        return body

    def delete(self, path: str | Path) -> None:
        key = self._key(path)
        logger.debug("S3 delete: bucket=%s key=%s", self._bucket, key)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, path: str | Path) -> bool:
        key = self._key(path)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception as exc:
            if _is_not_found_error(exc):
                return False
            raise

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        key = self._key(prefix)
        prefix_str = key if not key or key.endswith("/") else f"{key}/"
        logger.debug("S3 list_keys: bucket=%s prefix=%s recursive=%s", self._bucket, prefix_str, recursive)

        if recursive:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix_str):
                for obj in page.get("Contents", []):
                    k: str = obj["Key"]
                    if self._key_prefix and k.startswith(self._key_prefix + "/"):
                        k = k[len(self._key_prefix) + 1 :]
                    keys.append(k)
            return sorted(keys)

        # Non-recursive: use delimiter for directory grouping
        resp = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix_str, Delimiter="/")
        keys = []
        for cp in resp.get("CommonPrefixes", []):
            k: str = cp["Prefix"]
            if self._key_prefix and k.startswith(self._key_prefix + "/"):
                k = k[len(self._key_prefix) + 1 :]
            keys.append(k)
        for obj in resp.get("Contents", []):
            k: str = obj["Key"]
            if self._key_prefix and k.startswith(self._key_prefix + "/"):
                k = k[len(self._key_prefix) + 1 :]
            keys.append(k)
        return sorted(keys)

    def has_keys(self, prefix: str | Path) -> bool:
        key = self._key(prefix)
        prefix_str = key if not key or key.endswith("/") else f"{key}/"
        resp = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix_str, MaxKeys=1)
        return bool(resp.get("Contents"))

    def total_size_bytes(self) -> int:
        total = 0
        prefix = f"{self._key_prefix}/" if self._key_prefix else ""
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            total += sum(int(obj.get("Size", 0)) for obj in page.get("Contents", []))
        return total

    def mkdirs(self, path: str | Path) -> None:
        pass  # S3 has no directories; objects are created implicitly

    def compare_and_swap(self, path: str | Path, expected: bytes | None, new_value: bytes) -> bool:
        """Atomic conditional PUT against the active pointer object.

        Reads the current object's ETag, then ``put_object`` with the
        ``IfMatch=ETag`` constraint so a concurrent writer cannot silently
        overwrite an activation pointer with stale expected bytes. A
        missing current object (``expected is None``) uses ``IfNoneMatch='*'``
        so first-writer-wins on activation.

        Returns ``False`` when:

        - the local ``expected`` does not match the current ETag
          (``PreconditionFailed``, ``412``);
        - the object already exists when ``expected`` is ``None``
          (``PreconditionFailed`` for ``IfNoneMatch='*'``).

        On any other ``ClientError`` we re-raise so the caller can treat it
        as a real storage failure rather than silently degrading to
        last-writer-wins.
        """
        from botocore.exceptions import ClientError

        key = self._key(path)
        etag = None
        try:
            head = self._client.head_object(Bucket=self._bucket, Key=key)
            etag = head.get("ETag")
        except ClientError as exc:
            if not _is_not_found_error(exc):
                raise
            # Object is absent; that is a valid expected=None state.
        if expected is None:
            params: dict[str, Any] = {"Bucket": self._bucket, "Key": key, "Body": new_value}
            params["IfNoneMatch"] = "*"
        else:
            params = {"Bucket": self._bucket, "Key": key, "Body": new_value}
            if etag is None:
                # The expected bytes are not absent; if the object truly
                # does not exist we must refuse the swap rather than
                # silently degrading to last-writer-wins.
                return False
            params["IfMatch"] = etag
        try:
            self._client.put_object(**params)
        except ClientError as exc:
            response = getattr(exc, "response", None)
            if isinstance(response, dict):
                status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                error = response.get("Error", {}) if isinstance(response.get("Error"), dict) else {}
                code = str(error.get("Code", ""))
                if status == 412 or code in {"PreconditionFailed"}:
                    return False
            raise
        return True
