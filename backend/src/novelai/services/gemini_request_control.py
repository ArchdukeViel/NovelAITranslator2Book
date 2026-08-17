from __future__ import annotations

import contextlib
import json
import math
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from novelai.config.settings import settings
from novelai.storage.file_lock import InterProcessFileLock
from novelai.utils import atomic_write


@dataclass(frozen=True)
class QuotaReservation:
    reservation_id: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    reserved_at: str


@dataclass(frozen=True)
class QuotaRejection:
    code: str
    retry_after_seconds: int
    dimension: str
    current_requests_this_minute: int
    current_tokens_this_minute: int
    current_requests_today: int
    estimated_input_tokens: int
    estimated_output_tokens: int


def estimate_gemini_tokens(*parts: str, max_output_tokens: int | None = None) -> tuple[int, int]:
    """Return a conservative local estimate without a Gemini countTokens call."""
    input_chars = sum(len(part) for part in parts if isinstance(part, str))
    # Japanese and markup are intentionally estimated conservatively. The
    # estimate is only a scheduling guard; actual provider usage reconciles it.
    input_tokens = max(1, math.ceil(input_chars / 3))
    output_tokens = max(1, max_output_tokens or settings.GEMINI_ESTIMATED_OUTPUT_TOKENS)
    return input_tokens, output_tokens


class GeminiQuotaController:
    """Persisted shared RPM/TPM/RPD admission control for all Gemini calls."""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        resolved_base = (base_dir or settings.NOVEL_LIBRARY_DIR).resolve()
        self.state_path = resolved_base / "gemini_quota_state.json"
        self.lock_path = self.state_path.with_suffix(".lock")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutex = threading.RLock()

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _load_events(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError, OSError, ValueError:
            return []
        events = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(events, list):
            return []
        return [event for event in events if isinstance(event, dict)]

    def _write_events(self, events: list[dict[str, Any]]) -> None:
        atomic_write(
            self.state_path,
            json.dumps({"schema_version": 1, "events": events}, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _timestamp(event: dict[str, Any]) -> datetime | None:
        raw = event.get("timestamp")
        if not isinstance(raw, str):
            return None
        with contextlib.suppress(ValueError):
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)
        return None

    def _prune(self, events: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
        cutoff = now - timedelta(days=1)
        return [event for event in events if (timestamp := self._timestamp(event)) is not None and timestamp >= cutoff]

    @staticmethod
    def _int_value(value: Any) -> int:
        return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0

    def _window_totals(self, events: list[dict[str, Any]], now: datetime) -> tuple[int, int, int]:
        minute_cutoff = now - timedelta(seconds=60)
        today = now.date()
        requests_minute = 0
        tokens_minute = 0
        requests_today = 0
        for event in events:
            timestamp = self._timestamp(event)
            if timestamp is None:
                continue
            if timestamp.date() == today:
                requests_today += 1
            if timestamp >= minute_cutoff:
                requests_minute += 1
                tokens_minute += self._int_value(event.get("total_tokens"))
        return requests_minute, tokens_minute, requests_today

    def _retry_after_for_window(self, events: list[dict[str, Any]], now: datetime, *, tokens: bool) -> int:
        cutoff = now - timedelta(seconds=60)
        candidates: list[datetime] = []
        for event in events:
            timestamp = self._timestamp(event)
            if timestamp is None or timestamp < cutoff:
                continue
            if not tokens or self._int_value(event.get("total_tokens")) > 0:
                candidates.append(timestamp)
        if not candidates:
            return 60
        return max(1, math.ceil((min(candidates) + timedelta(seconds=60) - now).total_seconds()))

    def _with_file_lock(self) -> InterProcessFileLock:
        return InterProcessFileLock(self.lock_path)

    def reserve(
        self,
        *,
        purpose: str,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> QuotaReservation | QuotaRejection:
        estimated_input_tokens = max(1, int(estimated_input_tokens))
        estimated_output_tokens = max(1, int(estimated_output_tokens))
        estimated_total = estimated_input_tokens + estimated_output_tokens
        with self._mutex, self._with_file_lock():
            now = self._now()
            events = self._prune(self._load_events(), now)
            requests_minute, tokens_minute, requests_today = self._window_totals(events, now)
            limits = (
                settings.GEMINI_RPM_LIMIT,
                settings.GEMINI_TPM_LIMIT,
                settings.GEMINI_RPD_LIMIT,
            )
            if requests_minute + 1 > limits[0]:
                return QuotaRejection(
                    "rate_limited",
                    self._retry_after_for_window(events, now, tokens=False),
                    "rpm",
                    requests_minute,
                    tokens_minute,
                    requests_today,
                    estimated_input_tokens,
                    estimated_output_tokens,
                )
            if tokens_minute + estimated_total > limits[1]:
                return QuotaRejection(
                    "rate_limited",
                    self._retry_after_for_window(events, now, tokens=True),
                    "tpm",
                    requests_minute,
                    tokens_minute,
                    requests_today,
                    estimated_input_tokens,
                    estimated_output_tokens,
                )
            if requests_today + 1 > limits[2]:
                tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                retry_after = max(1, math.ceil((tomorrow - now).total_seconds()))
                return QuotaRejection(
                    "quota_exhausted",
                    retry_after,
                    "rpd",
                    requests_minute,
                    tokens_minute,
                    requests_today,
                    estimated_input_tokens,
                    estimated_output_tokens,
                )

            reservation = QuotaReservation(
                reservation_id=uuid.uuid4().hex,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                reserved_at=now.isoformat().replace("+00:00", "Z"),
            )
            events.append(
                {
                    "reservation_id": reservation.reservation_id,
                    "timestamp": reservation.reserved_at,
                    "purpose": str(purpose)[:64],
                    "model": str(model)[:128],
                    "estimated_input_tokens": estimated_input_tokens,
                    "estimated_output_tokens": estimated_output_tokens,
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": estimated_total,
                    "status": "reserved",
                }
            )
            self._write_events(events)
            return reservation

    def reconcile(
        self,
        reservation: QuotaReservation,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        success: bool,
    ) -> None:
        with self._mutex, self._with_file_lock():
            now = self._now()
            events = self._prune(self._load_events(), now)
            for event in events:
                if event.get("reservation_id") != reservation.reservation_id:
                    continue
                actual_input = max(0, int(input_tokens)) if isinstance(input_tokens, int) else None
                actual_output = max(0, int(output_tokens)) if isinstance(output_tokens, int) else None
                actual_total = max(0, int(total_tokens)) if isinstance(total_tokens, int) else None
                if actual_total is None and actual_input is not None and actual_output is not None:
                    actual_total = actual_input + actual_output
                event["input_tokens"] = actual_input
                event["output_tokens"] = actual_output
                event["total_tokens"] = (
                    actual_total
                    if actual_total is not None
                    else (reservation.estimated_input_tokens + reservation.estimated_output_tokens)
                )
                event["status"] = "success" if success else "failure"
                break
            self._write_events(events)

    def snapshot(self) -> dict[str, Any]:
        with self._mutex, self._with_file_lock():
            now = self._now()
            events = self._prune(self._load_events(), now)
            requests_minute, tokens_minute, requests_today = self._window_totals(events, now)
            return {
                "limits": {
                    "requests_per_minute": settings.GEMINI_RPM_LIMIT,
                    "tokens_per_minute": settings.GEMINI_TPM_LIMIT,
                    "requests_per_day": settings.GEMINI_RPD_LIMIT,
                },
                "current_minute": {
                    "requests": requests_minute,
                    "tokens": tokens_minute,
                },
                "today": {"requests": requests_today},
            }


_CONTROLLERS: dict[Path, GeminiQuotaController] = {}
_CONTROLLERS_LOCK = threading.Lock()


def get_gemini_quota_controller() -> GeminiQuotaController:
    path = (settings.NOVEL_LIBRARY_DIR / "gemini_quota_state.json").resolve()
    with _CONTROLLERS_LOCK:
        controller = _CONTROLLERS.get(path.parent)
        if controller is None:
            controller = GeminiQuotaController(path.parent)
            _CONTROLLERS[path.parent] = controller
        return controller
