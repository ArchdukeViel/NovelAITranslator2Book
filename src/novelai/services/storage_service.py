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
    """Simple filesystem-backed storage service.

    This is a starting point. Replace with a database-backed repository as needed.
    """

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """Create a filesystem-safe folder name from an arbitrary title."""
        name = name.strip().replace(" ", "_")
        # Remove any character that is not alphanumeric, underscore, hyphen, or dot.
        name = re.sub(r"[^A-Za-z0-9_\-\.]+", "", name)
        return name or "novel"

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _novel_dir(self, novel_id: str) -> Path:
        return self.base_dir / "novels" / novel_id

    def _web_novel_dir(self, novel_id: str) -> Path:
        return self.base_dir / "web" / "novels" / novel_id

    def delete_novel(self, novel_id: str) -> None:
        """Delete stored data for a novel (used for full re-scrapes)."""
        novel_dir = self._novel_dir(novel_id)
        web_dir = self._web_novel_dir(novel_id)
        if novel_dir.exists():
            shutil.rmtree(novel_dir)
        if web_dir.exists():
            shutil.rmtree(web_dir)

    def existing_chapter_hash(self, novel_id: str, chapter_id: str) -> Optional[str]:
        """Return SHA256 hash of an existing chapter file (if present)."""
        path = self._novel_dir(novel_id) / f"{chapter_id}.txt"
        if not path.exists():
            return None
        return self._hash_text(path.read_text(encoding="utf-8"))

    def save_chapter(self, novel_id: str, chapter_id: str, text: str) -> Path:
        novel_dir = self._novel_dir(novel_id)
        novel_dir.mkdir(parents=True, exist_ok=True)
        path = novel_dir / f"{chapter_id}.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def load_chapter(self, novel_id: str, chapter_id: str) -> Optional[str]:
        path = self._novel_dir(novel_id) / f"{chapter_id}.txt"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_translated_chapter(self, novel_id: str, chapter_id: str, text: str) -> Path:
        translated_dir = self._novel_dir(novel_id) / "translated"
        translated_dir.mkdir(parents=True, exist_ok=True)
        path = translated_dir / f"{chapter_id}.txt"
        path.write_text(text, encoding="utf-8")

        # Keep a mirror copy for the web UI to load easily.
        web_translated_dir = self._web_novel_dir(novel_id) / "translated"
        web_translated_dir.mkdir(parents=True, exist_ok=True)
        web_path = web_translated_dir / f"{chapter_id}.txt"
        web_path.write_text(text, encoding="utf-8")
        return path

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> Optional[str]:
        path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.txt"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_metadata(self, novel_id: str, data: dict[str, Any]) -> Path:
        """Save novel metadata (chapter list, title, etc.) as JSON."""
        # Enhance metadata with tracking fields
        title = data.get("title") or "novel"
        data["folder_name"] = self._sanitize_folder_name(title)
        data["scraped_at"] = data.get("scraped_at") or datetime.utcnow().isoformat() + "Z"

        novel_dir = self._novel_dir(novel_id)
        novel_dir.mkdir(parents=True, exist_ok=True)
        path = novel_dir / "metadata.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Mirror metadata for web UI consumption
        web_dir = self._web_novel_dir(novel_id)
        web_dir.mkdir(parents=True, exist_ok=True)
        web_path = web_dir / "metadata.json"
        web_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
        return [p.stem for p in translated_dir.iterdir() if p.is_file()]

    def count_translated_chapters(self, novel_id: str) -> int:
        return len(self.list_translated_chapters(novel_id))

    def list_novels(self) -> list[str]:
        novels_dir = self.base_dir / "novels"
        if not novels_dir.exists():
            return []
        return [p.name for p in novels_dir.iterdir() if p.is_dir()]
