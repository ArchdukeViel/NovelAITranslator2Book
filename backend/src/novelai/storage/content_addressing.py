"""Deterministic, content-addressed R2 artifact helpers.

The logical hash is calculated from canonical uncompressed JSON bytes. Gzip is
only a transport encoding and is deliberately deterministic so repeated
uploads of the same logical artifact have identical bytes as well as keys.
"""

from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import io
import json
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from novelai.core.security import validate_storage_identifier

ArtifactKind = Literal["chapters", "translations", "media", "generations"]

DEFAULT_VOLATILE_FIELDS = frozenset(
    {
        "created_at",
        "updated_at",
        "scraped_at",
        "translated_at",
        "last_updated",
        "timestamp",
    }
)


class ArtifactConflictError(RuntimeError):
    """Raised when an immutable key already contains different bytes."""


def _normalize(value: Any, *, volatile_fields: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {
            unicodedata.normalize("NFC", str(key)): _normalize(item, volatile_fields=volatile_fields)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in volatile_fields
        }
    if isinstance(value, list):
        return [_normalize(item, volatile_fields=volatile_fields) for item in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    return value


def canonical_json_bytes(
    payload: Any,
    *,
    volatile_fields: frozenset[str] = DEFAULT_VOLATILE_FIELDS,
) -> bytes:
    """Return stable UTF-8 JSON bytes suitable for logical hashing."""

    normalized = _normalize(copy.deepcopy(payload), volatile_fields=volatile_fields)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def deterministic_gzip(data: bytes) -> bytes:
    """Compress bytes without embedding the current time or filename."""

    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
        stream.write(data)
    return output.getvalue()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_base64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def _safe_component(value: str, field: str) -> str:
    safe = validate_storage_identifier(str(value), field)
    if safe in {".", ".."} or "/" in safe or "\\" in safe:
        raise ValueError(f"{field} must be one storage-key component")
    return safe


def validate_internal_novel_id(value: str | int) -> str:
    """Return the immutable PostgreSQL novel ID used in R2 object keys."""

    safe = _safe_component(str(value), "storage_novel_id")
    if not safe.isdecimal() or int(safe) <= 0 or str(int(safe)) != safe:
        raise ValueError("storage_novel_id must be a positive canonical PostgreSQL integer ID")
    return safe


def artifact_key(
    novel_id: str,
    kind: ArtifactKind,
    identity: str,
    logical_hash: str,
    *,
    extension: str = "json.gz",
) -> str:
    """Build the exact application key for a content-addressed artifact."""

    safe_novel = validate_internal_novel_id(novel_id)
    safe_identity = _safe_component(identity, "chapter_id")
    if len(logical_hash) != 64 or any(char not in "0123456789abcdef" for char in logical_hash):
        raise ValueError("logical_hash must be a lowercase SHA-256 hex digest")
    if extension != "json.gz":
        raise ValueError("JSON artifacts must use the json.gz extension")
    return f"novels/{safe_novel}/{kind}/{safe_identity}/{logical_hash}.{extension}"


def generation_key(novel_id: str, generation_id: str, logical_hash: str) -> str:
    safe_novel = validate_internal_novel_id(novel_id)
    safe_generation = _safe_component(generation_id, "generation_id")
    if len(logical_hash) != 64 or any(char not in "0123456789abcdef" for char in logical_hash):
        raise ValueError("logical_hash must be a lowercase SHA-256 hex digest")
    return f"novels/{safe_novel}/generations/{safe_generation}.json.gz"


def asset_key(novel_id: str, logical_hash: str, extension: str) -> str:
    safe_novel = validate_internal_novel_id(novel_id)
    if len(logical_hash) != 64 or any(char not in "0123456789abcdef" for char in logical_hash):
        raise ValueError("logical_hash must be a lowercase SHA-256 hex digest")
    safe_extension = extension.removeprefix(".").lower()
    if not safe_extension or not safe_extension.isalnum() or len(safe_extension) > 12:
        raise ValueError("asset extension must be a short alphanumeric suffix")
    return f"novels/{safe_novel}/assets/{logical_hash}.{safe_extension}"


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    """Canonical artifact bytes and the key that owns them."""

    logical_bytes: bytes
    compressed_bytes: bytes
    logical_hash: str
    key: str
    content_type: str = "application/json"
    content_encoding: str = "gzip"

    @property
    def checksum_sha256_base64(self) -> str:
        return sha256_base64(self.compressed_bytes)


def prepare_json_artifact(
    payload: Any,
    *,
    novel_id: str,
    kind: ArtifactKind,
    identity: str,
    volatile_fields: frozenset[str] = DEFAULT_VOLATILE_FIELDS,
) -> PreparedArtifact:
    logical_bytes = canonical_json_bytes(payload, volatile_fields=volatile_fields)
    logical_hash = sha256_hex(logical_bytes)
    compressed = deterministic_gzip(logical_bytes)
    return PreparedArtifact(
        logical_bytes=logical_bytes,
        compressed_bytes=compressed,
        logical_hash=logical_hash,
        key=artifact_key(novel_id, kind, identity, logical_hash),
    )
