from __future__ import annotations

import contextlib
import json
import math
import threading
import uuid
from collections.abc import Callable, Iterator
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
    linked_reservation_ids: tuple[str, ...] = ()


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
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        rpd_limit: int | None = None,
        concurrency_limit: int | None = None,
    ) -> None:
        resolved_base = (base_dir or settings.RUNTIME_DIR).resolve()
        self.state_path = resolved_base / "gemini_quota_state.json"
        self.lock_path = self.state_path.with_suffix(".lock")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutex = threading.RLock()
        self._rpm_limit = rpm_limit or settings.GEMINI_RPM_LIMIT
        self._tpm_limit = tpm_limit or settings.GEMINI_TPM_LIMIT
        self._rpd_limit = rpd_limit or settings.GEMINI_RPD_LIMIT
        # Explicit production factories pass a limit. Directly constructed
        # controllers remain quota-only for compatibility with maintenance and
        # unit-test callers that intentionally exercise RPM/TPM/RPD in isolation.
        self._concurrency_limit = concurrency_limit

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

    def _inflight_count(self, events: list[dict[str, Any]], now: datetime) -> int:
        cutoff = now - timedelta(seconds=settings.PROVIDER_RESERVATION_TTL_SECONDS)
        return sum(
            1
            for event in events
            if event.get("status") == "reserved"
            and (timestamp := self._timestamp(event)) is not None
            and timestamp >= cutoff
        )

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

    def _with_file_lock(self) -> Any:
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
            inflight = self._inflight_count(events, now)
            limits = (self._rpm_limit, self._tpm_limit, self._rpd_limit)
            if self._concurrency_limit is not None and inflight >= self._concurrency_limit:
                return QuotaRejection(
                    "rate_limited",
                    1,
                    "concurrency",
                    requests_minute,
                    tokens_minute,
                    requests_today,
                    estimated_input_tokens,
                    estimated_output_tokens,
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
                    "requests_per_minute": self._rpm_limit,
                    "tokens_per_minute": self._tpm_limit,
                    "requests_per_day": self._rpd_limit,
                    "concurrency": self._concurrency_limit,
                },
                "current_minute": {
                    "requests": requests_minute,
                    "tokens": tokens_minute,
                },
                "in_flight": self._inflight_count(events, now),
                "today": {"requests": requests_today},
            }


class CompositeGeminiQuotaController(GeminiQuotaController):
    """Apply a shared project cap and a per-credential cap atomically enough.

    A contributor key does not create a new provider quota domain merely by
    existing.  The shared controller reserves project capacity first, then
    the credential controller reserves the per-key allowance.  A failed
    second reservation reconciles the first one immediately; provider
    success/failure/timeout reconciliation fans out to both reservations.
    """

    def __init__(self, controllers: tuple[GeminiQuotaController, ...]) -> None:
        if len(controllers) < 2:
            raise ValueError("composite quota control requires project and credential controllers")
        self._controllers = controllers

    def reserve(
        self,
        *,
        purpose: str,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> QuotaReservation | QuotaRejection:
        reservations: list[QuotaReservation] = []
        for controller in self._controllers:
            decision = controller.reserve(
                purpose=purpose,
                model=model,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
            )
            if isinstance(decision, QuotaRejection):
                for reservation, reserved_controller in zip(reservations, self._controllers, strict=False):
                    reserved_controller.reconcile(
                        reservation,
                        input_tokens=None,
                        output_tokens=None,
                        total_tokens=None,
                        success=False,
                    )
                return decision
            reservations.append(decision)

        return QuotaReservation(
            reservation_id=uuid.uuid4().hex,
            estimated_input_tokens=max(1, int(estimated_input_tokens)),
            estimated_output_tokens=max(1, int(estimated_output_tokens)),
            reserved_at=reservations[0].reserved_at,
            linked_reservation_ids=tuple(reservation.reservation_id for reservation in reservations),
        )

    def reconcile(
        self,
        reservation: QuotaReservation,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        success: bool,
    ) -> None:
        linked_ids = reservation.linked_reservation_ids
        if len(linked_ids) != len(self._controllers):
            return
        for controller, linked_id in zip(self._controllers, linked_ids, strict=True):
            controller.reconcile(
                QuotaReservation(
                    reservation_id=linked_id,
                    estimated_input_tokens=reservation.estimated_input_tokens,
                    estimated_output_tokens=reservation.estimated_output_tokens,
                    reserved_at=reservation.reserved_at,
                ),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                success=success,
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "project": self._controllers[0].snapshot(),
            "credential": self._controllers[1].snapshot(),
        }


class RedisGeminiQuotaController(GeminiQuotaController):
    """Distributed quota controller for production and split deployments."""

    def __init__(
        self,
        *,
        namespace: str,
        clock: Callable[[], datetime] | None = None,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        rpd_limit: int | None = None,
        concurrency_limit: int | None = None,
    ) -> None:
        super().__init__(
            Path("."),
            clock=clock,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            rpd_limit=rpd_limit,
            concurrency_limit=concurrency_limit,
        )
        if not settings.REDIS_URL:
            raise RuntimeError("REDIS_URL is required for production Gemini quota coordination")
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("The redis package is required for production Gemini quota coordination") from exc
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        safe_namespace = "".join(char if char.isalnum() or char in "-_.:" else "_" for char in namespace)
        self._events_key = f"novelai:gemini:quota:{safe_namespace}:events"
        self._lock_key = f"novelai:gemini:quota:{safe_namespace}:lock"

    def _load_events(self) -> list[dict[str, Any]]:
        raw_events = self._redis.lrange(self._events_key, 0, -1)
        events: list[dict[str, Any]] = []
        for raw in raw_events:
            try:
                value = json.loads(raw)
            except TypeError, ValueError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events

    def _write_events(self, events: list[dict[str, Any]]) -> None:
        pipeline = self._redis.pipeline(transaction=True)
        pipeline.delete(self._events_key)
        if events:
            pipeline.rpush(
                self._events_key, *(json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in events)
            )
            pipeline.expire(self._events_key, 86_400)
        pipeline.execute()

    @contextlib.contextmanager
    def _with_file_lock(self) -> Iterator[None]:
        lock = self._redis.lock(self._lock_key, timeout=15, blocking_timeout=15)
        acquired = False
        try:
            acquired = bool(lock.acquire())
            if not acquired:
                raise TimeoutError("Redis quota lock could not be acquired")
            yield
        finally:
            if acquired:
                with contextlib.suppress(Exception):
                    lock.release()


_CONTROLLERS: dict[str, GeminiQuotaController] = {}
_CONTROLLERS_LOCK = threading.Lock()


def get_gemini_quota_controller() -> GeminiQuotaController:
    if settings.ENV != "test":
        key = f"redis:{settings.REDIS_URL}:owner"
        with _CONTROLLERS_LOCK:
            controller = _CONTROLLERS.get(key)
            if controller is None:
                controller = RedisGeminiQuotaController(
                    namespace="owner",
                    concurrency_limit=settings.GEMINI_CONCURRENCY_LIMIT,
                )
                _CONTROLLERS[key] = controller
            return controller

    key = str((settings.RUNTIME_DIR / "gemini_quota_state.json").resolve())
    with _CONTROLLERS_LOCK:
        controller = _CONTROLLERS.get(key)
        if controller is None:
            controller = GeminiQuotaController(
                settings.RUNTIME_DIR,
                concurrency_limit=settings.GEMINI_CONCURRENCY_LIMIT,
            )
            _CONTROLLERS[key] = controller
        return controller
