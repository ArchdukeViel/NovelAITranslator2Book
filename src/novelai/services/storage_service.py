from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from novelai.config.settings import settings


class StorageService:
    """Filesystem-backed storage service.

    Each novel is stored in a folder under `data/novels/<folder_name>`.
    The folder name is derived from the translated title (when available),
    and falls back to the novel ID when no translated title exists.

    The folder contains:
      - metadata.json
      - raw/<chapter_id>.json
      - translated/<chapter_id>.json

    A simple index file keeps the mapping from novel ID to folder name.
    """

    INDEX_FILENAME = "index.json"

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """Create a filesystem-safe folder name from an arbitrary title."""
        name = name.strip().replace(" ", "_")
        name = re.sub(r"[^A-Za-z0-9_\-\.]+", "", name)
        return name or "novel"

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

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
        except Exception:
            return {}

    def _persist_index(self, index: dict[str, dict[str, Any]]) -> None:
        path = self._index_path()
        path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    def _compute_folder_name(self, novel_id: str, metadata: dict[str, Any]) -> str:
        """Return a folder name for a novel.

        Prefer translated title when present. Fall back to the original title,
        then the novel ID.
        """
        translated_title = metadata.get("translated_title")
        if translated_title:
            return self._sanitize_folder_name(translated_title)

        title = metadata.get("title")
        if title:
            return self._sanitize_folder_name(title)

        return self._sanitize_folder_name(novel_id)

    def _get_folder_name(self, novel_id: str) -> str:
        index = self._load_index()
        entry = index.get(novel_id, {})
        return entry.get("folder_name", novel_id)

    def _novel_dir(self, novel_id: str) -> Path:
        folder = self._get_folder_name(novel_id)
        return self.novels_dir / folder

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

        novel_dir = self.novels_dir / folder_name
        novel_dir.mkdir(parents=True, exist_ok=True)

        index[novel_id] = {
            "folder_name": folder_name,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        self._persist_index(index)
        return novel_dir

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

    def existing_chapter_hash(self, novel_id: str, chapter_id: str) -> Optional[str]:
        """Return SHA256 hash of an existing raw chapter file (if present)."""
        json_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.txt"

        if json_path.exists():
            return self._hash_text(json_path.read_text(encoding="utf-8"))
        if txt_path.exists():
            return self._hash_text(txt_path.read_text(encoding="utf-8"))
        return None

    def save_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        title: str | None = None,
        source_key: str | None = None,
        source_url: str | None = None,
    ) -> Path:
        """Save a raw / scraped chapter as structured JSON."""
        novel_dir = self._novel_dir(novel_id)
        raw_dir = novel_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "id": chapter_id,
            "title": title,
            "source_key": source_key,
            "source_url": source_url,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "text": text,
        }

        path = raw_dir / f"{chapter_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_chapter(self, novel_id: str, chapter_id: str) -> Optional[dict[str, Any]]:
        json_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.txt"

        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                return None

        if txt_path.exists():
            # Backwards compatibility: older versions stored raw chapters as plain text.
            return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}

        return None

    def save_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> Path:
        """Save a translated chapter as structured JSON."""
        novel_dir = self._novel_dir(novel_id)
        translated_dir = novel_dir / "translated"
        translated_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "id": chapter_id,
            "provider": provider,
            "model": model,
            "translated_at": datetime.utcnow().isoformat() + "Z",
            "text": text,
        }

        path = translated_dir / f"{chapter_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> Optional[dict[str, Any]]:
        json_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.txt"

        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                return None

        if txt_path.exists():
            # Backwards compatibility: older versions stored translated chapters as plain text.
            return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}

        return None

    def save_metadata(self, novel_id: str, data: dict[str, Any]) -> Path:
        """Save novel metadata (chapter list, title, etc.) as JSON."""
        # Enhance metadata with tracking fields
        data["novel_id"] = novel_id
        data["scraped_at"] = data.get("scraped_at") or datetime.utcnow().isoformat() + "Z"

        folder_name = self._compute_folder_name(novel_id, data)
        data["folder_name"] = folder_name

        novel_dir = self._ensure_novel_dir(novel_id, folder_name)
        path = novel_dir / "metadata.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_metadata(self, novel_id: str) -> Optional[dict[str, Any]]:
        path = self._novel_dir(novel_id) / "metadata.json"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        try:
            return json.loads(content)
        except Exception:
            return None

    def list_translated_chapters(self, novel_id: str) -> list[str]:
        translated_dir = self._novel_dir(novel_id) / "translated"
        if not translated_dir.exists():
            return []

        stems: set[str] = set()
        for p in translated_dir.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() in {".json", ".txt"}:
                stems.add(p.stem)
        return sorted(stems)

    def count_translated_chapters(self, novel_id: str) -> int:
        return len(self.list_translated_chapters(novel_id))

    def list_novels(self) -> list[str]:
        index = self._load_index()
        return list(index.keys())
