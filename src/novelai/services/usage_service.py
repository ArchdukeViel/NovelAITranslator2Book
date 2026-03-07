from __future__ import annotations

import json
from datetime import date, datetime, timezone
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

    def _local_today(self) -> date:
        return datetime.now().astimezone().date()

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone()

    def _filter_entries(
        self,
        *,
        day: date | None = None,
        all_days: bool = False,
    ) -> List[Dict[str, Any]]:
        if all_days:
            return list(self._data)

        target_day = day or self._local_today()
        filtered: List[Dict[str, Any]] = []
        for entry in self._data:
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if timestamp.date() == target_day:
                filtered.append(entry)
        return filtered

    def _summarize_entries(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_requests = len(entries)
        total_tokens = sum((entry.get("tokens", 0) or 0) for entry in entries)
        estimated_cost = total_tokens * settings.COST_PER_TOKEN_USD
        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
        }

    def list(
        self,
        limit: int | None = None,
        *,
        day: date | None = None,
        all_days: bool = False,
    ) -> List[Dict[str, Any]]:
        entries = self._filter_entries(day=day, all_days=all_days)
        if limit is None:
            return entries
        return list(entries[-limit:])

    def summary(
        self,
        *,
        day: date | None = None,
        all_days: bool = False,
    ) -> Dict[str, Any]:
        return self._summarize_entries(self._filter_entries(day=day, all_days=all_days))

    def daily_history(self, limit: int | None = None) -> List[Dict[str, Any]]:
        grouped: dict[date, List[Dict[str, Any]]] = {}
        for entry in self._data:
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            grouped.setdefault(timestamp.date(), []).append(entry)

        history: List[Dict[str, Any]] = []
        for day_key in sorted(grouped.keys(), reverse=True):
            summary = self._summarize_entries(grouped[day_key])
            history.append(
                {
                    "date": day_key.isoformat(),
                    **summary,
                }
            )

        if limit is None:
            return history
        return history[:limit]

    def clear(self) -> None:
        self._data = []
        self._persist()
