from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.core.platform import ChapterVersionKind
from novelai.storage.common import _utc_now_iso

logger = logging.getLogger(__name__)

def _translated_payload_to_version(self: Any, translated: dict[str, Any], fallback_id: str) -> dict[str, Any]:
    raw_text = translated.get("text")
    text = raw_text if isinstance(raw_text, str) else ""
    created_at = self._clean_string(translated.get("created_at")) or self._clean_string(translated.get("translated_at")) or _utc_now_iso()
    raw_version_id = translated.get("version_id")
    raw_id = translated.get("id")

    version: dict[str, Any] = {
        "id": (
            raw_version_id
            if isinstance(raw_version_id, str)
            else raw_id if isinstance(raw_id, str) else fallback_id
        ),
        "kind": self._normalize_version_kind(translated.get("version_kind") or translated.get("kind")),
        "provider": translated.get("provider"),
        "model": translated.get("model"),
        "created_at": created_at,
        "translated_at": created_at,
        "text": text,
        "paragraphs": self._text_paragraphs(text),
    }
    if isinstance(translated.get("editor"), str):
        version["editor"] = translated["editor"]
    if isinstance(translated.get("note"), str):
        version["note"] = translated["note"]
    if isinstance(translated.get("base_version_id"), str):
        version["base_version_id"] = translated["base_version_id"]
    if isinstance(translated.get("source_hash"), str):
        version["source_hash"] = translated["source_hash"]
    if isinstance(translated.get("confidence_score"), float):
        version["confidence_score"] = max(0.0, min(1.0, translated["confidence_score"]))
    if isinstance(translated.get("polish_needed"), bool):
        version["polish_needed"] = translated["polish_needed"]
    if isinstance(translated.get("confidence_details"), dict):
        version["confidence_details"] = dict(translated["confidence_details"])
    return version


def _translation_versions_from_payload(self: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    raw_versions = payload.get("translation_versions")
    if isinstance(raw_versions, list):
        for index, raw_version in enumerate(raw_versions, start=1):
            if not isinstance(raw_version, dict):
                continue
            version = self._translated_payload_to_version(raw_version, f"v{index}")
            version_id = str(version["id"])
            if version_id in seen_ids:
                version["id"] = self._next_translation_version_id(versions)
                version_id = str(version["id"])
            seen_ids.add(version_id)
            versions.append(version)

    if not versions and isinstance(payload.get("translated"), dict):
        versions.append(self._translated_payload_to_version(payload["translated"], "v1"))

    return versions


def _active_translation_version(self: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    versions = self._translation_versions_from_payload(payload)
    if not versions:
        return None

    active_id = payload.get("active_translation_version_id")
    if isinstance(active_id, str):
        for version in versions:
            if version.get("id") == active_id:
                return version

    translated = payload.get("translated")
    if isinstance(translated, dict) and isinstance(translated.get("version_id"), str):
        for version in versions:
            if version.get("id") == translated["version_id"]:
                return version

    return versions[-1]


def _set_active_translation_version(self: Any, payload: dict[str, Any], version: dict[str, Any]) -> None:
    raw_text = version.get("text")
    text = raw_text if isinstance(raw_text, str) else ""
    payload["active_translation_version_id"] = version.get("id")
    payload["translated"] = {
        "version_id": version.get("id"),
        "version_kind": self._normalize_version_kind(version.get("kind")),
        "provider": version.get("provider"),
        "model": version.get("model"),
        "translated_at": version.get("created_at") or version.get("translated_at") or _utc_now_iso(),
        "created_at": version.get("created_at") or version.get("translated_at") or _utc_now_iso(),
        "text": text,
        "paragraphs": self._text_paragraphs(text),
    }
    for optional_key in (
        "editor",
        "note",
        "base_version_id",
        "source_hash",
        "confidence_score",
        "polish_needed",
        "confidence_details",
    ):
        if optional_key in version:
            payload["translated"][optional_key] = version[optional_key]


def _append_edit_history(
    self: Any,
    payload: dict[str, Any],
    *,
    action: ChapterVersionKind,
    version_id: str,
    previous_version_id: str | None = None,
    editor: str | None = None,
    note: str | None = None,
) -> None:
    entries = self._normalize_named_dict_items(payload.get("edit_history"))
    entry: dict[str, Any] = {
        "id": self._next_edit_history_id(entries),
        "action": action.value,
        "version_id": version_id,
        "previous_version_id": previous_version_id,
        "created_at": _utc_now_iso(),
    }
    if editor:
        entry["editor"] = editor
    if note:
        entry["note"] = note
    entries.append(entry)
    payload["edit_history"] = entries


def save_translated_chapter(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    provider: str | None = None,
    model: str | None = None,
    confidence_score: float | None = None,
    polish_needed: bool | None = None,
    confidence_details: dict[str, Any] | None = None,
    source_hash: str | None = None,
    version_kind: ChapterVersionKind = ChapterVersionKind.MACHINE_TRANSLATION,
) -> Path:
    """Save a translated chapter as structured JSON and append a version."""
    payload = self._load_chapter_bundle(novel_id, chapter_id) or {"id": chapter_id}
    versions = self._translation_versions_from_payload(payload)
    created_at = _utc_now_iso()
    translated_payload: dict[str, Any] = {
        "id": self._next_translation_version_id(versions),
        "kind": self._normalize_version_kind(version_kind),
        "provider": provider,
        "model": model,
        "created_at": created_at,
        "translated_at": created_at,
        "text": text,
        "paragraphs": self._text_paragraphs(text),
    }
    if isinstance(source_hash, str) and source_hash.strip():
        translated_payload["source_hash"] = source_hash.strip()
    if isinstance(confidence_score, float):
        translated_payload["confidence_score"] = max(0.0, min(1.0, confidence_score))
    if isinstance(polish_needed, bool):
        translated_payload["polish_needed"] = polish_needed
    if isinstance(confidence_details, dict):
        translated_payload["confidence_details"] = dict(confidence_details)
    versions.append(translated_payload)
    payload["translation_versions"] = versions
    self._set_active_translation_version(payload, translated_payload)
    return self._persist_chapter_bundle(novel_id, chapter_id, payload)


def load_translated_chapter(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Load the translated content for a single chapter.

    Returns a dict with id, text, provider, model, and timestamp,
    or ``None`` if the chapter has not been translated.
    """
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return None

    translated = self._active_translation_version(payload)
    if not isinstance(translated, dict):
        return None

    return {
        "id": chapter_id,
        "version_id": translated.get("id"),
        "version_kind": self._normalize_version_kind(translated.get("kind")),
        "provider": translated.get("provider"),
        "model": translated.get("model"),
        "translated_at": translated.get("translated_at") or translated.get("created_at"),
        "created_at": translated.get("created_at") or translated.get("translated_at"),
        "text": translated.get("text"),
        "editor": translated.get("editor"),
        "note": translated.get("note"),
        "base_version_id": translated.get("base_version_id"),
        "source_hash": translated.get("source_hash"),
        "confidence_score": translated.get("confidence_score"),
        "polish_needed": translated.get("polish_needed"),
        "confidence_details": translated.get("confidence_details") if isinstance(translated.get("confidence_details"), dict) else {},
        "input_adapter_key": payload.get("input_adapter_key"),
        "origin_type": payload.get("origin_type"),
        "origin_uri_or_path": payload.get("origin_uri_or_path"),
        "document_type": payload.get("document_type"),
        "unit_type": payload.get("unit_type"),
        "import_order": payload.get("import_order"),
        "context_group_id": payload.get("context_group_id"),
        "region_metadata": self._normalize_named_dict_items(payload.get("region_metadata")),
        "ocr_artifacts": self._normalize_named_dict_items(payload.get("ocr_artifacts")),
        "ocr_required": payload.get("ocr_required", False),
        "ocr_text": payload.get("ocr_text"),
        "ocr_status": payload.get("ocr_status", "skipped"),
        "reembed_status": payload.get("reembed_status", "skipped"),
    }


def list_translated_chapter_versions(self: Any, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
    """Return all stored translation/edit versions for a chapter."""
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return []

    versions = self._translation_versions_from_payload(payload)
    active_id = payload.get("active_translation_version_id")
    if not isinstance(active_id, str):
        active = self._active_translation_version(payload)
        active_id = active.get("id") if isinstance(active, dict) else None

    normalized: list[dict[str, Any]] = []
    for version in versions:
        item = dict(version)
        item["version_id"] = item.get("id")
        item["version_kind"] = self._normalize_version_kind(item.get("kind"))
        item["active"] = bool(active_id and item.get("id") == active_id)
        normalized.append(item)
    return normalized


def save_edited_translation(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    *,
    editor: str | None = None,
    note: str | None = None,
) -> Path:
    """Persist a manual translation edit as a new active version."""
    payload = self._load_chapter_bundle(novel_id, chapter_id) or {"id": chapter_id}
    versions = self._translation_versions_from_payload(payload)
    previous = self._active_translation_version(payload)
    previous_version_id = previous.get("id") if isinstance(previous, dict) else None
    created_at = _utc_now_iso()

    edited_payload: dict[str, Any] = {
        "id": self._next_translation_version_id(versions),
        "kind": ChapterVersionKind.MANUAL_EDIT.value,
        "provider": previous.get("provider") if isinstance(previous, dict) else None,
        "model": previous.get("model") if isinstance(previous, dict) else None,
        "created_at": created_at,
        "translated_at": created_at,
        "text": text,
        "paragraphs": self._text_paragraphs(text),
        "base_version_id": previous_version_id,
    }
    if isinstance(editor, str) and editor.strip():
        edited_payload["editor"] = editor.strip()
    if isinstance(note, str) and note.strip():
        edited_payload["note"] = note.strip()
    versions.append(edited_payload)
    payload["translation_versions"] = versions
    self._set_active_translation_version(payload, edited_payload)
    self._append_edit_history(
        payload,
        action=ChapterVersionKind.MANUAL_EDIT,
        version_id=str(edited_payload["id"]),
        previous_version_id=str(previous_version_id) if previous_version_id else None,
        editor=edited_payload.get("editor"),
        note=edited_payload.get("note"),
    )
    return self._persist_chapter_bundle(novel_id, chapter_id, payload)


def load_translation_edit_history(self: Any, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
    """Return manual edit and rollback history for a translated chapter."""
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return []
    return self._normalize_named_dict_items(payload.get("edit_history"))


def list_translated_chapters(self: Any, novel_id: str) -> list[str]:
    """Return sorted chapter IDs that have translated content on disk."""
    stems: set[str] = set()
    chapter_dir = self._novel_dir(novel_id) / self.CHAPTERS_DIRNAME
    if chapter_dir.exists():
        for chapter_path in chapter_dir.glob("*.json"):
            try:
                payload = json.loads(chapter_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.debug("Skipping unreadable chapter file %s.", chapter_path)
                continue
            if isinstance(payload, dict) and isinstance(payload.get("translated"), dict):
                stems.add(chapter_path.stem)

    legacy_translated_dir = self._novel_dir(novel_id) / "translated"
    if legacy_translated_dir.exists():
        for path in legacy_translated_dir.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() in {".json", ".txt"}:
                stems.add(path.stem)
    return sorted(stems)


def count_translated_chapters(self: Any, novel_id: str) -> int:
    return len(self.list_translated_chapters(novel_id))


def activate_translated_chapter_version(
    self: Any,
    novel_id: str,
    chapter_id: str,
    version_id: str,
    *,
    editor: str | None = None,
    note: str | None = None,
) -> bool:
    """Make an existing translation version active without deleting history."""
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return False

    versions = self._translation_versions_from_payload(payload)
    target = next((version for version in versions if version.get("id") == version_id), None)
    if target is None:
        return False

    previous = self._active_translation_version(payload)
    previous_version_id = previous.get("id") if isinstance(previous, dict) else None
    payload["translation_versions"] = versions
    self._set_active_translation_version(payload, target)
    self._append_edit_history(
        payload,
        action=ChapterVersionKind.ROLLBACK,
        version_id=version_id,
        previous_version_id=str(previous_version_id) if previous_version_id else None,
        editor=editor.strip() if isinstance(editor, str) and editor.strip() else None,
        note=note.strip() if isinstance(note, str) and note.strip() else None,
    )
    self._persist_chapter_bundle(novel_id, chapter_id, payload)
    return True
