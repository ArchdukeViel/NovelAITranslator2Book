"""Translation overlay storage (Section 6 contract).

Translations live outside the committed raw generation bundle so that
editing, re-running, or QA-rejecting translations never mutates the
raw bytes the activated raw-generation directory holds.

Overlay layout per novel::

    novels/<novel_id>/translations/
        active/
            <encoded-chapter-stem>.json       # {chapter_id, version_id, …}
        <encoded-chapter-stem>.json          # full overlay payload

The overlay file owns every translation-specific field (``text``,
``provider_*``, ``glossary_*``, ``version_id``, ``translation_versions``,
``active_translation_version_id``, ``edit_history``, ``confidence_*``).
The raw ``chapters/<id>.json`` file is byte-immutable after
:func:`commit_generation` activates the generation: readers compose
the active translation overlay with the raw bundle's non-translation
metadata fields (``origin_type``, ``document_type``, …) when
serving a translation.

Legacy chapter bundles that still carry
``translation_versions`` continue to be readable as a fallback so
older novels don't see a regression while the migration rolls out.
When a chapter has both a legacy bundle entry and an overlay, the
overlay wins (newer state), and the
:meth:`save_translated_chapter` migration copy ensures the overlay
gets populated automatically on the next write.

Activation tie-in: ``commit_generation`` does not touch translation
overlay files because those live at the novel root and have no
relationship to the activated generation snapshot. Generation
manifests do not enumerate translation-version ids — they only
reference raw bundle ids.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.core.platform import ChapterVersionKind
from novelai.storage.common import _utc_now_iso

logger = logging.getLogger(__name__)


# Public alias so callers can reference the field without an import cycle.
OVERLAY_SCHEMA_VERSION = "translation_overlay_v1"


def _resolve_glossary_snapshot_from_metadata(
    metadata: dict[str, Any] | None,
) -> Any:
    """Resolve a GlossarySnapshot from novel metadata if available."""
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
    """Return a copy of ``version`` with glossary freshness fields attached."""
    from novelai.translation.glossary_freshness import compute_glossary_freshness

    result = dict(version)
    result.update(compute_glossary_freshness(version, snapshot))
    return result


def _normalized_version_payload(translated: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized translation version record from caller-supplied kwargs."""
    version_id = translated.get("version_id")
    version_kind = translated.get("version_kind")
    glossary_revision = translated.get("glossary_revision")
    if not isinstance(version_id, str) or not version_id:
        raise ValueError("Translation version requires version_id")
    if not isinstance(version_kind, str) or version_kind not in {kind.value for kind in ChapterVersionKind}:
        raise ValueError("Translation version requires a valid version_kind")
    if type(glossary_revision) is not int or glossary_revision < 0:
        raise ValueError("Translation version requires a non-negative glossary_revision")
    raw_text = translated.get("text")
    created_at = translated.get("created_at") if isinstance(translated.get("created_at"), str) else None
    if not isinstance(raw_text, str) or not created_at:
        raise ValueError("Translation version requires text and created_at")

    version: dict[str, Any] = {
        "version_id": version_id,
        "version_kind": version_kind,
        "provider_key": translated.get("provider_key"),
        "provider_model": translated.get("provider_model"),
        "created_at": created_at,
        "translated_at": translated.get("translated_at") or created_at,
        "text": raw_text,
        "paragraphs": translated.get("paragraphs"),
        "glossary_revision": glossary_revision,
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
    if isinstance(translated.get("glossary_injected_term_count"), int):
        version["glossary_injected_term_count"] = translated["glossary_injected_term_count"]
    if isinstance(translated.get("prompt_template_version"), str) and translated["prompt_template_version"]:
        version["prompt_template_version"] = translated["prompt_template_version"]
    if isinstance(translated.get("glossary_hash"), str) and translated["glossary_hash"]:
        version["glossary_hash"] = translated["glossary_hash"]
    if isinstance(translated.get("batch_id"), str) and translated["batch_id"]:
        version["batch_id"] = translated["batch_id"]
    if isinstance(translated.get("qa_status"), str):
        version["qa_status"] = translated["qa_status"]
    if isinstance(translated.get("qa_score"), (int, float)):
        version["qa_score"] = translated["qa_score"]
    if isinstance(translated.get("qa_warnings"), list):
        version["qa_warnings"] = list(translated["qa_warnings"])
    if isinstance(translated.get("qa_errors"), list):
        version["qa_errors"] = list(translated["qa_errors"])
    return version


def _build_overlay_payload(
    translation_versions: list[dict[str, Any]],
    *,
    active_translation_version_id: str | None,
    edit_history: list[dict[str, Any]] | None,
    prompt_template_version: str | None,
    glossary_hash: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "translation_versions": list(translation_versions),
        "active_translation_version_id": active_translation_version_id,
        "edit_history": list(edit_history or []),
        "prompt_template_version": prompt_template_version or "",
        "glossary_hash": glossary_hash or "",
    }


def _load_translation_overlay(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Read the chapter's overlay payload (returns ``None`` when absent)."""
    path = self._translation_overlay_path(novel_id, chapter_id)
    if not self._path_exists(path):
        return None
    try:
        return json.loads(self._read_text(path))
    except Exception as exc:
        logger.warning("Failed to parse translation overlay %s/%s: %s", novel_id, chapter_id, exc)
        return None


def _persist_translation_overlay(
    self: Any,
    novel_id: str,
    chapter_id: str,
    payload: dict[str, Any],
) -> Any:
    payload = dict(payload)
    payload["schema_version"] = "translation_overlay_v1"
    versions = payload.get("translation_versions") or []
    seen: set[str] = set()
    for version in versions:
        if not isinstance(version, dict):
            continue
        version_id = version.get("version_id")
        if not isinstance(version_id, str) or not version_id:
            continue
        if version_id in seen:
            raise ValueError(f"Duplicate translation version_id: {version_id}")
        seen.add(version_id)
    path = self._translation_overlay_path(novel_id, chapter_id)
    self._write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def _next_translation_version_id(existing_versions: list[dict[str, Any]]) -> str:
    seen_max = -1
    for version in existing_versions:
        version_id = version.get("version_id") if isinstance(version, dict) else None
        if not isinstance(version_id, str):
            continue
        try:
            numeric = int(version_id)
        except ValueError:
            continue
        if numeric > seen_max:
            seen_max = numeric
    return f"{seen_max + 1:04d}"


def _normalize_version_kind(kind: Any) -> str:
    if isinstance(kind, ChapterVersionKind):
        return kind.value
    if isinstance(kind, str) and kind in {item.value for item in ChapterVersionKind}:
        return kind
    return ChapterVersionKind.MACHINE_TRANSLATION.value


def save_translated_chapter(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    provider_key: str | None = None,
    provider_model: str | None = None,
    confidence_score: float | None = None,
    polish_needed: bool | None = None,
    confidence_details: dict[str, Any] | None = None,
    source_hash: str | None = None,
    glossary_revision: int = 0,
    glossary_injected_term_count: int | None = None,
    version_kind: ChapterVersionKind = ChapterVersionKind.MACHINE_TRANSLATION,
    prompt_template_version: str | None = None,
    glossary_hash: str | None = None,
    batch_id: str | None = None,
    base_version_id: str | None = None,
    auto_activate: bool = True,
) -> Any:
    """Persist a translation version into the per-chapter overlay.

    The raw chapter bundle is never modified here. ``save_translated_chapter``
    loads any existing overlay state, appends a new version, optionally
    promotes it to active, and writes the overlay back. Reading paths
    (load_translated_chapter / list_translated_chapter_versions / …)
    compose this overlay with the raw bundle's non-translation fields.

    Returns the path the overlay was written to.
    """
    if not isinstance(version_kind, ChapterVersionKind):
        raise TypeError("version_kind must be ChapterVersionKind")
    if type(glossary_revision) is not int or glossary_revision < 0:
        raise ValueError("glossary_revision must be a non-negative integer")
    if provider_key is not None and not isinstance(provider_key, str):
        raise TypeError("provider_key must be a string or None")
    if provider_model is not None and not isinstance(provider_model, str):
        raise TypeError("provider_model must be a string or None")

    overlay = self._load_translation_overlay(novel_id, chapter_id) or _build_overlay_payload(
        translation_versions=[],
        active_translation_version_id=None,
        edit_history=[],
        prompt_template_version=None,
        glossary_hash=None,
    )
    overlay["chapter_id"] = chapter_id
    versions = list(overlay.get("translation_versions") or [])
    created_at = _utc_now_iso()
    translated_payload: dict[str, Any] = {
        "version_id": _next_translation_version_id(versions),
        "version_kind": _normalize_version_kind(version_kind),
        "provider_key": provider_key,
        "provider_model": provider_model,
        "created_at": created_at,
        "translated_at": created_at,
        "text": text,
        "paragraphs": self._text_paragraphs(text),
        "glossary_revision": glossary_revision,
    }
    if isinstance(source_hash, str) and source_hash.strip():
        translated_payload["source_hash"] = source_hash.strip()
    if isinstance(confidence_score, float):
        translated_payload["confidence_score"] = max(0.0, min(1.0, confidence_score))
    if isinstance(polish_needed, bool):
        translated_payload["polish_needed"] = polish_needed
    if isinstance(confidence_details, dict):
        translated_payload["confidence_details"] = dict(confidence_details)
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
    overlay["translation_versions"] = versions
    overlay["chapter_id"] = chapter_id
    overlay["prompt_template_version"] = translated_payload.get(
        "prompt_template_version", overlay.get("prompt_template_version", "")
    )
    overlay["glossary_hash"] = translated_payload.get("glossary_hash", overlay.get("glossary_hash", ""))
    if auto_activate:
        overlay["active_translation_version_id"] = translated_payload["version_id"]
    else:
        logger.warning(
            "Chapter %s/%s saved with low confidence (%.2f), not activated. Use activate endpoint to promote.",
            novel_id,
            chapter_id,
            confidence_score or 0.0,
        )
    return self._persist_translation_overlay(novel_id, chapter_id, overlay)


def load_translated_chapter(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Compose raw bundle metadata with the active translation overlay.

    Reads the raw chapter bundle for non-translation metadata fields
    (origin, document_type, ocr, …), and the per-chapter overlay for
    ``text``, ``version_id``, ``provider_*``, ``glossary_*``, …
    Returns ``None`` when neither the raw bundle nor the overlay has an
    active translation. A stored-but-not-activated version still
    appears in :func:`list_translated_chapter_versions` (with
    ``active=False``).
    """
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    overlay = self._load_translation_overlay(novel_id, chapter_id) or {}
    if overlay and isinstance(overlay, dict):
        versions = list(overlay.get("translation_versions") or [])
        active_id = overlay.get("active_translation_version_id")
        if not isinstance(active_id, str):
            return None
        translated = None
        for version in versions:
            if isinstance(version, dict) and version.get("version_id") == active_id:
                translated = version
                break
        if not isinstance(translated, dict):
            return None
    else:
        if payload is None:
            return None
        versions_legacy = self._translation_versions_from_payload_compat(payload)
        active_id_legacy = payload.get("active_translation_version_id") if isinstance(payload, dict) else None
        if not isinstance(active_id_legacy, str):
            return None
        translated = None
        for version in versions_legacy:
            if isinstance(version, dict) and version.get("version_id") == active_id_legacy:
                translated = version
                break
        if not isinstance(translated, dict):
            return None
    # Compose raw non-translation metadata for the response.
    if payload is None:
        # Bare overlay, no raw bundle yet — only minimal fields survive.
        metadata_source: dict[str, Any] = {}
    else:
        metadata_source = payload if isinstance(payload, dict) else {}

    metadata = self.load_metadata(novel_id) if hasattr(self, "load_metadata") else None
    snapshot = _resolve_glossary_snapshot_from_metadata(metadata)
    version_with_freshness = _attach_freshness_fields(translated, snapshot)

    return {
        "chapter_id": chapter_id,
        "version_id": translated.get("version_id"),
        "version_kind": translated.get("version_kind"),
        "provider_key": translated.get("provider_key"),
        "provider_model": translated.get("provider_model"),
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
        "input_adapter_key": metadata_source.get("input_adapter_key"),
        "origin_type": metadata_source.get("origin_type"),
        "origin_uri_or_path": metadata_source.get("origin_uri_or_path"),
        "document_type": metadata_source.get("document_type"),
        "unit_type": metadata_source.get("unit_type"),
        "import_order": metadata_source.get("import_order"),
        "context_group_id": metadata_source.get("context_group_id"),
        "region_metadata": self._normalize_named_dict_items(metadata_source.get("region_metadata")),
        "ocr_artifacts": self._normalize_named_dict_items(metadata_source.get("ocr_artifacts")),
        "ocr_required": metadata_source.get("ocr_required", False),
        "ocr_text": metadata_source.get("ocr_text"),
        "ocr_status": metadata_source.get("ocr_status", "skipped"),
        "reembed_status": metadata_source.get("reembed_status", "skipped"),
        "glossary_freshness": version_with_freshness.get("glossary_freshness"),
        "glossary_stale": version_with_freshness.get("glossary_stale"),
        "glossary_stale_reason": version_with_freshness.get("glossary_stale_reason"),
        "current_glossary_revision": version_with_freshness.get("current_glossary_revision"),
        "current_glossary_hash": version_with_freshness.get("current_glossary_hash"),
    }


def _translation_versions_from_payload_compat(
    self: Any,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_versions = payload.get("translation_versions")
    if not isinstance(raw_versions, list):
        return []
    versions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_versions:
        if not isinstance(raw, dict):
            continue
        version_id = raw.get("version_id")
        if isinstance(version_id, str) and version_id:
            if version_id in seen:
                raise ValueError(f"Duplicate translation version_id: {version_id}")
            seen.add(version_id)
        versions.append(_normalized_version_payload(raw))
    return versions


def load_translated_chapter_by_version_id(
    self: Any,
    novel_id: str,
    chapter_id: str,
    version_id: str,
) -> dict[str, Any] | None:
    overlay = self._load_translation_overlay(novel_id, chapter_id)
    if isinstance(overlay, dict):
        for version in overlay.get("translation_versions") or []:
            if isinstance(version, dict) and version.get("version_id") == version_id:
                created_at = version.get("created_at") or version.get("translated_at")
                translated_at = version.get("translated_at") or version.get("created_at")
                return {
                    "chapter_id": chapter_id,
                    "version_id": version_id,
                    "version_kind": version.get("version_kind"),
                    "provider_key": version.get("provider_key"),
                    "provider_model": version.get("provider_model"),
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
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if not isinstance(payload, dict):
        return None
    for version in self._translation_versions_from_payload_compat(payload):
        if version.get("version_id") == version_id:
            created_at = version.get("created_at") or version.get("translated_at")
            translated_at = version.get("translated_at") or version.get("created_at")
            return {
                "chapter_id": chapter_id,
                "version_id": version_id,
                "version_kind": version.get("version_kind"),
                "provider_key": version.get("provider_key"),
                "provider_model": version.get("provider_model"),
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
    overlay = self._load_translation_overlay(novel_id, chapter_id) or {}
    if overlay and isinstance(overlay, dict):
        versions = [
            _normalized_version_payload(v) for v in (overlay.get("translation_versions") or []) if isinstance(v, dict)
        ]
        active_id = overlay.get("active_translation_version_id")
    else:
        payload = self._load_chapter_bundle(novel_id, chapter_id)
        versions = self._translation_versions_from_payload_compat(payload) if isinstance(payload, dict) else []
        active_id = payload.get("active_translation_version_id") if isinstance(payload, dict) else None

    metadata = self.load_metadata(novel_id) if hasattr(self, "load_metadata") else None
    snapshot = _resolve_glossary_snapshot_from_metadata(metadata)

    normalized: list[dict[str, Any]] = []
    for version in versions:
        item = dict(version)
        item["active"] = bool(active_id and item.get("version_id") == active_id)
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
    glossary_revision: int,
) -> Any:
    """Persist a manual translation edit as a new active version in the overlay."""
    if type(glossary_revision) is not int or glossary_revision < 0:
        raise ValueError("glossary_revision must be a non-negative integer")
    overlay = self._load_translation_overlay(novel_id, chapter_id) or _build_overlay_payload(
        translation_versions=[],
        active_translation_version_id=None,
        edit_history=[],
        prompt_template_version=None,
        glossary_hash=None,
    )
    versions = list(overlay.get("translation_versions") or [])
    previous_id = overlay.get("active_translation_version_id")
    previous_provider_key = None
    previous_provider_model = None
    for version in versions:
        if isinstance(version, dict) and version.get("version_id") == previous_id:
            previous_provider_key = version.get("provider_key")
            previous_provider_model = version.get("provider_model")
            break
    created_at = _utc_now_iso()
    edited_payload: dict[str, Any] = {
        "version_id": _next_translation_version_id(versions),
        "version_kind": ChapterVersionKind.MANUAL_EDIT.value,
        "provider_key": previous_provider_key,
        "provider_model": previous_provider_model,
        "created_at": created_at,
        "translated_at": created_at,
        "text": text,
        "paragraphs": self._text_paragraphs(text),
        "base_version_id": previous_id,
        "glossary_revision": glossary_revision,
    }
    if isinstance(editor, str) and editor.strip():
        edited_payload["editor"] = editor.strip()
    if isinstance(note, str) and note.strip():
        edited_payload["note"] = note.strip()
    if isinstance(glossary_qa, dict) and glossary_qa:
        edited_payload["glossary_qa"] = glossary_qa
    versions.append(edited_payload)
    overlay["translation_versions"] = versions
    overlay["chapter_id"] = chapter_id
    overlay["active_translation_version_id"] = edited_payload["version_id"]
    history = list(overlay.get("edit_history") or [])
    history.append(
        {
            "id": f"e{len(history) + 1}",
            "action": ChapterVersionKind.MANUAL_EDIT.value,
            "version_id": edited_payload["version_id"],
            "previous_version_id": previous_id,
            "created_at": created_at,
            "editor": edited_payload.get("editor"),
            "note": edited_payload.get("note"),
        }
    )
    overlay["edit_history"] = history
    return self._persist_translation_overlay(novel_id, chapter_id, overlay)


def load_translation_edit_history(self: Any, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
    overlay = self._load_translation_overlay(novel_id, chapter_id) or {}
    if overlay and isinstance(overlay, dict):
        return list(overlay.get("edit_history") or [])
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if not isinstance(payload, dict):
        return []
    return list(payload.get("edit_history") or [])


def list_translated_chapters(self: Any, novel_id: str) -> list[str]:
    ids: set[str] = set()
    overlay_root = self._novel_dir(novel_id) / "translations"
    if self._is_dir_present(overlay_root):
        for entry in self._glob(overlay_root, "*.json"):
            stem = entry.stem
            if stem == "active":
                continue
            try:
                payload = json.loads(self._read_text(entry))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            chapter_id = payload.get("chapter_id") or stem
            if isinstance(chapter_id, str) and chapter_id and payload.get("active_translation_version_id"):
                ids.add(chapter_id)
    chapter_dir = self._content_root(novel_id) / "chapters"
    if self._is_dir_present(chapter_dir):
        for chapter_path in self._glob(chapter_dir, "*.json"):
            try:
                payload = json.loads(self._read_text(chapter_path))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            versions = _translation_versions_from_payload_compat(self, payload)
            if versions and isinstance(payload.get("active_translation_version_id"), str):
                ids.add(self.logical_id_from_stem(chapter_path.stem))
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
    overlay = self._load_translation_overlay(novel_id, chapter_id)
    if isinstance(overlay, dict) and overlay.get("translation_versions"):
        versions = list(overlay.get("translation_versions") or [])
        target = next(
            (v for v in versions if isinstance(v, dict) and v.get("version_id") == version_id),
            None,
        )
        if target is None:
            return False
        previous_id = overlay.get("active_translation_version_id")
        overlay["active_translation_version_id"] = version_id
        history = list(overlay.get("edit_history") or [])
        history.append(
            {
                "id": f"e{len(history) + 1}",
                "action": ChapterVersionKind.ROLLBACK.value,
                "version_id": version_id,
                "previous_version_id": previous_id,
                "created_at": _utc_now_iso(),
                "editor": editor.strip() if isinstance(editor, str) and editor.strip() else None,
                "note": note.strip() if isinstance(note, str) and note.strip() else None,
            }
        )
        overlay["edit_history"] = history
        self._persist_translation_overlay(novel_id, chapter_id, overlay)
        return True
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if not isinstance(payload, dict):
        return False
    versions = _translation_versions_from_payload_compat(self, payload)
    target = next((v for v in versions if v.get("version_id") == version_id), None)
    if target is None:
        return False
    previous = next(
        (
            v
            for v in versions
            if isinstance(payload.get("active_translation_version_id"), str)
            and v.get("version_id") == payload.get("active_translation_version_id")
        ),
        None,
    )
    previous_version_id = previous.get("version_id") if isinstance(previous, dict) else None
    raw_versions = payload.get("translation_versions")
    if not isinstance(raw_versions, list):
        return False
    for raw in raw_versions:
        if isinstance(raw, dict) and raw.get("version_id") == version_id:
            raw["active"] = True
    payload["translation_versions"] = raw_versions
    payload["active_translation_version_id"] = version_id
    history = list(payload.get("edit_history") or [])
    history.append(
        {
            "id": f"e{len(history) + 1}",
            "action": ChapterVersionKind.ROLLBACK.value,
            "version_id": version_id,
            "previous_version_id": previous_version_id,
            "created_at": _utc_now_iso(),
            "editor": editor.strip() if isinstance(editor, str) and editor.strip() else None,
            "note": note.strip() if isinstance(note, str) and note.strip() else None,
        }
    )
    payload["edit_history"] = history
    self._persist_chapter_bundle(novel_id, chapter_id, payload)
    return True


def save_translation_run_manifest(self: Any, novel_id: str, manifest: Any) -> Path:
    """Save a translation run manifest tracking execution parameters and input hashes."""
    g_dir = self._generations_dir(novel_id)
    manifest_path = g_dir / f"translation_run_{manifest.translation_run_id}.json"
    self._write_text_atomic(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return manifest_path


def load_translation_run_manifest(self: Any, novel_id: str, translation_run_id: str) -> Any | None:
    from novelai.translation.run_manifest import TranslationRunManifest

    g_dir = self._generations_dir(novel_id)
    manifest_path = g_dir / f"translation_run_{translation_run_id}.json"
    if not self._path_exists(manifest_path):
        return None
    try:
        return TranslationRunManifest.from_dict(json.loads(self._read_text(manifest_path)))
    except Exception as exc:
        logger.warning("Failed to load translation run manifest for %s/%s: %s", novel_id, translation_run_id, exc)
        return None
