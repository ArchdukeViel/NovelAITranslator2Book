from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState, ChapterStateTransition
from novelai.core.platform import ChapterVersionKind
from novelai.storage.chapters import (
    _chapter_dir,
    _chapter_path,
    _load_chapter_bundle,
    _load_legacy_raw_chapter,
    _load_legacy_translated_chapter,
    _persist_chapter_bundle,
    count_stored_chapters,
    existing_chapter_hash,
    get_chapter_progress,
    get_chapters_by_state,
    get_chapters_with_errors,
    get_scraping_progress,
    list_stored_chapters,
    load_chapter,
    query_chapters,
    save_chapter,
)
from novelai.storage.exports import build_export_path, get_chapters_ready_for_export
from novelai.storage.glossary import load_glossary, save_glossary
from novelai.storage.jobs import (
    _get_checkpoints_dir,
    _get_state_dir,
    create_checkpoint,
    list_checkpoints,
    load_chapter_state,
    restore_from_checkpoint,
    rollback_to_state,
    save_chapter_state,
    update_chapter_state,
)
from novelai.storage.media import (
    _asset_relative_path,
    _chapter_image_dir,
    _guess_asset_suffix,
    _normalize_media_fields,
    clear_chapter_image_assets,
    load_chapter_export_images,
    load_chapter_media_state,
    resolve_asset_path,
    save_chapter_image_asset,
    save_chapter_media_state,
)
from novelai.storage.novels import (
    _backup_metadata_file,
    _compute_folder_name,
    _ensure_novel_dir,
    _folder_has_novel_data,
    _folder_in_use_by_other_novel,
    _folder_path,
    _get_folder_name,
    _index_path,
    _legacy_folder_candidates,
    _load_index,
    _load_latest_valid_metadata_backup,
    _metadata_backup_dir,
    _metadata_history_entry,
    _normalize_library_novel_id,
    _normalize_loaded_metadata,
    _novel_dir,
    _persist_index,
    _recover_metadata_from_backup,
    _validate_folder_name,
    delete_novel,
    list_metadata_history,
    list_novels,
    load_metadata,
    load_metadata_snapshot,
    resolve_onboarding_status,
    save_metadata,
    update_onboarding_status,
)
from novelai.storage.runtime_contracts import (
    _fetch_cache_dir,
    _runtime_dir,
    _translation_runtime_dir,
    cleanup_expired_runtime_data,
    cleanup_fetch_cache,
    cleanup_pipeline_events,
    delete_translation_bundle,
    fetch_cache_conditional_headers,
    list_chunk_attempt_records,
    list_provider_request_records,
    read_fetch_cache_entry,
    read_translation_bundle,
    read_translation_chunks,
    read_translation_output,
    save_chunk_attempt_record,
    save_fetch_cache_entry,
    save_provider_request_record,
    save_translation_bundle,
    save_translation_chunks,
    save_translation_output,
    update_translation_chunk_status,
)
from novelai.storage.traceability import (
    _read_json_file,
    _trace_dir,
    append_pipeline_event,
    append_pipeline_events,
    list_pipeline_events,
    load_chunk_states,
    load_scheduler_state,
    save_scheduler_state,
    upsert_chunk_state,
)
from novelai.storage.translations import (
    _active_translation_version,
    _append_edit_history,
    _set_active_translation_version,
    _translated_payload_to_version,
    _translation_versions_from_payload,
    activate_translated_chapter_version,
    count_translated_chapters,
    list_translated_chapter_versions,
    list_translated_chapters,
    load_translated_chapter,
    load_translated_chapter_by_version_id,
    load_translation_edit_history,
    save_edited_translation,
    save_translated_chapter,
)

logger = logging.getLogger(__name__)


def _fsync_directory(directory: Path) -> None:
    """Best-effort fsync of a directory so a rename is durable.

    Failures are debug-level only; directory fsync is unsupported on some
    platforms and must never break the write.
    """
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        logger.debug("Directory fsync failed for %s", directory, exc_info=True)
    finally:
        os.close(fd)


class StorageService:
    """Filesystem-backed storage service.

    The public API is kept on this compatibility class while domain
    implementations live in smaller storage modules.
    """

    INDEX_FILENAME = "index.json"
    CHAPTERS_DIRNAME = "chapters"
    SCHEMA_VERSION = 2
    OCR_STATUSES = {"pending", "reviewed", "skipped", "failed"}
    REEMBED_STATUSES = {"pending", "completed", "failed", "skipped"}

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """Create a filesystem-safe folder name from an arbitrary title."""
        name = name.strip().replace(" ", "_")
        name = re.sub(r"[^A-Za-z0-9_\-\.]+", "", name)
        return name or "novel"


    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


    @staticmethod
    def _text_paragraphs(text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []
        return [paragraph for paragraph in re.split(r"\n{2,}", normalized) if paragraph]


    @staticmethod
    def _normalize_source_blocks(blocks: Any) -> list[dict[str, Any]]:
        if not isinstance(blocks, list):
            return []

        normalized: list[dict[str, Any]] = []
        previous_type: str | None = None
        line_index = 0
        break_index = 0
        source_order = 0
        for item in blocks:
            if not isinstance(item, dict):
                continue
            block_type = item.get("type")
            if block_type == "break":
                if previous_type == "break" or not normalized:
                    continue
                break_index += 1
                source_order += 1
                normalized.append(
                    {
                        "type": "break",
                        "source_block_id": str(item.get("source_block_id") or f"b{break_index:04d}"),
                        "source_order": source_order,
                    }
                )
                previous_type = "break"
                continue
            if block_type != "line":
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            line_index += 1
            source_order += 1
            normalized.append(
                {
                    "type": "line",
                    "source_block_id": f"s{line_index:04d}",
                    "paragraph_id": f"p{line_index:04d}",
                    "text": text.strip("\n"),
                    "source_order": source_order,
                }
            )
            previous_type = "line"
        if normalized and normalized[-1].get("type") == "break":
            normalized.pop()
        return normalized


    @staticmethod
    def _clean_string(value: Any, default: str | None = None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return default


    def __init__(self, base_dir: Path | None = None, backend: Any | None = None) -> None:
        if backend is not None:
            self._backend = backend
        elif base_dir is not None:
            from novelai.storage.backends.filesystem import FilesystemBackend
            self._backend = FilesystemBackend(base_dir.resolve())
        else:
            from novelai.storage.backends import get_storage_backend
            self._backend = get_storage_backend()

        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self._backend.mkdirs(self.base_dir)

        self.novels_dir = self.base_dir / "novels"
        self._backend.mkdirs(self.novels_dir)


    # ── backend-abstracted I/O helpers ──────────────────────────────

    def _rel(self, path: Path) -> str:
        """Convert absolute Path to backend-relative key."""
        return str(path.relative_to(self.base_dir))

    def _read_text(self, path: Path) -> str:
        """Read text content via storage backend."""
        return self._backend.load(self._rel(path)).decode("utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        """Write text content via storage backend."""
        self._backend.save(self._rel(path), content.encode("utf-8"))

    def _write_text_atomic(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        """Write ``content`` to ``path`` atomically.

        Writes to a unique temp file in the same directory, flushes and fsyncs
        it, then replaces the target with ``os.replace`` so readers never see a
        partial file. Best-effort fsyncs the parent directory and removes the
        temp file on failure before the rename.

        For non-local backends (e.g. S3/R2), falls back to direct write since
        atomic rename is not supported.
        """
        backing = getattr(self._backend, "_BACKING", "filesystem")
        if backing == "s3":
            self._write_text(path, content)
            return
        self._backend.mkdirs(self._rel(path.parent))
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        replaced = False
        try:
            self._backend.save(self._rel(temp_path), content.encode(encoding))
            os.replace(temp_path, path)
            replaced = True
            _fsync_directory(path.parent)
        except Exception as exc:
            if not replaced:
                with contextlib.suppress(OSError):
                    temp_path.unlink(missing_ok=True)
                logger.warning("Atomic write failed for %s: %s", path, exc)
            raise

    def _write_json_atomic(self, path: Path, payload: Any, *, encoding: str = "utf-8") -> None:
        """Serialize ``payload`` as JSON and write it atomically."""
        self._write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding=encoding)

    def _path_exists(self, path: Path) -> bool:
        """Check existence via storage backend."""
        return self._backend.exists(self._rel(path))

    def _unlink_path(self, path: Path) -> None:
        """Delete file via storage backend."""
        self._backend.delete(self._rel(path))

    def _mkdirs(self, path: Path) -> None:
        """Create directory via storage backend."""
        self._backend.mkdirs(self._rel(path))

    def _list_dir(self, path: Path) -> list[Path]:
        """List immediate children via storage backend."""
        return sorted(self.base_dir / key for key in self._backend.list_keys(self._rel(path)))

    def _glob(self, path: Path, pattern: str) -> list[Path]:
        """List children matching glob pattern via storage backend."""
        import fnmatch

        return sorted(
            self.base_dir / key
            for key in self._backend.list_keys(self._rel(path))
            if fnmatch.fnmatch(Path(key).name, pattern)
        )

    def _rmtree(self, path: Path) -> None:
        """Remove directory tree via storage backend."""
        prefix = self._rel(path)
        for key in self._backend.list_keys(prefix):
            self._backend.delete(key)

    def runtime_path(self, *parts: str) -> Path:
        """Resolve path under runtime/ via storage base_dir.

        ponytail: returns absolute Path; direct OS ops bypass backend.
        Add backend-abstracted runtime I/O when non-filesystem backends
        are needed for runtime data.
        """
        return self.base_dir / "runtime" / Path(*parts)

    def backups_path(self, *parts: str) -> Path:
        """Resolve path under backups/ via storage base_dir."""
        return self.base_dir / "backups" / Path(*parts)

    @staticmethod
    def _normalize_image_manifest(images: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not images:
            return []

        normalized: list[dict[str, Any]] = []
        for image in images:
            if not isinstance(image, dict):
                continue
            item = dict(image)
            local_path = item.get("local_path")
            if isinstance(local_path, Path):
                item["local_path"] = local_path.as_posix()
            normalized.append(item)
        normalized.sort(key=lambda item: int(item.get("index", 0)))
        return normalized


    @staticmethod
    def _normalize_named_dict_items(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(dict(item))
        return normalized


    @staticmethod
    def _normalize_version_kind(value: Any, default: ChapterVersionKind = ChapterVersionKind.MACHINE_TRANSLATION) -> str:
        if isinstance(value, ChapterVersionKind):
            return value.value
        if isinstance(value, str) and value in {kind.value for kind in ChapterVersionKind}:
            return value
        return default.value


    @staticmethod
    def _next_translation_version_id(versions: list[dict[str, Any]]) -> str:
        used = {str(version.get("id")) for version in versions if version.get("id") is not None}
        index = len(used) + 1
        while f"v{index}" in used:
            index += 1
        return f"v{index}"


    @staticmethod
    def _next_edit_history_id(entries: list[dict[str, Any]]) -> str:
        used = {str(entry.get("id")) for entry in entries if entry.get("id") is not None}
        index = len(used) + 1
        while f"e{index}" in used:
            index += 1
        return f"e{index}"


    @staticmethod
    def _normalize_optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None


    @staticmethod
    def _serialize_checkpoint_state(state_data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert chapter state payload to JSON-safe data for checkpoints."""
        if not isinstance(state_data, dict):
            return None

        current_state_raw = state_data.get("current_state")
        if isinstance(current_state_raw, ChapterState):
            current_state = current_state_raw.value
        else:
            current_state = current_state_raw if isinstance(current_state_raw, str) else ChapterState.SCRAPED.value

        transitions: list[dict[str, Any]] = []
        for transition in state_data.get("transitions", []):
            if isinstance(transition, ChapterStateTransition):
                from_state = transition.from_state.value if transition.from_state else None
                to_state = transition.to_state.value if transition.to_state else None
                timestamp = (
                    transition.timestamp.isoformat()
                    if isinstance(transition.timestamp, datetime)
                    else transition.timestamp
                )
                error = transition.error
            elif isinstance(transition, dict):
                from_state_raw = transition.get("from_state")
                to_state_raw = transition.get("to_state")
                if isinstance(from_state_raw, ChapterState):
                    from_state = from_state_raw.value
                else:
                    from_state = from_state_raw if isinstance(from_state_raw, str) else None

                if isinstance(to_state_raw, ChapterState):
                    to_state = to_state_raw.value
                else:
                    to_state = to_state_raw if isinstance(to_state_raw, str) else None

                timestamp_raw = transition.get("timestamp")
                timestamp = timestamp_raw.isoformat() if isinstance(timestamp_raw, datetime) else timestamp_raw
                error = transition.get("error")
            else:
                continue

            transitions.append(
                {
                    "from_state": from_state,
                    "to_state": to_state,
                    "timestamp": timestamp,
                    "error": error,
                }
            )

        last_updated_raw = state_data.get("last_updated")
        last_updated = last_updated_raw.isoformat() if isinstance(last_updated_raw, datetime) else last_updated_raw

        return {
            "chapter_id": state_data.get("chapter_id"),
            "current_state": current_state,
            "transitions": transitions,
            "last_updated": last_updated,
            "error_count": int(state_data.get("error_count", 0) or 0),
            "retry_count": int(state_data.get("retry_count", 0) or 0),
        }


    # Novel metadata and folder index
    _index_path = _index_path
    _load_index = _load_index
    _persist_index = _persist_index
    _validate_folder_name = _validate_folder_name
    _normalize_library_novel_id = _normalize_library_novel_id
    _legacy_folder_candidates = _legacy_folder_candidates
    _compute_folder_name = _compute_folder_name
    _folder_in_use_by_other_novel = _folder_in_use_by_other_novel
    _get_folder_name = _get_folder_name
    _folder_path = _folder_path
    _novel_dir = _novel_dir
    _ensure_novel_dir = _ensure_novel_dir
    delete_novel = delete_novel
    save_metadata = save_metadata
    load_metadata = load_metadata
    update_onboarding_status = update_onboarding_status
    resolve_onboarding_status = resolve_onboarding_status
    _load_latest_valid_metadata_backup = _load_latest_valid_metadata_backup
    _normalize_loaded_metadata = _normalize_loaded_metadata
    _recover_metadata_from_backup = _recover_metadata_from_backup
    list_metadata_history = list_metadata_history
    load_metadata_snapshot = load_metadata_snapshot
    list_novels = list_novels
    _backup_metadata_file = _backup_metadata_file
    _metadata_history_entry = _metadata_history_entry
    _metadata_backup_dir = _metadata_backup_dir
    _folder_has_novel_data = _folder_has_novel_data
    _chapter_dir = _chapter_dir
    _chapter_path = _chapter_path
    _load_legacy_raw_chapter = _load_legacy_raw_chapter
    _load_legacy_translated_chapter = _load_legacy_translated_chapter
    _load_chapter_bundle = _load_chapter_bundle
    _persist_chapter_bundle = _persist_chapter_bundle
    existing_chapter_hash = existing_chapter_hash
    save_chapter = save_chapter
    load_chapter = load_chapter
    list_stored_chapters = list_stored_chapters
    count_stored_chapters = count_stored_chapters
    get_chapters_by_state = get_chapters_by_state
    get_chapter_progress = get_chapter_progress
    query_chapters = query_chapters
    get_chapters_with_errors = get_chapters_with_errors
    get_scraping_progress = get_scraping_progress
    _translated_payload_to_version = _translated_payload_to_version
    _translation_versions_from_payload = _translation_versions_from_payload
    _active_translation_version = _active_translation_version
    _set_active_translation_version = _set_active_translation_version
    _append_edit_history = _append_edit_history
    save_translated_chapter = save_translated_chapter
    load_translated_chapter = load_translated_chapter
    load_translated_chapter_by_version_id = load_translated_chapter_by_version_id
    list_translated_chapter_versions = list_translated_chapter_versions
    save_edited_translation = save_edited_translation
    load_translation_edit_history = load_translation_edit_history
    activate_translated_chapter_version = activate_translated_chapter_version
    list_translated_chapters = list_translated_chapters
    count_translated_chapters = count_translated_chapters
    _chapter_image_dir = _chapter_image_dir
    _asset_relative_path = _asset_relative_path
    _guess_asset_suffix = _guess_asset_suffix
    clear_chapter_image_assets = clear_chapter_image_assets
    save_chapter_image_asset = save_chapter_image_asset
    resolve_asset_path = resolve_asset_path
    load_chapter_export_images = load_chapter_export_images
    _normalize_media_fields = _normalize_media_fields
    load_chapter_media_state = load_chapter_media_state
    save_chapter_media_state = save_chapter_media_state
    _get_state_dir = _get_state_dir
    save_chapter_state = save_chapter_state
    load_chapter_state = load_chapter_state
    update_chapter_state = update_chapter_state
    _get_checkpoints_dir = _get_checkpoints_dir
    create_checkpoint = create_checkpoint
    list_checkpoints = list_checkpoints
    restore_from_checkpoint = restore_from_checkpoint
    rollback_to_state = rollback_to_state
    build_export_path = build_export_path
    get_chapters_ready_for_export = get_chapters_ready_for_export
    save_glossary = save_glossary
    load_glossary = load_glossary
    _trace_dir = _trace_dir
    _read_json_file = _read_json_file
    append_pipeline_event = append_pipeline_event
    append_pipeline_events = append_pipeline_events
    list_pipeline_events = list_pipeline_events
    upsert_chunk_state = upsert_chunk_state
    load_chunk_states = load_chunk_states
    save_scheduler_state = save_scheduler_state
    load_scheduler_state = load_scheduler_state
    _runtime_dir = _runtime_dir
    _translation_runtime_dir = _translation_runtime_dir
    _fetch_cache_dir = _fetch_cache_dir
    save_translation_chunks = save_translation_chunks
    read_translation_chunks = read_translation_chunks
    update_translation_chunk_status = update_translation_chunk_status
    save_chunk_attempt_record = save_chunk_attempt_record
    cleanup_expired_runtime_data = cleanup_expired_runtime_data
    cleanup_fetch_cache = cleanup_fetch_cache
    cleanup_pipeline_events = cleanup_pipeline_events
    list_chunk_attempt_records = list_chunk_attempt_records
    save_translation_bundle = save_translation_bundle
    read_translation_bundle = read_translation_bundle
    delete_translation_bundle = delete_translation_bundle
    save_translation_output = save_translation_output
    read_translation_output = read_translation_output
    save_provider_request_record = save_provider_request_record
    list_provider_request_records = list_provider_request_records
    save_fetch_cache_entry = save_fetch_cache_entry
    read_fetch_cache_entry = read_fetch_cache_entry
    fetch_cache_conditional_headers = fetch_cache_conditional_headers
