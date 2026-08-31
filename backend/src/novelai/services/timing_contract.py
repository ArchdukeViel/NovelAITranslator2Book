"""Fixed, privacy-safe timing contracts for bounded diagnostics.

The contract deliberately represents intervals and aggregate samples instead of
request traces.  It has no fields for users, URLs, SQL, object keys, payloads,
credentials, or provider responses.  Durations are measured with one
process-local monotonic clock; UTC belongs only in the surrounding evidence
record.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

TIMING_SCHEMA_VERSION = 1
MONOTONIC_CLOCK = "monotonic_ns"

TIMING_SPANS: tuple[str, ...] = (
    "total_client",
    "dns",
    "tcp",
    "tls",
    "cloudflare_edge",
    "tunnel",
    "caddy",
    "application_total",
    "db_pool_checkout",
    "sql_execution",
    "r2_exact_read",
    "r2_exact_write",
    "cache_or_fallback",
    "serialization",
    "application_exclusive",
    "network_remainder",
)

PIPELINE_TIMING_STAGES: tuple[str, ...] = (
    "intake_validation",
    "source_fetch",
    "parsing",
    "database_persistence",
    "queue_enqueue",
    "queue_wait",
    "worker_dequeue",
    "provider_request",
    "provider_wait",
    "provider_ttfb",
    "provider_body_parse",
    "retry_backoff",
    "translation",
    "qa",
    "r2_write",
    "database_commit",
    "notification",
)

DATABASE_TIMING_SPANS: tuple[str, ...] = (
    "request_preparation",
    "serialized_input",
    "db_pool_checkout",
    "sql_execution",
    "row_mapping",
    "database_commit",
    "rollback",
    "connection_release",
    "serialized_output",
    "total_client",
)

R2_TIMING_SPANS: tuple[str, ...] = (
    "upload_preparation",
    "download_preparation",
    "request_connection",
    "gateway_handling",
    "binding_operation",
    "first_byte",
    "full_body",
    "checksum_verification",
    "etag_verification",
    "decode_decompress",
    "cache_or_fallback",
    "serialization",
)

TIMING_SOURCES: tuple[str, ...] = (
    "client",
    "proxy",
    "application",
    "database",
    "r2_gateway",
    "r2_binding",
    "pipeline",
    "provider_mock",
    "ci",
    "local_synthetic",
    "hosted_mcp",
)

TIMING_AGGREGATIONS: tuple[str, ...] = (
    "single",
    "count",
    "mean",
    "p50",
    "p95",
    "p99",
)

UNAVAILABLE_REASONS: tuple[str, ...] = (
    "provider_internal_timing_unavailable",
    "pooler_granularity_unavailable",
    "test_r2_gateway_not_authorized",
    "test_worker_not_authorized",
    "isolated_reader_runtime_unavailable",
    "cross_system_correlation_unavailable",
    "translation_worker_paused",
    "full_translation_queue_paused",
    "network_layer_not_observable",
    "hosted_telemetry_unavailable",
    "permission_denied",
    "retry_not_exercised",
    "notification_not_exercised",
    "span_not_instrumented",
)

_ALLOWED_NAMES = frozenset((*TIMING_SPANS, *PIPELINE_TIMING_STAGES, *DATABASE_TIMING_SPANS, *R2_TIMING_SPANS))
_ALLOWED_PARENTS = frozenset((*_ALLOWED_NAMES, "pipeline_total", "database_cell", "r2_cell"))


def _finite_nonnegative(value: float | int, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite non-negative number")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return round(numeric, 3)


def _positive_count(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class TimingInterval:
    """An interval on the trace's single monotonic clock."""

    start_offset_ms: float
    duration_ms: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_offset_ms", _finite_nonnegative(self.start_offset_ms, "start_offset_ms"))
        object.__setattr__(self, "duration_ms", _finite_nonnegative(self.duration_ms, "duration_ms"))

    @property
    def end_offset_ms(self) -> float:
        return round(self.start_offset_ms + self.duration_ms, 3)


@dataclass(frozen=True, slots=True)
class TimingSpan:
    """One fixed-label timing observation or an explicit unavailable cell."""

    name: str
    source: str
    parent: str | None = None
    clock: str = MONOTONIC_CLOCK
    start_offset_ms: float | None = None
    duration_ms: float | None = None
    sample_count: int = 0
    aggregation: str = "single"
    available: bool = True
    unavailable_reason: str | None = None
    critical_path: bool = False

    def __post_init__(self) -> None:
        if self.name not in _ALLOWED_NAMES:
            raise ValueError("timing span name is not in the fixed contract")
        if self.source not in TIMING_SOURCES:
            raise ValueError("timing span source is not in the fixed contract")
        if self.parent is not None and self.parent not in _ALLOWED_PARENTS:
            raise ValueError("timing span parent is not in the fixed contract")
        if self.clock != MONOTONIC_CLOCK:
            raise ValueError("timing spans must use the process-local monotonic clock")
        if self.aggregation not in TIMING_AGGREGATIONS:
            raise ValueError("timing aggregation is not in the fixed contract")
        if not isinstance(self.critical_path, bool):
            raise ValueError("critical_path must be boolean")
        if self.available:
            if self.start_offset_ms is None or self.duration_ms is None:
                raise ValueError("available timing spans require start and duration")
            if self.unavailable_reason is not None:
                raise ValueError("available timing spans cannot have an unavailable reason")
            if self.sample_count <= 0:
                raise ValueError("available timing spans require a positive sample count")
            object.__setattr__(self, "start_offset_ms", _finite_nonnegative(self.start_offset_ms, "start_offset_ms"))
            object.__setattr__(self, "duration_ms", _finite_nonnegative(self.duration_ms, "duration_ms"))
        else:
            if self.start_offset_ms is not None or self.duration_ms is not None:
                raise ValueError("unavailable timing spans cannot contain a duration")
            if self.sample_count != 0:
                raise ValueError("unavailable timing spans must have zero samples")
            if self.unavailable_reason not in UNAVAILABLE_REASONS:
                raise ValueError("unavailable timing spans require a fixed reason")

    @classmethod
    def unavailable(
        cls,
        name: str,
        *,
        source: str,
        reason: str,
        parent: str | None = None,
        critical_path: bool = False,
    ) -> TimingSpan:
        return cls(
            name=name,
            source=source,
            parent=parent,
            available=False,
            unavailable_reason=reason,
            critical_path=critical_path,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source": self.source,
            "parent": self.parent,
            "clock": self.clock,
            "start_offset_ms": self.start_offset_ms,
            "duration_ms": self.duration_ms,
            "sample_count": self.sample_count,
            "aggregation": self.aggregation,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "critical_path": self.critical_path,
        }


def _interval_union_ms(parent: TimingInterval, children: Iterable[TimingInterval]) -> float:
    segments: list[tuple[float, float]] = []
    for child in children:
        if child.start_offset_ms < parent.start_offset_ms or child.end_offset_ms > parent.end_offset_ms:
            raise ValueError("child timing interval must be nested inside its parent")
        if child.duration_ms > 0:
            segments.append((child.start_offset_ms, child.end_offset_ms))
    segments.sort()
    covered = 0.0
    current_start: float | None = None
    current_end = 0.0
    for start, end in segments:
        if current_start is None:
            current_start, current_end = start, end
        elif start <= current_end:
            current_end = max(current_end, end)
        else:
            covered += current_end - current_start
            current_start, current_end = start, end
    if current_start is not None:
        covered += current_end - current_start
    return round(covered, 3)


def exclusive_duration_ms(parent: TimingInterval, children: Iterable[TimingInterval]) -> float:
    """Return parent time not covered by the union of nested child intervals."""

    covered = _interval_union_ms(parent, children)
    return round(parent.duration_ms - covered, 3)


def network_remainder_ms(total: TimingInterval, measured_network: Iterable[TimingInterval]) -> float:
    """Return a valid correlated network residual, or reject unsafe nesting."""

    return exclusive_duration_ms(total, measured_network)


@dataclass(slots=True)
class TimingTrace:
    """Bounded in-process trace builder with no identity or request fields."""

    max_spans: int = 128
    _started_ns: int = field(default_factory=time.perf_counter_ns, init=False, repr=False)
    _spans: list[TimingSpan] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not 1 <= self.max_spans <= 4096:
            raise ValueError("max_spans must be between 1 and 4096")

    @property
    def spans(self) -> tuple[TimingSpan, ...]:
        return tuple(self._spans)

    def add(self, span: TimingSpan) -> TimingSpan:
        if len(self._spans) >= self.max_spans:
            raise ValueError("timing trace span limit exceeded")
        self._spans.append(span)
        return span

    @contextmanager
    def measure(
        self,
        name: str,
        *,
        source: str,
        parent: str | None = None,
        sample_count: int = 1,
        aggregation: str = "single",
        critical_path: bool = False,
    ) -> Iterator[None]:
        started_ns = time.perf_counter_ns()
        try:
            yield
        finally:
            ended_ns = time.perf_counter_ns()
            self.add(
                TimingSpan(
                    name=name,
                    source=source,
                    parent=parent,
                    start_offset_ms=round((started_ns - self._started_ns) / 1_000_000, 3),
                    duration_ms=round((ended_ns - started_ns) / 1_000_000, 3),
                    sample_count=sample_count,
                    aggregation=aggregation,
                    critical_path=critical_path,
                )
            )

    def add_unavailable(
        self,
        name: str,
        *,
        source: str,
        reason: str,
        parent: str | None = None,
        critical_path: bool = False,
    ) -> TimingSpan:
        return self.add(
            TimingSpan.unavailable(
                name,
                source=source,
                reason=reason,
                parent=parent,
                critical_path=critical_path,
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TIMING_SCHEMA_VERSION,
            "clock": MONOTONIC_CLOCK,
            "spans": [span.to_dict() for span in self._spans],
        }


class BoundedTimingTraceBuffer:
    """Thread-safe bounded sink for internal timing spans only."""

    def __init__(self, *, max_traces: int = 256) -> None:
        if not 1 <= max_traces <= 4096:
            raise ValueError("max_traces must be between 1 and 4096")
        self.max_traces = max_traces
        self._traces: deque[TimingTrace] = deque(maxlen=max_traces)
        self._lock = threading.Lock()

    def record(self, trace: TimingTrace) -> None:
        if not isinstance(trace, TimingTrace):
            raise TypeError("timing sink accepts TimingTrace values only")
        with self._lock:
            self._traces.append(trace)

    def snapshot(self) -> tuple[TimingTrace, ...]:
        with self._lock:
            return tuple(self._traces)

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()


def record_internal_span(
    name: str,
    *,
    source: str,
    duration_ms: float,
    parent: str | None = None,
    critical_path: bool = False,
) -> None:
    """Record one fixed internal span without request or identity context."""

    trace = TimingTrace(max_spans=1)
    trace.add(
        TimingSpan(
            name=name,
            source=source,
            parent=parent,
            start_offset_ms=0.0,
            duration_ms=duration_ms,
            sample_count=1,
            critical_path=critical_path,
        )
    )
    runtime_timing_traces.record(trace)


def record_internal_unavailable_span(
    name: str,
    *,
    source: str,
    reason: str,
    parent: str | None = None,
) -> None:
    """Record a fixed internal span when a layer cannot be observed safely."""

    trace = TimingTrace(max_spans=1)
    trace.add_unavailable(name, source=source, reason=reason, parent=parent)
    runtime_timing_traces.record(trace)


def fixed_contract() -> dict[str, object]:
    """Return the JSON-safe schema contract used by evidence validators."""

    return {
        "schema_version": TIMING_SCHEMA_VERSION,
        "clock": MONOTONIC_CLOCK,
        "spans": list(TIMING_SPANS),
        "pipeline_stages": list(PIPELINE_TIMING_STAGES),
        "database_spans": list(DATABASE_TIMING_SPANS),
        "r2_spans": list(R2_TIMING_SPANS),
        "sources": list(TIMING_SOURCES),
        "aggregations": list(TIMING_AGGREGATIONS),
        "unavailable_reasons": list(UNAVAILABLE_REASONS),
        "protected_fields": [
            "user_id",
            "requesting_user_id",
            "url",
            "sql",
            "query",
            "object_key",
            "credential",
            "secret",
            "token",
            "response_body",
        ],
    }


runtime_timing_traces = BoundedTimingTraceBuffer()
