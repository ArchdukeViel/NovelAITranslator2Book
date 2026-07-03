from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def save_glossary(self: Any, novel_id: str, entries: list[dict[str, Any]]) -> Path:
    """Persist glossary entries for a novel."""
    novel_dir = self._novel_dir(novel_id)
    self._mkdirs(novel_dir)
    path = novel_dir / "glossary.json"
    self._write_text(
        path,
        json.dumps({"schema_version": self.SCHEMA_VERSION, "entries": entries}, ensure_ascii=False, indent=2),
    )
    return path


def load_glossary(self: Any, novel_id: str) -> list[dict[str, Any]]:
    """Load glossary entries for a novel (returns empty list if none)."""
    path = self._novel_dir(novel_id) / "glossary.json"
    if not self._path_exists(path):
        return []
    try:
        data = json.loads(self._read_text(path))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data["entries"]
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to parse glossary for novel %s.", novel_id)
        pass
    return []
