from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from novelai.config.workflow_profiles import normalize_workflow_defaults, normalize_workflow_profiles
from novelai.core.security import safe_child_path, validate_storage_identifier
from novelai.sources.status import normalize_publication_status
from novelai.storage.common import _utc_now_iso

logger = logging.getLogger(__name__)

_SYOSETU_NCODE_PATTERN = re.compile(r"^n\d{4}[a-z]{2}$", re.IGNORECASE)
_LEGACY_SYOSETU_NCODE_FOLDER_PATTERN = re.compile(r"^\d{4}[a-z]{2}$", re.IGNORECASE)
METADATA_BACKUP_DIRNAME = "metadata_backups"
METADATA_BACKUP_RETENTION = 5
TITLE_SLUG_DIRNAME = "novel"
STORAGE_SLUG_MAX_LENGTH = 100
_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}

def _index_path(self: Any) -> Path:
    return self.novels_dir / self.INDEX_FILENAME


def _load_index(self: Any) -> dict[str, dict[str, Any]]:
    path = self._index_path()
    if not self._path_exists(path):
        return {}
    try:
        return json.loads(self._read_text(path))
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupted novel index at %s; resetting to empty.", path)
        return {}


def _persist_index(self: Any, index: dict[str, dict[str, Any]]) -> None:
    path = self._index_path()
    self._write_text(path, json.dumps(index, ensure_ascii=False, indent=2))


def _metadata_backup_dir(novel_dir: Path) -> Path:
    return novel_dir / METADATA_BACKUP_DIRNAME


def _backup_metadata_file(self: Any, metadata_path: Path, *, keep: int = METADATA_BACKUP_RETENTION) -> Path | None:
    if keep <= 0 or not self._path_exists(metadata_path):
        return None

    try:
        existing_payload = json.loads(self._read_text(metadata_path))
    except (json.JSONDecodeError, OSError):
        return None

    backup_dir = _metadata_backup_dir(metadata_path.parent)
    self._mkdirs(backup_dir)
    updated_at = str(existing_payload.get("updated_at") or _utc_now_iso()) if isinstance(existing_payload, dict) else _utc_now_iso()
    safe_stamp = re.sub(r"[^0-9A-Za-z_\-.]+", "_", updated_at).strip("._") or "metadata"
    backup_path = backup_dir / f"{safe_stamp}.json"
    suffix = 1
    while self._path_exists(backup_path):
        backup_path = backup_dir / f"{safe_stamp}_{suffix}.json"
        suffix += 1
    self._write_text(backup_path, self._read_text(metadata_path))

    backups = sorted(self._glob(backup_dir, "*.json"), key=lambda path: path.name, reverse=True)
    for stale_backup in backups[keep:]:
        try:
            self._unlink_path(stale_backup)
        except OSError:
            logger.warning("Could not prune stale metadata backup at %s.", stale_backup)
    return backup_path


def _metadata_history_entry(self: Any, path: Path, *, snapshot_id: str, is_current: bool) -> dict[str, Any] | None:
    try:
        payload = json.loads(self._read_text(path))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read metadata history snapshot at %s: %s", path, exc)
        return None
    if not isinstance(payload, dict):
        return None

    publication_status = normalize_publication_status(payload.get("publication_status") or payload.get("status"))
    return {
        "snapshot_id": snapshot_id,
        "created_at": payload.get("updated_at") if isinstance(payload.get("updated_at"), str) else None,
        "size_bytes": len(json.dumps(payload)),
        "is_current": is_current,
        "publication_status": publication_status,
        "title": payload.get("translated_title") if isinstance(payload.get("translated_title"), str) else payload.get("title"),
        "source_title": payload.get("title") if isinstance(payload.get("title"), str) else None,
        "author": payload.get("translated_author") if isinstance(payload.get("translated_author"), str) else payload.get("author"),
    }


def list_metadata_history(self: Any, novel_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Return bounded current/backup metadata snapshot summaries for a novel."""
    novel_id = self._normalize_library_novel_id(novel_id) or novel_id
    limit = max(1, min(limit, 25))
    novel_dir = self._novel_dir(novel_id)
    entries: list[dict[str, Any]] = []

    current_path = novel_dir / "metadata.json"
    if self._path_exists(current_path):
        current_entry = self._metadata_history_entry(
            current_path,
            snapshot_id="current",
            is_current=True,
        )
        if current_entry is not None:
            entries.append(current_entry)

    backup_dir = _metadata_backup_dir(novel_dir)
    if self._path_exists(backup_dir):
        backups = sorted(
            self._glob(backup_dir, "*.json"),
            key=lambda path: path.name,
            reverse=True,
        )
        for backup_path in backups:
            if len(entries) >= limit:
                break
            backup_entry = self._metadata_history_entry(
                backup_path,
                snapshot_id=backup_path.name,
                is_current=False,
            )
            if backup_entry is not None:
                entries.append(backup_entry)

    return entries[:limit]


def load_metadata_snapshot(self: Any, novel_id: str, snapshot_id: str) -> dict[str, Any] | None:
    """Return one metadata snapshot with its summary entry and raw JSON payload.

    Snapshot IDs are deliberately narrow: "current" for the active metadata file,
    or a JSON filename that already exists under the novel's metadata_backups
    directory. Callers are responsible for sanitizing the returned metadata before
    exposing it outside the storage boundary.
    """
    novel_id = self._normalize_library_novel_id(novel_id) or novel_id
    snapshot_id = validate_storage_identifier(snapshot_id, "snapshot_id")
    novel_dir = self._novel_dir(novel_id)

    if snapshot_id == "current":
        snapshot_path = novel_dir / "metadata.json"
        is_current = True
    else:
        if not snapshot_id.endswith(".json"):
            return None
        backup_dir = _metadata_backup_dir(novel_dir)
        snapshot_path = backup_dir / snapshot_id
        is_current = False
        try:
            snapshot_path.resolve().relative_to(backup_dir.resolve())
        except ValueError as exc:
            raise ValueError("snapshot_id must stay within metadata_backups.") from exc
        if snapshot_id not in {path.name for path in self._glob(backup_dir, "*.json")}:
            return None

    if not self._path_exists(snapshot_path):
        return None

    try:
        payload = json.loads(self._read_text(snapshot_path))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read metadata snapshot at %s: %s", snapshot_path, exc)
        return None
    if not isinstance(payload, dict):
        return None

    entry = self._metadata_history_entry(snapshot_path, snapshot_id=snapshot_id, is_current=is_current)
    if entry is None:
        return None
    return {
        **entry,
        "metadata": payload,
    }


def _storage_slug_source(novel_id: str, metadata: dict[str, Any]) -> str:
    for key in ("translated_title", "title"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return novel_id


def _storage_slug_from_text(text: str, *, fallback_source_id: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_text = re.sub(r"[\x00-\x1f\x7f]+", " ", ascii_text)
    ascii_text = ascii_text.replace("/", " ").replace("\\", " ")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    slug = slug.strip("-._ ")
    slug = slug[:STORAGE_SLUG_MAX_LENGTH].strip("-._ ")
    fallback = re.sub(r"[^a-z0-9]+", "-", fallback_source_id.lower()).strip("-._ ")
    if not slug:
        slug = f"novel-{fallback or 'unknown'}"
    if slug in _WINDOWS_RESERVED_NAMES:
        slug = f"novel-{slug}"
    return slug[:STORAGE_SLUG_MAX_LENGTH].strip("-._ ") or "novel"


def _source_suffix(novel_id: str) -> str:
    return _storage_slug_from_text(novel_id, fallback_source_id=novel_id)


def _validate_folder_name(self: Any, folder_name: str) -> str:
    cleaned = folder_name.strip().replace("\\", "/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) == 1:
        return validate_storage_identifier(parts[0], "folder_name")
    if len(parts) == 2 and parts[0] == TITLE_SLUG_DIRNAME:
        slug = validate_storage_identifier(parts[1], "storage_slug")
        if slug.lower() in _WINDOWS_RESERVED_NAMES:
            raise ValueError("storage_slug must not be a Windows reserved name.")
        return f"{TITLE_SLUG_DIRNAME}/{slug}"
    raise ValueError("folder_name must be a legacy folder or novel/{storage_slug}.")


def _folder_path(self: Any, folder_name: str) -> Path:
    folder_name = self._validate_folder_name(folder_name)
    if folder_name.startswith(f"{TITLE_SLUG_DIRNAME}/"):
        return safe_child_path(self.base_dir, folder_name)
    return self.novels_dir / folder_name


def _folder_in_use_by_other_novel(self: Any, folder_name: str, novel_id: str, index: dict[str, dict[str, Any]]) -> bool:
    for indexed_id, entry in index.items():
        if indexed_id == novel_id or not isinstance(entry, dict):
            continue
        if entry.get("folder_name") == folder_name:
            return True

    folder_path = self._folder_path(folder_name)
    if not self._path_exists(folder_path):
        return False
    metadata_path = folder_path / "metadata.json"
    if not self._path_exists(metadata_path):
        return True
    try:
        payload = json.loads(self._read_text(metadata_path))
    except (json.JSONDecodeError, OSError):
        return True
    if not isinstance(payload, dict):
        return True
    return self._clean_string(payload.get("novel_id")) != novel_id


def _compute_folder_name(self: Any, novel_id: str, metadata: dict[str, Any]) -> str:
    """Return a stable folder name for a novel."""
    index = self._load_index()
    existing_entry = index.get(novel_id)
    existing_folder = existing_entry.get("folder_name") if isinstance(existing_entry, dict) else None
    if isinstance(existing_folder, str) and existing_folder.strip():
        return self._validate_folder_name(existing_folder)

    current_folder = self._get_folder_name(novel_id)
    if self._path_exists(self._folder_path(current_folder)):
        return self._validate_folder_name(current_folder)

    source = _storage_slug_source(novel_id, metadata)
    storage_slug = _storage_slug_from_text(source, fallback_source_id=novel_id)
    folder_name = f"{TITLE_SLUG_DIRNAME}/{storage_slug}"
    if not self._folder_in_use_by_other_novel(folder_name, novel_id, index):
        return folder_name

    suffix = _source_suffix(novel_id)
    storage_slug = f"{storage_slug}--{suffix}"[:STORAGE_SLUG_MAX_LENGTH].strip("-._ ")
    folder_name = f"{TITLE_SLUG_DIRNAME}/{storage_slug}"
    if not self._folder_in_use_by_other_novel(folder_name, novel_id, index):
        return folder_name

    source_hash = hashlib.sha256(
        f"{novel_id}:{metadata.get('source_url') or ''}".encode()
    ).hexdigest()[:8]
    storage_slug = f"{storage_slug}--{source_hash}"[:STORAGE_SLUG_MAX_LENGTH].strip("-._ ")
    return f"{TITLE_SLUG_DIRNAME}/{storage_slug}"


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
            folder_name = self._validate_folder_name(folder_name)
        except ValueError:
            logger.warning("Ignoring unsafe folder name in novel index for %s.", normalized_id)
            folder_name = None
    if folder_name and self._path_exists(self._folder_path(folder_name)):
        return folder_name

    for candidate in self._legacy_folder_candidates(normalized_id):
        if self._path_exists(self._folder_path(candidate)):
            return candidate
    if folder_name:
        return folder_name
    return normalized_id


def _novel_dir(self: Any, novel_id: str) -> Path:
    folder = self._get_folder_name(novel_id)
    return self._folder_path(folder)


def _ensure_novel_dir(self: Any, novel_id: str, folder_name: str) -> Path:
    """Ensure the novel directory exists and the index is updated."""
    index = self._load_index()
    entry = index.get(novel_id, {})
    old_folder = entry.get("folder_name")

    if isinstance(old_folder, str) and old_folder.strip() and old_folder != folder_name:
        folder_name = self._validate_folder_name(old_folder)
    else:
        folder_name = self._validate_folder_name(folder_name)

    novel_dir = self._folder_path(folder_name)
    self._mkdirs(novel_dir)

    index[novel_id] = {
        "folder_name": folder_name,
        "updated_at": _utc_now_iso(),
    }
    self._persist_index(index)
    return novel_dir


def delete_novel(self: Any, novel_id: str) -> None:
    """Delete stored data for a novel (used for full re-scrapes)."""
    folder_name = self._get_folder_name(novel_id)
    novel_dir = self._folder_path(folder_name)
    if self._path_exists(novel_dir):
        self._rmtree(novel_dir)

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
    merged["translation_profiles"] = normalize_workflow_profiles(merged.get("translation_profiles", existing.get("translation_profiles")))["steps"]
    merged["translation_defaults"] = normalize_workflow_defaults(merged.get("translation_defaults", existing.get("translation_defaults")))
    publication_status = normalize_publication_status(merged.get("publication_status") or merged.get("status"))
    merged["publication_status"] = publication_status
    merged["status"] = publication_status
    if merged.get("metadata_translation_status") != "failed":
        merged.pop("metadata_translation_error", None)

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
    storage_slug = folder_name.split("/", 1)[1] if folder_name.startswith(f"{TITLE_SLUG_DIRNAME}/") else folder_name
    merged["source_novel_id"] = self._clean_string(merged.get("source_novel_id"), novel_id)
    merged["storage_slug"] = storage_slug
    merged["folder_name"] = folder_name

    novel_dir = self._ensure_novel_dir(novel_id, folder_name)
    path = novel_dir / "metadata.json"
    self._backup_metadata_file(path)
    self._write_text(path, json.dumps(merged, ensure_ascii=False, indent=2))
    return path


def load_metadata(self: Any, novel_id: str) -> dict[str, Any] | None:
    novel_id = self._normalize_library_novel_id(novel_id) or novel_id
    path = self._novel_dir(novel_id) / "metadata.json"
    if not self._path_exists(path):
        return None
    content = self._read_text(path)
    try:
        payload = json.loads(content)
        if not isinstance(payload, dict):
            return None
        payload["translation_profiles"] = normalize_workflow_profiles(payload.get("translation_profiles"))["steps"]
        payload["translation_defaults"] = normalize_workflow_defaults(payload.get("translation_defaults"))
        source_url_text = self._clean_string(payload.get("source_url"))
        payload["origin_type"] = self._clean_string(payload.get("origin_type"), "url" if source_url_text else "library")
        payload["origin_uri_or_path"] = self._clean_string(payload.get("origin_uri_or_path"))
        payload["document_type"] = self._clean_string(payload.get("document_type"), "web_novel")
        payload["input_adapter_key"] = self._clean_string(payload.get("input_adapter_key"))
        payload["context_group_id"] = self._clean_string(payload.get("context_group_id"), novel_id)
        publication_status = normalize_publication_status(payload.get("publication_status") or payload.get("status"))
        payload["publication_status"] = publication_status
        payload["status"] = publication_status
        return payload
    except json.JSONDecodeError as exc:
        logger.warning("Corrupted metadata for novel %s at %s: %s", novel_id, path, exc)
        return None
    except OSError as exc:
        logger.warning("Failed to read metadata for novel %s at %s: %s", novel_id, path, exc)
        return None

# ---- Glossary persistence -------------------------------------------------


def _folder_has_novel_data(self: Any, novel_dir: Path) -> bool:
    if self._path_exists(novel_dir / "metadata.json"):
        return True
    for dirname in ("chapters", "raw", "translated"):
        data_dir = novel_dir / dirname
        if self._path_exists(data_dir) and any(self._path_exists(path) for path in self._list_dir(data_dir)):
            return True
    return False


def list_novels(self: Any) -> list[str]:
    if not self._path_exists(self.novels_dir):
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
        try:
            metadata_path = self._folder_path(folder_name) / "metadata.json"
        except ValueError:
            logger.warning("Ignoring unsafe folder name in novel index for %s.", novel_id)
            continue
        resolved_id = novel_id
        if self._path_exists(metadata_path):
            try:
                metadata = json.loads(self._read_text(metadata_path))
                if isinstance(metadata, dict):
                    resolved_id = self._clean_string(metadata.get("novel_id"), novel_id) or novel_id
            except json.JSONDecodeError as exc:
                logger.warning("Corrupted metadata for novel folder %s at %s: %s", folder_name, metadata_path, exc)
            except OSError as exc:
                logger.warning("Failed to read metadata for novel folder %s at %s: %s", folder_name, metadata_path, exc)
        add_novel(resolved_id, folder_name)

    for novel_dir in sorted(self._list_dir(self.novels_dir), key=lambda path: path.name.lower()):
        if not novel_dir.is_dir():
            continue
        if not self._folder_has_novel_data(novel_dir):
            continue
        metadata_path = novel_dir / "metadata.json"
        if not self._path_exists(metadata_path):
            add_novel(novel_dir.name, novel_dir.name)
            continue
        try:
            metadata = json.loads(self._read_text(metadata_path))
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

    title_slug_root = self.base_dir / TITLE_SLUG_DIRNAME
    if self._path_exists(title_slug_root):
        for novel_dir in sorted(self._list_dir(title_slug_root), key=lambda path: path.name.lower()):
            if not novel_dir.is_dir():
                continue
            folder_name = f"{TITLE_SLUG_DIRNAME}/{novel_dir.name}"
            if not self._folder_has_novel_data(novel_dir):
                continue
            metadata_path = novel_dir / "metadata.json"
            if not self._path_exists(metadata_path):
                add_novel(novel_dir.name, folder_name)
                continue
            try:
                metadata = json.loads(self._read_text(metadata_path))
            except json.JSONDecodeError as exc:
                logger.warning("Corrupted metadata for novel folder %s at %s: %s", folder_name, metadata_path, exc)
                add_novel(novel_dir.name, folder_name)
                continue
            except OSError as exc:
                logger.warning("Failed to read metadata for novel folder %s at %s: %s", folder_name, metadata_path, exc)
                add_novel(novel_dir.name, folder_name)
                continue
            if not isinstance(metadata, dict):
                logger.warning("Metadata for novel folder %s is not a JSON object.", folder_name)
                add_novel(novel_dir.name, folder_name)
                continue
            resolved_id = self._clean_string(metadata.get("novel_id"), novel_dir.name) or novel_dir.name
            add_novel(resolved_id, folder_name)

    if index_changed:
        self._persist_index(updated_index)
    return discovered
