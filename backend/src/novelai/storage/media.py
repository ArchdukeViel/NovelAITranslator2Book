from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

from novelai.core.security import encode_physical_stem, safe_child_path, validate_storage_identifier
from novelai.storage.common import _UNSET

logger = logging.getLogger(__name__)

# Section 10/11: OCR / re-embedding state lives in a per-novel overlay
# directory (``novel_dir/media/``) parallel to the translation overlay,
# never inside the active raw generation snapshot. The raw generation's
# ``chapters/*.json`` bundles and ``assets/images/*`` tree are
# byte-immutable once committed; mutable derived state must be composed
# on read instead of written into the snapshot.
MEDIA_OVERLAY_SCHEMA_VERSION = "media_overlay_v1"

_MEDIA_OVERLAY_FIELDS = (
    "ocr_required",
    "ocr_text",
    "ocr_pages",
    "ocr_status",
    "reembed_status",
)


def _media_overlay_dir(self: Any, novel_id: str) -> Path:
    """Directory holding mutable media/OCR overlays for a novel."""
    overlay = self._novel_dir(novel_id) / "media"
    self._mkdirs(overlay)
    return overlay


def _media_overlay_path(self: Any, novel_id: str, chapter_id: str) -> Path:
    """File path for a chapter's media overlay payload."""
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    encoded_stem = encode_physical_stem(safe_chapter_id)
    return _media_overlay_dir(self, novel_id) / f"{encoded_stem}.json"


def _load_media_overlay(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Read the chapter's media overlay payload (``None`` when absent)."""
    path = _media_overlay_path(self, novel_id, chapter_id)
    if not self._path_exists(path):
        return None
    try:
        data = json.loads(self._read_text(path))
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to parse media overlay %s/%s.", novel_id, chapter_id)
        return None
    if not isinstance(data, dict):
        return None
    return self._normalize_media_fields(data)


def _save_media_overlay(self: Any, novel_id: str, chapter_id: str, payload: dict[str, Any]) -> Path:
    """Persist a media overlay payload atomically at the novel root."""
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    normalized = {key: payload.get(key, _UNSET) for key in _MEDIA_OVERLAY_FIELDS}
    stored: dict[str, Any] = {"schema_version": MEDIA_OVERLAY_SCHEMA_VERSION}
    for key, value in normalized.items():
        if value is not _UNSET:
            stored[key] = value
    path = _media_overlay_path(self, novel_id, safe_chapter_id)
    self._write_text_atomic(path, json.dumps(stored, ensure_ascii=False, indent=2))
    return path


def _chapter_image_dir(self: Any, novel_id: str, chapter_id: str) -> Path:
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    image_dir = self._content_root(novel_id) / "assets" / "images" / encode_physical_stem(safe_chapter_id)
    self._mkdirs(image_dir)
    return image_dir


def _asset_relative_path(self: Any, novel_id: str, path: Path) -> str:
    return path.relative_to(self._novel_dir(novel_id)).as_posix()


def _guess_asset_suffix(self: Any, source_url: str | None, content_type: str | None) -> str:
    if isinstance(content_type, str) and content_type.strip():
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            if guessed == ".jpe":
                return ".jpg"
            return guessed

    if isinstance(source_url, str) and source_url.strip():
        suffix = Path(source_url.split("?", 1)[0]).suffix.lower()
        if suffix:
            return suffix

    return ".bin"


def clear_chapter_image_assets(self: Any, novel_id: str, chapter_id: str) -> None:
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    image_dir = self._content_root(novel_id) / "assets" / "images" / encode_physical_stem(safe_chapter_id)
    if self._path_exists(image_dir):
        self._rmtree(image_dir)


def save_chapter_image_asset(
    self: Any,
    novel_id: str,
    chapter_id: str,
    *,
    image_index: int,
    content: bytes,
    source_url: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    suffix = self._guess_asset_suffix(source_url, content_type)
    filename = f"{image_index:04d}{suffix}"
    path = self._chapter_image_dir(novel_id, chapter_id) / filename
    self._backend.save(self._rel(path), content)
    return {
        "local_path": self._asset_relative_path(novel_id, path),
        "content_type": content_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def resolve_asset_path(self: Any, novel_id: str, local_path: str | None) -> Path | None:
    """Resolve a logical asset ``local_path`` to an on-disk ``Path``.

    Looks under the active generation's ``assets/images/...`` layout.
    The legacy novel-root layout is consulted *only* when no active
    generation exists (Section 10/11: with a committed snapshot the
    snapshot is authoritative and legacy fallback must not silently
    resolve into mutable novel-root state). Returns ``None`` when the
    path is empty or unsafe.

    The ``local_path`` may contain percent-escapes from the chapter-identity
    codec (e.g. ``kakuyomu%3A...``); ``safe_child_path`` keeps those intact
    while still rejecting path traversal.
    """
    if not isinstance(local_path, str) or not local_path.strip():
        return None

    # The active generation's staged ``assets/`` tree mirrors the logical
    # local_path exactly (Section 2 contract).
    try:
        active_manifest = self.get_active_generation(novel_id)
    except Exception:
        active_manifest = None
    if active_manifest is not None and getattr(active_manifest, "generation_id", None):
        gen_path = safe_child_path(
            self._generations_dir(novel_id) / str(active_manifest.generation_id),
            local_path,
            unquote=False,
        )
        if gen_path is not None and self._path_exists(gen_path):
            return gen_path
        # An active generation exists but the asset is not inside it:
        # never fall back to the legacy novel-root layout.
        return None

    # Legacy layout: novels without an active generation still store
    # assets directly under the novel directory.
    return safe_child_path(self._novel_dir(novel_id), local_path, unquote=False)


def _normalize_media_fields(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
    ocr_required = bool(payload.get("ocr_required", False))

    ocr_status = payload.get("ocr_status")
    if ocr_status not in self.OCR_STATUSES:
        ocr_status = "pending" if ocr_required else "skipped"

    reembed_status = payload.get("reembed_status")
    if reembed_status not in self.REEMBED_STATUSES:
        reembed_status = "skipped"

    payload["ocr_required"] = ocr_required
    payload["ocr_text"] = payload.get("ocr_text") if isinstance(payload.get("ocr_text"), str) else None
    raw_pages = payload.get("ocr_pages")
    normalized_pages: list[dict[str, Any]] = []
    if isinstance(raw_pages, list):
        for index, page in enumerate(raw_pages, start=1):
            if not isinstance(page, dict):
                continue
            page_text = page.get("text") if isinstance(page.get("text"), str) else ""
            page_status = page.get("status")
            if page_status not in self.OCR_STATUSES:
                page_status = "pending" if ocr_required else "skipped"
            normalized_pages.append(
                {
                    "page": int(page.get("page", index)) if str(page.get("page", index)).isdigit() else index,
                    "text": page_text,
                    "status": page_status,
                }
            )
    payload["ocr_pages"] = normalized_pages
    payload["ocr_status"] = ocr_status
    payload["reembed_status"] = reembed_status
    payload["input_adapter_key"] = self._clean_string(payload.get("input_adapter_key"))
    payload["origin_type"] = self._clean_string(payload.get("origin_type"), "web")
    payload["origin_uri_or_path"] = self._clean_string(payload.get("origin_uri_or_path"))
    payload["document_type"] = self._clean_string(payload.get("document_type"), "web_novel")
    payload["unit_type"] = self._clean_string(payload.get("unit_type"), "chapter")
    payload["import_order"] = self._normalize_optional_int(payload.get("import_order"))
    payload["context_group_id"] = self._clean_string(payload.get("context_group_id"))
    payload["region_metadata"] = self._normalize_named_dict_items(payload.get("region_metadata"))
    payload["ocr_artifacts"] = self._normalize_named_dict_items(payload.get("ocr_artifacts"))
    return payload


def load_chapter_media_state(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Load OCR and re-embedding fields for a chapter bundle.

    Composes the raw chapter bundle's media fields with the novel-root
    media overlay; the overlay (mutable derived state) wins over the
    bundle (committed snapshot) whenever both exist. Returns ``None``
    when neither the bundle nor the overlay exists.
    """
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    overlay = self._load_media_overlay(novel_id, chapter_id)
    if payload is None and overlay is None:
        return None

    result = {
        "id": chapter_id,
        "input_adapter_key": payload.get("input_adapter_key") if payload else None,
        "origin_type": payload.get("origin_type") if payload else None,
        "origin_uri_or_path": payload.get("origin_uri_or_path") if payload else None,
        "document_type": payload.get("document_type") if payload else None,
        "unit_type": payload.get("unit_type") if payload else None,
        "import_order": payload.get("import_order") if payload else None,
        "context_group_id": payload.get("context_group_id") if payload else None,
        "region_metadata": self._normalize_named_dict_items(payload.get("region_metadata")) if payload else [],
        "ocr_artifacts": self._normalize_named_dict_items(payload.get("ocr_artifacts")) if payload else [],
        "ocr_required": payload.get("ocr_required", False) if payload else False,
        "ocr_text": payload.get("ocr_text") if payload else None,
        "ocr_pages": payload.get("ocr_pages") if payload and isinstance(payload.get("ocr_pages"), list) else [],
        "ocr_status": payload.get("ocr_status", "skipped") if payload else "skipped",
        "reembed_status": payload.get("reembed_status", "skipped") if payload else "skipped",
    }
    if overlay is not None:
        for key in _MEDIA_OVERLAY_FIELDS:
            if key in overlay:
                result[key] = overlay[key]
        if isinstance(overlay.get("ocr_pages"), list):
            result["ocr_pages"] = overlay["ocr_pages"]
    return result


def save_chapter_media_state(
    self: Any,
    novel_id: str,
    chapter_id: str,
    *,
    ocr_required: bool | object = _UNSET,
    ocr_text: str | object | None = _UNSET,
    ocr_pages: list[dict[str, Any]] | object = _UNSET,
    ocr_status: str | object = _UNSET,
    reembed_status: str | object = _UNSET,
) -> Path:
    """Update OCR and re-embedding fields in the novel-root media overlay.

    Never writes into the raw chapter bundle: the committed generation's
    ``chapters/*.json`` payloads are byte-immutable (Section 10/11), so
    derived OCR state is persisted to the per-novel ``media/`` overlay and
    composed on read.
    """
    previous = self._load_media_overlay(novel_id, chapter_id) or {}
    payload: dict[str, Any] = dict(previous)
    if ocr_required is not _UNSET:
        payload["ocr_required"] = bool(ocr_required)
    if ocr_text is not _UNSET:
        payload["ocr_text"] = ocr_text
    if ocr_pages is not _UNSET:
        payload["ocr_pages"] = ocr_pages
    if ocr_status is not _UNSET:
        payload["ocr_status"] = ocr_status
    if reembed_status is not _UNSET:
        payload["reembed_status"] = reembed_status

    return self._save_media_overlay(novel_id, chapter_id, payload)
