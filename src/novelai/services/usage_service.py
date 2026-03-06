from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from novelai.config.settings import settings


class UsageService:
    """Track translation usage (tokens, costs, provider/model choices, etc.)."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.usage_path = self.base_dir / "usage.json"
        self._data: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.usage_path.exists():
            return []
        try:
            return json.loads(self.usage_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _persist(self) -> None:
        self.usage_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, entry: Dict[str, Any]) -> None:
        """Add a usage entry. The entry should already include timestamp."""
        self._data.append(entry)
        self._persist()

    def list(self, limit: int | None = None) -> List[Dict[str, Any]]:
        if limit is None:
            return list(self._data)
        return list(self._data[-limit:])

    def summary(self) -> Dict[str, Any]:
        total_requests = len(self._data)
        total_tokens = sum((e.get("tokens", 0) or 0) for e in self._data)
        estimated_cost = total_tokens * settings.COST_PER_TOKEN_USD
        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
        }

    def clear(self) -> None:
        self._data = []
        self._persist()
