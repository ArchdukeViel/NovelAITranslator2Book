"""RQ queue factory.

Provides Redis connections and RQ queues bound to settings.REDIS_URL.
All queue access goes through this module — never create ad-hoc Redis
connections or queues elsewhere in the codebase.

Queue names:
  crawl        - novel metadata and chapter fetch jobs
  translation  - chapter translation jobs
  default      - fallback / misc tasks

Usage:
    from novelai.worker.queue import get_queue
    q = get_queue("crawl")
    job = q.enqueue(some_task, arg1, arg2)
"""

from __future__ import annotations

from typing import Any

from redis import Redis
from rq import Queue

from novelai.config.settings import settings

# Standard queue names used across the worker boundary.
QUEUE_CRAWL = "crawl"
QUEUE_TRANSLATION = "translation"
QUEUE_DEFAULT = "default"

ALL_QUEUES = [QUEUE_CRAWL, QUEUE_TRANSLATION, QUEUE_DEFAULT]


def get_redis_connection(url: str | None = None) -> Redis:
    """Create a Redis connection.

    Args:
        url: explicit Redis URL; falls back to settings.REDIS_URL.

    Raises:
        RuntimeError: if no URL is configured.
    """
    redis_url = url or settings.REDIS_URL
    if not redis_url:
        raise RuntimeError(
            "REDIS_URL is not configured. "
            "Set REDIS_URL in .env or as an environment variable. "
            "Example: REDIS_URL=redis://localhost:6379/0"
        )
    return Redis.from_url(redis_url)


def get_queue(name: str = QUEUE_DEFAULT, url: str | None = None) -> Queue:
    """Return an RQ Queue bound to the given Redis connection.

    Args:
        name: Queue name (use module-level constants: QUEUE_CRAWL, etc.).
        url: explicit Redis URL; falls back to settings.REDIS_URL.

    Returns:
        An RQ Queue instance ready for enqueue() calls.
    """
    conn = get_redis_connection(url)
    return Queue(name, connection=conn)


def get_failed_jobs(limit: int = 50) -> list[dict[str, Any]]:
    """List recent failed jobs across worker queues."""
    from rq.job import Job
    from rq.registry import FailedJobRegistry

    failed_jobs: list[dict[str, Any]] = []
    conn = get_redis_connection()
    for queue_name in ALL_QUEUES:
        q = Queue(queue_name, connection=conn)
        registry = FailedJobRegistry(queue=q)
        for job_id in registry.get_job_ids()[:limit]:
            try:
                job = Job.fetch(job_id, connection=conn)
                failed_jobs.append(
                    {
                        "job_id": job_id,
                        "queue": queue_name,
                        "func_name": job.func_name,
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                        "exc_info": job.exc_info,
                    }
                )
            except Exception:
                failed_jobs.append({"job_id": job_id, "queue": queue_name})
            if len(failed_jobs) >= limit:
                break
        if len(failed_jobs) >= limit:
            break
    return failed_jobs


def requeue_failed_job(job_id: str) -> bool:
    """Requeue a failed job by ID."""
    from rq.registry import FailedJobRegistry

    conn = get_redis_connection()
    for queue_name in ALL_QUEUES:
        q = Queue(queue_name, connection=conn)
        registry = FailedJobRegistry(queue=q)
        if job_id in registry.get_job_ids():
            registry.requeue(job_id)
            return True
    return False
