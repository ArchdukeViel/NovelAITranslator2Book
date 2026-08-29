from __future__ import annotations

import gc
import os
import threading
import time
from collections import Counter

from fastapi import APIRouter
from fastapi.responses import Response

from novelai.services.analytics_writer import analytics_writer_stats
from novelai.services.health_service import HealthCacheStats
from novelai.services.provider_metrics import provider_runtime_stats
from novelai.services.public_projection_cache import public_projection_cache_stats
from novelai.services.public_ranking_cache import public_ranking_cache_stats
from novelai.services.runtime_telemetry import TelemetryOperation, TelemetryStage, runtime_telemetry

router = APIRouter()

_START_TIME = time.time()


def _load_container_activity_log():
    """Return the runtime container's activity_log (patchable seam for tests).

    Returns the container's activity_log service, or ``None`` if the
    container is not initialized. The Prometheus endpoint must fail closed
    when the container is unavailable — never raise out of ``/metrics``.
    """
    try:
        from novelai.runtime.container import container  # local import: avoid app init

        return getattr(container, "activity_log", None)
    except Exception:
        return None


def _load_container_health_service():
    """Return the shared health service without allowing metrics to fail."""
    try:
        from novelai.runtime.container import container

        return getattr(container, "health_service", None)
    except Exception:
        return None


def _activity_counts() -> dict[str, int]:
    """Pull queue depth from the activity log (best-effort, fail closed)."""
    counts: Counter[str] = Counter()
    activity_log = _load_container_activity_log()
    if activity_log is None:
        return {}
    try:
        activities = activity_log.list_activity() or []
    except Exception:
        return {}
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        status = str(activity.get("status") or "unknown").lower()
        counts[status] += 1
    return dict(counts)


def _activity_queue_stats() -> dict[str, object]:
    activity_log = _load_container_activity_log()
    if activity_log is None:
        return {}
    try:
        stats = activity_log.queue_stats()
    except Exception:
        return {}
    return stats if isinstance(stats, dict) else {}


def _queue_age_seconds(stats: dict[str, object]) -> float:
    value = stats.get("queue_age_seconds")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _queue_operation_total_ms(stats: dict[str, object]) -> float:
    operations = stats.get("operations")
    if not isinstance(operations, dict):
        return 0.0
    total = 0.0
    for operation in operations.values():
        if not isinstance(operation, dict):
            continue
        value = operation.get("total_ms")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += float(value)
    return total


def _activity_failures_per_source() -> dict[str, int]:
    """Count failed activities by ``source_key`` (low cardinality, safe label)."""
    counts: Counter[str] = Counter()
    activity_log = _load_container_activity_log()
    if activity_log is None:
        return {}
    try:
        activities = activity_log.list_activity() or []
    except Exception:
        return {}
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        if str(activity.get("status") or "").lower() != "failed":
            continue
        metadata = activity.get("metadata") or {}
        source_key = str(metadata.get("source_key") or "unknown")
        counts[source_key] += 1
    return dict(counts)


@router.get("/metrics")
def get_metrics() -> Response:
    """Return standard Prometheus format metrics payload (DEBT-040).

    Public-safe: no secrets, no paths, no user identifiers. Only low-cardinality
    labels (process, scope, status, source_key) are used. Process and queue
    gauges are always emitted; per-source failure counts are emitted only when
    a non-zero count exists to keep label cardinality bounded.
    """
    uptime_seconds = time.time() - _START_TIME
    cpu_count = os.cpu_count() or 0
    active_threads = threading.active_count()
    gc_counts = gc.get_count()
    gc_objects = len(gc.get_objects())

    activity_counts = _activity_counts()
    ranking_cache = public_ranking_cache_stats()
    projection_cache = public_projection_cache_stats()
    analytics_writer = analytics_writer_stats()
    activity_queue = _activity_queue_stats()
    provider_runtime = provider_runtime_stats()
    process_sample = runtime_telemetry.sample_process_resources()
    event_loop_sample = runtime_telemetry.latest(
        stage=TelemetryStage.PROCESS,
        operation=TelemetryOperation.EVENT_LOOP_LAG,
    )
    event_loop_lag_ms = event_loop_sample.event_loop_lag_ms if event_loop_sample is not None else 0.0
    health_service = _load_container_health_service()
    health_cache = (
        health_service.health_cache_stats()
        if health_service is not None
        else HealthCacheStats(hits=0, misses=0, entries=0, age_seconds=None)
    )
    pending = activity_counts.get("pending", 0)
    queued = activity_counts.get("queued", 0)
    running = activity_counts.get("running", 0)
    failed = activity_counts.get("failed", 0)
    completed = activity_counts.get("completed", 0)
    cancelled = activity_counts.get("cancelled", 0)

    lines: list[str] = [
        "# HELP novelai_process_uptime_seconds Process uptime in seconds",
        "# TYPE novelai_process_uptime_seconds gauge",
        f"novelai_process_uptime_seconds {uptime_seconds:.2f}",
        "# HELP novelai_cpu_count_total Number of CPUs available",
        "# TYPE novelai_cpu_count_total gauge",
        f"novelai_cpu_count_total {cpu_count}",
        "# HELP novelai_active_threads_count Number of active Python threads",
        "# TYPE novelai_active_threads_count gauge",
        f"novelai_active_threads_count {active_threads}",
        "# HELP novelai_gc_tracked_objects_count Number of objects tracked by GC",
        "# TYPE novelai_gc_tracked_objects_count gauge",
        f"novelai_gc_tracked_objects_count {gc_objects}",
        "# HELP novelai_gc_collection_0_count GC generation 0 collection count",
        "# TYPE novelai_gc_collection_0_count gauge",
        f"novelai_gc_collection_0_count {gc_counts[0]}",
        "# HELP novelai_gc_collection_1_count GC generation 1 collection count",
        "# TYPE novelai_gc_collection_1_count gauge",
        f"novelai_gc_collection_1_count {gc_counts[1]}",
        "# HELP novelai_gc_collection_2_count GC generation 2 collection count",
        "# TYPE novelai_gc_collection_2_count gauge",
        f"novelai_gc_collection_2_count {gc_counts[2]}",
        "# HELP novelai_event_loop_lag_ms Latest sampled event-loop lag",
        "# TYPE novelai_event_loop_lag_ms gauge",
        f"novelai_event_loop_lag_ms {event_loop_lag_ms or 0.0:.3f}",
        "# HELP novelai_process_cpu_time_ms Process CPU time used",
        "# TYPE novelai_process_cpu_time_ms gauge",
        f"novelai_process_cpu_time_ms {process_sample.cpu_ms or 0.0:.3f}",
        "# HELP novelai_process_memory_bytes Process memory high-water mark, when available",
        "# TYPE novelai_process_memory_bytes gauge",
        f"novelai_process_memory_bytes {process_sample.memory_bytes or 0}",
        "# HELP novelai_process_memory_available Whether process memory sampling is available",
        "# TYPE novelai_process_memory_available gauge",
        f"novelai_process_memory_available {1 if process_sample.memory_bytes is not None else 0}",
        "# HELP novelai_network_bytes_available Whether network byte attribution is available",
        "# TYPE novelai_network_bytes_available gauge",
        "novelai_network_bytes_available 0",
        "# HELP novelai_runtime_observations_buffered Current bounded runtime observation count",
        "# TYPE novelai_runtime_observations_buffered gauge",
        f"novelai_runtime_observations_buffered {len(runtime_telemetry.snapshot())}",
        "# HELP novelai_runtime_unavailable_samples_total Buffered observations with named unavailable fields",
        "# TYPE novelai_runtime_unavailable_samples_total gauge",
        f"novelai_runtime_unavailable_samples_total {runtime_telemetry.unavailable_count()}",
        "# HELP novelai_activity_pending_count Activities in pending state",
        "# TYPE novelai_activity_pending_count gauge",
        f"novelai_activity_pending_count {pending}",
        "# HELP novelai_activity_queued_count Activities waiting in queue",
        "# TYPE novelai_activity_queued_count gauge",
        f"novelai_activity_queued_count {queued}",
        "# HELP novelai_activity_running_count Activities currently running",
        "# TYPE novelai_activity_running_count gauge",
        f"novelai_activity_running_count {running}",
        "# HELP novelai_activity_failed_count Activities that ended in failure",
        "# TYPE novelai_activity_failed_count gauge",
        f"novelai_activity_failed_count {failed}",
        "# HELP novelai_activity_completed_count Activities that completed",
        "# TYPE novelai_activity_completed_count gauge",
        f"novelai_activity_completed_count {completed}",
        "# HELP novelai_activity_cancelled_count Activities that were cancelled",
        "# TYPE novelai_activity_cancelled_count gauge",
        f"novelai_activity_cancelled_count {cancelled}",
        "# HELP novelai_activity_queue_age_seconds Age of the oldest pending activity",
        "# TYPE novelai_activity_queue_age_seconds gauge",
        f"novelai_activity_queue_age_seconds {_queue_age_seconds(activity_queue):.3f}",
        "# HELP novelai_activity_queue_operation_total_ms Total activity queue operation time",
        "# TYPE novelai_activity_queue_operation_total_ms gauge",
        f"novelai_activity_queue_operation_total_ms {_queue_operation_total_ms(activity_queue):.3f}",
        "# HELP novelai_provider_calls_total Provider calls observed by this process",
        "# TYPE novelai_provider_calls_total counter",
        f"novelai_provider_calls_total {provider_runtime.calls}",
        "# HELP novelai_provider_failures_total Provider call failures observed by this process",
        "# TYPE novelai_provider_failures_total counter",
        f"novelai_provider_failures_total {provider_runtime.failures}",
        "# HELP novelai_provider_retries_total Provider retry attempts observed by this process",
        "# TYPE novelai_provider_retries_total counter",
        f"novelai_provider_retries_total {provider_runtime.retries}",
        "# HELP novelai_provider_wait_ms_total Provider admission wait time",
        "# TYPE novelai_provider_wait_ms_total counter",
        f"novelai_provider_wait_ms_total {provider_runtime.wait_ms_total:.3f}",
        "# HELP novelai_provider_execution_ms_total Provider execution time",
        "# TYPE novelai_provider_execution_ms_total counter",
        f"novelai_provider_execution_ms_total {provider_runtime.execution_ms_total:.3f}",
        "# HELP novelai_provider_quota_reservation_ms_total Provider quota reservation time",
        "# TYPE novelai_provider_quota_reservation_ms_total counter",
        f"novelai_provider_quota_reservation_ms_total {provider_runtime.quota_reservation_ms_total:.3f}",
        "# HELP novelai_provider_usage_write_ms_total Provider usage-ledger write time",
        "# TYPE novelai_provider_usage_write_ms_total counter",
        f"novelai_provider_usage_write_ms_total {provider_runtime.usage_write_ms_total:.3f}",
        "# HELP novelai_public_ranking_cache_hits_total Successful public ranking cache lookups",
        "# TYPE novelai_public_ranking_cache_hits_total counter",
        f"novelai_public_ranking_cache_hits_total {ranking_cache.hits}",
        "# HELP novelai_public_ranking_cache_misses_total Public ranking cache misses",
        "# TYPE novelai_public_ranking_cache_misses_total counter",
        f"novelai_public_ranking_cache_misses_total {ranking_cache.misses}",
        "# HELP novelai_public_ranking_cache_entries Current public ranking cache entries",
        "# TYPE novelai_public_ranking_cache_entries gauge",
        f"novelai_public_ranking_cache_entries {ranking_cache.entries}",
        "# HELP novelai_public_projection_cache_hits_total Successful public projection cache lookups",
        "# TYPE novelai_public_projection_cache_hits_total counter",
        f"novelai_public_projection_cache_hits_total {projection_cache.hits}",
        "# HELP novelai_public_projection_cache_misses_total Public projection cache misses",
        "# TYPE novelai_public_projection_cache_misses_total counter",
        f"novelai_public_projection_cache_misses_total {projection_cache.misses}",
        "# HELP novelai_public_projection_cache_entries Current public projection cache entries",
        "# TYPE novelai_public_projection_cache_entries gauge",
        f"novelai_public_projection_cache_entries {projection_cache.entries}",
        "# HELP novelai_public_projection_cache_invalidations_total Public projection cache invalidations",
        "# TYPE novelai_public_projection_cache_invalidations_total counter",
        f"novelai_public_projection_cache_invalidations_total {projection_cache.invalidations}",
        "# HELP novelai_readiness_cache_hits_total Cached readiness responses served",
        "# TYPE novelai_readiness_cache_hits_total counter",
        f"novelai_readiness_cache_hits_total {health_cache.hits}",
        "# HELP novelai_readiness_cache_misses_total Readiness probe refreshes started",
        "# TYPE novelai_readiness_cache_misses_total counter",
        f"novelai_readiness_cache_misses_total {health_cache.misses}",
        "# HELP novelai_readiness_cache_entries Current readiness cache entries",
        "# TYPE novelai_readiness_cache_entries gauge",
        f"novelai_readiness_cache_entries {health_cache.entries}",
        "# HELP novelai_readiness_cache_age_seconds Age of cached readiness results",
        "# TYPE novelai_readiness_cache_age_seconds gauge",
        f"novelai_readiness_cache_age_seconds {health_cache.age_seconds or 0.0:.2f}",
        "# HELP novelai_analytics_writer_accepted_total Analytics events accepted by the bounded writer",
        "# TYPE novelai_analytics_writer_accepted_total counter",
        f"novelai_analytics_writer_accepted_total {analytics_writer.accepted}",
        "# HELP novelai_analytics_writer_dropped_total Analytics events dropped by the bounded writer",
        "# TYPE novelai_analytics_writer_dropped_total counter",
        f"novelai_analytics_writer_dropped_total {analytics_writer.dropped}",
        "# HELP novelai_analytics_writer_processed_total Analytics events persisted by the writer",
        "# TYPE novelai_analytics_writer_processed_total counter",
        f"novelai_analytics_writer_processed_total {analytics_writer.processed}",
        "# HELP novelai_analytics_writer_failures_total Analytics writer failures",
        "# TYPE novelai_analytics_writer_failures_total counter",
        f"novelai_analytics_writer_failures_total {analytics_writer.failures}",
        "# HELP novelai_analytics_writer_queue_depth Current analytics writer queue depth",
        "# TYPE novelai_analytics_writer_queue_depth gauge",
        f"novelai_analytics_writer_queue_depth {analytics_writer.queue_depth}",
    ]

    for source_key, count in sorted(_activity_failures_per_source().items()):
        lines.append("# HELP novelai_activity_failures_per_source Failed activities by source_key")
        lines.append("# TYPE novelai_activity_failures_per_source counter")
        # source_key is escaped for the Prometheus label format.
        safe = source_key.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        lines.append(f'novelai_activity_failures_per_source{{source_key="{safe}"}} {count}')

    content = "\n".join(lines) + "\n"
    return Response(content=content, media_type="text/plain; version=0.0.4")
