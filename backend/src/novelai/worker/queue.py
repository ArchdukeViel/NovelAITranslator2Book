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
