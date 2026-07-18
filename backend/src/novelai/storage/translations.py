from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.core.platform import ChapterVersionKind
from novelai.storage.common import _utc_now_iso

logger = logging.getLogger(__name__)


def _resolve_glossary_snapshot_from_metadata(
    metadata: dict[str, Any] | None,
) -> Any:
    """Resolve a GlossarySnapshot from novel metadata if available.

    Returns None when metadata is missing or has no glossary fields.
    This is a best-effort resolver for the file-based storage layer;
    callers that have DB access should resolve the snapshot directly.
    """
    # Lazy import to avoid circular dependency between storage and translation.
    from novelai.translation.glossary_freshness import GlossarySnapshot

    if not isinstance(metadata, dict):
        return None
    revision = metadata.get("glossary_revision")
    if not isinstance(revision, int):
        return None
    hash_value = metadata.get("glossary_hash")
    if not isinstance(hash_value, str) or not hash_value:
        hash_value = None
    term_count = metadata.get("glossary_term_count")
    if not isinstance(term_count, int):
        term_count = None
    return GlossarySnapshot(
        revision=revision,
        hash=hash_value,
        approved_term_count=term_count,
    )


def _attach_freshness_fields(
    version: dict[str, Any],
    snapshot: Any,
) -> dict[str, Any]:
    """Return a copy of ``version`` with glossary freshness fields attached.

    Non-mutating: does not modify ``version``. If ``snapshot`` is None,
    freshness is reported as ``unknown``.
    """
    # Lazy import to avoid circular dependency between storage and translation.
    from novelai.translation.glossary_freshness import compute_glossary_freshness

    result = dict(version)
    result.update(compute_glossary_freshness(version, snapshot))
    return result


def _translated_payload_to_version(self: Any, translated: dict[str, Any], fallback_id: str) -> dict[str, Any]:
    raw_text = translated.get("text")
    text = raw_text if isinstance(raw_text, str) else ""
    created_at = (
        self._clean_string(translated.get("created_at"))
        or self._clean_string(translated.get("translated_at"))
        or _utc_now_iso()
    )
    raw_version_id = translated.get("version_id")
    raw_id = translated.get("id")

    version: dict[str, Any] = {
        "id": (
            raw_version_id if isinstance(raw_version_id, str) else raw_id if isinstance(raw_id, str) else fallback_id
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
    if isinstance(translated.get("glossary_revision"), int):
        version["glossary_revision"] = translated["glossary_revision"]
    if isinstance(translated.get("glossary_injected_term_count"), int):
        version["glossary_injected_term_count"] = translated["glossary_injected_term_count"]
    if isinstance(translated.get("prompt_template_version"), str) and translated["prompt_template_version"]:
        version["prompt_template_version"] = translated["prompt_template_version"]
    if isinstance(translated.get("glossary_hash"), str) and translated["glossary_hash"]:
        version["glossary_hash"] = translated["glossary_hash"]
    if isinstance(translated.get("batch_id"), str) and translated["batch_id"]:
        version["batch_id"] = translated["batch_id"]
    # QA fields (REQ-6.1, REQ-6.2)
    if isinstance(translated.get("qa_status"), str):
        version["qa_status"] = translated["qa_status"]
    if isinstance(translated.get("qa_score"), (int, float)):
        version["qa_score"] = translated["qa_score"]
    qa_warnings = translated.get("qa_warnings")
    if isinstance(qa_warnings, list):
        version["qa_warnings"] = list(qa_warnings)
    qa_errors = translated.get("qa_errors")
    if isinstance(qa_errors, list):
        version["qa_errors"] = list(qa_errors)
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
        "prompt_template_version",
        "glossary_hash",
        "batch_id",
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
    batch_id: str | None = None,
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
    if isinstance(batch_id, str) and batch_id.strip():
        entry["batch_id"] = batch_id.strip()
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
    glossary_revision: int | None = None,
    glossary_injected_term_count: int | None = None,
    version_kind: ChapterVersionKind = ChapterVersionKind.MACHINE_TRANSLATION,
    prompt_template_version: str | None = None,
    glossary_hash: str | None = None,
    batch_id: str | None = None,
    base_version_id: str | None = None,
    auto_activate: bool = True,
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
    if isinstance(glossary_revision, int) and glossary_revision >= 0:
        translated_payload["glossary_revision"] = glossary_revision
    if isinstance(glossary_injected_term_count, int) and glossary_injected_term_count >= 0:
        translated_payload["glossary_injected_term_count"] = glossary_injected_term_count
    if isinstance(prompt_template_version, str) and prompt_template_version.strip():
        translated_payload["prompt_template_version"] = prompt_template_version.strip()
    if isinstance(glossary_hash, str) and glossary_hash.strip():
        translated_payload["glossary_hash"] = glossary_hash.strip()
    if isinstance(batch_id, str) and batch_id.strip():
        translated_payload["batch_id"] = batch_id.strip()
    if isinstance(base_version_id, str) and base_version_id.strip():
        translated_payload["base_version_id"] = base_version_id.strip()
    versions.append(translated_payload)
    payload["prompt_template_version"] = translated_payload.get("prompt_template_version", "")
    payload["glossary_hash"] = translated_payload.get("glossary_hash", "")
    payload["translation_versions"] = versions
    if auto_activate:
        self._set_active_translation_version(payload, translated_payload)
    else:
        logger.warning(
            "Chapter %s/%s saved with low confidence (%.2f), not activated. Use activate endpoint to promote.",
            novel_id,
            chapter_id,
            confidence_score or 0.0,
        )
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

    metadata = self.load_metadata(novel_id) if hasattr(self, "load_metadata") else None
    snapshot = _resolve_glossary_snapshot_from_metadata(metadata)
    version_with_freshness = _attach_freshness_fields(translated, snapshot)

    return {
        "id": chapter_id,
        "version_id": version_with_freshness.get("version_id") or translated.get("id"),
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
        "confidence_details": translated.get("confidence_details")
        if isinstance(translated.get("confidence_details"), dict)
        else {},
        "glossary_revision": translated.get("glossary_revision")
        if isinstance(translated.get("glossary_revision"), int)
        else 0,
        "glossary_injected_term_count": (
            translated.get("glossary_injected_term_count")
            if isinstance(translated.get("glossary_injected_term_count"), int)
            else 0
        ),
        "prompt_template_version": translated.get("prompt_template_version", None),
        "glossary_hash": translated.get("glossary_hash", None),
        "batch_id": translated.get("batch_id", None),
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
        "glossary_freshness": version_with_freshness.get("glossary_freshness"),
        "glossary_stale": version_with_freshness.get("glossary_stale"),
        "glossary_stale_reason": version_with_freshness.get("glossary_stale_reason"),
        "current_glossary_revision": version_with_freshness.get("current_glossary_revision"),
        "current_glossary_hash": version_with_freshness.get("current_glossary_hash"),
    }


def load_translated_chapter_by_version_id(
    self: Any,
    novel_id: str,
    chapter_id: str,
    version_id: str,
) -> dict[str, Any] | None:
    """Load a specific translation version by its version id.

    Returns a normalized dict compatible with public response building,
    or ``None`` when the bundle or version does not exist. Does not
    modify storage.
    """
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return None

    versions = self._translation_versions_from_payload(payload)
    for version in versions:
        if not isinstance(version, dict):
            continue
        if str(version.get("id")) != str(version_id):
            continue
        created_at = version.get("created_at") or version.get("translated_at")
        translated_at = version.get("translated_at") or version.get("created_at")
        return {
            "id": chapter_id,
            "version_id": version.get("id"),
            "version_kind": self._normalize_version_kind(version.get("kind")),
            "provider": version.get("provider"),
            "model": version.get("model"),
            "created_at": created_at,
            "translated_at": translated_at,
            "text": version.get("text"),
            "editor": version.get("editor"),
            "note": version.get("note"),
            "confidence_score": version.get("confidence_score"),
            "glossary_revision": version.get("glossary_revision", 0)
            if isinstance(version.get("glossary_revision"), int)
            else 0,
        }

    return None


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

    metadata = self.load_metadata(novel_id) if hasattr(self, "load_metadata") else None
    snapshot = _resolve_glossary_snapshot_from_metadata(metadata)

    normalized: list[dict[str, Any]] = []
    for version in versions:
        item = dict(version)
        item["version_id"] = item.get("id")
        item["version_kind"] = self._normalize_version_kind(item.get("kind"))
        item["active"] = bool(active_id and item.get("id") == active_id)
        item.update(_attach_freshness_fields(item, snapshot))
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
    glossary_qa: dict[str, Any] | None = None,
    glossary_revision: int | None = None,
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
    if isinstance(glossary_qa, dict) and glossary_qa:
        edited_payload["glossary_qa"] = glossary_qa
    if isinstance(glossary_revision, int):
        edited_payload["glossary_revision"] = glossary_revision
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
    ids: set[str] = set()
    chapter_dir = self._novel_dir(novel_id) / self.CHAPTERS_DIRNAME
    if self._is_dir_present(chapter_dir):
        for chapter_path in self._glob(chapter_dir, "*.json"):
            try:
                payload = json.loads(self._read_text(chapter_path))
            except (json.JSONDecodeError, OSError):
                logger.debug("Skipping unreadable chapter file %s.", chapter_path)
                continue
            if isinstance(payload, dict) and isinstance(payload.get("translated"), dict):
                ids.add(self._logical_id_from_stem(chapter_path.stem))

    return sorted(ids)


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
