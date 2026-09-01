"""Cloudflare R2 access through the private native-binding gateway."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import BinaryIO, Literal
from urllib.parse import quote

import httpx

from novelai.infrastructure.http.client import validate_safe_url
from novelai.services.timing_contract import record_internal_span
from novelai.storage.backends.base import R2StorageBackend
from novelai.storage.content_addressing import ArtifactConflictError, sha256_base64

logger = logging.getLogger(__name__)

R2BucketClass = Literal["app", "backup"]
_FIXED_METADATA = frozenset({"logical-sha256", "checksum-sha256", "source-etag", "sha256"})
_NOT_FOUND_STATUS = 404
_CONFLICT_STATUS = 412
_MAX_KEY_LENGTH = 1024


class R2GatewayError(RuntimeError):
    """Safe, status-bearing error from the private R2 gateway."""

    def __init__(self, *, status_code: int, error_code: str, request_id: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id
        super().__init__(f"R2 gateway request failed (status={status_code}, code={error_code})")


class R2GatewayPreconditionError(R2GatewayError):
    """The gateway rejected a conditional write."""


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


@dataclass(frozen=True, slots=True)
class R2ListResult:
    objects: tuple[R2ObjectMetadata, ...]
    prefixes: tuple[str, ...]
    cursor: str | None
    truncated: bool


@dataclass(slots=True)
class R2OperationStats:
    """Bounded in-process timing counters for operator diagnostics and tests."""

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


def _normalize_key(path: str | Path, *, allow_empty: bool = False) -> str:
    raw = str(path).replace("\\", "/")
    if not raw:
        if allow_empty:
            return ""
        raise ValueError("R2 object key must not be blank")
    if raw.startswith("/") or len(raw) > _MAX_KEY_LENGTH:
        raise ValueError("R2 object key is outside the allowed namespace")
    parts = raw.strip("/").split("/")
    if not parts or (not allow_empty and not parts[0]):
        raise ValueError("R2 object key must not be blank")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("R2 object keys cannot contain empty, dot, or parent components")
    return "/".join(parts)


def _prefix(path: str | Path) -> str:
    value = _normalize_key(path, allow_empty=True)
    return f"{value}/" if value else ""


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped.strip('"') or None


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError, IndexError:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


class R2GatewayStorage(R2StorageBackend):
    """Canonical object-store client for one fixed R2 gateway bucket class."""

    _BACKING = "r2"

    def __init__(
        self,
        *,
        bucket: str,
        bucket_class: R2BucketClass,
        gateway_url: str,
        client_id: str,
        client_secret: str,
        client: httpx.Client | None = None,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 60.0,
        max_object_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        if not bucket.strip():
            raise ValueError("R2 bucket must not be blank")
        if bucket_class not in {"app", "backup"}:
            raise ValueError("R2 gateway bucket class is invalid")
        if not client_id.strip() or not client_secret:
            raise ValueError("R2 gateway Access identity is required")
        validated_url = validate_safe_url(gateway_url.rstrip("/"))
        if not validated_url.startswith("https://") and client is None:
            raise ValueError("R2 gateway URL must use HTTPS")
        if max_object_bytes <= 0:
            raise ValueError("R2 gateway object limit must be positive")
        self._bucket = bucket.strip()
        self._bucket_class: R2BucketClass = bucket_class
        self._base_url = validated_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._max_object_bytes = max_object_bytes
        self._stats = R2OperationStats()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(
                connect=connect_timeout_seconds,
                read=read_timeout_seconds,
                write=read_timeout_seconds,
                pool=connect_timeout_seconds,
            ),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def bucket_class(self) -> R2BucketClass:
        return self._bucket_class

    @property
    def stats(self) -> R2OperationStats:
        return self._stats

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> R2GatewayStorage:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request_headers(self, request_id: str | None = None) -> dict[str, str]:
        return {
            "CF-Access-Client-Id": self._client_id,
            "CF-Access-Client-Secret": self._client_secret,
            "X-Request-ID": request_id or uuid.uuid4().hex,
        }

    def _object_path(self, key: str) -> str:
        return f"/v1/{self._bucket_class}/objects/{quote(key, safe='')}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str | int | bool] | None = None,
        content: bytes | BinaryIO | None = None,
    ) -> httpx.Response:
        request_headers = self._request_headers()
        if headers:
            request_headers.update(headers)
        response = self._client.request(method, path, headers=request_headers, params=params, content=content)
        if response.status_code >= 400:
            request_id = response.headers.get("x-request-id", request_headers["X-Request-ID"])
            error_code = response.headers.get("x-r2-error-code")
            if not error_code:
                try:
                    payload = response.json()
                    candidate = payload.get("error_code") if isinstance(payload, dict) else None
                    error_code = str(candidate)[:64] if candidate else "http_error"
                except ValueError, json.JSONDecodeError:
                    error_code = "http_error"
            response.close()
            error_type = R2GatewayPreconditionError if response.status_code == _CONFLICT_STATUS else R2GatewayError
            raise error_type(status_code=response.status_code, error_code=error_code, request_id=request_id)
        return response

    def _observe(self, operation: str, started: float, *, error: bool = False) -> None:
        elapsed_ms = max(0.0, (time.perf_counter() - started) * 1000)
        self._stats.record(operation, elapsed_ms=elapsed_ms, error=error)
        span_name = "r2_exact_read" if operation in {"head", "get", "get_range", "list"} else "r2_exact_write"
        record_internal_span(span_name, source="r2_gateway", duration_ms=elapsed_ms)

    def _metadata_from_headers(self, key: str, headers: httpx.Headers) -> R2ObjectMetadata:
        try:
            size = int(headers.get("content-length", "0"))
        except ValueError as exc:
            raise R2GatewayError(
                status_code=502,
                error_code="invalid_gateway_metadata",
                request_id=headers.get("x-request-id", "unknown"),
            ) from exc
        metadata = {name: value for name in _FIXED_METADATA if (value := headers.get(f"x-r2-meta-{name}")) is not None}
        return R2ObjectMetadata(
            key=key,
            size_bytes=size,
            etag=_strip_quotes(headers.get("etag")),
            logical_sha256=metadata.get("logical-sha256"),
            checksum_sha256=headers.get("x-r2-checksum-sha256"),
            content_type=headers.get("content-type"),
            content_encoding=headers.get("content-encoding"),
            last_modified=_timestamp(headers.get("last-modified")),
            metadata=metadata,
        )

    @staticmethod
    def _metadata_headers(metadata: dict[str, str] | None) -> dict[str, str]:
        if not metadata:
            return {}
        headers: dict[str, str] = {}
        for key, value in metadata.items():
            normalized = str(key).strip().lower()
            if normalized not in _FIXED_METADATA:
                raise ValueError(f"R2 metadata field is not allowed: {normalized}")
            if len(str(value)) > 256:
                raise ValueError("R2 metadata value exceeds the gateway limit")
            headers[f"X-R2-Meta-{normalized}"] = str(value)
        return headers

    def head(self, path: str | Path) -> R2ObjectMetadata:
        key = _normalize_key(path)
        started = time.perf_counter()
        observed = False
        try:
            response = self._request("HEAD", self._object_path(key))
            try:
                return self._metadata_from_headers(key, response.headers)
            finally:
                response.close()
        except R2GatewayError as exc:
            self._observe("head", started, error=True)
            observed = True
            if exc.status_code == _NOT_FOUND_STATUS:
                raise FileNotFoundError("R2 object not found") from exc
            raise
        except Exception:
            self._observe("head", started, error=True)
            observed = True
            raise
        finally:
            if not observed:
                self._observe("head", started)

    def save(
        self,
        path: str | Path,
        data: bytes,
        *,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        if len(data) > self._max_object_bytes:
            raise ValueError("R2 object exceeds the gateway limit")
        key = _normalize_key(path)
        headers = {"Content-Length": str(len(data)), **self._metadata_headers(metadata)}
        if content_type:
            headers["X-R2-Content-Type"] = content_type
        if content_encoding:
            headers["X-R2-Content-Encoding"] = content_encoding
        started = time.perf_counter()
        try:
            response = self._request("PUT", self._object_path(key), headers=headers, content=data)
            response.close()
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
        if content_length is None or content_length < 0:
            raise ValueError("R2 gateway stream uploads require a non-negative content length")
        if content_length > self._max_object_bytes:
            raise ValueError("R2 stream exceeds the gateway limit")
        key = _normalize_key(path)
        headers = {"Content-Length": str(content_length), **self._metadata_headers(metadata)}
        if content_type:
            headers["X-R2-Content-Type"] = content_type
        if content_encoding:
            headers["X-R2-Content-Encoding"] = content_encoding
        started = time.perf_counter()
        try:
            response = self._request("PUT", self._object_path(key), headers=headers, content=source)
            response.close()
            committed = self.head(key)
            if committed.size_bytes != content_length:
                self.delete(key)
                raise ValueError("R2 gateway stream length mismatch")
            self._stats.bytes_written += committed.size_bytes
        except Exception:
            self._observe("put_stream", started, error=True)
            raise
        self._observe("put_stream", started)
        return content_length

    def put_immutable(
        self,
        path: str | Path,
        data: bytes,
        *,
        logical_sha256: str,
        content_type: str = "application/json",
        content_encoding: str | None = "gzip",
    ) -> ImmutableWriteResult:
        key = _normalize_key(path)
        try:
            existing = self.head(key)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing.logical_sha256 == logical_sha256 and existing.size_bytes == len(data):
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            if self.load(key) == data:
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            raise ArtifactConflictError("Immutable R2 object differs")

        headers = {
            "Content-Length": str(len(data)),
            "If-None-Match": "*",
            "X-R2-Content-Type": content_type,
            "X-R2-Meta-Logical-Sha256": logical_sha256,
            "X-R2-Checksum-Sha256": sha256_base64(data),
        }
        if content_encoding:
            headers["X-R2-Content-Encoding"] = content_encoding
        started = time.perf_counter()
        try:
            response = self._request("PUT", self._object_path(key), headers=headers, content=data)
            response.close()
            self._stats.bytes_written += len(data)
        except R2GatewayPreconditionError as exc:
            self._observe("put_immutable", started, error=True)
            try:
                existing = self.head(key)
            except FileNotFoundError:
                raise exc from None
            if existing.logical_sha256 == logical_sha256 and existing.size_bytes == len(data):
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            if self.load(key) == data:
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            raise ArtifactConflictError("Immutable R2 object differs") from exc
        except Exception:
            self._observe("put_immutable", started, error=True)
            raise
        self._observe("put_immutable", started)
        return ImmutableWriteResult(key, True, len(data), logical_sha256)

    def load(self, path: str | Path) -> bytes:
        key = _normalize_key(path)
        started = time.perf_counter()
        observed = False
        try:
            response = self._request("GET", self._object_path(key))
            try:
                declared = int(response.headers.get("content-length", "0"))
                if declared > self._max_object_bytes:
                    raise ValueError("R2 object exceeds the gateway limit")
                data = response.read()
                if len(data) > self._max_object_bytes:
                    raise ValueError("R2 object exceeds the gateway limit")
                self._stats.bytes_read += len(data)
                return data
            finally:
                response.close()
        except R2GatewayError as exc:
            self._observe("get", started, error=True)
            observed = True
            if exc.status_code == _NOT_FOUND_STATUS:
                raise FileNotFoundError("R2 object not found") from exc
            raise
        except Exception:
            self._observe("get", started, error=True)
            observed = True
            raise
        finally:
            if not observed:
                self._observe("get", started)

    def load_range(self, path: str | Path, *, start: int, end: int | None = None) -> bytes:
        if start < 0 or (end is not None and end < start):
            raise ValueError("R2 byte range is invalid")
        key = _normalize_key(path)
        value = f"bytes={start}-{'' if end is None else end}"
        started = time.perf_counter()
        observed = False
        try:
            response = self._request("GET", self._object_path(key), headers={"Range": value})
            try:
                data = response.read()
                if len(data) > self._max_object_bytes:
                    raise ValueError("R2 range exceeds the gateway limit")
                self._stats.bytes_read += len(data)
                return data
            finally:
                response.close()
        except Exception:
            self._observe("get_range", started, error=True)
            observed = True
            raise
        finally:
            if not observed:
                self._observe("get_range", started)

    def delete(self, path: str | Path) -> None:
        key = _normalize_key(path)
        started = time.perf_counter()
        try:
            response = self._request("DELETE", self._object_path(key))
            response.close()
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
        source_key = _normalize_key(source)
        destination_key = _normalize_key(destination)
        metadata = self.head(source_key)
        self.save(
            destination_key,
            self.load(source_key),
            content_type=metadata.content_type,
            content_encoding=metadata.content_encoding,
            metadata=metadata.metadata,
        )

    def list_objects(
        self,
        prefix: str | Path = "",
        *,
        recursive: bool = False,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> R2ListResult:
        if not 1 <= limit <= 1000:
            raise ValueError("R2 list limit must be between 1 and 1000")
        normalized = _prefix(prefix)
        started = time.perf_counter()
        try:
            response = self._request(
                "GET",
                f"/v1/{self._bucket_class}/list",
                params={
                    "prefix": normalized,
                    "recursive": str(recursive).lower(),
                    "limit": limit,
                    **({"cursor": cursor} if cursor else {}),
                },
            )
            try:
                payload = response.json()
            finally:
                response.close()
            if not isinstance(payload, dict):
                raise R2GatewayError(
                    status_code=502,
                    error_code="invalid_gateway_response",
                    request_id="unknown",
                )
            objects: list[R2ObjectMetadata] = []
            raw_objects = payload.get("objects", [])
            if not isinstance(raw_objects, list):
                raise R2GatewayError(status_code=502, error_code="invalid_gateway_response", request_id="unknown")
            for item in raw_objects:
                if not isinstance(item, dict) or not isinstance(item.get("key"), str):
                    raise R2GatewayError(status_code=502, error_code="invalid_gateway_response", request_id="unknown")
                item_metadata = item.get("metadata")
                metadata = (
                    {str(k): str(v) for k, v in item_metadata.items() if str(k) in _FIXED_METADATA}
                    if isinstance(item_metadata, dict)
                    else {}
                )
                objects.append(
                    R2ObjectMetadata(
                        key=str(item["key"]),
                        size_bytes=int(item.get("size_bytes", 0)),
                        etag=_strip_quotes(str(item["etag"])) if item.get("etag") else None,
                        logical_sha256=metadata.get("logical-sha256"),
                        checksum_sha256=str(item["checksum_sha256"]) if item.get("checksum_sha256") else None,
                        content_type=str(item["content_type"]) if item.get("content_type") else None,
                        content_encoding=str(item["content_encoding"]) if item.get("content_encoding") else None,
                        last_modified=_timestamp(str(item["last_modified"])) if item.get("last_modified") else None,
                        metadata=metadata,
                    )
                )
            raw_prefixes = payload.get("delimited_prefixes", [])
            prefixes = tuple(str(value) for value in raw_prefixes) if isinstance(raw_prefixes, list) else ()
            result = R2ListResult(
                objects=tuple(objects),
                prefixes=prefixes,
                cursor=str(payload["cursor"]) if payload.get("cursor") else None,
                truncated=bool(payload.get("truncated", False)),
            )
        except Exception:
            self._observe("list", started, error=True)
            raise
        self._observe("list", started)
        return result

    def _iter_objects(self, prefix: str | Path = "", *, recursive: bool = True) -> Iterator[R2ObjectMetadata]:
        cursor: str | None = None
        while True:
            page = self.list_objects(prefix, recursive=recursive, cursor=cursor)
            yield from page.objects
            if not page.truncated or not page.cursor:
                return
            cursor = page.cursor

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        keys = [item.key for page in self._iter_list_pages(prefix, recursive=recursive) for item in page.objects]
        if not recursive:
            keys.extend(
                prefix_value
                for page in self._iter_list_pages(prefix, recursive=False)
                for prefix_value in page.prefixes
            )
        return sorted(set(keys))

    def _iter_list_pages(self, prefix: str | Path, *, recursive: bool) -> Iterator[R2ListResult]:
        cursor: str | None = None
        while True:
            page = self.list_objects(prefix, recursive=recursive, cursor=cursor)
            yield page
            if not page.truncated or not page.cursor:
                return
            cursor = page.cursor

    def has_keys(self, prefix: str | Path) -> bool:
        page = self.list_objects(prefix, recursive=False, limit=1)
        return bool(page.objects or page.prefixes)

    def total_size_bytes(self) -> int:
        return sum(item.size_bytes for item in self._iter_objects("", recursive=True))

    def delete_prefix(self, prefix: str | Path) -> int:
        keys = [item.key for item in self._iter_objects(prefix, recursive=True)]
        for key in keys:
            self.delete(key)
        return len(keys)

    def mkdirs(self, path: str | Path) -> None:
        del path

    def probe_readiness(self) -> bool:
        response = self._request("GET", "/v1/health")
        try:
            return response.status_code == 200
        finally:
            response.close()

    def compare_and_swap(self, path: str | Path, expected: bytes | None, new_value: bytes) -> bool:
        key = _normalize_key(path)
        if expected is None:
            try:
                response = self._request(
                    "PUT",
                    self._object_path(key),
                    headers={"Content-Length": str(len(new_value)), "If-None-Match": "*"},
                    content=new_value,
                )
                response.close()
                self._stats.bytes_written += len(new_value)
                return True
            except R2GatewayPreconditionError:
                return False
        try:
            current = self.head(key)
            current_bytes = self.load(key)
        except FileNotFoundError:
            return False
        if current_bytes != expected or not current.etag:
            return False
        try:
            response = self._request(
                "PUT",
                self._object_path(key),
                headers={
                    "Content-Length": str(len(new_value)),
                    "If-Match": f'"{current.etag}"',
                },
                content=new_value,
            )
            response.close()
            self._stats.bytes_written += len(new_value)
            return True
        except R2GatewayPreconditionError:
            return False


@dataclass(slots=True)
class _MemoryRecord:
    body: bytes
    metadata: R2ObjectMetadata


class InMemoryR2GatewayStorage(R2StorageBackend):
    """R2-semantic local test double with no network, disk, or alternate provider."""

    _TEST_DOUBLE = True
    _BACKING = "r2"

    def __init__(self, bucket: str = "test-r2") -> None:
        self._bucket = bucket
        self._objects: dict[str, _MemoryRecord] = {}
        self._lock = threading.RLock()
        self._stats = R2OperationStats()

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def bucket_class(self) -> R2BucketClass:
        bucket_class: R2BucketClass = "backup" if self._bucket.endswith("-backup") else "app"
        return bucket_class

    @property
    def stats(self) -> R2OperationStats:
        return self._stats

    @staticmethod
    def _etag(data: bytes) -> str:
        return f'"{hashlib.sha256(data).hexdigest()[:32]}"'

    @staticmethod
    def _metadata(
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> R2ObjectMetadata:
        return R2ObjectMetadata(
            key=key,
            size_bytes=len(data),
            etag=InMemoryR2GatewayStorage._etag(data),
            logical_sha256=(metadata or {}).get("logical-sha256"),
            checksum_sha256=(metadata or {}).get("checksum-sha256"),
            content_type=content_type,
            content_encoding=content_encoding,
            last_modified=datetime.now(UTC),
            metadata=dict(metadata or {}),
        )

    def head(self, path: str | Path) -> R2ObjectMetadata:
        key = _normalize_key(path)
        with self._lock:
            record = self._objects.get(key)
            if record is None:
                raise FileNotFoundError("R2 object not found")
            return record.metadata

    def save(
        self,
        path: str | Path,
        data: bytes,
        *,
        content_type: str | None = None,
        content_encoding: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        key = _normalize_key(path)
        if metadata and not set(metadata).issubset(_FIXED_METADATA):
            raise ValueError("R2 metadata field is not allowed")
        with self._lock:
            self._objects[key] = _MemoryRecord(
                body=bytes(data),
                metadata=self._metadata(
                    key,
                    data,
                    content_type=content_type,
                    content_encoding=content_encoding,
                    metadata=metadata,
                ),
            )

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
        data = source.read()
        if content_length is not None and len(data) != content_length:
            raise ValueError("R2 gateway stream length mismatch")
        self.save(path, data, content_type=content_type, content_encoding=content_encoding, metadata=metadata)
        return len(data)

    def put_immutable(
        self,
        path: str | Path,
        data: bytes,
        *,
        logical_sha256: str,
        content_type: str = "application/json",
        content_encoding: str | None = "gzip",
    ) -> ImmutableWriteResult:
        key = _normalize_key(path)
        try:
            existing = self.head(key)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing.logical_sha256 == logical_sha256 and existing.size_bytes == len(data):
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            if self.load(key) == data:
                return ImmutableWriteResult(key, False, len(data), logical_sha256)
            raise ArtifactConflictError("Immutable R2 object differs")
        self.save(
            key,
            data,
            content_type=content_type,
            content_encoding=content_encoding,
            metadata={"logical-sha256": logical_sha256, "checksum-sha256": sha256_base64(data)},
        )
        return ImmutableWriteResult(key, True, len(data), logical_sha256)

    def load(self, path: str | Path) -> bytes:
        key = _normalize_key(path)
        with self._lock:
            record = self._objects.get(key)
            if record is None:
                raise FileNotFoundError("R2 object not found")
            return record.body

    def load_range(self, path: str | Path, *, start: int, end: int | None = None) -> bytes:
        return self.load(path)[start : None if end is None else end + 1]

    def delete(self, path: str | Path) -> None:
        key = _normalize_key(path)
        with self._lock:
            self._objects.pop(key, None)

    def exists(self, path: str | Path) -> bool:
        try:
            self.head(path)
        except FileNotFoundError:
            return False
        return True

    def copy_object(self, source: str | Path, destination: str | Path) -> None:
        source_key = _normalize_key(source)
        destination_key = _normalize_key(destination)
        with self._lock:
            record = self._objects.get(source_key)
            if record is None:
                raise FileNotFoundError("R2 object not found")
            metadata = record.metadata
            self._objects[destination_key] = _MemoryRecord(
                body=record.body,
                metadata=self._metadata(
                    destination_key,
                    record.body,
                    content_type=metadata.content_type,
                    content_encoding=metadata.content_encoding,
                    metadata=metadata.metadata,
                ),
            )

    def list_objects(
        self,
        prefix: str | Path = "",
        *,
        recursive: bool = False,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> R2ListResult:
        if not 1 <= limit <= 1000:
            raise ValueError("R2 list limit must be between 1 and 1000")
        prefix_value = _prefix(prefix)
        try:
            start = 0 if cursor is None else int(cursor)
        except (TypeError, ValueError) as exc:
            raise ValueError("R2 list cursor is invalid") from exc
        if start < 0:
            raise ValueError("R2 list cursor is invalid")
        with self._lock:
            keys = sorted(key for key in self._objects if key.startswith(prefix_value))
            entries: list[tuple[str, str]] = []
            seen_prefixes: set[str] = set()
            for key in keys:
                suffix = key[len(prefix_value) :]
                if not recursive and "/" in suffix:
                    item = prefix_value + suffix.split("/", 1)[0] + "/"
                    if item not in seen_prefixes:
                        seen_prefixes.add(item)
                        entries.append(("prefix", item))
                    continue
                entries.append(("object", key))
            if start > len(entries):
                raise ValueError("R2 list cursor is invalid")
            page_entries = entries[start : start + limit]
            objects = tuple(self._objects[value].metadata for kind, value in page_entries if kind == "object")
            prefixes = tuple(value for kind, value in page_entries if kind == "prefix")
            next_start = start + len(page_entries)
            truncated = next_start < len(entries)
            return R2ListResult(
                objects,
                prefixes,
                str(next_start) if truncated else None,
                truncated,
            )

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        keys: list[str] = []
        cursor: str | None = None
        while True:
            page = self.list_objects(prefix, recursive=recursive, cursor=cursor)
            keys.extend(item.key for item in page.objects)
            keys.extend(page.prefixes)
            if not page.truncated or not page.cursor:
                return sorted(set(keys))
            cursor = page.cursor

    def has_keys(self, prefix: str | Path) -> bool:
        page = self.list_objects(prefix, recursive=False, limit=1)
        return bool(page.objects or page.prefixes)

    def total_size_bytes(self) -> int:
        with self._lock:
            return sum(len(record.body) for record in self._objects.values())

    def delete_prefix(self, prefix: str | Path) -> int:
        prefix_value = _prefix(prefix)
        with self._lock:
            keys = [key for key in self._objects if key.startswith(prefix_value)]
            for key in keys:
                del self._objects[key]
            return len(keys)

    def mkdirs(self, path: str | Path) -> None:
        del path

    def probe_readiness(self) -> bool:
        return True

    def compare_and_swap(self, path: str | Path, expected: bytes | None, new_value: bytes) -> bool:
        key = _normalize_key(path)
        with self._lock:
            current = self._objects.get(key)
            current_body = current.body if current else None
            if current_body != expected:
                return False
            self._objects[key] = _MemoryRecord(body=bytes(new_value), metadata=self._metadata(key, new_value))
            return True
