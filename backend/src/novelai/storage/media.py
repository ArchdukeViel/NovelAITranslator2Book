from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path
from typing import Any

from novelai.storage.common import _UNSET


def _chapter_image_dir(self: Any, novel_id: str, chapter_id: str) -> Path:
    image_dir = self._novel_dir(novel_id) / "assets" / "images" / str(chapter_id)
    image_dir.mkdir(parents=True, exist_ok=True)
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
    image_dir = self._novel_dir(novel_id) / "assets" / "images" / str(chapter_id)
    if image_dir.exists():
        shutil.rmtree(image_dir, ignore_errors=True)


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
    path.write_bytes(content)
    return {
        "local_path": self._asset_relative_path(novel_id, path),
        "content_type": content_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def resolve_asset_path(self: Any, novel_id: str, local_path: str | None) -> Path | None:
    if not isinstance(local_path, str) or not local_path.strip():
        return None
    return self._novel_dir(novel_id) / Path(local_path)


def load_chapter_export_images(self: Any, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
    """Return chapter image metadata augmented with resolved local asset paths."""
    chapter = self.load_chapter(novel_id, chapter_id) or {}
    images_value = chapter.get("images")
    raw_images: list[Any] = images_value if isinstance(images_value, list) else []
    export_images: list[dict[str, Any]] = []

    for image in raw_images:
        if not isinstance(image, dict):
            continue
        entry = dict(image)
        asset_path = self.resolve_asset_path(novel_id, entry.get("local_path"))
        entry["asset_path"] = str(asset_path) if asset_path is not None and asset_path.exists() else None
        export_images.append(entry)

    return self._normalize_image_manifest(export_images)


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
    """Load OCR and re-embedding fields for a chapter bundle."""
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return None

    return {
        "id": chapter_id,
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
        "ocr_pages": payload.get("ocr_pages") if isinstance(payload.get("ocr_pages"), list) else [],
        "ocr_status": payload.get("ocr_status", "skipped"),
        "reembed_status": payload.get("reembed_status", "skipped"),
    }


def save_chapter_media_state(
    self: Any,
    novel_id: str,
    chapter_id: str,
    *,
    ocr_required: bool | object = _UNSET,
    ocr_text: str | None | object = _UNSET,
    ocr_pages: list[dict[str, Any]] | object = _UNSET,
    ocr_status: str | object = _UNSET,
    reembed_status: str | object = _UNSET,
) -> Path:
    """Update OCR and re-embedding fields while preserving chapter content blocks."""
    payload: dict[str, Any] = self._load_chapter_bundle(novel_id, chapter_id) or {"id": chapter_id}

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

    return self._persist_chapter_bundle(novel_id, chapter_id, payload)
