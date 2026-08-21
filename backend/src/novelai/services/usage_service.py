from __future__ import annotations

import builtins
import json
import logging
import threading
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from novelai.config.settings import settings
from novelai.storage.file_lock import InterProcessFileLock
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)
_USAGE_LOCK = threading.RLock()


class UsageService:
    """Track translation usage (tokens, costs, provider/model choices, etc.)."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.RUNTIME_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.usage_path = self.base_dir / "usage.json"
        self.lock_path = self.usage_path.with_suffix(".lock")
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
        atomic_write(self.usage_path, json.dumps(self._data, ensure_ascii=False, indent=2))

    def reload(self) -> None:
        """Reload usage history from disk."""
        with _USAGE_LOCK, InterProcessFileLock(self.lock_path):
            self._data = self._load()

    def record(self, entry: dict[str, Any], *, measure_write: bool = False) -> float | None:
        """Add a usage entry. The entry should already include timestamp."""
        with _USAGE_LOCK, InterProcessFileLock(self.lock_path):
            # Providers may be constructed independently from the runtime
            # container. Reload before appending so one instance cannot
            # overwrite another instance's accounting entries.
            self._data = self._load()
            stored_entry = dict(entry)
            self._data.append(stored_entry)
            self._evict_if_needed()
            started = time.perf_counter()
            self._persist()
            if not measure_write:
                return None
            duration_ms = round(max(0.0, (time.perf_counter() - started) * 1000), 3)
            stored_entry["usage_write_ms"] = duration_ms
            self._persist()
            return duration_ms

    def record_provider_request(
        self,
        *,
        timestamp: str,
        provider_key: str,
        provider_model: str,
        purpose: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        success: bool,
        retry_attempt: int,
        chapter_id: str | None = None,
        chunk_id: str | None = None,
        cache_status: str | None = None,
        error_code: str | None = None,
        request_made: bool = True,
        provider_wait_ms: float | None = None,
        provider_execution_ms: float | None = None,
        quota_reservation_ms: float | None = None,
        usage_write_ms: float | None = None,
    ) -> float | None:
        """Persist sanitized per-request accounting without prompt contents."""

        def _safe(value: Any, limit: int = 255) -> str | None:
            if value is None:
                return None
            text = str(value).strip()
            return text[:limit] or None

        def _duration(value: float | None) -> float | None:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            return round(max(0.0, float(value)), 3)

        return self.record(
            {
                "entry_type": "provider_request",
                "timestamp": timestamp,
                "provider": _safe(provider_key, 64),
                "model": _safe(provider_model, 128),
                "purpose": _safe(purpose, 64),
                "input_tokens": input_tokens if isinstance(input_tokens, int) else None,
                "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
                "total_tokens": total_tokens if isinstance(total_tokens, int) else None,
                "tokens": total_tokens if isinstance(total_tokens, int) else None,
                "estimated_input_tokens": max(0, int(estimated_input_tokens)),
                "estimated_output_tokens": max(0, int(estimated_output_tokens)),
                "success": bool(success),
                "retry_attempt": max(0, int(retry_attempt)),
                "chapter_id": _safe(chapter_id),
                "chunk_id": _safe(chunk_id),
                "cache_status": _safe(cache_status, 32),
                "error_code": _safe(error_code, 64),
                "request_made": bool(request_made),
                "provider_wait_ms": _duration(provider_wait_ms),
                "provider_execution_ms": _duration(provider_execution_ms),
                "quota_reservation_ms": _duration(quota_reservation_ms),
                "usage_write_ms": _duration(usage_write_ms),
            },
            measure_write=True,
        )

    def provider_request_summary(self) -> dict[str, Any]:
        """Return current-minute/day counters grouped by request purpose."""
        with _USAGE_LOCK, InterProcessFileLock(self.lock_path):
            self._data = self._load()
            now = datetime.now(UTC)
            minute_cutoff = now - timedelta(seconds=60)
            requests: list[dict[str, Any]] = []
            for entry in self._data:
                if self._entry_type(entry) != "provider_request":
                    continue
                timestamp = self._parse_timestamp(entry.get("timestamp"))
                if timestamp is None:
                    continue
                requests.append({"entry": entry, "timestamp": timestamp.astimezone(UTC)})

            def _aggregate(items: list[dict[str, Any]]) -> dict[str, int]:
                return {
                    "requests": len(items),
                    "input_tokens": sum(self._int_value(item["entry"].get("input_tokens")) for item in items),
                    "output_tokens": sum(self._int_value(item["entry"].get("output_tokens")) for item in items),
                    "total_tokens": sum(self._int_value(item["entry"].get("total_tokens")) for item in items),
                }

            current = [item for item in requests if item["timestamp"] >= minute_cutoff]
            today = [item for item in requests if item["timestamp"].date() == now.date()]
            current_api = [item for item in current if item["entry"].get("request_made", True) is not False]
            today_api = [item for item in today if item["entry"].get("request_made", True) is not False]
            by_purpose: dict[str, dict[str, int]] = {}
            cache_hits_today = sum(1 for item in today if item["entry"].get("cache_status") == "hit")
            for item in today_api:
                purpose = str(item["entry"].get("purpose") or "unknown")
                by_purpose.setdefault(purpose, {"requests": 0, "total_tokens": 0})
                by_purpose[purpose]["requests"] += 1
                by_purpose[purpose]["total_tokens"] += self._int_value(item["entry"].get("total_tokens"))
            return {
                "current_minute": _aggregate(current_api),
                "today": _aggregate(today_api),
                "by_purpose": by_purpose,
                "cache_hits_today": cache_hits_today,
            }

    def _evict_if_needed(self) -> None:
        """Drop oldest entries when the log exceeds the configured maximum."""
        max_entries = settings.USAGE_LOG_MAX_ENTRIES
        if len(self._data) <= max_entries:
            return
        excess = len(self._data) - max_entries
        self._data = self._data[excess:]
        logger.info("Trimmed %d oldest usage entries (max %d).", excess, max_entries)

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
        return self._int_value(entry.get("estimated_input_tokens")) + self._int_value(
            entry.get("estimated_output_tokens")
        )

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
        estimated_output_tokens = sum(
            self._int_value(entry.get("estimated_output_tokens")) for entry in estimate_entries
        )
        estimated_total_tokens = sum(self._estimate_total_tokens(entry) for entry in estimate_entries)
        estimated_projection_cost = sum(
            self._float_value(entry.get("estimated_cost_usd")) for entry in estimate_entries
        )

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
