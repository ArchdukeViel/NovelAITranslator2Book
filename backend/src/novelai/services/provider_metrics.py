"""Low-cardinality provider timing counters for runtime metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderRuntimeStats:
    calls: int = 0
    failures: int = 0
    retries: int = 0
    wait_ms_total: float = 0.0
    execution_ms_total: float = 0.0
    quota_reservation_ms_total: float = 0.0
    usage_write_ms_total: float = 0.0


_LOCK = threading.Lock()
_STATS = ProviderRuntimeStats()


def record_provider_timing(
    *,
    wait_ms: float | None = None,
    execution_ms: float | None = None,
    quota_reservation_ms: float | None = None,
    usage_write_ms: float | None = None,
    retry_attempt: int = 0,
    success: bool = True,
) -> None:
    global _STATS

    def _duration(value: float | None) -> float:
        return max(0.0, float(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0

    with _LOCK:
        _STATS = ProviderRuntimeStats(
            calls=_STATS.calls + 1,
            failures=_STATS.failures + (0 if success else 1),
            retries=_STATS.retries + max(0, int(retry_attempt)),
            wait_ms_total=_STATS.wait_ms_total + _duration(wait_ms),
            execution_ms_total=_STATS.execution_ms_total + _duration(execution_ms),
            quota_reservation_ms_total=_STATS.quota_reservation_ms_total + _duration(quota_reservation_ms),
            usage_write_ms_total=_STATS.usage_write_ms_total + _duration(usage_write_ms),
        )


def provider_runtime_stats() -> ProviderRuntimeStats:
    with _LOCK:
        return _STATS


def reset_provider_runtime_stats() -> None:
    global _STATS
    with _LOCK:
        _STATS = ProviderRuntimeStats()
