from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.core.chapter_state import ChapterState
from novelai.core.security import validate_storage_identifier
from novelai.services.query_builder import ChapterQueryBuilder
from novelai.storage.common import _utc_now_iso
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)

def _chapter_dir(self: Any, novel_id: str) -> Path:
    chapter_dir = self._novel_dir(novel_id) / self.CHAPTERS_DIRNAME
    chapter_dir.mkdir(parents=True, exist_ok=True)
    return chapter_dir


def _chapter_path(self: Any, novel_id: str, chapter_id: str) -> Path:
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    return self._chapter_dir(novel_id) / f"{safe_chapter_id}.json"


def _load_legacy_raw_chapter(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    json_path = self._novel_dir(novel_id) / "raw" / f"{safe_chapter_id}.json"
    txt_path = self._novel_dir(novel_id) / "raw" / f"{safe_chapter_id}.txt"

    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse legacy raw chapter %s/%s.", novel_id, chapter_id)
            return None

    if txt_path.exists():
        return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}
    return None


def _load_legacy_translated_chapter(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    json_path = self._novel_dir(novel_id) / "translated" / f"{safe_chapter_id}.json"
    txt_path = self._novel_dir(novel_id) / "translated" / f"{safe_chapter_id}.txt"

    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse legacy translated chapter %s/%s.", novel_id, chapter_id)
            return None

    if txt_path.exists():
        return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}
    return None


def _load_chapter_bundle(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Load a chapter bundle (raw + translated + metadata) from disk.

    Falls back to legacy ``raw/`` and ``translated/`` directories if the
    unified bundle file does not exist.
    """
    chapter_path = self._chapter_path(novel_id, chapter_id)
    if chapter_path.exists():
        try:
            data = json.loads(chapter_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return self._normalize_media_fields(data)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse chapter bundle %s/%s.", novel_id, chapter_id)
            return None

    raw = self._load_legacy_raw_chapter(novel_id, chapter_id)
    translated = self._load_legacy_translated_chapter(novel_id, chapter_id)
    if raw is None and translated is None:
        return None

    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    bundle: dict[str, Any] = {"id": safe_chapter_id}
    if raw is not None:
        bundle["title"] = raw.get("title")
        bundle["source_key"] = raw.get("source_key")
        bundle["source_url"] = raw.get("source_url")
        bundle["raw"] = {
            "scraped_at": raw.get("scraped_at"),
            "text": raw.get("text"),
        }
    if translated is not None:
        bundle["translated"] = {
            "provider": translated.get("provider"),
            "model": translated.get("model"),
            "translated_at": translated.get("translated_at"),
            "text": translated.get("text"),
        }
    return self._normalize_media_fields(bundle)


def _persist_chapter_bundle(self: Any, novel_id: str, chapter_id: str, payload: dict[str, Any]) -> Path:
    self._normalize_media_fields(payload)
    payload["schema_version"] = self.SCHEMA_VERSION
    path = self._chapter_path(novel_id, chapter_id)
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def existing_chapter_hash(self: Any, novel_id: str, chapter_id: str) -> str | None:
    """Return SHA256 hash of an existing raw chapter file (if present)."""
    chapter = self.load_chapter(novel_id, chapter_id)
    if chapter is None:
        return None

    text = chapter.get("text")
    if not isinstance(text, str):
        return None
    return self._hash_text(text)


def save_chapter(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    title: str | None = None,
    source_key: str | None = None,
    source_url: str | None = None,
    images: list[dict[str, Any]] | None = None,
    input_adapter_key: str | None = None,
    origin_type: str | None = None,
    origin_uri_or_path: str | None = None,
    document_type: str | None = None,
    unit_type: str | None = None,
    import_order: int | None = None,
    context_group_id: str | None = None,
    region_metadata: list[dict[str, Any]] | None = None,
    ocr_artifacts: list[dict[str, Any]] | None = None,
) -> Path:
    """Save a raw / scraped chapter as structured JSON."""
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    payload: dict[str, Any] = self._load_chapter_bundle(novel_id, safe_chapter_id) or {"id": safe_chapter_id}
    payload["id"] = safe_chapter_id
    payload["title"] = title if title is not None else payload.get("title")
    payload["source_key"] = source_key if source_key is not None else payload.get("source_key")
    payload["source_url"] = source_url if source_url is not None else payload.get("source_url")
    if input_adapter_key is not None:
        payload["input_adapter_key"] = input_adapter_key
    if origin_type is not None:
        payload["origin_type"] = origin_type
    if origin_uri_or_path is not None:
        payload["origin_uri_or_path"] = origin_uri_or_path
    if document_type is not None:
        payload["document_type"] = document_type
    if unit_type is not None:
        payload["unit_type"] = unit_type
    if import_order is not None:
        payload["import_order"] = int(import_order)
    if context_group_id is not None:
        payload["context_group_id"] = context_group_id
    if region_metadata is not None:
        payload["region_metadata"] = self._normalize_named_dict_items(region_metadata)
    if ocr_artifacts is not None:
        payload["ocr_artifacts"] = self._normalize_named_dict_items(ocr_artifacts)
    existing_raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
    payload["raw"] = {
        "id": safe_chapter_id,
        "scraped_at": _utc_now_iso(),
        "text": text,
        "paragraphs": self._text_paragraphs(text),
        "images": self._normalize_image_manifest(images)
        if images is not None
        else self._normalize_image_manifest(existing_raw.get("images") if isinstance(existing_raw, dict) else None),
    }
    return self._persist_chapter_bundle(novel_id, safe_chapter_id, payload)


def load_chapter(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Load the raw (source) content for a single chapter.

    Returns a dict with id, title, text, images, and source metadata,
    or ``None`` if the chapter has not been scraped.
    """
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return None

    raw = payload.get("raw")
    if not isinstance(raw, dict):
        return None

    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    return {
        "id": safe_chapter_id,
        "title": payload.get("title"),
        "source_key": payload.get("source_key"),
        "source_url": payload.get("source_url"),
        "input_adapter_key": payload.get("input_adapter_key"),
        "origin_type": payload.get("origin_type"),
        "origin_uri_or_path": payload.get("origin_uri_or_path"),
        "document_type": payload.get("document_type"),
        "unit_type": payload.get("unit_type"),
        "import_order": payload.get("import_order"),
        "context_group_id": payload.get("context_group_id"),
        "region_metadata": self._normalize_named_dict_items(payload.get("region_metadata")),
        "ocr_artifacts": self._normalize_named_dict_items(payload.get("ocr_artifacts")),
        "scraped_at": raw.get("scraped_at"),
        "text": raw.get("text"),
        "images": self._normalize_image_manifest(raw.get("images") if isinstance(raw, dict) else None),
        "ocr_required": payload.get("ocr_required", False),
        "ocr_text": payload.get("ocr_text"),
        "ocr_status": payload.get("ocr_status", "skipped"),
        "reembed_status": payload.get("reembed_status", "skipped"),
    }


def list_stored_chapters(self: Any, novel_id: str) -> list[str]:
    """Return sorted chapter IDs that have raw or translated data on disk.

    Checks both the unified ``chapters/`` directory and legacy
    ``raw/`` / ``translated/`` directories.
    """
    stems: set[str] = set()
    chapter_dir = self._novel_dir(novel_id) / self.CHAPTERS_DIRNAME
    if chapter_dir.exists():
        for chapter_path in chapter_dir.glob("*.json"):
            try:
                payload = json.loads(chapter_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.debug("Skipping unreadable chapter file %s.", chapter_path)
                continue
            if not isinstance(payload, dict):
                continue
            if isinstance(payload.get("raw"), dict) or isinstance(payload.get("translated"), dict):
                stems.add(chapter_path.stem)

    for legacy_dirname in ("raw", "translated"):
        legacy_dir = self._novel_dir(novel_id) / legacy_dirname
        if not legacy_dir.exists():
            continue
        for path in legacy_dir.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() in {".json", ".txt"}:
                stems.add(path.stem)

    return sorted(stems)


def count_stored_chapters(self: Any, novel_id: str) -> int:
    return len(self.list_stored_chapters(novel_id))


def get_chapters_by_state(self: Any, novel_id: str, state: ChapterState) -> list[str]:
    """Get all chapters in a specific state."""
    state_dir = self._get_state_dir(novel_id)
    if not state_dir.exists():
        return []

    chapters = []
    for state_file in state_dir.glob("*.json"):
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            if ChapterState(state_data["current_state"]) == state:
                chapters.append(state_data["chapter_id"])
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            logger.debug("Skipping unreadable state file %s.", state_file)
            continue

    return sorted(chapters)


def get_chapter_progress(self: Any, novel_id: str) -> dict[str, int]:
    """Get count of chapters in each state."""
    from novelai.core.chapter_state import ChapterState

    progress = {s.value: 0 for s in ChapterState}

    state_dir = self._get_state_dir(novel_id)
    if not state_dir.exists():
        return progress

    for state_file in state_dir.glob("*.json"):
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            current_state = state_data["current_state"]
            progress[current_state] += 1
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            logger.debug("Skipping unreadable state file %s.", state_file)
            continue

    return progress

# Query Methods

def query_chapters(self: Any, novel_id: str) -> ChapterQueryBuilder:
    """Create a query builder for chapters."""
    state_dir = self._get_state_dir(novel_id)
    return ChapterQueryBuilder(state_dir)


def get_chapters_with_errors(self: Any, novel_id: str, limit: int = 100) -> list[str]:
    """Get chapters that have errors, for retry."""
    results = (
        self.query_chapters(novel_id)
        .has_errors()
        .sort_by("errors", reverse=True)
        .limit(limit)
        .execute()
    )
    logger.info(f"Found {len(results)} chapters with errors in {novel_id}")
    return [r.chapter_id for r in results]


def get_scraping_progress(self: Any, novel_id: str) -> dict[str, Any]:
    """Get detailed scraping progress for a novel."""

    progress = {
        "total": 0,
        "by_state": self.get_chapter_progress(novel_id),
        "with_errors": 0,
        "success_rate": 0.0,
    }

    state_dir = self._get_state_dir(novel_id)
    if not state_dir.exists():
        return progress

    total_files = 0
    error_count = 0

    for state_file in state_dir.glob("*.json"):
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            total_files += 1
            if state_data.get("error_count", 0) > 0:
                error_count += 1
        except (json.JSONDecodeError, OSError):
            logger.debug("Skipping unreadable state file %s.", state_file)
            continue

    progress["total"] = total_files
    progress["with_errors"] = error_count
    if total_files > 0:
        progress["success_rate"] = ((total_files - error_count) / total_files) * 100

    logger.debug(
        f"Progress for {novel_id}: {progress['by_state']} "
        f"(success rate: {progress['success_rate']:.1f}%)"
    )
    return progress

# Rollback & Recovery Methods
