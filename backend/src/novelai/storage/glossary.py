from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.utils import atomic_write

logger = logging.getLogger(__name__)


def save_glossary(self: Any, novel_id: str, entries: list[dict[str, Any]]) -> Path:
    """Persist glossary entries for a novel."""
    novel_dir = self._novel_dir(novel_id)
    novel_dir.mkdir(parents=True, exist_ok=True)
    path = novel_dir / "glossary.json"
    atomic_write(
        path,
        json.dumps({"schema_version": self.SCHEMA_VERSION, "entries": entries}, ensure_ascii=False, indent=2),
    )
    return path


def load_glossary(self: Any, novel_id: str) -> list[dict[str, Any]]:
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
