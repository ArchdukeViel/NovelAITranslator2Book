from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from novelai.config.workflow_profiles import normalize_workflow_profiles
from novelai.core.security import validate_storage_identifier
from novelai.storage.common import _utc_now_iso
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)

_SYOSETU_NCODE_PATTERN = re.compile(r"^n\d{4}[a-z]{2}$", re.IGNORECASE)
_LEGACY_SYOSETU_NCODE_FOLDER_PATTERN = re.compile(r"^\d{4}[a-z]{2}$", re.IGNORECASE)

def _index_path(self: Any) -> Path:
    return self.novels_dir / self.INDEX_FILENAME


def _load_index(self: Any) -> dict[str, dict[str, Any]]:
    path = self._index_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupted novel index at %s; resetting to empty.", path)
        return {}


def _persist_index(self: Any, index: dict[str, dict[str, Any]]) -> None:
    path = self._index_path()
    atomic_write(path, json.dumps(index, ensure_ascii=False, indent=2))


def _compute_folder_name(self: Any, novel_id: str, metadata: dict[str, Any]) -> str:
    """Return a stable folder name for a novel."""
    return self._sanitize_folder_name(novel_id)


def _normalize_library_novel_id(self: Any, value: Any) -> str | None:
    novel_id = self._clean_string(value)
    if novel_id is None:
        return None

    normalized = novel_id.strip("/")
    if _SYOSETU_NCODE_PATTERN.fullmatch(normalized):
        return normalized.lower()
    if _LEGACY_SYOSETU_NCODE_FOLDER_PATTERN.fullmatch(normalized):
        return f"n{normalized.lower()}"
    return validate_storage_identifier(normalized, "novel_id")


def _legacy_folder_candidates(self: Any, novel_id: str) -> list[str]:
    canonical_id = self._normalize_library_novel_id(novel_id) or novel_id
    candidates = [self._sanitize_folder_name(canonical_id)]
    if _SYOSETU_NCODE_PATTERN.fullmatch(canonical_id):
        candidates.append(canonical_id[1:])
    return candidates


def _get_folder_name(self: Any, novel_id: str) -> str:
    index = self._load_index()
    normalized_id = self._normalize_library_novel_id(novel_id) or novel_id
    entry = index.get(normalized_id, {})
    folder_name = entry.get("folder_name") if isinstance(entry, dict) else None
    if isinstance(folder_name, str):
        try:
            folder_name = validate_storage_identifier(folder_name, "folder_name")
        except ValueError:
            logger.warning("Ignoring unsafe folder name in novel index for %s.", normalized_id)
            folder_name = None
    if folder_name and (self.novels_dir / folder_name).exists():
        return folder_name

    for candidate in self._legacy_folder_candidates(normalized_id):
        if (self.novels_dir / candidate).exists():
            return candidate
    if folder_name:
        return folder_name
    return normalized_id


def _novel_dir(self: Any, novel_id: str) -> Path:
    folder = self._get_folder_name(novel_id)
    return self.novels_dir / folder


def _ensure_novel_dir(self: Any, novel_id: str, folder_name: str) -> Path:
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


def delete_novel(self: Any, novel_id: str) -> None:
    """Delete stored data for a novel (used for full re-scrapes)."""
    folder_name = self._get_folder_name(novel_id)
    novel_dir = self.novels_dir / folder_name
    if novel_dir.exists():
        shutil.rmtree(novel_dir)

    index = self._load_index()
    if novel_id in index:
        del index[novel_id]
        self._persist_index(index)


def save_metadata(self: Any, novel_id: str, data: dict[str, Any]) -> Path:
    """Save novel metadata (chapter list, title, etc.) as JSON."""
    novel_id = self._normalize_library_novel_id(novel_id) or novel_id
    existing = self.load_metadata(novel_id) or {}
    merged = dict(existing)
    merged.update(data)

    merged["novel_id"] = novel_id
    merged["schema_version"] = self.SCHEMA_VERSION
    merged["scraped_at"] = existing.get("scraped_at") or merged.get("scraped_at") or _utc_now_iso()
    merged["updated_at"] = _utc_now_iso()
    source_url = merged.get("source_url")
    source_url_text = self._clean_string(source_url)
    merged["origin_type"] = self._clean_string(merged.get("origin_type"), "url" if source_url_text else "library")
    merged["origin_uri_or_path"] = self._clean_string(merged.get("origin_uri_or_path"), source_url_text)
    merged["document_type"] = self._clean_string(merged.get("document_type"), "web_novel")
    merged["input_adapter_key"] = self._clean_string(merged.get("input_adapter_key"))
    merged["context_group_id"] = self._clean_string(merged.get("context_group_id"), novel_id)
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


def load_metadata(self: Any, novel_id: str) -> dict[str, Any] | None:
    novel_id = self._normalize_library_novel_id(novel_id) or novel_id
    path = self._novel_dir(novel_id) / "metadata.json"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(content)
        if not isinstance(payload, dict):
            return None
        payload["translation_profiles"] = normalize_workflow_profiles(payload.get("translation_profiles"))
        source_url_text = self._clean_string(payload.get("source_url"))
        payload["origin_type"] = self._clean_string(payload.get("origin_type"), "url" if source_url_text else "library")
        payload["origin_uri_or_path"] = self._clean_string(payload.get("origin_uri_or_path"))
        payload["document_type"] = self._clean_string(payload.get("document_type"), "web_novel")
        payload["input_adapter_key"] = self._clean_string(payload.get("input_adapter_key"))
        payload["context_group_id"] = self._clean_string(payload.get("context_group_id"), novel_id)
        return payload
    except json.JSONDecodeError as exc:
        logger.warning("Corrupted metadata for novel %s at %s: %s", novel_id, path, exc)
        return None
    except OSError as exc:
        logger.warning("Failed to read metadata for novel %s at %s: %s", novel_id, path, exc)
        return None

# ---- Glossary persistence -------------------------------------------------


def _folder_has_novel_data(novel_dir: Path) -> bool:
    if (novel_dir / "metadata.json").exists():
        return True
    for dirname in ("chapters", "raw", "translated"):
        data_dir = novel_dir / dirname
        if data_dir.exists() and any(path.is_file() for path in data_dir.iterdir()):
            return True
    return False


def list_novels(self: Any) -> list[str]:
    if not self.novels_dir.exists():
        logger.warning("Novel storage path does not exist: %s", self.novels_dir)
        return []

    index = self._load_index()
    discovered: list[str] = []
    seen: set[str] = set()
    updated_index = dict(index)
    index_changed = False

    def add_novel(novel_id: str, folder_name: str | None = None) -> None:
        nonlocal index_changed
        normalized_id = self._normalize_library_novel_id(novel_id)
        if normalized_id is None or normalized_id in seen:
            return
        seen.add(normalized_id)
        discovered.append(normalized_id)
        if folder_name and updated_index.get(normalized_id, {}).get("folder_name") != folder_name:
            updated_index[normalized_id] = {
                "folder_name": folder_name,
                "updated_at": _utc_now_iso(),
            }
            index_changed = True

    for novel_id, entry in index.items():
        folder_name = entry.get("folder_name") if isinstance(entry, dict) else None
        folder_name = self._clean_string(folder_name, novel_id) or novel_id
        metadata_path = self.novels_dir / folder_name / "metadata.json"
        resolved_id = novel_id
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if isinstance(metadata, dict):
                    resolved_id = self._clean_string(metadata.get("novel_id"), novel_id) or novel_id
            except json.JSONDecodeError as exc:
                logger.warning("Corrupted metadata for novel folder %s at %s: %s", folder_name, metadata_path, exc)
            except OSError as exc:
                logger.warning("Failed to read metadata for novel folder %s at %s: %s", folder_name, metadata_path, exc)
        add_novel(resolved_id, folder_name)

    for novel_dir in sorted(self.novels_dir.iterdir(), key=lambda path: path.name.lower()):
        if not novel_dir.is_dir():
            continue
        if not _folder_has_novel_data(novel_dir):
            continue
        metadata_path = novel_dir / "metadata.json"
        if not metadata_path.exists():
            add_novel(novel_dir.name, novel_dir.name)
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Corrupted metadata for novel folder %s at %s: %s", novel_dir.name, metadata_path, exc)
            add_novel(novel_dir.name, novel_dir.name)
            continue
        except OSError as exc:
            logger.warning("Failed to read metadata for novel folder %s at %s: %s", novel_dir.name, metadata_path, exc)
            add_novel(novel_dir.name, novel_dir.name)
            continue
        if not isinstance(metadata, dict):
            logger.warning("Metadata for novel folder %s is not a JSON object.", novel_dir.name)
            add_novel(novel_dir.name, novel_dir.name)
            continue
        resolved_id = self._clean_string(metadata.get("novel_id"), novel_dir.name) or novel_dir.name
        add_novel(resolved_id, novel_dir.name)

    if index_changed:
        self._persist_index(updated_index)
    return discovered
