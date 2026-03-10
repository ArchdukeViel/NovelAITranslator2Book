from __future__ import annotations

import builtins
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from novelai.config.settings import settings

logger = logging.getLogger(__name__)


class UsageService:
    """Track translation usage (tokens, costs, provider/model choices, etc.)."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.usage_path = self.base_dir / "usage.json"
        self._data: list[dict[str, Any]] = self._load()

    def _load(self) -> builtins.list[dict[str, Any]]:
        if not self.usage_path.exists():
            return []
        try:
            return json.loads(self.usage_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Corrupted usage file at %s; resetting to empty.", self.usage_path)
            return []

    def _persist(self) -> None:
        self.usage_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, entry: dict[str, Any]) -> None:
        """Add a usage entry. The entry should already include timestamp."""
        self._data.append(entry)
        self._persist()

    def _entry_type(self, entry: dict[str, Any]) -> str:
        entry_type = entry.get("entry_type")
        if isinstance(entry_type, str) and entry_type.strip():
            return entry_type.strip().lower()
        return "usage"

    def _int_value(self, value: Any) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return 0

    def _float_value(self, value: Any) -> float:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def _usage_cost_usd(self, entry: dict[str, Any]) -> float:
        explicit_cost = entry.get("actual_cost_usd")
        if isinstance(explicit_cost, (int, float)):
            return float(explicit_cost)
        return self._int_value(entry.get("tokens")) * settings.COST_PER_TOKEN_USD

    def _estimate_total_tokens(self, entry: dict[str, Any]) -> int:
        explicit_total = entry.get("estimated_total_tokens")
        if isinstance(explicit_total, (int, float)):
            return int(explicit_total)
        return self._int_value(entry.get("estimated_input_tokens")) + self._int_value(entry.get("estimated_output_tokens"))

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
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone()

    def _filter_entries(
        self,
        *,
        day: date | None = None,
        all_days: bool = False,
    ) -> builtins.list[dict[str, Any]]:
        if all_days:
            return list(self._data)

        target_day = day or self._local_today()
        filtered: list[dict[str, Any]] = []
        for entry in self._data:
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if timestamp.date() == target_day:
                filtered.append(entry)
        return filtered

    def _summarize_entries(self, entries: builtins.list[dict[str, Any]]) -> dict[str, Any]:
        usage_entries = [entry for entry in entries if self._entry_type(entry) != "estimate"]
        estimate_entries = [entry for entry in entries if self._entry_type(entry) == "estimate"]

        total_requests = len(usage_entries)
        total_tokens = sum(self._int_value(entry.get("tokens")) for entry in usage_entries)
        estimated_cost = sum(self._usage_cost_usd(entry) for entry in usage_entries)
        estimated_input_tokens = sum(self._int_value(entry.get("estimated_input_tokens")) for entry in estimate_entries)
        estimated_output_tokens = sum(self._int_value(entry.get("estimated_output_tokens")) for entry in estimate_entries)
        estimated_total_tokens = sum(self._estimate_total_tokens(entry) for entry in estimate_entries)
        estimated_projection_cost = sum(self._float_value(entry.get("estimated_cost_usd")) for entry in estimate_entries)

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
            "total_estimates": len(estimate_entries),
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_total_tokens,
            "estimated_projection_cost_usd": estimated_projection_cost,
        }

    def list(
        self,
        limit: int | None = None,
        *,
        day: date | None = None,
        all_days: bool = False,
    ) -> builtins.list[dict[str, Any]]:
        entries = self._filter_entries(day=day, all_days=all_days)
        if limit is None:
            return entries
        return list(entries[-limit:])

    def summary(
        self,
        *,
        day: date | None = None,
        all_days: bool = False,
    ) -> dict[str, Any]:
        return self._summarize_entries(self._filter_entries(day=day, all_days=all_days))

    def daily_history(self, limit: int | None = None) -> builtins.list[dict[str, Any]]:
        grouped: dict[date, list[dict[str, Any]]] = {}
        for entry in self._data:
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            grouped.setdefault(timestamp.date(), []).append(entry)

        history: list[dict[str, Any]] = []
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
