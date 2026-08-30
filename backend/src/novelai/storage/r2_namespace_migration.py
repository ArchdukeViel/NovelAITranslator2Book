"""One-time migration from mutable slug R2 prefixes to immutable novel IDs."""

from __future__ import annotations

import copy
import gzip
import json
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.storage.backends.base import R2StorageBackend
from novelai.storage.backends.r2_gateway import R2ObjectMetadata
from novelai.storage.content_addressing import (
    ArtifactKind,
    artifact_key,
    canonical_json_bytes,
    deterministic_gzip,
    generation_key,
    sha256_hex,
    validate_internal_novel_id,
)

_ARTIFACT_KINDS = frozenset({"chapters", "translations", "media"})
_MAX_REWRITE_ROUNDS = 12


@dataclass(frozen=True, slots=True)
class R2NamespaceMigrationResult:
    """Evidence for one source-slug to internal-ID namespace migration."""

    novel_slug: str
    storage_novel_id: str
    source_prefix: str
    target_prefix: str
    dry_run: bool
    source_keys: tuple[str, ...]
    destination_keys: tuple[str, ...]
    json_objects: int
    asset_objects: int
    changed_database_references: int
    deleted_source_objects: int = 0


@dataclass(frozen=True, slots=True)
class _ObjectRecord:
    old_key: str
    kind: str
    identity: str
    payload: dict[str, Any] | None
    data: bytes
    metadata: R2ObjectMetadata


def _rewrite_value(value: Any, mapping: dict[str, str], source_prefix: str, target_prefix: str) -> Any:
    """Rewrite exact object keys recursively without changing ordinary text."""

    if isinstance(value, dict):
        return {key: _rewrite_value(item, mapping, source_prefix, target_prefix) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_value(item, mapping, source_prefix, target_prefix) for item in value]
    if not isinstance(value, str):
        return value
    if value in mapping:
        return mapping[value]
    source_object_prefix = f"{source_prefix}/"
    if value.startswith(source_object_prefix):
        return f"{target_prefix}/{value[len(source_object_prefix) :]}"
    return value


def _artifact_hash_from_key(key: str) -> str | None:
    filename = key.rsplit("/", 1)[-1]
    if not filename.endswith(".json.gz"):
        return None
    digest = filename[: -len(".json.gz")]
    if len(digest) == 64 and all(character in "0123456789abcdef" for character in digest):
        return digest
    return None


def _rewrite_manifest_hashes(payload: dict[str, Any], content_hash_mapping: dict[str, str]) -> None:
    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        return
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        for storage_field in ("raw_storage_key", "translated_storage_key", "media_storage_key"):
            key = chapter.get(storage_field)
            if not isinstance(key, str):
                continue
            hash_field = storage_field.removesuffix("_storage_key") + "_content_hash"
            current_hash = chapter.get(hash_field)
            destination_hash = _artifact_hash_from_key(key)
            if isinstance(current_hash, str) and current_hash in content_hash_mapping:
                destination_hash = content_hash_mapping[current_hash]
            if destination_hash is not None:
                chapter[hash_field] = destination_hash


def _rewrite_content_hash_fields(value: Any, content_hash_mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        rewritten = {key: _rewrite_content_hash_fields(item, content_hash_mapping) for key, item in value.items()}
        for storage_field in ("raw_storage_key", "translated_storage_key", "media_storage_key", "storage_key"):
            key = rewritten.get(storage_field)
            if not isinstance(key, str):
                continue
            hash_field = (
                "content_hash"
                if storage_field == "storage_key"
                else storage_field.removesuffix("_storage_key") + "_content_hash"
            )
            key_hash = _artifact_hash_from_key(key)
            if key_hash is not None:
                rewritten[hash_field] = key_hash
            elif isinstance(rewritten.get(hash_field), str):
                rewritten[hash_field] = content_hash_mapping.get(rewritten[hash_field], rewritten[hash_field])
        return rewritten
    if isinstance(value, list):
        return [_rewrite_content_hash_fields(item, content_hash_mapping) for item in value]
    return value


def _load_json_payload(storage: R2StorageBackend, key: str) -> dict[str, Any]:
    try:
        payload = json.loads(gzip.decompress(storage.load(key)).decode("utf-8"))
    except (FileNotFoundError, OSError, gzip.BadGzipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"R2 namespace migration found an invalid JSON artifact: {key}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"R2 namespace migration requires object JSON artifacts: {key}")
    return payload


def _parse_record(storage: R2StorageBackend, key: str, source_prefix: str) -> _ObjectRecord:
    prefix = f"{source_prefix}/"
    if not key.startswith(prefix):
        raise RuntimeError(f"R2 key is outside the requested namespace: {key}")
    suffix = key[len(prefix) :]
    parts = suffix.split("/")
    if len(parts) == 3 and parts[0] in _ARTIFACT_KINDS and parts[2].endswith(".json.gz"):
        kind = parts[0]
        identity = parts[1]
        payload = _load_json_payload(storage, key)
    elif len(parts) == 2 and parts[0] == "generations" and parts[1].endswith(".json.gz"):
        kind = "generations"
        identity = parts[1][: -len(".json.gz")]
        payload = _load_json_payload(storage, key)
    elif len(parts) == 2 and parts[0] == "assets" and "." in parts[1]:
        kind = "assets"
        identity = parts[1]
        payload = None
    else:
        raise RuntimeError(f"R2 namespace migration found an unsupported object key: {key}")
    return _ObjectRecord(
        old_key=key,
        kind=kind,
        identity=identity,
        payload=payload,
        data=storage.load(key),
        metadata=storage.head(key),
    )


def _initial_mapping(
    records: list[_ObjectRecord],
    *,
    source_prefix: str,
    target_prefix: str,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for record in records:
        if record.kind == "assets":
            extension = record.identity.rsplit(".", 1)[-1].lower()
            digest = sha256_hex(record.data)
            mapping[record.old_key] = f"{target_prefix}/assets/{digest}.{extension}"
        else:
            mapping[record.old_key] = f"{target_prefix}/{record.old_key[len(source_prefix) + 1 :]}"
    return mapping


def _render_json_record(
    record: _ObjectRecord,
    mapping: dict[str, str],
    *,
    source_prefix: str,
    target_prefix: str,
    storage_novel_id: str,
    novel_slug: str,
    content_hash_mapping: dict[str, str] | None = None,
) -> tuple[str, bytes, str]:
    if record.payload is None:
        raise RuntimeError(f"R2 namespace migration expected JSON payload: {record.old_key}")
    payload = _rewrite_value(copy.deepcopy(record.payload), mapping, source_prefix, target_prefix)
    if record.kind == "generations":
        # Generation manifests written before the internal-ID contract used
        # the source slug as their identity. Normalize that contract while
        # preserving the public slug for diagnostics and future activation.
        if payload.get("novel_id") == novel_slug:
            payload["novel_id"] = storage_novel_id
        payload.setdefault("public_slug", novel_slug)
        _rewrite_manifest_hashes(payload, content_hash_mapping or {})
    logical_bytes = canonical_json_bytes(payload)
    logical_hash = sha256_hex(logical_bytes)
    compressed = deterministic_gzip(logical_bytes)
    if record.kind == "generations":
        destination = generation_key(storage_novel_id, record.identity, logical_hash)
    else:
        kind = cast(ArtifactKind, record.kind)
        destination = artifact_key(storage_novel_id, kind, record.identity, logical_hash)
    return destination, compressed, logical_hash


def _count_changed_references(
    novel: Novel,
    chapters: list[Chapter],
    mapping: dict[str, str],
    *,
    source_prefix: str,
    target_prefix: str,
) -> int:
    changed = 0
    for field in ("active_generation_storage_key", "cover_storage_key"):
        value = getattr(novel, field)
        if isinstance(value, str) and value in mapping:
            changed += 1
    for field in ("metadata_json", "metadata_history_json", "source_state_json"):
        value = getattr(novel, field)
        if value is not None and _rewrite_value(value, mapping, source_prefix, target_prefix) != value:
            changed += 1
    for chapter in chapters:
        for field, hash_field in (
            ("raw_storage_key", "raw_content_hash"),
            ("translated_storage_key", "translated_content_hash"),
            ("media_storage_key", "media_content_hash"),
        ):
            value = getattr(chapter, field)
            if isinstance(value, str) and value in mapping:
                changed += 1
            content_hash = getattr(chapter, hash_field)
            destination_hash = (
                _artifact_hash_from_key(mapping[value]) if isinstance(value, str) and value in mapping else None
            )
            if destination_hash is not None and content_hash != destination_hash:
                changed += 1
        for field in ("media_state_json", "translation_versions_json", "translation_edit_history_json"):
            value = getattr(chapter, field)
            if value is not None and _rewrite_value(value, mapping, source_prefix, target_prefix) != value:
                changed += 1
    return changed


def _rewrite_db_references(
    novel: Novel,
    chapters: list[Chapter],
    mapping: dict[str, str],
    *,
    source_prefix: str,
    target_prefix: str,
    content_hash_mapping: dict[str, str],
) -> int:
    changed = 0

    def rewrite_field(owner: Any, field: str) -> None:
        nonlocal changed
        current = getattr(owner, field)
        rewritten = _rewrite_value(current, mapping, source_prefix, target_prefix)
        rewritten = _rewrite_content_hash_fields(rewritten, content_hash_mapping)
        if rewritten != current:
            setattr(owner, field, rewritten)
            changed += 1

    for field in ("active_generation_storage_key", "cover_storage_key"):
        rewrite_field(novel, field)
    for field in ("metadata_json", "metadata_history_json", "source_state_json"):
        rewrite_field(novel, field)
    for chapter in chapters:
        for field, hash_field in (
            ("raw_storage_key", "raw_content_hash"),
            ("translated_storage_key", "translated_content_hash"),
            ("media_storage_key", "media_content_hash"),
        ):
            rewrite_field(chapter, field)
            storage_key = getattr(chapter, field)
            destination_hash = _artifact_hash_from_key(storage_key) if isinstance(storage_key, str) else None
            if destination_hash is not None and getattr(chapter, hash_field) != destination_hash:
                setattr(chapter, hash_field, destination_hash)
                changed += 1
        for field in ("media_state_json", "translation_versions_json", "translation_edit_history_json"):
            rewrite_field(chapter, field)
    return changed


class R2NovelNamespaceMigrator:
    """Rekey one or more slug namespaces with dry-run and commit separation."""

    def __init__(self, *, storage: R2StorageBackend, db_session: Session) -> None:
        self.storage = storage
        self.db_session = db_session

    def migrate_novel(self, novel_slug: str, *, dry_run: bool = True) -> R2NamespaceMigrationResult:
        novel = self.db_session.query(Novel).filter(Novel.slug == novel_slug).one_or_none()
        if novel is None or novel.id is None:
            raise ValueError(f"Novel does not exist: {novel_slug}")
        storage_novel_id = validate_internal_novel_id(novel.id)
        source_prefix = f"novels/{novel_slug.strip('/')}"
        target_prefix = f"novels/{storage_novel_id}"
        if source_prefix == target_prefix:
            return R2NamespaceMigrationResult(
                novel_slug=novel_slug,
                storage_novel_id=storage_novel_id,
                source_prefix=source_prefix,
                target_prefix=target_prefix,
                dry_run=dry_run,
                source_keys=(),
                destination_keys=(),
                json_objects=0,
                asset_objects=0,
                changed_database_references=0,
            )

        source_keys = tuple(sorted(self.storage.list_keys(source_prefix, recursive=True)))
        if not source_keys:
            return R2NamespaceMigrationResult(
                novel_slug=novel_slug,
                storage_novel_id=storage_novel_id,
                source_prefix=source_prefix,
                target_prefix=target_prefix,
                dry_run=dry_run,
                source_keys=(),
                destination_keys=(),
                json_objects=0,
                asset_objects=0,
                changed_database_references=0,
            )

        records = [_parse_record(self.storage, key, source_prefix) for key in source_keys]
        mapping = _initial_mapping(records, source_prefix=source_prefix, target_prefix=target_prefix)
        json_records = [record for record in records if record.payload is not None]
        for _ in range(_MAX_REWRITE_ROUNDS):
            changed = False
            for record in json_records:
                destination, _, _ = _render_json_record(
                    record,
                    mapping,
                    source_prefix=source_prefix,
                    target_prefix=target_prefix,
                    storage_novel_id=storage_novel_id,
                    novel_slug=novel_slug,
                )
                if mapping[record.old_key] != destination:
                    mapping[record.old_key] = destination
                    changed = True
            if not changed:
                break
        else:
            raise RuntimeError(f"R2 namespace migration did not converge for {novel_slug}")

        chapters = self.db_session.query(Chapter).filter(Chapter.novel_id == novel.id).all()
        content_hash_mapping: dict[str, str] = {}
        for record in records:
            if record.payload is None or record.kind == "generations" or record.metadata.logical_sha256 is None:
                continue
            destination_hash = _artifact_hash_from_key(mapping[record.old_key])
            if destination_hash is not None:
                content_hash_mapping[record.metadata.logical_sha256] = destination_hash
        changed_references = _count_changed_references(
            novel,
            chapters,
            mapping,
            source_prefix=source_prefix,
            target_prefix=target_prefix,
        )
        destination_keys = tuple(sorted(set(mapping.values())))
        if not dry_run:
            for record in records:
                destination = mapping[record.old_key]
                if record.payload is None:
                    logical_hash = sha256_hex(record.data)
                    self.storage.put_immutable(
                        destination,
                        record.data,
                        logical_sha256=logical_hash,
                        content_type=record.metadata.content_type or "application/octet-stream",
                        content_encoding=record.metadata.content_encoding,
                    )
                else:
                    rendered_destination, compressed, logical_hash = _render_json_record(
                        record,
                        mapping,
                        source_prefix=source_prefix,
                        target_prefix=target_prefix,
                        storage_novel_id=storage_novel_id,
                        novel_slug=novel_slug,
                        content_hash_mapping=content_hash_mapping,
                    )
                    if rendered_destination != destination:
                        raise RuntimeError(f"R2 namespace mapping changed during verification: {record.old_key}")
                    self.storage.put_immutable(
                        destination,
                        compressed,
                        logical_sha256=logical_hash,
                        content_type=record.metadata.content_type or "application/json",
                        content_encoding="gzip",
                    )
                metadata = self.storage.head(destination)
                if metadata.size_bytes <= 0:
                    raise RuntimeError(f"R2 namespace migration wrote an empty destination: {destination}")
            changed_references = _rewrite_db_references(
                novel,
                chapters,
                mapping,
                source_prefix=source_prefix,
                target_prefix=target_prefix,
                content_hash_mapping=content_hash_mapping,
            )
            self.db_session.add(novel)
            self.db_session.add_all(chapters)
            self.db_session.flush()

        return R2NamespaceMigrationResult(
            novel_slug=novel_slug,
            storage_novel_id=storage_novel_id,
            source_prefix=source_prefix,
            target_prefix=target_prefix,
            dry_run=dry_run,
            source_keys=source_keys,
            destination_keys=destination_keys,
            json_objects=len(json_records),
            asset_objects=len(records) - len(json_records),
            changed_database_references=changed_references,
        )


def delete_migrated_source_namespace(storage: R2StorageBackend, result: R2NamespaceMigrationResult) -> int:
    """Delete old objects only after the caller has committed PostgreSQL."""

    if result.dry_run:
        raise ValueError("Cannot finalize a dry-run namespace migration")
    remaining = tuple(sorted(storage.list_keys(result.source_prefix, recursive=True)))
    if remaining != result.source_keys:
        raise RuntimeError("R2 source namespace changed; refusing to delete unverified objects")
    return storage.delete_prefix(result.source_prefix)
