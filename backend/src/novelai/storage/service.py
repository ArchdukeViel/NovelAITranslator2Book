from __future__ import annotations

import hashlib
import re
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
    _compute_folder_name,
    _ensure_novel_dir,
    _get_folder_name,
    _index_path,
    _legacy_folder_candidates,
    _load_index,
    _normalize_library_novel_id,
    _novel_dir,
    _persist_index,
    delete_novel,
    list_novels,
    load_metadata,
    save_metadata,
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
    load_translation_edit_history,
    save_edited_translation,
    save_translated_chapter,
)
from novelai.storage.traceability import (
    _trace_dir,
    append_pipeline_event,
    append_pipeline_events,
    list_pipeline_events,
    load_chunk_states,
    load_scheduler_state,
    save_scheduler_state,
    upsert_chunk_state,
)


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
    def _clean_string(value: Any, default: str | None = None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return default


    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.novels_dir = self.base_dir / "novels"
        self.novels_dir.mkdir(parents=True, exist_ok=True)


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
    _normalize_library_novel_id = _normalize_library_novel_id
    _legacy_folder_candidates = _legacy_folder_candidates
    _compute_folder_name = _compute_folder_name
    _get_folder_name = _get_folder_name
    _novel_dir = _novel_dir
    _ensure_novel_dir = _ensure_novel_dir
    delete_novel = delete_novel
    save_metadata = save_metadata
    load_metadata = load_metadata
    list_novels = list_novels
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
    append_pipeline_event = append_pipeline_event
    append_pipeline_events = append_pipeline_events
    list_pipeline_events = list_pipeline_events
    upsert_chunk_state = upsert_chunk_state
    load_chunk_states = load_chunk_states
    save_scheduler_state = save_scheduler_state
    load_scheduler_state = load_scheduler_state
