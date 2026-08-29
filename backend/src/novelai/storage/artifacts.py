"""Canonical immutable artifact repository for the application R2 bucket."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from typing import Any, Literal

from novelai.storage.backends.r2 import ImmutableWriteResult, R2Storage
from novelai.storage.content_addressing import asset_key, generation_key, prepare_json_artifact, sha256_hex

ArtifactKind = Literal["chapters", "translations", "media", "generations"]


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    key: str
    logical_sha256: str
    size_bytes: int
    created: bool


class R2ArtifactRepository:
    """Small policy layer above R2Storage.

    This class owns key construction and immutable JSON metadata. It never
    lists an object prefix; callers must provide exact keys for reads.
    """

    def __init__(self, storage: R2Storage) -> None:
        self.storage = storage

    def put_json(
        self,
        *,
        storage_novel_id: str,
        kind: ArtifactKind,
        identity: str,
        payload: Any,
    ) -> StoredArtifact:
        artifact = prepare_json_artifact(
            payload,
            novel_id=storage_novel_id,
            kind=kind,
            identity=identity,
        )
        result = self.storage.put_immutable(
            artifact.key,
            artifact.compressed_bytes,
            logical_sha256=artifact.logical_hash,
            content_type=artifact.content_type,
            content_encoding=artifact.content_encoding,
        )
        return self._stored(result)

    def put_generation_manifest(
        self,
        *,
        storage_novel_id: str,
        generation_id: str,
        payload: Any,
    ) -> StoredArtifact:
        artifact = prepare_json_artifact(
            payload,
            novel_id=storage_novel_id,
            kind="generations",
            identity=generation_id,
        )
        # Generation keys intentionally omit the manifest hash so a generation
        # ID is addressable exactly once; the manifest contains its own hash.
        key = generation_key(storage_novel_id, generation_id, artifact.logical_hash)
        result = self.storage.put_immutable(
            key,
            artifact.compressed_bytes,
            logical_sha256=artifact.logical_hash,
            content_type=artifact.content_type,
            content_encoding=artifact.content_encoding,
        )
        return self._stored(result)

    def put_asset(self, *, storage_novel_id: str, content: bytes, extension: str) -> StoredArtifact:
        digest = sha256_hex(content)
        key = asset_key(storage_novel_id, digest, extension)
        result = self.storage.put_immutable(
            key,
            content,
            logical_sha256=digest,
            content_type="application/octet-stream",
            content_encoding=None,
        )
        return self._stored(result)

    def load_json(self, key: str) -> dict[str, Any]:
        compressed = self.storage.load(key)
        try:
            payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("R2 JSON artifact is corrupt") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("R2 JSON artifact must contain an object")
        return payload

    @staticmethod
    def _stored(result: ImmutableWriteResult) -> StoredArtifact:
        return StoredArtifact(
            key=result.key,
            logical_sha256=result.logical_sha256,
            size_bytes=result.size_bytes,
            created=result.created,
        )
