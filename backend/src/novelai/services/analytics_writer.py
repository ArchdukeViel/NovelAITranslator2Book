"""Bounded asynchronous analytics event writer.

Public request handlers only enqueue a sanitized, bounded event record. A
single daemon worker owns the database session for each event, so analytics
backpressure or database latency cannot hold the public content request open.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from queue import Full, Queue
from threading import Event, Lock, Thread
from typing import Any

from novelai.config.settings import settings
from novelai.services.analytics_service import sanitize_metadata, validate_event_name

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalyticsEventJob:
    """Sanitized fields that may cross the request/worker boundary."""

    event_name: str
    user_id: int | None
    session_id: str | None
    novel_id: str | None
    chapter_id: str | None
    metadata_json: str | None
    created_at: Any | None


@dataclass(frozen=True)
class AnalyticsWriterStats:
    accepted: int
    dropped: int
    processed: int
    failures: int
    queue_depth: int


class AnalyticsWriter:
    """A bounded, process-local analytics queue with explicit loss policy."""

    def __init__(self, *, maxsize: int | None = None, start_worker: bool = True) -> None:
        self._queue: Queue[AnalyticsEventJob | None] = Queue(maxsize=maxsize or settings.ANALYTICS_ASYNC_QUEUE_SIZE)
        self._start_worker = start_worker
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._stopped = False
        self._accepted = 0
        self._dropped = 0
        self._processed = 0
        self._failures = 0

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    def enqueue(
        self,
        event_name: str,
        *,
        user_id: int | None = None,
        session_id: str | None = None,
        novel_id: str | None = None,
        chapter_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: Any | None = None,
    ) -> bool:
        """Queue one privacy-sanitized event without waiting for capacity."""
        if not settings.ANALYTICS_ENABLED or not validate_event_name(event_name):
            return False
        job = AnalyticsEventJob(
            event_name=event_name,
            user_id=user_id,
            session_id=session_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            metadata_json=sanitize_metadata(event_name, metadata),
            created_at=created_at,
        )
        with self._lock:
            if self._stopped:
                self._dropped += 1
                return False
            if self._start_worker:
                self._ensure_worker_locked()
            try:
                self._queue.put_nowait(job)
            except Full:
                self._dropped += 1
                return False
            self._accepted += 1
            return True

    def stats(self) -> AnalyticsWriterStats:
        with self._lock:
            return AnalyticsWriterStats(
                accepted=self._accepted,
                dropped=self._dropped,
                processed=self._processed,
                failures=self._failures,
                queue_depth=self._queue.qsize(),
            )

    def flush(self, timeout_seconds: float = 2.0) -> bool:
        """Wait for queued jobs; intended for shutdown and deterministic tests."""
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while self._queue.unfinished_tasks:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    def shutdown(self, timeout_seconds: float = 5.0) -> None:
        """Drain queued events briefly, then stop the worker."""
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
            thread = self._thread
        if thread is None:
            return
        self.flush(timeout_seconds)
        remaining = max(0.0, timeout_seconds - 0.01)
        try:
            self._queue.put(None, timeout=remaining)
        except Full:
            logger.debug("Analytics writer shutdown queue remained full")
        self._stop.set()
        thread.join(timeout=max(0.0, timeout_seconds))

    def _ensure_worker_locked(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._run, name="novelai-analytics-writer", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                from novelai.db.engine import session_scope
                from novelai.services.analytics_service import AnalyticsService

                with session_scope() as db_session:
                    succeeded = AnalyticsService().record_event(
                        db_session,
                        job.event_name,
                        user_id=job.user_id,
                        session_id=job.session_id,
                        novel_id=job.novel_id,
                        chapter_id=job.chapter_id,
                        metadata_json=job.metadata_json,
                        created_at=job.created_at,
                    )
                with self._lock:
                    if succeeded:
                        self._processed += 1
                    else:
                        self._failures += 1
            except Exception:
                with self._lock:
                    self._failures += 1
                logger.debug("Analytics worker event failed (suppressed)", exc_info=True)
            finally:
                self._queue.task_done()
            if self._stop.is_set() and self._queue.empty():
                return


_writer_lock = Lock()
_writer: AnalyticsWriter | None = None


def get_analytics_writer() -> AnalyticsWriter:
    """Return the process-local writer, creating it lazily."""
    global _writer
    with _writer_lock:
        if _writer is None or _writer.is_stopped:
            _writer = AnalyticsWriter()
        return _writer


def enqueue_analytics_event(event_name: str, **kwargs: Any) -> bool:
    """Enqueue a trusted event and suppress all writer failures."""
    try:
        return get_analytics_writer().enqueue(event_name, **kwargs)
    except Exception:
        logger.debug("Analytics enqueue failed (suppressed)", exc_info=True)
        return False


def analytics_writer_stats() -> AnalyticsWriterStats:
    writer = _writer
    if writer is None:
        return AnalyticsWriterStats(accepted=0, dropped=0, processed=0, failures=0, queue_depth=0)
    return writer.stats()


def shutdown_analytics_writer() -> None:
    writer = _writer
    if writer is not None:
        writer.shutdown()


def reset_analytics_writer_for_tests() -> None:
    """Stop and discard the singleton for isolated unit tests."""
    global _writer
    with _writer_lock:
        writer = _writer
        _writer = None
    if writer is not None:
        writer.shutdown()
