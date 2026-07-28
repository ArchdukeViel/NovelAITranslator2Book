"""Export manifest service — storage-backend-safe observability for exports.

Manifests are compact JSON records written alongside export artifacts.
They enable export history enumeration, freshness computation, and
admin visibility without storing chapter text or provider payloads.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status values  (REQ-5)
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_DELETED = "deleted"
STATUS_LEGACY_UNKNOWN = "legacy_unknown"

FRESHNESS_FRESH = "fresh"
FRESHNESS_STALE = "stale"
FRESHNESS_MISSING = "missing"
FRESHNESS_UNKNOWN = "unknown"
FRESHNESS_ERROR = "error"

_VALID_STATUSES = {
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
    STATUS_DELETED,
    STATUS_LEGACY_UNKNOWN,
}

# ---------------------------------------------------------------------------
# Failure codes  (REQ-6)
# ---------------------------------------------------------------------------

FAILURE_MISSING_TRANSLATION = "missing_translation"
FAILURE_MISSING_ASSET = "missing_asset"
FAILURE_RENDER_ERROR = "render_error"
FAILURE_WRITE_ERROR = "write_error"
FAILURE_VERIFY_ERROR = "verify_error"
FAILURE_STORAGE_ERROR = "storage_error"
FAILURE_INVALID_OPTIONS = "invalid_options"
FAILURE_UNKNOWN = "unknown"


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def compute_export_input_metadata(
    storage: StorageService,
    novel_id: str,
    export_format: str,
    *,
    export_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = storage.load_metadata(novel_id)
    if not isinstance(metadata, dict):
        raise LookupError("novel metadata unavailable")

    chapters = metadata.get("chapters")
    if not isinstance(chapters, list):
        raise LookupError("chapter metadata unavailable")

    chapter_rows: list[tuple[str, str]] = []
    translation_rows: list[tuple[str, str, str]] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id") or "")
        if not chapter_id:
            continue
        chapter_rows.append((chapter_id, str(chapter.get("title") or "")))
        translated = storage.load_translated_chapter(novel_id, chapter_id)
        if isinstance(translated, dict) and isinstance(translated.get("text"), str):
            translation_rows.append(
                (chapter_id, str(translated.get("version_id") or ""), _compute_hash(translated["text"]))
            )

    return {
        "chapter_set_hash": _compute_hash(json.dumps(chapter_rows, ensure_ascii=False, separators=(",", ":"))),
        "translation_version_count": len(translation_rows),
        "translation_versions_hash": _compute_hash(
            json.dumps(translation_rows, ensure_ascii=False, separators=(",", ":"))
        ),
        "glossary_revision": metadata.get("glossary_revision"),
        "glossary_hash": metadata.get("glossary_hash"),
        "novel_updated_at": metadata.get("updated_at"),
        "export_template_version": export_format,
        "export_profile_hash": _compute_hash(
            json.dumps(export_options or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        ),
    }


# ---------------------------------------------------------------------------
# Manifest schema  (REQ-3)
# ---------------------------------------------------------------------------


def build_manifest(
    *,
    novel_id: str,
    export_format: str,
    status: str = STATUS_PENDING,
    output_filename: str | None = None,
    artifact_key: str | None = None,
    chapter_count: int | None = None,
    source_chapter_count: int | None = None,
    file_size_bytes: int | None = None,
    checksum: str | None = None,
    glossary_revision: int | None = None,
    glossary_hash: str | None = None,
    translation_version_count: int | None = None,
    translation_versions_hash: str | None = None,
    chapter_set_hash: str | None = None,
    novel_updated_at: str | None = None,
    export_template_version: str | None = None,
    export_profile_hash: str | None = None,
    export_options: dict[str, Any] | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
    previous_manifest_key: str | None = None,
) -> dict[str, Any]:
    """Build a compact export manifest dict.

    All keys are storage-backend-safe — no absolute paths, no credentials.
    """
    now = _utc_now_iso()
    export_id = _compute_hash(f"{novel_id}:{export_format}:{now}")

    manifest: dict[str, Any] = {
        "export_id": export_id,
        "novel_id": novel_id,
        "format": export_format,
        "status": status,
        "created_at": now,
        "manifest_key": _manifest_key(novel_id, export_format, export_id),
        "artifact_key": artifact_key or _artifact_key(novel_id, export_format, export_id),
    }

    if output_filename is not None:
        manifest["output_filename"] = output_filename
    if chapter_count is not None:
        manifest["chapter_count"] = chapter_count
    if source_chapter_count is not None:
        manifest["source_chapter_count"] = source_chapter_count
    if file_size_bytes is not None:
        manifest["file_size_bytes"] = file_size_bytes
    if checksum is not None:
        manifest["checksum"] = checksum
    if glossary_revision is not None:
        manifest["glossary_revision"] = glossary_revision
    if glossary_hash is not None:
        manifest["glossary_hash"] = glossary_hash
    if translation_version_count is not None:
        manifest["translation_version_count"] = translation_version_count
    if translation_versions_hash is not None:
        manifest["translation_versions_hash"] = translation_versions_hash
    if chapter_set_hash is not None:
        manifest["chapter_set_hash"] = chapter_set_hash
    if novel_updated_at is not None:
        manifest["novel_updated_at"] = novel_updated_at
    if export_template_version is not None:
        manifest["export_template_version"] = export_template_version
    if export_profile_hash is not None:
        manifest["export_profile_hash"] = export_profile_hash
    if export_options is not None:
        manifest["export_options"] = export_options
    if failure_code is not None:
        manifest["failure_code"] = failure_code
    if failure_message is not None:
        manifest["failure_message"] = failure_message
    if status == STATUS_SUCCEEDED:
        manifest["completed_at"] = now
        manifest["freshness_status"] = "fresh"
        manifest["freshness_checked_at"] = now
        manifest["freshness_stale_reason"] = None
    if status == STATUS_FAILED:
        manifest["failed_at"] = now
    if previous_manifest_key is not None:
        manifest["previous_manifest_key"] = previous_manifest_key

    return manifest


# ---------------------------------------------------------------------------
# Storage-safe key helpers  (REQ-2)
# ---------------------------------------------------------------------------


def _safe_id(value: str) -> str:
    """Sanitize an ID for use in storage keys."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in value)


def _manifest_key(novel_id: str, export_format: str, export_id: str) -> str:
    return f"exports/{_safe_id(novel_id)}/{_safe_id(export_format)}/{_safe_id(export_id)}.manifest.json"


def _artifact_key(novel_id: str, export_format: str, export_id: str) -> str:
    return f"exports/{_safe_id(novel_id)}/{_safe_id(export_format)}/{_safe_id(export_id)}.{_safe_id(export_format)}"


# ---------------------------------------------------------------------------
# Storage helpers  (REQ-7)
# ---------------------------------------------------------------------------


def _exports_dir(storage: StorageService, novel_id: str) -> Path:
    return storage._novel_dir(novel_id) / "exports"


def write_manifest(storage: StorageService, novel_id: str, manifest: dict[str, Any]) -> Path:
    """Write an export manifest through the configured storage backend."""
    exports = _exports_dir(storage, novel_id)
    path = exports / f"{manifest['export_id']}.manifest.json"
    storage._write_json_atomic(path, manifest)
    return path


def read_manifest(storage: StorageService, novel_id: str, export_id: str) -> dict[str, Any] | None:
    """Read an export manifest through the configured storage backend."""
    path = _exports_dir(storage, novel_id) / f"{_safe_id(export_id)}.manifest.json"
    if not storage._path_exists(path):
        return None
    try:
        loaded = json.loads(storage._read_text(path))
    except (json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def list_manifests(storage: StorageService, novel_id: str) -> list[dict[str, Any]]:
    """List all export manifests for a novel, newest first."""
    exports = _exports_dir(storage, novel_id)
    if not storage._is_dir_present(exports):
        return []
    manifests: list[dict[str, Any]] = []
    for path in sorted(storage._glob(exports, "*.manifest.json"), reverse=True):
        try:
            loaded = json.loads(storage._read_text(path))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(loaded, dict):
            manifests.append(loaded)
    return manifests


def latest_export(storage: StorageService, novel_id: str, export_format: str) -> dict[str, Any] | None:
    """Get the most recent SUCCEEDED export for a given format."""
    for m in list_manifests(storage, novel_id):
        if m.get("format") == export_format and m.get("status") == STATUS_SUCCEEDED:
            return m
    return None


# ---------------------------------------------------------------------------
# Freshness computation  (REQ-9)
# ---------------------------------------------------------------------------


_FRESHNESS_FIELDS = (
    ("translation_versions_hash", "translation_changed"),
    ("chapter_set_hash", "chapter_order_changed"),
    ("novel_updated_at", "novel_metadata_changed"),
    ("glossary_revision", "glossary_changed"),
    ("glossary_hash", "glossary_changed"),
    ("export_template_version", "export_template_changed"),
    ("export_profile_hash", "export_profile_changed"),
)


def compute_export_freshness(
    manifest: dict[str, Any],
    current_metadata: dict[str, Any],
) -> tuple[str, str | None]:
    comparable = False
    for field, reason in _FRESHNESS_FIELDS:
        recorded = manifest.get(field)
        if recorded is None:
            continue
        current = current_metadata.get(field)
        if current is None:
            return FRESHNESS_UNKNOWN, None
        comparable = True
        if recorded != current:
            return FRESHNESS_STALE, reason
    if not comparable:
        return FRESHNESS_UNKNOWN, None
    return FRESHNESS_FRESH, None


# ---------------------------------------------------------------------------
# Scheduled freshness check  (DEBT-033)
# ---------------------------------------------------------------------------


def _artifact_exists(storage: StorageService, novel_id: str, manifest: dict[str, Any]) -> bool:
    artifact_key = manifest.get("artifact_key")
    if isinstance(artifact_key, str) and artifact_key.strip():
        return storage._path_exists(storage.base_dir / artifact_key)
    output_filename = manifest.get("output_filename")
    if isinstance(output_filename, str) and output_filename.strip():
        return storage._path_exists(storage._novel_dir(novel_id) / output_filename)
    return False


def _run_status_path(storage: StorageService) -> Path:
    return storage.base_dir / "runtime" / "export_freshness_status.json"


def load_export_freshness_status(storage: StorageService) -> dict[str, Any]:
    path = _run_status_path(storage)
    if not storage._path_exists(path):
        return {"status": "never_run", "summary": {}}
    try:
        loaded = json.loads(storage._read_text(path))
    except (json.JSONDecodeError, OSError):
        return {"status": "unknown", "summary": {}}
    return loaded if isinstance(loaded, dict) else {"status": "unknown", "summary": {}}


def run_export_freshness_check(
    storage: StorageService,
    *,
    batch_size: int = 100,
    max_artifacts: int = 1000,
) -> dict[str, Any]:
    """Scan and persist export freshness with bounded work and locking."""
    from novelai.storage.file_lock import InterProcessFileLock

    started_at = datetime.now(UTC)
    summary = {
        "scanned": 0,
        "fresh": 0,
        "stale": 0,
        "missing": 0,
        "unknown": 0,
        "error": 0,
        "skipped_locked": 0,
    }
    lock_path = storage.base_dir / "runtime" / "export_freshness.lock"
    try:
        lock = InterProcessFileLock(lock_path)
        lock.acquire()
    except TimeoutError:
        summary["skipped_locked"] = 1
        result = {
            "status": "skipped_locked",
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "summary": summary,
        }
        storage._write_json_atomic(_run_status_path(storage), result)
        return result

    try:
        processed = 0
        for novel_id in storage.list_novels():
            if processed >= max_artifacts:
                break
            candidates = [m for m in list_manifests(storage, novel_id) if m.get("status") == STATUS_SUCCEEDED]
            for offset in range(0, len(candidates), max(1, batch_size)):
                for manifest in candidates[offset : offset + max(1, batch_size)]:
                    if processed >= max_artifacts:
                        break
                    processed += 1
                    summary["scanned"] += 1
                    checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                    try:
                        if not _artifact_exists(storage, novel_id, manifest):
                            status, reason = FRESHNESS_MISSING, "artifact_missing"
                        else:
                            current_metadata = compute_export_input_metadata(
                                storage,
                                novel_id,
                                str(manifest.get("format") or ""),
                                export_options=manifest.get("export_options")
                                if isinstance(manifest.get("export_options"), dict)
                                else None,
                            )
                            status, reason = compute_export_freshness(manifest, current_metadata)
                        manifest["freshness_status"] = status
                        manifest["freshness_checked_at"] = checked_at
                        manifest["freshness_stale_reason"] = reason
                        manifest.pop("freshness_error_message", None)
                        write_manifest(storage, novel_id, manifest)
                        summary[status] += 1
                    except Exception as exc:
                        summary["error"] += 1
                        manifest["freshness_status"] = "error"
                        manifest["freshness_checked_at"] = checked_at
                        manifest["freshness_stale_reason"] = "storage_error"
                        manifest["freshness_error_message"] = exc.__class__.__name__
                        with contextlib.suppress(Exception):
                            write_manifest(storage, novel_id, manifest)
                        logger.warning(
                            "Export freshness check failed novel_id=%s export_id=%s type=%s",
                            novel_id,
                            manifest.get("export_id"),
                            exc.__class__.__name__,
                        )
                if processed >= max_artifacts:
                    break
        status = "partially_succeeded" if summary["error"] else "succeeded"
    except Exception as exc:
        logger.warning("Export freshness scan failed type=%s", exc.__class__.__name__)
        status = "failed"
        summary["error"] += 1
    finally:
        lock.release()

    finished_at = datetime.now(UTC)
    result = {
        "status": status,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "duration_ms": max(0, int((finished_at - started_at).total_seconds() * 1000)),
        "summary": summary,
    }
    storage._write_json_atomic(_run_status_path(storage), result)
    return result
