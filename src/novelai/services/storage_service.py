from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from novelai.config.settings import settings
from novelai.config.workflow_profiles import normalize_workflow_profiles
from novelai.core.chapter_state import ChapterState, ChapterStateTransition
from novelai.services.query_builder import ChapterQueryBuilder
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)
_UNSET = object()


class CheckpointInfo(TypedDict):
    """Validated checkpoint metadata returned from storage."""

    filename: str
    timestamp: str
    checkpoint_name: str


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return _utc_now().isoformat().replace("+00:00", "Z")


class StorageService:
    """Filesystem-backed storage service.

    Each novel is stored in a folder under `novel_library/novels/<novel_id>`.
    The folder name is a stable filesystem-safe variant of the novel ID.

    The folder contains:
      - metadata.json
      - chapters/<chapter_id>.json

    A simple index file keeps the mapping from novel ID to folder name.
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

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.novels_dir = self.base_dir / "novels"
        self.novels_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.novels_dir / self.INDEX_FILENAME

    def _load_index(self) -> dict[str, dict[str, Any]]:
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupted novel index at %s; resetting to empty.", path)
            return {}

    def _persist_index(self, index: dict[str, dict[str, Any]]) -> None:
        path = self._index_path()
        atomic_write(path, json.dumps(index, ensure_ascii=False, indent=2))

    def _compute_folder_name(self, novel_id: str, metadata: dict[str, Any]) -> str:
        """Return a stable folder name for a novel."""
        return self._sanitize_folder_name(novel_id)

    def _get_folder_name(self, novel_id: str) -> str:
        index = self._load_index()
        entry = index.get(novel_id, {})
        return entry.get("folder_name", novel_id)

    def _novel_dir(self, novel_id: str) -> Path:
        folder = self._get_folder_name(novel_id)
        return self.novels_dir / folder

    def build_export_path(
        self,
        novel_id: str,
        export_format: str,
        output_dir: str | Path | None = None,
    ) -> Path:
        """Resolve where an export should be written."""
        if output_dir is not None:
            custom_dir = Path(output_dir).expanduser()
            custom_dir.mkdir(parents=True, exist_ok=True)
            return custom_dir / f"{novel_id}.{export_format}"

        novel_dir = self._novel_dir(novel_id)
        novel_dir.mkdir(parents=True, exist_ok=True)
        return novel_dir / f"full_novel.{export_format}"

    def _ensure_novel_dir(self, novel_id: str, folder_name: str) -> Path:
        """Ensure the novel directory exists and the index is updated."""
        index = self._load_index()
        entry = index.get(novel_id, {})
        old_folder = entry.get("folder_name")

        # If the folder name has changed, rename the existing folder to preserve data.
        if old_folder and old_folder != folder_name:
            old_dir = self.novels_dir / old_folder
            new_dir = self.novels_dir / folder_name
            if old_dir.exists() and not new_dir.exists():
                shutil.move(str(old_dir), str(new_dir))
            elif old_dir.exists() and new_dir.exists():
                for child in old_dir.iterdir():
                    target = new_dir / child.name
                    if not target.exists():
                        shutil.move(str(child), str(target))
                        continue
                    if child.is_dir() and target.is_dir():
                        for nested in child.iterdir():
                            nested_target = target / nested.name
                            if not nested_target.exists():
                                shutil.move(str(nested), str(nested_target))
                shutil.rmtree(old_dir, ignore_errors=True)

        novel_dir = self.novels_dir / folder_name
        novel_dir.mkdir(parents=True, exist_ok=True)

        index[novel_id] = {
            "folder_name": folder_name,
            "updated_at": _utc_now_iso(),
        }
        self._persist_index(index)
        return novel_dir

    def _chapter_dir(self, novel_id: str) -> Path:
        chapter_dir = self._novel_dir(novel_id) / self.CHAPTERS_DIRNAME
        chapter_dir.mkdir(parents=True, exist_ok=True)
        return chapter_dir

    def _chapter_path(self, novel_id: str, chapter_id: str) -> Path:
        return self._chapter_dir(novel_id) / f"{chapter_id}.json"

    def _chapter_image_dir(self, novel_id: str, chapter_id: str) -> Path:
        image_dir = self._novel_dir(novel_id) / "assets" / "images" / str(chapter_id)
        image_dir.mkdir(parents=True, exist_ok=True)
        return image_dir

    def _asset_relative_path(self, novel_id: str, path: Path) -> str:
        return path.relative_to(self._novel_dir(novel_id)).as_posix()

    def _guess_asset_suffix(self, source_url: str | None, content_type: str | None) -> str:
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

    def clear_chapter_image_assets(self, novel_id: str, chapter_id: str) -> None:
        image_dir = self._novel_dir(novel_id) / "assets" / "images" / str(chapter_id)
        if image_dir.exists():
            shutil.rmtree(image_dir, ignore_errors=True)

    def save_chapter_image_asset(
        self,
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

    def resolve_asset_path(self, novel_id: str, local_path: str | None) -> Path | None:
        if not isinstance(local_path, str) or not local_path.strip():
            return None
        return self._novel_dir(novel_id) / Path(local_path)

    def load_chapter_export_images(self, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
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
    def _normalize_optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _load_legacy_raw_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        json_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.txt"

        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Failed to parse legacy raw chapter %s/%s.", novel_id, chapter_id)
                return None

        if txt_path.exists():
            return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}
        return None

    def _load_legacy_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        json_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.txt"

        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Failed to parse legacy translated chapter %s/%s.", novel_id, chapter_id)
                return None

        if txt_path.exists():
            return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}
        return None

    def _load_chapter_bundle(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        """Load a chapter bundle (raw + translated + metadata) from disk.

        Falls back to legacy ``raw/`` and ``translated/`` directories if the
        unified bundle file does not exist.
        """
        chapter_path = self._novel_dir(novel_id) / self.CHAPTERS_DIRNAME / f"{chapter_id}.json"
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

        bundle: dict[str, Any] = {"id": chapter_id}
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

    def _normalize_media_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        ocr_required = bool(payload.get("ocr_required", False))

        ocr_status = payload.get("ocr_status")
        if ocr_status not in self.OCR_STATUSES:
            ocr_status = "pending" if ocr_required else "skipped"

        reembed_status = payload.get("reembed_status")
        if reembed_status not in self.REEMBED_STATUSES:
            reembed_status = "skipped"

        payload["ocr_required"] = ocr_required
        payload["ocr_text"] = payload.get("ocr_text") if isinstance(payload.get("ocr_text"), str) else None
        payload["ocr_status"] = ocr_status
        payload["reembed_status"] = reembed_status
        payload["input_adapter_key"] = (
            payload.get("input_adapter_key").strip()
            if isinstance(payload.get("input_adapter_key"), str) and payload.get("input_adapter_key").strip()
            else None
        )
        payload["origin_type"] = (
            payload.get("origin_type").strip()
            if isinstance(payload.get("origin_type"), str) and payload.get("origin_type").strip()
            else "web"
        )
        payload["origin_uri_or_path"] = (
            payload.get("origin_uri_or_path").strip()
            if isinstance(payload.get("origin_uri_or_path"), str) and payload.get("origin_uri_or_path").strip()
            else None
        )
        payload["document_type"] = (
            payload.get("document_type").strip()
            if isinstance(payload.get("document_type"), str) and payload.get("document_type").strip()
            else "web_novel"
        )
        payload["unit_type"] = (
            payload.get("unit_type").strip()
            if isinstance(payload.get("unit_type"), str) and payload.get("unit_type").strip()
            else "chapter"
        )
        payload["import_order"] = self._normalize_optional_int(payload.get("import_order"))
        payload["context_group_id"] = (
            payload.get("context_group_id").strip()
            if isinstance(payload.get("context_group_id"), str) and payload.get("context_group_id").strip()
            else None
        )
        payload["region_metadata"] = self._normalize_named_dict_items(payload.get("region_metadata"))
        payload["ocr_artifacts"] = self._normalize_named_dict_items(payload.get("ocr_artifacts"))
        return payload

    def _persist_chapter_bundle(self, novel_id: str, chapter_id: str, payload: dict[str, Any]) -> Path:
        self._normalize_media_fields(payload)
        payload["schema_version"] = self.SCHEMA_VERSION
        path = self._chapter_path(novel_id, chapter_id)
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return path

    def delete_novel(self, novel_id: str) -> None:
        """Delete stored data for a novel (used for full re-scrapes)."""
        folder_name = self._get_folder_name(novel_id)
        novel_dir = self.novels_dir / folder_name
        if novel_dir.exists():
            shutil.rmtree(novel_dir)

        index = self._load_index()
        if novel_id in index:
            del index[novel_id]
            self._persist_index(index)

    def existing_chapter_hash(self, novel_id: str, chapter_id: str) -> str | None:
        """Return SHA256 hash of an existing raw chapter file (if present)."""
        chapter = self.load_chapter(novel_id, chapter_id)
        if chapter is None:
            return None

        text = chapter.get("text")
        if not isinstance(text, str):
            return None
        return self._hash_text(text)

    def save_chapter(
        self,
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
        payload = self._load_chapter_bundle(novel_id, chapter_id) or {"id": chapter_id}
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
            "id": chapter_id,
            "scraped_at": _utc_now_iso(),
            "text": text,
            "paragraphs": self._text_paragraphs(text),
            "images": self._normalize_image_manifest(images)
            if images is not None
            else self._normalize_image_manifest(existing_raw.get("images") if isinstance(existing_raw, dict) else None),
        }
        return self._persist_chapter_bundle(novel_id, chapter_id, payload)

    def load_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
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

        return {
            "id": chapter_id,
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

    def save_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> Path:
        """Save a translated chapter as structured JSON."""
        payload = self._load_chapter_bundle(novel_id, chapter_id) or {"id": chapter_id}
        payload["translated"] = {
            "provider": provider,
            "model": model,
            "translated_at": _utc_now_iso(),
            "text": text,
            "paragraphs": self._text_paragraphs(text),
        }
        return self._persist_chapter_bundle(novel_id, chapter_id, payload)

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        """Load the translated content for a single chapter.

        Returns a dict with id, text, provider, model, and timestamp,
        or ``None`` if the chapter has not been translated.
        """
        payload = self._load_chapter_bundle(novel_id, chapter_id)
        if payload is None:
            return None

        translated = payload.get("translated")
        if not isinstance(translated, dict):
            return None

        return {
            "id": chapter_id,
            "provider": translated.get("provider"),
            "model": translated.get("model"),
            "translated_at": translated.get("translated_at"),
            "text": translated.get("text"),
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

    def load_chapter_media_state(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
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
            "ocr_status": payload.get("ocr_status", "skipped"),
            "reembed_status": payload.get("reembed_status", "skipped"),
        }

    def save_chapter_media_state(
        self,
        novel_id: str,
        chapter_id: str,
        *,
        ocr_required: bool | object = _UNSET,
        ocr_text: str | None | object = _UNSET,
        ocr_status: str | object = _UNSET,
        reembed_status: str | object = _UNSET,
    ) -> Path:
        """Update OCR and re-embedding fields while preserving chapter content blocks."""
        payload = self._load_chapter_bundle(novel_id, chapter_id) or {"id": chapter_id}

        if ocr_required is not _UNSET:
            payload["ocr_required"] = bool(ocr_required)
        if ocr_text is not _UNSET:
            payload["ocr_text"] = ocr_text
        if ocr_status is not _UNSET:
            payload["ocr_status"] = ocr_status
        if reembed_status is not _UNSET:
            payload["reembed_status"] = reembed_status

        return self._persist_chapter_bundle(novel_id, chapter_id, payload)

    def save_metadata(self, novel_id: str, data: dict[str, Any]) -> Path:
        """Save novel metadata (chapter list, title, etc.) as JSON."""
        existing = self.load_metadata(novel_id) or {}
        merged = dict(existing)
        merged.update(data)

        merged["novel_id"] = novel_id
        merged["schema_version"] = self.SCHEMA_VERSION
        merged["scraped_at"] = existing.get("scraped_at") or merged.get("scraped_at") or _utc_now_iso()
        merged["updated_at"] = _utc_now_iso()
        merged["origin_type"] = (
            merged.get("origin_type").strip()
            if isinstance(merged.get("origin_type"), str) and merged.get("origin_type").strip()
            else ("url" if isinstance(merged.get("source_url"), str) and merged.get("source_url") else "library")
        )
        merged["origin_uri_or_path"] = (
            merged.get("origin_uri_or_path").strip()
            if isinstance(merged.get("origin_uri_or_path"), str) and merged.get("origin_uri_or_path").strip()
            else (merged.get("source_url") if isinstance(merged.get("source_url"), str) else None)
        )
        merged["document_type"] = (
            merged.get("document_type").strip()
            if isinstance(merged.get("document_type"), str) and merged.get("document_type").strip()
            else "web_novel"
        )
        merged["input_adapter_key"] = (
            merged.get("input_adapter_key").strip()
            if isinstance(merged.get("input_adapter_key"), str) and merged.get("input_adapter_key").strip()
            else None
        )
        merged["context_group_id"] = (
            merged.get("context_group_id").strip()
            if isinstance(merged.get("context_group_id"), str) and merged.get("context_group_id").strip()
            else novel_id
        )
        merged["translation_profiles"] = normalize_workflow_profiles(merged.get("translation_profiles", existing.get("translation_profiles")))

        titles = existing.get("titles", {}) if isinstance(existing.get("titles"), dict) else {}
        if isinstance(merged.get("title"), str) and merged.get("title"):
            titles["original"] = merged["title"]
        if isinstance(merged.get("translated_title"), str) and merged.get("translated_title"):
            titles["translated"] = merged["translated_title"]
        if titles:
            merged["titles"] = titles

        authors = existing.get("authors", {}) if isinstance(existing.get("authors"), dict) else {}
        if isinstance(merged.get("author"), str) and merged.get("author"):
            authors["original"] = merged["author"]
        if isinstance(merged.get("translated_author"), str) and merged.get("translated_author"):
            authors["translated"] = merged["translated_author"]
        if authors:
            merged["authors"] = authors

        folder_name = self._compute_folder_name(novel_id, merged)
        merged["folder_name"] = folder_name

        novel_dir = self._ensure_novel_dir(novel_id, folder_name)
        path = novel_dir / "metadata.json"
        atomic_write(path, json.dumps(merged, ensure_ascii=False, indent=2))
        return path

    def load_metadata(self, novel_id: str) -> dict[str, Any] | None:
        path = self._novel_dir(novel_id) / "metadata.json"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        try:
            payload = json.loads(content)
            if not isinstance(payload, dict):
                return None
            payload["translation_profiles"] = normalize_workflow_profiles(payload.get("translation_profiles"))
            payload["origin_type"] = (
                payload.get("origin_type").strip()
                if isinstance(payload.get("origin_type"), str) and payload.get("origin_type").strip()
                else ("url" if isinstance(payload.get("source_url"), str) and payload.get("source_url") else "library")
            )
            payload["origin_uri_or_path"] = (
                payload.get("origin_uri_or_path").strip()
                if isinstance(payload.get("origin_uri_or_path"), str) and payload.get("origin_uri_or_path").strip()
                else None
            )
            payload["document_type"] = (
                payload.get("document_type").strip()
                if isinstance(payload.get("document_type"), str) and payload.get("document_type").strip()
                else "web_novel"
            )
            payload["input_adapter_key"] = (
                payload.get("input_adapter_key").strip()
                if isinstance(payload.get("input_adapter_key"), str) and payload.get("input_adapter_key").strip()
                else None
            )
            payload["context_group_id"] = (
                payload.get("context_group_id").strip()
                if isinstance(payload.get("context_group_id"), str) and payload.get("context_group_id").strip()
                else novel_id
            )
            return payload
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupted metadata for novel %s.", novel_id)
            return None

    # ---- Glossary persistence -------------------------------------------------

    def save_glossary(self, novel_id: str, entries: list[dict[str, Any]]) -> Path:
        """Persist glossary entries for a novel."""
        novel_dir = self._novel_dir(novel_id)
        novel_dir.mkdir(parents=True, exist_ok=True)
        path = novel_dir / "glossary.json"
        atomic_write(
            path,
            json.dumps({"schema_version": self.SCHEMA_VERSION, "entries": entries}, ensure_ascii=False, indent=2),
        )
        return path

    def load_glossary(self, novel_id: str) -> list[dict[str, Any]]:
        """Load glossary entries for a novel (returns empty list if none)."""
        path = self._novel_dir(novel_id) / "glossary.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                return data["entries"]
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse glossary for novel %s.", novel_id)
            pass
        return []

    def list_stored_chapters(self, novel_id: str) -> list[str]:
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

    def count_stored_chapters(self, novel_id: str) -> int:
        return len(self.list_stored_chapters(novel_id))

    def list_translated_chapters(self, novel_id: str) -> list[str]:
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

    def count_translated_chapters(self, novel_id: str) -> int:
        return len(self.list_translated_chapters(novel_id))

    # State Tracking Methods
    def _get_state_dir(self, novel_id: str) -> Path:
        """Get the directory for chapter state files."""
        novel_dir = self._novel_dir(novel_id)
        state_dir = novel_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir

    def save_chapter_state(self, novel_id: str, chapter_id: str, state_data: dict[str, Any]) -> Path:
        """Save chapter state tracking information (including transitions)."""
        state_dir = self._get_state_dir(novel_id)

        # Serialize ChapterMetadata to JSON-safe format
        transitions = []
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

            transitions.append({
                "from_state": from_state,
                "to_state": to_state,
                "timestamp": timestamp,
                "error": error,
            })

        payload = {
            "chapter_id": chapter_id,
            "current_state": state_data["current_state"].value if isinstance(state_data["current_state"], ChapterState) else state_data["current_state"],
            "transitions": transitions,
            "last_updated": state_data["last_updated"].isoformat() if isinstance(state_data["last_updated"], datetime) else state_data["last_updated"],
            "error_count": state_data.get("error_count", 0),
            "retry_count": state_data.get("retry_count", 0),
        }

        path = state_dir / f"{chapter_id}.json"
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return path

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

    def load_chapter_state(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        """Load chapter state tracking information."""
        state_dir = self._get_state_dir(novel_id)
        path = state_dir / f"{chapter_id}.json"

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            # Deserialize to proper types
            transitions = []
            for t in data.get("transitions", []):
                transitions.append(ChapterStateTransition(
                    from_state=ChapterState(t["from_state"]) if t["from_state"] else None,
                    to_state=ChapterState(t["to_state"]) if t["to_state"] else ChapterState.SCRAPED,
                    timestamp=datetime.fromisoformat(t["timestamp"]) if isinstance(t["timestamp"], str) else t["timestamp"],
                    error=t.get("error"),
                ))

            return {
                "chapter_id": data["chapter_id"],
                "current_state": ChapterState(data["current_state"]),
                "transitions": transitions,
                "last_updated": datetime.fromisoformat(data["last_updated"]) if isinstance(data["last_updated"], str) else data["last_updated"],
                "error_count": data.get("error_count", 0),
                "retry_count": data.get("retry_count", 0),
            }
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            logger.warning("Failed to load chapter state %s/%s.", novel_id, chapter_id)
            return None

    def update_chapter_state(
        self,
        novel_id: str,
        chapter_id: str,
        new_state: ChapterState,
        error: str | None = None,
    ) -> None:
        """Update a chapter's state with a new transition."""
        # Load existing state or create new
        state_data = self.load_chapter_state(novel_id, chapter_id)

        if state_data is None:
            # Create new state
            state_data = {
                "chapter_id": chapter_id,
                "current_state": new_state,
                "transitions": [
                    ChapterStateTransition(
                        from_state=None,
                        to_state=new_state,
                        error=error,
                    )
                ],
                "last_updated": _utc_now(),
                "error_count": 1 if error else 0,
                "retry_count": 0,
            }
        else:
            # Update existing state
            if error:
                state_data["error_count"] += 1
            else:
                state_data["retry_count"] = 0

            # Add transition
            state_data["transitions"].append(
                ChapterStateTransition(
                    from_state=state_data["current_state"],
                    to_state=new_state,
                    error=error,
                )
            )
            state_data["current_state"] = new_state
            state_data["last_updated"] = _utc_now()

        self.save_chapter_state(novel_id, chapter_id, state_data)

    def get_chapters_by_state(self, novel_id: str, state: ChapterState) -> list[str]:
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

    def get_chapter_progress(self, novel_id: str) -> dict[str, int]:
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
    def query_chapters(self, novel_id: str) -> ChapterQueryBuilder:
        """Create a query builder for chapters."""
        state_dir = self._get_state_dir(novel_id)
        return ChapterQueryBuilder(state_dir)

    def get_chapters_ready_for_export(self, novel_id: str) -> list[str]:
        """Get all chapters that have been translated (ready for export)."""
        from novelai.core.chapter_state import ChapterState

        results = (
            self.query_chapters(novel_id)
            .by_states([ChapterState.TRANSLATED, ChapterState.EXPORTED])
            .sort_by("updated")
            .execute()
        )
        logger.info(f"Found {len(results)} chapters ready for export in {novel_id}")
        return [r.chapter_id for r in results]

    def get_chapters_with_errors(self, novel_id: str, limit: int = 100) -> list[str]:
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

    def get_scraping_progress(self, novel_id: str) -> dict[str, Any]:
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
    def _get_checkpoints_dir(self, novel_id: str) -> Path:
        """Get directory for chapter checkpoints."""
        novel_dir = self._novel_dir(novel_id)
        checkpoints_dir = novel_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        return checkpoints_dir

    def create_checkpoint(self, novel_id: str, chapter_id: str, checkpoint_name: str = "auto") -> Path:
        """Create a checkpoint of current chapter state.

        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            checkpoint_name: Name for checkpoint (auto-generates if not provided)

        Returns:
            Path to checkpoint file
        """
        checkpoints_dir = self._get_checkpoints_dir(novel_id)

        # Load current state
        raw_chapter = self.load_chapter(novel_id, chapter_id)
        translated_chapter = self.load_translated_chapter(novel_id, chapter_id)
        chapter_state = self.load_chapter_state(novel_id, chapter_id)

        # Create checkpoint
        checkpoint_data = {
            "chapter_id": chapter_id,
            "timestamp": _utc_now_iso(),
            "checkpoint_name": checkpoint_name,
            "raw_chapter": raw_chapter,
            "translated_chapter": translated_chapter,
            "chapter_state": self._serialize_checkpoint_state(chapter_state),
        }

        # Use timestamp in filename if no name provided
        if checkpoint_name == "auto":
            filename = f"{chapter_id}__{_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            filename = f"{chapter_id}__{checkpoint_name}.json"

        path = checkpoints_dir / filename
        atomic_write(path, json.dumps(checkpoint_data, ensure_ascii=False, indent=2))
        logger.info(f"Checkpoint created: {checkpoint_name} for {novel_id}/{chapter_id}")
        return path

    def list_checkpoints(self, novel_id: str, chapter_id: str) -> list[CheckpointInfo]:
        """List all checkpoints for a chapter.

        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier

        Returns:
            List of checkpoint info dicts
        """
        checkpoints_dir = self._get_checkpoints_dir(novel_id)
        if not checkpoints_dir.exists():
            return []

        checkpoints: list[CheckpointInfo] = []
        for checkpoint_file in sorted(checkpoints_dir.glob(f"{chapter_id}__*.json")):
            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                timestamp = data.get("timestamp")
                checkpoint_name = data.get("checkpoint_name")
                if not isinstance(timestamp, str):
                    continue
                if not isinstance(checkpoint_name, str):
                    continue
                checkpoints.append({
                    "filename": checkpoint_file.name,
                    "timestamp": timestamp,
                    "checkpoint_name": checkpoint_name,
                })
            except (json.JSONDecodeError, OSError):
                logger.debug("Skipping unreadable checkpoint file %s.", checkpoint_file)
                continue

        return checkpoints

    def restore_from_checkpoint(
        self,
        novel_id: str,
        chapter_id: str,
        checkpoint_name: str,
    ) -> bool:
        """Restore a chapter from a checkpoint.

        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            checkpoint_name: Name of checkpoint to restore from

        Returns:
            True if restored successfully
        """
        checkpoints_dir = self._get_checkpoints_dir(novel_id)
        checkpoint_file = None

        for cf in checkpoints_dir.glob(f"{chapter_id}__*.json"):
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
                if data.get("checkpoint_name") == checkpoint_name:
                    checkpoint_file = cf
                    break
            except (json.JSONDecodeError, OSError):
                logger.debug("Skipping unreadable checkpoint file %s.", cf)
                continue

        if not checkpoint_file:
            logger.warning(f"Checkpoint not found: {checkpoint_name}")
            return False

        try:
            checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))

            # Restore raw chapter
            if checkpoint_data.get("raw_chapter"):
                raw_chapter = checkpoint_data["raw_chapter"]
                self.save_chapter(
                    novel_id,
                    chapter_id,
                    raw_chapter.get("text", ""),
                    title=raw_chapter.get("title"),
                    source_key=raw_chapter.get("source_key"),
                    source_url=raw_chapter.get("source_url"),
                    images=raw_chapter.get("images"),
                )

            # Restore translated chapter
            if checkpoint_data.get("translated_chapter"):
                translated_chapter = checkpoint_data["translated_chapter"]
                self.save_translated_chapter(
                    novel_id,
                    chapter_id,
                    translated_chapter.get("text", ""),
                    provider=translated_chapter.get("provider"),
                    model=translated_chapter.get("model"),
                )

            # Restore state (if available)
            if checkpoint_data.get("chapter_state"):
                self.save_chapter_state(novel_id, chapter_id, checkpoint_data["chapter_state"])

            logger.info(f"Restored from checkpoint: {checkpoint_name} for {novel_id}/{chapter_id}")
            return True

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_name}: {e}")
            return False

    def rollback_to_state(self, novel_id: str, chapter_id: str, target_state: ChapterState) -> None:
        """Rollback chapter to a previous state.

        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            target_state: Target state to rollback to
        """
        state_data = self.load_chapter_state(novel_id, chapter_id)
        if not state_data:
            logger.warning(f"No state found for {novel_id}/{chapter_id}")
            return

        current_state = state_data["current_state"]

        # Check if rolling back
        state_order = [
            ChapterState.SCRAPED,
            ChapterState.PARSED,
            ChapterState.SEGMENTED,
            ChapterState.TRANSLATED,
            ChapterState.EXPORTED,
        ]

        current_idx = state_order.index(current_state)
        target_idx = state_order.index(target_state)

        if target_idx >= current_idx:
            logger.warning(f"Cannot rollback to {target_state.value} from {current_state.value}")
            return

        # Delete files for states beyond target
        if target_idx < state_order.index(ChapterState.TRANSLATED):
            chapter_payload = self._load_chapter_bundle(novel_id, chapter_id)
            if chapter_payload and "translated" in chapter_payload:
                del chapter_payload["translated"]
                self._persist_chapter_bundle(novel_id, chapter_id, chapter_payload)
                logger.debug(f"Deleted translated chapter {chapter_id}")
            translated_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.json"
            if translated_path.exists():
                translated_path.unlink()

        if target_idx < state_order.index(ChapterState.SEGMENTED):
            # Segmentation is in-memory only, but we mark state
            pass

        # Update state
        self.update_chapter_state(novel_id, chapter_id, target_state)
        logger.info(f"Rolled back {novel_id}/{chapter_id} to {target_state.value}")

    def list_novels(self) -> list[str]:
        index = self._load_index()
        return list(index.keys())
