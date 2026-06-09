"""RQ background worker boundary.

Provides the queue factory and enqueueable task functions for
crawl/translation work. Runs alongside the existing in-process
ActivityWorkerService during the parallel-run transition period.

Architecture rule: RQ tasks delegate to the existing
ActivityWorkerService — they do not reimplement pipeline logic.
"""

from __future__ import annotations

from novelai.worker.queue import get_queue, get_redis_connection
from novelai.worker.tasks import enqueue_crawl_job, enqueue_translation_job

__all__ = [
    "get_redis_connection",
    "get_queue",
    "enqueue_crawl_job",
    "enqueue_translation_job",
]
