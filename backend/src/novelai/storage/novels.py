from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from novelai.config.workflow_profiles import normalize_workflow_profiles
from novelai.storage.common import _utc_now_iso
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)

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


def _get_folder_name(self: Any, novel_id: str) -> str:
    index = self._load_index()
    entry = index.get(novel_id, {})
    return entry.get("folder_name", novel_id)


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
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupted metadata for novel %s.", novel_id)
        return None

# ---- Glossary persistence -------------------------------------------------


def list_novels(self: Any) -> list[str]:
    index = self._load_index()
    return list(index.keys())
