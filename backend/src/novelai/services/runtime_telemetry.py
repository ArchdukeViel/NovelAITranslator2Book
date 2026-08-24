"""Bounded, privacy-safe runtime observations.

This module deliberately stores only fixed-cardinality metric fields.  It is
an interval/application observation seam, not a trace or request-log store:
prompts, responses, URLs, credentials, identities, and exception messages do
not have a representation in the observation schema.
"""

from __future__ import annotations

import asyncio
import importlib
import math
import sys
import threading
import time
import tracemalloc
from collections import deque
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TelemetryStage(StrEnum):
    FETCH = "fetch"
    RAW_NORMALIZATION = "raw_normalization"
    NOVEL_METADATA = "novel_metadata_load"
    GLOSSARY = "glossary_load"
    SELECTION = "selection"
    SEGMENTATION = "segmentation"
    PROVIDER_WAIT = "provider_wait"
    PROVIDER_RETRY = "provider_retry"
    PROVIDER_EXECUTION = "provider_execution"
    QA = "qa"
    PERSISTENCE = "persistence"
    POSTGRES_COMMIT = "postgres_commit"
    ACTIVITY_STATE = "activity_state_update"
    R2 = "r2"
    QUEUE = "queue"
    PROCESS = "process"


class TelemetryOperation(StrEnum):
    STAGE = "pipeline_stage"
    EXECUTOR_QUEUE = "executor_queue"
    DB_CHECKOUT = "db_checkout"
    DB_STATEMENT = "db_statement"
    DB_COMMIT = "db_commit"
    PROVIDER_WAIT = "provider_wait"
    PROVIDER_RETRY = "provider_retry"
    PROVIDER_CALL = "provider_call"
    QA = "qa"
    R2_OPERATION = "r2_operation"
    QUEUE_AGE = "queue_age"
    EVENT_LOOP_LAG = "event_loop_lag"
    PROCESS_RESOURCES = "process_resources"


class TelemetryOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"


class TelemetryUnavailableReason(StrEnum):
    EVENT_LOOP_SAMPLER_NOT_STARTED = "event_loop_sampler_not_started"
    PROCESS_MEMORY_SAMPLER_UNAVAILABLE = "process_memory_sampler_unavailable"
    NETWORK_BYTES_UNAVAILABLE = "network_bytes_unavailable"
    DB_POOL_CHECKOUT_NOT_INSTRUMENTED = "db_pool_checkout_not_instrumented"
    DB_BILLED_BYTES_UNAVAILABLE = "db_billed_bytes_unavailable"
    PROVIDER_RESPONSE_BYTES_UNAVAILABLE = "provider_response_bytes_unavailable"
    R2_BYTES_UNAVAILABLE = "r2_bytes_unavailable"
    QUEUE_AGE_UNAVAILABLE = "queue_age_unavailable"
    METRIC_COLLECTION_FAILED = "metric_collection_failed"


REQUIRED_TELEMETRY_OPERATIONS: tuple[tuple[TelemetryStage, TelemetryOperation], ...] = (
    (TelemetryStage.FETCH, TelemetryOperation.STAGE),
    (TelemetryStage.RAW_NORMALIZATION, TelemetryOperation.STAGE),
    (TelemetryStage.NOVEL_METADATA, TelemetryOperation.STAGE),
    (TelemetryStage.GLOSSARY, TelemetryOperation.STAGE),
    (TelemetryStage.SELECTION, TelemetryOperation.STAGE),
    (TelemetryStage.SEGMENTATION, TelemetryOperation.STAGE),
    (TelemetryStage.PROVIDER_WAIT, TelemetryOperation.PROVIDER_WAIT),
    (TelemetryStage.PROVIDER_RETRY, TelemetryOperation.PROVIDER_RETRY),
    (TelemetryStage.PROVIDER_EXECUTION, TelemetryOperation.PROVIDER_CALL),
    (TelemetryStage.QA, TelemetryOperation.QA),
    (TelemetryStage.PERSISTENCE, TelemetryOperation.STAGE),
    (TelemetryStage.POSTGRES_COMMIT, TelemetryOperation.DB_COMMIT),
    (TelemetryStage.ACTIVITY_STATE, TelemetryOperation.STAGE),
    (TelemetryStage.R2, TelemetryOperation.R2_OPERATION),
    (TelemetryStage.QUEUE, TelemetryOperation.QUEUE_AGE),
    (TelemetryStage.PROCESS, TelemetryOperation.PROCESS_RESOURCES),
)


def _enum_value(enum_type: type[StrEnum], value: StrEnum | str, field_name: str) -> str:
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValueError(f"unsupported telemetry {field_name}") from exc


def _nonnegative_float(value: float | int | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return round(max(0.0, numeric), 3)


def _nonnegative_int(value: int | None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(0, value)


def _validated_reasons(reasons: Iterable[TelemetryUnavailableReason | str]) -> tuple[str, ...]:
    values: set[str] = set()
    for reason in reasons:
        values.add(_enum_value(TelemetryUnavailableReason, reason, "unavailable_reason"))
    return tuple(sorted(values))


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    """One bounded observation with no free-form or protected fields."""

    stage: TelemetryStage | str
    operation: TelemetryOperation | str
    outcome: TelemetryOutcome | str = TelemetryOutcome.SUCCESS
    duration_ms: float | None = None
    queue_wait_ms: float | None = None
    event_loop_lag_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_count: int | None = None
    db_rows: int | None = None
    r2_operation_count: int | None = None
    r2_bytes: int | None = None
    cpu_ms: float | None = None
    memory_bytes: int | None = None
    network_bytes: int | None = None
    unavailable_reasons: tuple[TelemetryUnavailableReason | str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage", _enum_value(TelemetryStage, self.stage, "stage"))
        object.__setattr__(self, "operation", _enum_value(TelemetryOperation, self.operation, "operation"))
        outcome = _enum_value(TelemetryOutcome, self.outcome, "outcome")
        object.__setattr__(self, "outcome", outcome)
        for field_name in (
            "duration_ms",
            "queue_wait_ms",
            "event_loop_lag_ms",
            "cpu_ms",
        ):
            object.__setattr__(self, field_name, _nonnegative_float(getattr(self, field_name)))
        for field_name in (
            "input_tokens",
            "output_tokens",
            "retry_count",
            "db_rows",
            "r2_operation_count",
            "r2_bytes",
            "memory_bytes",
            "network_bytes",
        ):
            object.__setattr__(self, field_name, _nonnegative_int(getattr(self, field_name)))
        reasons = _validated_reasons(self.unavailable_reasons)
        if outcome == TelemetryOutcome.UNAVAILABLE.value and not reasons:
            raise ValueError("unavailable telemetry observations require a named reason")
        object.__setattr__(self, "unavailable_reasons", reasons)

    def to_dict(self) -> dict[str, object]:
        values = {
            "schema_version": 1,
            "stage": self.stage,
            "operation": self.operation,
            "outcome": self.outcome,
            "duration_ms": self.duration_ms,
            "queue_wait_ms": self.queue_wait_ms,
            "event_loop_lag_ms": self.event_loop_lag_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "retry_count": self.retry_count,
            "db_rows": self.db_rows,
            "r2_operation_count": self.r2_operation_count,
            "r2_bytes": self.r2_bytes,
            "cpu_ms": self.cpu_ms,
            "memory_bytes": self.memory_bytes,
            "network_bytes": self.network_bytes,
            "unavailable_reasons": list(self.unavailable_reasons),
        }
        return {key: value for key, value in values.items() if value is not None and value != []}


def _process_memory_bytes() -> tuple[int | None, str | None]:
    try:
        process_resource: Any = importlib.import_module("resource")
    except ImportError:
        if tracemalloc.is_tracing():
            current, _peak = tracemalloc.get_traced_memory()
            return max(0, int(current)), None
        return None, TelemetryUnavailableReason.PROCESS_MEMORY_SAMPLER_UNAVAILABLE.value

    getrusage = getattr(process_resource, "getrusage", None)
    rusage_self = getattr(process_resource, "RUSAGE_SELF", None)
    if not callable(getrusage) or rusage_self is None:
        return None, TelemetryUnavailableReason.PROCESS_MEMORY_SAMPLER_UNAVAILABLE.value
    usage = getrusage(rusage_self)
    # Linux reports KiB; macOS reports bytes.  Windows takes the explicit
    # unavailable path above because the optional platform API is not a
    # required runtime dependency.
    max_rss = getattr(usage, "ru_maxrss", None)
    if isinstance(max_rss, bool) or not isinstance(max_rss, (int, float)) or not math.isfinite(float(max_rss)):
        return None, TelemetryUnavailableReason.PROCESS_MEMORY_SAMPLER_UNAVAILABLE.value
    multiplier = 1 if sys.platform == "darwin" else 1024
    return max(0, int(max_rss * multiplier)), None


class BoundedRuntimeTelemetry:
    """Thread-safe bounded observation buffer and event-loop lag sampler."""

    def __init__(self, *, max_observations: int = 256, sample_interval_seconds: float = 0.25) -> None:
        if not 1 <= max_observations <= 4096:
            raise ValueError("max_observations must be between 1 and 4096")
        if not 0.01 <= sample_interval_seconds <= 60.0:
            raise ValueError("sample_interval_seconds must be between 0.01 and 60")
        self.max_observations = max_observations
        self.sample_interval_seconds = sample_interval_seconds
        self._observations: deque[RuntimeObservation] = deque(maxlen=max_observations)
        self._lock = threading.Lock()
        self._sampler_task: asyncio.Task[None] | None = None

    def record(self, observation: RuntimeObservation) -> None:
        """Append one observation; the deque bounds memory by construction."""

        if not isinstance(observation, RuntimeObservation):
            raise TypeError("telemetry record must be a RuntimeObservation")
        with self._lock:
            self._observations.append(observation)

    def configure(self, *, max_observations: int, sample_interval_seconds: float) -> None:
        """Apply validated runtime settings before the sampler is started."""

        if self.sampler_running():
            raise RuntimeError("runtime telemetry cannot be reconfigured while sampling")
        if not 1 <= max_observations <= 4096:
            raise ValueError("max_observations must be between 1 and 4096")
        if not 0.01 <= sample_interval_seconds <= 60.0:
            raise ValueError("sample_interval_seconds must be between 0.01 and 60")
        with self._lock:
            self.max_observations = max_observations
            self.sample_interval_seconds = sample_interval_seconds
            self._observations = deque(self._observations, maxlen=max_observations)

    def snapshot(self) -> tuple[RuntimeObservation, ...]:
        with self._lock:
            return tuple(self._observations)

    def clear(self) -> None:
        with self._lock:
            self._observations.clear()

    def latest(self, *, stage: TelemetryStage, operation: TelemetryOperation) -> RuntimeObservation | None:
        stage_value = stage.value
        operation_value = operation.value
        with self._lock:
            for observation in reversed(self._observations):
                if observation.stage == stage_value and observation.operation == operation_value:
                    return observation
        return None

    def unavailable_count(self) -> int:
        with self._lock:
            return sum(1 for observation in self._observations if observation.unavailable_reasons)

    def sample_process_resources(self) -> RuntimeObservation:
        memory_bytes, memory_reason = _process_memory_bytes()
        reasons = [TelemetryUnavailableReason.NETWORK_BYTES_UNAVAILABLE.value]
        if memory_reason is not None:
            reasons.append(memory_reason)
        observation = RuntimeObservation(
            stage=TelemetryStage.PROCESS,
            operation=TelemetryOperation.PROCESS_RESOURCES,
            cpu_ms=_nonnegative_float(time.process_time() * 1000),
            memory_bytes=memory_bytes,
            unavailable_reasons=tuple(reasons),
        )
        self.record(observation)
        return observation

    async def start(self) -> None:
        if self._sampler_task is not None and not self._sampler_task.done():
            return
        self._sampler_task = asyncio.create_task(self._sample_loop(), name="novelai-event-loop-telemetry")

    async def stop(self) -> None:
        task = self._sampler_task
        self._sampler_task = None
        if task is None or task.done():
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    def sampler_running(self) -> bool:
        return self._sampler_task is not None and not self._sampler_task.done()

    async def _sample_loop(self) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.sample_interval_seconds
        while True:
            await asyncio.sleep(self.sample_interval_seconds)
            now = loop.time()
            lag_ms = max(0.0, (now - deadline) * 1000)
            self.record(
                RuntimeObservation(
                    stage=TelemetryStage.PROCESS,
                    operation=TelemetryOperation.EVENT_LOOP_LAG,
                    event_loop_lag_ms=lag_ms,
                    unavailable_reasons=()
                    if self.sampler_running()
                    else (TelemetryUnavailableReason.EVENT_LOOP_SAMPLER_NOT_STARTED.value,),
                )
            )
            deadline = now + self.sample_interval_seconds


runtime_telemetry = BoundedRuntimeTelemetry()
