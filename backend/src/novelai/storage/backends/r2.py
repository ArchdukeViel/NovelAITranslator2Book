"""Explicit Cloudflare R2 object storage.

R2 speaks the S3 API, but this module deliberately exposes an R2-specific
application boundary: there is no configurable key prefix, filesystem mode,
or silent fallback. Listing is fully paginated and is intended for inventory,
backup, migration, and garbage-collection workflows only.
"""

from __future__ import annotations

import hashlib
import io
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from novelai.storage.backends.base import R2StorageBackend
from novelai.storage.content_addressing import ArtifactConflictError, sha256_base64

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound", "NoSuchObject"}
_CONFLICT_CODES = {"409", "412", "PreconditionFailed"}


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return ""
    error = response.get("Error")
    if not isinstance(error, dict):
        return ""
    return str(error.get("Code", ""))


def _is_not_found_error(exc: Exception) -> bool:
    return _error_code(exc) in _NOT_FOUND_CODES


def _is_precondition_error(exc: Exception) -> bool:
    code = _error_code(exc)
    response = getattr(exc, "response", None)
    status = None
    if isinstance(response, dict):
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict):
            status = metadata.get("HTTPStatusCode")
    return code in _CONFLICT_CODES or status == 412


@dataclass(frozen=True, slots=True)
class R2ObjectMetadata:
    key: str
    size_bytes: int
    etag: str | None = None
    logical_sha256: str | None = None
    checksum_sha256: str | None = None
    content_type: str | None = None
    content_encoding: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImmutableWriteResult:
    key: str
    created: bool
    size_bytes: int
    logical_sha256: str


@dataclass(slots=True)
class R2OperationStats:
    """Bounded in-process counters for operator metrics and tests."""

    operations: dict[str, int] = field(default_factory=dict)
    bytes_read: int = 0
    bytes_written: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0

    def record(self, operation: str, *, elapsed_ms: float, error: bool = False) -> None:
        self.operations[operation] = self.operations.get(operation, 0) + 1
        self.total_latency_ms += elapsed_ms
        if error:
            self.errors += 1


class R2Storage(R2StorageBackend):
    """Object store for the canonical `dokushodo` application bucket."""

    _BACKING = "r2"
    _MULTIPART_THRESHOLD_BYTES = 8 * 1024 * 1024
    _MULTIPART_CHUNKSIZE_BYTES = 8 * 1024 * 1024
    _MULTIPART_MAX_CONCURRENCY = 4

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region: str = "auto",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: Any | None = None,
        connect_timeout_seconds: int = 10,
        read_timeout_seconds: int = 60,
    ) -> None:
        if not bucket.strip():
            raise ValueError("R2 bucket must not be blank")
        self._bucket = bucket.strip()
        self._stats = R2OperationStats()
        if client is not None:
            self._client = client
            return

        import boto3
        from botocore.config import Config

        kwargs: dict[str, Any] = {
            "region_name": region,
            "config": Config(
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"mode": "standard", "max_attempts": 4},
            ),
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key_id:
            kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key:
            kwargs["aws_secret_access_key"] = secret_access_key
        self._client: Any = boto3.client("s3", **kwargs)

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def stats(self) -> R2OperationStats:
        return self._stats

    @staticmethod
    def _normalize_key(path: str | Path) -> str:
        key = str(path).replace("\\", "/").strip("/")
        if not key:
            return ""
        parts = key.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("R2 object keys cannot contain empty, dot, or parent components")
        return "/".join(parts)

    @staticmethod
    def _strip_prefix(key: str, prefix: str) -> str:
        if prefix and key.startswith(prefix + "/"):
            return key[len(prefix) + 1 :]
        return key

    def _observe(self, operation: str, started: float, *, error: bool = False) -> None:
        self._stats.record(operation, elapsed_ms=(time.perf_counter() - started) * 1000, error=error)

    def _head_raw(self, key: str) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception:
            self._observe("head", started, error=True)
            raise
        self._observe("head", started)
        return response

    def _metadata_from_response(self, key: str, response: dict[str, Any]) -> R2ObjectMetadata:
        metadata_raw = response.get("Metadata")
        metadata = (
            {str(name).lower(): str(value) for name, value in metadata_raw.items()}
            if isinstance(metadata_raw, dict)
            else {}
        )
        checksum = response.get("ChecksumSHA256")
        return R2ObjectMetadata(
            key=key,
            size_bytes=int(response.get("ContentLength", 0)),
            etag=str(response.get("ETag", "")).strip('"') or None,
            logical_sha256=metadata.get("logical-sha256"),
            checksum_sha256=str(checksum) if checksum else None,
            content_type=str(response.get("ContentType")) if response.get("ContentType") else None,
            content_encoding=str(response.get("ContentEncoding")) if response.get("ContentEncoding") else None,
            last_modified=response.get("LastModified") if isinstance(response.get("LastModified"), datetime) else None,
            metadata=metadata,
        )

    def head(self, path: str | Path) -> R2ObjectMetadata:
        key = self._normalize_key(path)
        try:
            return self._metadata_from_response(key, self._head_raw(key))
        except Exception as exc:
            if _is_not_found_error(exc):
                raise FileNotFoundError(f"R2 object not found: {key}") from exc
            raise

    def save(
        self,
        path: str | Path,
        data: bytes,
        *,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        key = self._normalize_key(path)
        kwargs: dict[str, Any] = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        if content_encoding:
            kwargs["ContentEncoding"] = content_encoding
        if metadata:
            kwargs["Metadata"] = metadata
        started = time.perf_counter()
        try:
            self._client.put_object(**kwargs)
            self._stats.bytes_written += len(data)
        except Exception:
            self._observe("put", started, error=True)
            raise
        self._observe("put", started)

    def save_stream(
        self,
        path: str | Path,
        source: BinaryIO,
        *,
        content_length: int | None = None,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> int:
        """Upload a binary stream with bounded multipart transfer settings.

        ``upload_fileobj`` keeps small writes as one request and switches to
        multipart transfer at the configured threshold. The provider computes
        and validates a SHA-256 checksum for both paths. The returned length is
        read from the committed object metadata rather than inferred from the
        source stream, so non-seekable producers are supported.
        """

        if content_length is not None and content_length < 0:
            raise ValueError("R2 stream content length must not be negative")
        key = self._normalize_key(path)
        extra_args: dict[str, Any] = {"ChecksumAlgorithm": "SHA256"}
        if content_type:
            extra_args["ContentType"] = content_type
        if content_encoding:
            extra_args["ContentEncoding"] = content_encoding
        if metadata:
            extra_args["Metadata"] = metadata

        from boto3.s3.transfer import TransferConfig

        config = TransferConfig(
            multipart_threshold=self._MULTIPART_THRESHOLD_BYTES,
            multipart_chunksize=self._MULTIPART_CHUNKSIZE_BYTES,
            max_concurrency=self._MULTIPART_MAX_CONCURRENCY,
            use_threads=True,
        )
        started = time.perf_counter()
        try:
            self._client.upload_fileobj(
                source,
                self._bucket,
                key,
                ExtraArgs=extra_args,
                Config=config,
            )
            response = self._head_raw(key)
            size_bytes = int(response.get("ContentLength", 0))
            if content_length is not None and size_bytes != content_length:
                try:
                    self.delete(key)
                except Exception:
                    logger.warning("Could not clean R2 stream with unexpected length: %s", key, exc_info=True)
                raise ValueError(f"R2 stream length mismatch for {key}: expected {content_length}, got {size_bytes}")
            self._stats.bytes_written += size_bytes
        except Exception:
            self._observe("put_stream", started, error=True)
            raise
        self._observe("put_stream", started)
        return size_bytes

    def put_immutable(
        self,
        path: str | Path,
        data: bytes,
        *,
        logical_sha256: str,
        content_type: str = "application/json",
        content_encoding: str | None = "gzip",
    ) -> ImmutableWriteResult:
        """Create an immutable object or verify the existing exact object."""

        key = self._normalize_key(path)
        try:
            existing = self.head(key)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing.logical_sha256 == logical_sha256 and existing.size_bytes == len(data):
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            # Older objects may not have metadata; compare bytes before
            # treating a same-key retry as a conflict.
            current = self.load(key)
            if current == data:
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            raise ArtifactConflictError(f"Immutable R2 object differs: {key}")

        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            "Metadata": {"logical-sha256": logical_sha256},
            "ChecksumSHA256": sha256_base64(data),
            "IfNoneMatch": "*",
        }
        if content_encoding:
            kwargs["ContentEncoding"] = content_encoding
        started = time.perf_counter()
        try:
            self._client.put_object(**kwargs)
            self._stats.bytes_written += len(data)
        except Exception as exc:
            self._observe("put_immutable", started, error=True)
            if _is_precondition_error(exc):
                existing = self.head(key)
                if existing.logical_sha256 == logical_sha256 and existing.size_bytes == len(data):
                    return ImmutableWriteResult(key, False, len(data), logical_sha256)
            raise
        self._observe("put_immutable", started)
        return ImmutableWriteResult(key, True, len(data), logical_sha256)

    def load(self, path: str | Path) -> bytes:
        key = self._normalize_key(path)
        started = time.perf_counter()
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                data = body.read()
            finally:
                body.close()
            self._stats.bytes_read += len(data)
        except Exception as exc:
            self._observe("get", started, error=True)
            if _is_not_found_error(exc):
                raise FileNotFoundError(f"R2 object not found: {key}") from exc
            raise
        self._observe("get", started)
        return data

    def delete(self, path: str | Path) -> None:
        key = self._normalize_key(path)
        started = time.perf_counter()
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception:
            self._observe("delete", started, error=True)
            raise
        self._observe("delete", started)

    def exists(self, path: str | Path) -> bool:
        try:
            self.head(path)
        except FileNotFoundError:
            return False
        return True

    def copy_object(self, source: str | Path, destination: str | Path) -> None:
        source_key = self._normalize_key(source)
        destination_key = self._normalize_key(destination)
        started = time.perf_counter()
        try:
            self._client.copy_object(
                Bucket=self._bucket,
                Key=destination_key,
                CopySource={"Bucket": self._bucket, "Key": source_key},
            )
        except Exception:
            self._observe("copy", started, error=True)
            raise
        self._observe("copy", started)

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        normalized = self._normalize_key(prefix)
        prefix_str = normalized if not normalized or normalized.endswith("/") else f"{normalized}/"
        started = time.perf_counter()
        keys: list[str] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self._bucket, Prefix=prefix_str, **({} if recursive else {"Delimiter": "/"})
            )
            for page in pages:
                keys.extend(str(item["Key"]) for item in page.get("Contents", []) if item.get("Key"))
                if not recursive:
                    keys.extend(str(item["Prefix"]) for item in page.get("CommonPrefixes", []) if item.get("Prefix"))
        except Exception:
            self._observe("list", started, error=True)
            raise
        self._observe("list", started)
        return sorted(set(self._strip_prefix(key, "") for key in keys))

    def has_keys(self, prefix: str | Path) -> bool:
        normalized = self._normalize_key(prefix)
        prefix_str = normalized if not normalized or normalized.endswith("/") else f"{normalized}/"
        started = time.perf_counter()
        try:
            response = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix_str, MaxKeys=1)
        except Exception:
            self._observe("exists_prefix", started, error=True)
            raise
        self._observe("exists_prefix", started)
        return bool(response.get("Contents") or response.get("CommonPrefixes"))

    def total_size_bytes(self) -> int:
        started = time.perf_counter()
        total = 0
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket):
                total += sum(int(item.get("Size", 0)) for item in page.get("Contents", []))
        except Exception:
            self._observe("inventory", started, error=True)
            raise
        self._observe("inventory", started)
        return total

    def delete_prefix(self, prefix: str | Path) -> int:
        """Delete every object under a prefix, including all list pages.

        The full key list is collected before any delete request. Mutating an
        object store while advancing the same listing can invalidate its
        continuation cursor and skip keys on providers that re-evaluate the
        listing between pages.
        """

        normalized = self._normalize_key(prefix)
        prefix_str = normalized if not normalized or normalized.endswith("/") else f"{normalized}/"
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix_str):
            keys.extend(str(item["Key"]) for item in page.get("Contents", []) if item.get("Key"))
        for start in range(0, len(keys), 1000):
            batch = keys[start : start + 1000]
            if not batch:
                continue
            self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
            )
        return len(keys)

    def mkdirs(self, path: str | Path) -> None:
        # R2 has virtual prefixes; marker objects would violate the app layout.
        return None

    def probe_readiness(self) -> bool:
        started = time.perf_counter()
        try:
            # Readiness is a bucket reachability check, not an inventory
            # operation. HEAD avoids enumerating the canonical content prefix
            # on every health probe.
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._observe("probe", started, error=True)
            raise
        self._observe("probe", started)
        return True

    def compare_and_swap(self, path: str | Path, expected: bytes | None, new_value: bytes) -> bool:
        """Conditionally replace an object using one observed ETag version."""

        key = self._normalize_key(path)
        from botocore.exceptions import ClientError

        if expected is None:
            try:
                self._client.put_object(Bucket=self._bucket, Key=key, Body=new_value, IfNoneMatch="*")
            except ClientError as exc:
                if _is_precondition_error(exc):
                    return False
                raise
            return True

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                current = body.read()
            finally:
                body.close()
            etag = response.get("ETag")
        except ClientError as exc:
            if _is_not_found_error(exc):
                return False
            raise
        if current != expected or not etag:
            return False
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=new_value, IfMatch=etag)
        except ClientError as exc:
            if _is_precondition_error(exc):
                return False
            raise
        return True


class _MemoryR2Error(Exception):
    """Small botocore-shaped error used by the in-memory R2 test double."""

    def __init__(self, code: str) -> None:
        status = int(code) if code.isdigit() else 404 if code in {"NoSuchKey", "NotFound"} else 412
        self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}
        super().__init__(code)


class _MemoryR2Body(io.BytesIO):
    """Closable response body matching the subset consumed by R2Storage."""


class _MemoryR2Paginator:
    def __init__(self, client: _MemoryR2Client) -> None:
        self._client = client

    def paginate(
        self, *, Bucket: str, Prefix: str = "", Delimiter: str | None = None, **_: Any
    ) -> list[dict[str, Any]]:
        return [self._client.list_objects_v2(Bucket=Bucket, Prefix=Prefix, Delimiter=Delimiter)]


class _MemoryR2Client:
    """Minimal S3-protocol double for isolated tests; it never touches disk."""

    def __init__(self) -> None:
        self._objects: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _etag(data: bytes) -> str:
        return f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'

    def head_object(self, *, Bucket: str, Key: str, **_: Any) -> dict[str, Any]:
        del Bucket
        with self._lock:
            record = self._objects.get(Key)
            if record is None:
                raise _MemoryR2Error("404")
            return dict(record["metadata"])

    def head_bucket(self, *, Bucket: str, **_: Any) -> dict[str, Any]:
        del Bucket
        return {}

    def get_object(self, *, Bucket: str, Key: str, **_: Any) -> dict[str, Any]:
        del Bucket
        with self._lock:
            record = self._objects.get(Key)
            if record is None:
                raise _MemoryR2Error("NoSuchKey")
            return {"Body": _MemoryR2Body(record["body"]), "ETag": record["metadata"]["ETag"]}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **kwargs: Any) -> dict[str, Any]:
        del Bucket
        data = bytes(Body)
        with self._lock:
            existing = self._objects.get(Key)
            if kwargs.get("IfNoneMatch") == "*" and existing is not None:
                raise _MemoryR2Error("412")
            expected_etag = kwargs.get("IfMatch")
            if expected_etag is not None and (existing is None or existing["metadata"]["ETag"] != expected_etag):
                raise _MemoryR2Error("412")
            metadata = {str(k).lower(): str(v) for k, v in (kwargs.get("Metadata") or {}).items()}
            record_metadata: dict[str, Any] = {
                "ContentLength": len(data),
                "ETag": self._etag(data),
                "Metadata": metadata,
                "ChecksumSHA256": kwargs.get("ChecksumSHA256"),
            }
            record_metadata["ContentType"] = kwargs.get("ContentType")
            record_metadata["ContentEncoding"] = kwargs.get("ContentEncoding")
            self._objects[Key] = {"body": data, "metadata": record_metadata}
        return {}

    def delete_object(self, *, Bucket: str, Key: str, **_: Any) -> dict[str, Any]:
        del Bucket
        with self._lock:
            self._objects.pop(Key, None)
        return {}

    def copy_object(self, *, Bucket: str, Key: str, CopySource: dict[str, str], **_: Any) -> dict[str, Any]:
        del Bucket
        source_key = CopySource["Key"]
        with self._lock:
            source = self._objects.get(source_key)
            if source is None:
                raise _MemoryR2Error("NoSuchKey")
            self._objects[Key] = {
                "body": source["body"],
                "metadata": dict(source["metadata"]),
            }
        return {}

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str = "",
        Delimiter: str | None = None,
        MaxKeys: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        del Bucket
        with self._lock:
            keys = sorted(key for key in self._objects if key.startswith(Prefix))
            contents: list[dict[str, Any]] = []
            common_prefixes: set[str] = set()
            for key in keys:
                suffix = key[len(Prefix) :]
                if Delimiter and Delimiter in suffix:
                    common_prefixes.add(Prefix + suffix.split(Delimiter, 1)[0] + Delimiter)
                    continue
                record = self._objects[key]
                contents.append({"Key": key, "Size": len(record["body"])})
                if MaxKeys and len(contents) >= MaxKeys:
                    break
            result: dict[str, Any] = {"Contents": contents}
            if common_prefixes:
                result["CommonPrefixes"] = [{"Prefix": prefix} for prefix in sorted(common_prefixes)]
            return result

    def get_paginator(self, name: str) -> _MemoryR2Paginator:
        if name != "list_objects_v2":
            raise ValueError(name)
        return _MemoryR2Paginator(self)

    def delete_objects(self, *, Bucket: str, Delete: dict[str, Any], **_: Any) -> dict[str, Any]:
        del Bucket
        for item in Delete.get("Objects", []):
            if isinstance(item, dict) and item.get("Key"):
                self._objects.pop(str(item["Key"]), None)
        return {}


class InMemoryR2Storage(R2Storage):
    """R2-semantic test double that keeps objects only in process memory."""

    _TEST_DOUBLE = True

    def __init__(self) -> None:
        super().__init__(bucket="test-r2", endpoint_url=None, client=_MemoryR2Client())

    def compare_and_swap(self, path: str | Path, expected: bytes | None, new_value: bytes) -> bool:
        current: bytes | None
        try:
            current = self.load(path)
        except FileNotFoundError:
            current = None
        if current != expected:
            return False
        self.save(path, new_value)
        return True
