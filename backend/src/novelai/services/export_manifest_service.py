"""Export manifest service — storage-backend-safe observability for exports.

Manifests are compact JSON records written alongside export artifacts.
They enable export history enumeration, freshness computation, and
admin visibility without storing chapter text or provider payloads.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.storage.service import StorageService

# ---------------------------------------------------------------------------
# Status values  (REQ-5)
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_DELETED = "deleted"
STATUS_LEGACY_UNKNOWN = "legacy_unknown"

_VALID_STATUSES = {
    STATUS_PENDING, STATUS_RUNNING, STATUS_SUCCEEDED,
    STATUS_FAILED, STATUS_DELETED, STATUS_LEGACY_UNKNOWN,
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
    novel_updated_at: str | None = None,
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
    if novel_updated_at is not None:
        manifest["novel_updated_at"] = novel_updated_at
    if export_options is not None:
        manifest["export_options"] = export_options
    if failure_code is not None:
        manifest["failure_code"] = failure_code
    if failure_message is not None:
        manifest["failure_message"] = failure_message
    if status == STATUS_SUCCEEDED:
        manifest["completed_at"] = now
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
    """Write an export manifest through the storage backend."""
    exports = _exports_dir(storage, novel_id)
    path = exports / f"{manifest['export_id']}.manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_manifest(storage: StorageService, novel_id: str, export_id: str) -> dict[str, Any] | None:
    """Read an export manifest."""
    path = _exports_dir(storage, novel_id) / f"{_safe_id(export_id)}.manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_manifests(storage: StorageService, novel_id: str) -> list[dict[str, Any]]:
    """List all export manifests for a novel, newest first."""
    exports = _exports_dir(storage, novel_id)
    if not exports.exists():
        return []
    manifests: list[dict[str, Any]] = []
    for path in sorted(exports.glob("*.manifest.json"), reverse=True):
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
            manifests.append(m)
        except (json.JSONDecodeError, OSError):
            continue
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


def compute_export_freshness(
    storage: StorageService,
    novel_id: str,
    manifest: dict[str, Any],
    current_glossary_revision: int | None = None,
    current_novel_updated_at: str | None = None,
) -> str:
    """Compute whether an export is up-to-date.

    Returns one of:
    - ``stale`` — input state has changed since export
    - ``current`` — input state matches
    - ``unknown_legacy_manifest`` — manifest has no input state to compare
    - ``current_state_unavailable`` — cannot resolve current input state
    """
    if not manifest.get("glossary_revision") and not manifest.get("novel_updated_at"):
        return "unknown_legacy_manifest"

    if current_glossary_revision is not None and manifest.get("glossary_revision") is not None:
        if manifest["glossary_revision"] != current_glossary_revision:
            return "stale"

    if current_novel_updated_at is not None and manifest.get("novel_updated_at") is not None:
        if manifest["novel_updated_at"] != current_novel_updated_at:
            return "stale"

    return "current"
