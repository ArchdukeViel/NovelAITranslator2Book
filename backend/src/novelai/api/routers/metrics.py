from __future__ import annotations

import gc
import os
import threading
import time
from collections import Counter

from fastapi import APIRouter
from fastapi.responses import Response

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
    ]

    for source_key, count in sorted(_activity_failures_per_source().items()):
        lines.append("# HELP novelai_activity_failures_per_source Failed activities by source_key")
        lines.append("# TYPE novelai_activity_failures_per_source counter")
        # source_key is escaped for the Prometheus label format.
        safe = source_key.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        lines.append(f'novelai_activity_failures_per_source{{source_key="{safe}"}} {count}')

    content = "\n".join(lines) + "\n"
    return Response(content=content, media_type="text/plain; version=0.0.4")
