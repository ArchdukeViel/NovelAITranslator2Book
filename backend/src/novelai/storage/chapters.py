from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.core.chapter_state import ChapterState
from novelai.core.security import encode_physical_stem, validate_storage_identifier
from novelai.services.query_builder import ChapterQueryBuilder
from novelai.storage.common import _utc_now_iso, validate_storage_schema_version

logger = logging.getLogger(__name__)


# Section 6: section-scoped aliases for the raw / translation chapters trees.
# The active raw generation's ``chapters`` directory is byte-immutable
# once committed; translations live in a parallel ``translations``
# directory at the novel root so QA-accepted edits never overwrite
# raw bytes. The intermediate / pre-existing consumer tree is the
# ``chapters`` directory itself; we keep that name for backward
# compatibility and just split the *translation* path to a different
# root.
RAW_CHAPTERS_SUBDIR = "chapters"


def _chapter_dir(self: Any, novel_id: str) -> Path:
    chapter_dir = self._content_root(novel_id) / RAW_CHAPTERS_SUBDIR
    self._mkdirs(chapter_dir)
    return chapter_dir


def _chapter_filename(chapter_id: str) -> str:
    """Return the physical filename for a logical chapter ID.

    Numeric IDs keep the legacy zero-padded 4-digit form. Non-numeric IDs
    (e.g. Kakuyomu's ``kakuyomu:<episode-id>``) are percent-encoded with
    :func:`encode_physical_stem` so characters such as ``:`` never reach the
    filesystem (invalid on Windows) while remaining reversible through
    ``logical_id_from_stem``.
    """
    raw = str(chapter_id)
    try:
        num = int(raw)
        return f"{num:04d}.json"
    except (ValueError, TypeError):
        safe = validate_storage_identifier(raw, "chapter_id")
        return f"{encode_physical_stem(safe)}.json"


def _translation_overlay_dir(self: Any, novel_id: str) -> Path:
    """Directory holding mutable translation overlays for a novel.

    Section 6: translation overlays live outside the active raw
    generation's ``chapters/`` directory so that QA-accepted edits and
    retranslations never mutate the immutable raw bytes. The overlay
    is always at the novel root regardless of whether an active
    generation exists, ensuring readers compose the active raw
    generation with the active translation overlay consistently.
    """
    overlay = self._novel_dir(novel_id) / "translations"
    self._mkdirs(overlay)
    self._mkdirs(overlay / "active")
    return overlay


def _translation_overlay_path(self: Any, novel_id: str, chapter_id: str) -> Path:
    """File path for a chapter's translation overlay payload."""
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    encoded_stem = encode_physical_stem(safe_chapter_id)
    return _translation_overlay_dir(self, novel_id) / f"{encoded_stem}.json"


def _translation_active_pointer_path(self: Any, novel_id: str, chapter_id: str) -> Path:
    """Path to the per-chapter active-translation pointer inside the overlay."""
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    encoded_stem = encode_physical_stem(safe_chapter_id)
    return _translation_overlay_dir(self, novel_id) / "active" / f"{encoded_stem}.json"


def _chapter_path(self: Any, novel_id: str, chapter_id: str) -> Path:
    """Return the raw chapter bundle path.

    For a novel with an active generation the path is inside the
    generation snapshot's ``chapters/`` directory; otherwise it
    falls back to the novel-level legacy root. Raw bundles are
    byte-immutable once committed so translation writes never go
    through this path: see
    :func:`storage.translations._persist_translation_overlay`.
    """
    return self._chapter_dir(novel_id) / _chapter_filename(chapter_id)


def _load_chapter_bundle(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Load a current-schema chapter bundle from the canonical chapter directory."""
    chapter_path = self._chapter_path(novel_id, chapter_id)
    if self._path_exists(chapter_path):
        try:
            data = json.loads(self._read_text(chapter_path))
            if isinstance(data, dict):
                validate_storage_schema_version(
                    data,
                    current_version=self.SCHEMA_VERSION,
                    artifact_type="chapter bundle",
                )
                return self._normalize_media_fields(data)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse chapter bundle %s/%s.", novel_id, chapter_id)
            return None

    return None


def _persist_chapter_bundle(self: Any, novel_id: str, chapter_id: str, payload: dict[str, Any]) -> Path:
    """Persist a chapter bundle to its canonical raw location.

    Callers that only mutate raw content should land here.
    Translation writes must use ``_persist_translation_overlay`` so the
    raw generation stays byte-immutable (Section 6).

    Section 10/11: when a generation snapshot is active, the snapshot's
    ``chapters/`` tree is byte-immutable and the canonical raw layout.
    Raw writes are refused outright instead of silently mutating or
    shadowing committed bytes; mutable derived state belongs in the
    media/translation overlays at the novel root.
    """
    self._normalize_media_fields(payload)
    payload["schema_version"] = self.SCHEMA_VERSION
    if self.get_active_generation(novel_id) is not None:
        raise RuntimeError(
            f"Refusing to overwrite committed raw chapter {novel_id}/{chapter_id}: "
            "an active generation snapshot is the authoritative raw layout"
        )
    path = self._chapter_path(novel_id, chapter_id)
    self._write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))
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


def build_chapter_payload(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    title: str | None = None,
    source_key: str | None = None,
    source_url: str | None = None,
    images: list[dict[str, Any]] | None = None,
    source_blocks: list[dict[str, Any]] | None = None,
    input_adapter_key: str | None = None,
    origin_type: str | None = None,
    origin_uri_or_path: str | None = None,
    document_type: str | None = None,
    unit_type: str | None = None,
    import_order: int | None = None,
    context_group_id: str | None = None,
    region_metadata: list[dict[str, Any]] | None = None,
    ocr_artifacts: list[dict[str, Any]] | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a current-schema chapter bundle without writing it.

    Used by both :func:`save_chapter` (legacy direct writes) and staged
    generation writes so payload normalization stays in one place.

    When ``existing`` is supplied, fields whose arguments are ``None`` are
    preserved from the existing bundle instead of being cleared (e.g. a
    catalog title-only edit must not wipe stored images or source blocks).
    """
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    existing_raw = existing.get("raw") if isinstance(existing, dict) else None
    existing_raw = existing_raw if isinstance(existing_raw, dict) else None
    payload: dict[str, Any] = {"id": safe_chapter_id}
    payload["title"] = title if title is not None else (existing.get("title") if isinstance(existing, dict) else None)
    payload["source_key"] = source_key
    payload["source_url"] = source_url
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
    if images is None and existing_raw is not None and existing_raw.get("images") is not None:
        resolved_images = existing_raw.get("images")
    else:
        resolved_images = self._normalize_image_manifest(images)
    raw: dict[str, Any] = {
        "id": safe_chapter_id,
        "scraped_at": _utc_now_iso(),
        "text": text,
        "paragraphs": self._text_paragraphs(text),
        "images": resolved_images,
    }
    if source_blocks is not None:
        raw["source_blocks"] = self._normalize_source_blocks(source_blocks)
    elif existing_raw is not None and existing_raw.get("source_blocks") is not None:
        raw["source_blocks"] = existing_raw.get("source_blocks")
    payload["raw"] = raw
    return payload


def save_chapter(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    title: str | None = None,
    source_key: str | None = None,
    source_url: str | None = None,
    images: list[dict[str, Any]] | None = None,
    source_blocks: list[dict[str, Any]] | None = None,
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
    existing_bundle = payload if payload.get("id") == safe_chapter_id else None
    payload.update(
        build_chapter_payload(
            self,
            novel_id,
            chapter_id,
            text,
            title=title,
            source_key=source_key,
            source_url=source_url,
            images=images,
            source_blocks=source_blocks,
            input_adapter_key=input_adapter_key,
            origin_type=origin_type,
            origin_uri_or_path=origin_uri_or_path,
            document_type=document_type,
            unit_type=unit_type,
            import_order=import_order,
            context_group_id=context_group_id,
            region_metadata=region_metadata,
            ocr_artifacts=ocr_artifacts,
            existing=existing_bundle,
        )
    )
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
    result = {
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
        "source_blocks": self._normalize_source_blocks(raw.get("source_blocks")),
        "images": self._normalize_image_manifest(raw.get("images") if isinstance(raw, dict) else None),
        "ocr_required": payload.get("ocr_required", False),
        "ocr_text": payload.get("ocr_text"),
        "ocr_status": payload.get("ocr_status", "skipped"),
        "reembed_status": payload.get("reembed_status", "skipped"),
    }
    # Section 11: the novel-root media overlay holds mutable derived OCR
    # state that must not live in the committed snapshot; compose it on
    # read so OCR workers see overlay state win over the bundle.
    media_overlay = self._load_media_overlay(novel_id, safe_chapter_id)
    if media_overlay is not None:
        for key in ("ocr_required", "ocr_text", "ocr_status", "reembed_status"):
            if key in media_overlay:
                result[key] = media_overlay[key]
    return result


def list_stored_chapters(self: Any, novel_id: str) -> list[str]:
    """Return sorted chapter IDs that have raw or translated data on disk.

    Reads the raw ``chapters/`` directory (legacy merged payloads plus
    active-generation bundles) and the per-novel translation overlay
    directory so chapter ids surface regardless of whether translation
    data lives in the bundle or in the overlay.
    """
    ids: set[str] = set()
    chapter_dir = self._content_root(novel_id) / self.CHAPTERS_DIRNAME
    if self._is_dir_present(chapter_dir):
        for chapter_path in self._glob(chapter_dir, "*.json"):
            try:
                payload = json.loads(self._read_text(chapter_path))
            except (json.JSONDecodeError, OSError):
                logger.debug("Skipping unreadable chapter file %s.", chapter_path)
                continue
            if not isinstance(payload, dict):
                continue
            try:
                validate_storage_schema_version(
                    payload,
                    current_version=self.SCHEMA_VERSION,
                    artifact_type="chapter bundle",
                )
            except Exception:
                logger.debug("Skipping chapter with invalid schema_version %s.", chapter_path)
                continue
            has_translation_versions = bool(self._translation_versions_from_payload_compat(payload))
            if isinstance(payload.get("raw"), dict) or has_translation_versions:
                ids.add(self.logical_id_from_stem(chapter_path.stem))

    overlay_dir = self._novel_dir(novel_id) / "translations"
    if self._is_dir_present(overlay_dir):
        for overlay_path in self._glob(overlay_dir, "*.json"):
            if overlay_path.stem == "active":
                continue
            try:
                payload = json.loads(self._read_text(overlay_path))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            chapter_id = payload.get("chapter_id") or self.logical_id_from_stem(overlay_path.stem)
            if isinstance(chapter_id, str) and chapter_id:
                ids.add(chapter_id)

    return sorted(ids)


def count_stored_chapters(self: Any, novel_id: str) -> int:
    return len(self.list_stored_chapters(novel_id))


def get_chapters_by_state(self: Any, novel_id: str, state: ChapterState) -> list[str]:
    """Get all chapters in a specific state."""
    state_dir = self._get_state_dir(novel_id)
    if not self._is_dir_present(state_dir):
        return []

    chapters = []
    for state_file in self._glob(state_dir, "*.json"):
        try:
            state_data = json.loads(self._read_text(state_file))
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
    if not self._is_dir_present(state_dir):
        return progress

    for state_file in self._glob(state_dir, "*.json"):
        try:
            state_data = json.loads(self._read_text(state_file))
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
    # Inject backend-aware callables to avoid direct Path I/O
    return ChapterQueryBuilder(
        state_dir,
        path_exists=lambda: self._is_dir_present(state_dir),
        list_files=lambda: self._glob(state_dir, "*.json"),
        read_file=lambda p: self._read_text(p),
    )


def get_chapters_with_errors(self: Any, novel_id: str, limit: int = 100) -> list[str]:
    """Get chapters that have errors, for retry."""
    results = self.query_chapters(novel_id).has_errors().sort_by("errors", reverse=True).limit(limit).execute()
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
    if not self._is_dir_present(state_dir):
        return progress

    total_files = 0
    error_count = 0

    for state_file in self._glob(state_dir, "*.json"):
        try:
            state_data = json.loads(self._read_text(state_file))
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

    logger.debug(f"Progress for {novel_id}: {progress['by_state']} (success rate: {progress['success_rate']:.1f}%)")
    return progress


# Rollback & Recovery Methods
