"""RQ enqueueable task functions.

These are the functions that RQ workers execute. They delegate to the
existing ActivityWorkerService — no pipeline logic lives here.

Architecture rules:
- Tasks run in a fresh process; they must bootstrap their own container.
- Tasks reuse existing ActivityWorkerService and orchestration; they do
  NOT reimplement crawl or translation logic.
- Job lifecycle (pending→running→completed/failed) is written to both the
  existing file-backed ActivityQueueService AND the DB CrawlJob/TranslationJob
  rows during the parallel-run transition.
- Successful chunk progress must never be lost on retry.

Parallel-run note:
  The in-process BackgroundActivityRunner continues to work unchanged.
  These RQ tasks are the new path; both paths share the same
  ActivityQueueService file-backed queue so jobs enqueued via the API
  can be picked up by either worker during the transition period.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from rq import Retry

from novelai.worker.queue import QUEUE_CRAWL, QUEUE_TRANSLATION, get_queue

logger = logging.getLogger(__name__)

DEFAULT_JOB_TIMEOUT_SECONDS: int = 600
DEFAULT_JOB_RETRY: Retry = Retry(max=3, interval=[10, 30, 60])
DEFAULT_RESULT_TTL_SECONDS: int = 86400  # 24 hours
DEFAULT_FAILURE_TTL_SECONDS: int = 604800  # 7 days


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_worker_service() -> Any:
    """Bootstrap and return the ActivityWorkerService.

    Called inside the RQ worker process; each task gets a fresh bootstrap.
    """
    from novelai.runtime.bootstrap import bootstrap
    from novelai.runtime.container import container

    bootstrap()
    runner = getattr(container, "activity_runner", None) or getattr(container, "job_runner", None)
    if runner is None:
        raise RuntimeError("No activity runner found on container after bootstrap.")
    return runner


# ---------------------------------------------------------------------------
# RQ task functions
# ---------------------------------------------------------------------------


def run_crawl_activity(activity_id: str) -> dict[str, Any]:
    """RQ task: execute a single crawl activity by ID.

    Picks up the activity from the file-backed ActivityQueueService,
    runs it through ActivityWorkerService, and returns the final status dict.

    Args:
        activity_id: The activity ID created by ActivityQueueService.

    Returns:
        The activity status dict after execution.

    Raises:
        ValueError: if the activity is not found or in a non-runnable state.
    """
    logger.info("RQ crawl task starting: activity_id=%s", activity_id)
    runner = _get_worker_service()

    try:
        result = asyncio.run(runner.worker.run_activity(activity_id))
    except Exception as exc:
        logger.error("RQ crawl task failed: activity_id=%s error=%s", activity_id, exc)
        raise

    logger.info("RQ crawl task done: activity_id=%s status=%s", activity_id, result and result.get("status"))
    return result or {}


def run_translation_activity(activity_id: str) -> dict[str, Any]:
    """RQ task: execute a single translation activity by ID.

    Args:
        activity_id: The activity ID created by ActivityQueueService.

    Returns:
        The activity status dict after execution.
    """
    logger.info("RQ translation task starting: activity_id=%s", activity_id)
    runner = _get_worker_service()

    try:
        result = asyncio.run(runner.worker.run_activity(activity_id))
    except Exception as exc:
        logger.error("RQ translation task failed: activity_id=%s error=%s", activity_id, exc)
        raise

    logger.info("RQ translation task done: activity_id=%s status=%s", activity_id, result and result.get("status"))
    return result or {}


# ---------------------------------------------------------------------------
# Enqueue helpers (called by API/services)
# ---------------------------------------------------------------------------


def enqueue_crawl_job(
    activity_id: str,
    *,
    redis_url: str | None = None,
    retry: Retry | None = DEFAULT_JOB_RETRY,
    job_timeout: int = DEFAULT_JOB_TIMEOUT_SECONDS,
    result_ttl: int = DEFAULT_RESULT_TTL_SECONDS,
    failure_ttl: int = DEFAULT_FAILURE_TTL_SECONDS,
) -> str:
    """Enqueue a crawl activity onto the RQ crawl queue.

    Args:
        activity_id: The activity ID already created in ActivityQueueService.
        redis_url: Optional explicit Redis URL; falls back to settings.REDIS_URL.
        retry: RQ Retry policy for transient failures.
        job_timeout: Execution timeout in seconds.
        result_ttl: Time in seconds to keep successful job results in Redis.
        failure_ttl: Time in seconds to keep failed jobs in Redis.

    Returns:
        The RQ job ID (str).
    """
    q = get_queue(QUEUE_CRAWL, url=redis_url)
    job = q.enqueue(
        run_crawl_activity,
        activity_id,
        retry=retry,
        job_timeout=job_timeout,
        result_ttl=result_ttl,
        failure_ttl=failure_ttl,
    )
    logger.info("Enqueued crawl activity %s as RQ job %s", activity_id, job.id)
    return job.id


def enqueue_translation_job(
    activity_id: str,
    *,
    redis_url: str | None = None,
    retry: Retry | None = DEFAULT_JOB_RETRY,
    job_timeout: int = DEFAULT_JOB_TIMEOUT_SECONDS,
    result_ttl: int = DEFAULT_RESULT_TTL_SECONDS,
    failure_ttl: int = DEFAULT_FAILURE_TTL_SECONDS,
) -> str:
    """Enqueue a translation activity onto the RQ translation queue.

    Args:
        activity_id: The activity ID already created in ActivityQueueService.
        redis_url: Optional explicit Redis URL; falls back to settings.REDIS_URL.
        retry: RQ Retry policy for transient failures.
        job_timeout: Execution timeout in seconds.
        result_ttl: Time in seconds to keep successful job results in Redis.
        failure_ttl: Time in seconds to keep failed jobs in Redis.

    Returns:
        The RQ job ID (str).
    """
    q = get_queue(QUEUE_TRANSLATION, url=redis_url)
    job = q.enqueue(
        run_translation_activity,
        activity_id,
        retry=retry,
        job_timeout=job_timeout,
        result_ttl=result_ttl,
        failure_ttl=failure_ttl,
    )
    logger.info("Enqueued translation activity %s as RQ job %s", activity_id, job.id)
    return job.id
