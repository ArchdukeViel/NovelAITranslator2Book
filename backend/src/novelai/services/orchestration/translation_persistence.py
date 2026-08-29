"""Bounded async-facing boundary for synchronous translation persistence.

The translation coordinator is asynchronous, while the current SQLAlchemy,
R2, and disposable-runtime facades are synchronous.  This module keeps those
operations behind a small, measurable boundary.  Callers submit operation
classes and immutable/scalar arguments; the boundary owns the storage facade,
limits submitted work, and returns detached values.
"""

from __future__ import annotations

import asyncio
import copy
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Connection, Engine, Transaction
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import Session
from sqlalchemy.orm.session import SessionTransaction
from sqlalchemy.orm.state import InstanceState

from novelai.config.settings import settings
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.pipeline.checkpoint import Checkpoint, CheckpointManager
from novelai.translation.run_manifest import TranslationRunManifest


class PersistenceOperation(StrEnum):
    """Fixed operation classes used by the async persistence boundary."""

    DB_READ_SCALAR = "DB_READ_SCALAR"
    DB_READ_BUNDLE = "DB_READ_BUNDLE"
    DB_WRITE_PROGRESS = "DB_WRITE_PROGRESS"
    DB_WRITE_TERMINAL = "DB_WRITE_TERMINAL"
    R2_EXACT_READ = "R2_EXACT_READ"
    R2_IMMUTABLE_WRITE = "R2_IMMUTABLE_WRITE"
    RUNTIME_CHECKPOINT = "RUNTIME_CHECKPOINT"
    PROVIDER_WAIT = "PROVIDER_WAIT"
    QA = "QA"
    ACTIVITY_STATE = "ACTIVITY_STATE"
    SHUTDOWN = "SHUTDOWN"


# The alias keeps the design vocabulary available to callers without creating
# a second enum that could drift from the operation allowlist.
OperationClass = PersistenceOperation


class BoundaryOwnershipError(TypeError):
    """Raised when a live DB or ORM-owned object crosses the boundary."""


_OWNED_BOUNDARY_TYPES = (Connection, Engine, Transaction, Session, SessionTransaction)


def _assert_boundary_value(value: object, *, path: str = "$", seen: set[int] | None = None) -> None:
    """Reject live SQLAlchemy resources and mapped instances in boundary values."""

    if isinstance(value, _OWNED_BOUNDARY_TYPES):
        raise BoundaryOwnershipError(f"live database resource cannot cross persistence boundary at {path}")
    if value is None or isinstance(value, (str, bytes, bytearray, int, float, bool, Path)):
        return

    visited = seen if seen is not None else set()
    object_id = id(value)
    if object_id in visited:
        return
    visited.add(object_id)

    if isinstance(value, Mapping):
        for index, (key, item) in enumerate(value.items()):
            _assert_boundary_value(key, path=f"{path}.key[{index}]", seen=visited)
            _assert_boundary_value(item, path=f"{path}.value[{index}]", seen=visited)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            _assert_boundary_value(item, path=f"{path}[{index}]", seen=visited)
        return
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _assert_boundary_value(getattr(value, field.name), path=f"{path}.{field.name}", seen=visited)
        return

    try:
        inspected = sa_inspect(value)
    except NoInspectionAvailable, TypeError:
        return
    if isinstance(inspected, InstanceState):
        raise BoundaryOwnershipError(f"live ORM object cannot cross persistence boundary at {path}")


def _validate_boundary_arguments(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    for index, value in enumerate(args):
        _assert_boundary_value(value, path=f"args[{index}]")
    for index, value in enumerate(kwargs.values()):
        _assert_boundary_value(value, path=f"kwargs[{index}]")


@dataclass(frozen=True, slots=True)
class PersistenceObservation:
    """Sanitized bounded observation for one synchronous operation."""

    operation_class: str
    outcome: str
    queue_wait_ms: float
    duration_ms: float
    error_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "operation_class": self.operation_class,
            "outcome": self.outcome,
            "queue_wait_ms": round(max(0.0, self.queue_wait_ms), 3),
            "duration_ms": round(max(0.0, self.duration_ms), 3),
        }
        if self.error_code is not None:
            result["error_code"] = self.error_code
        return result


_SAFE_ERROR_CODE = re.compile(r"[^A-Za-z0-9_.-]")


def _error_code(exc: BaseException) -> str:
    """Return an allowlisted error category without exception text."""

    candidate = getattr(exc, "error_code", None)
    if candidate is None:
        candidate = type(exc).__name__
    value = getattr(candidate, "value", candidate)
    normalized = _SAFE_ERROR_CODE.sub("_", str(value))[:64].strip("_")
    return normalized or "operation_failed"


def _detach[T](value: T) -> T:
    """Detach a result while still inside the worker boundary.

    Storage results are normally JSON-compatible dictionaries/lists or scalar
    values.  Deep-copying there prevents a caller from receiving a mutable
    object owned by a storage/client implementation.  A value that cannot be
    detached is rejected rather than crossing the boundary by reference.
    """

    _assert_boundary_value(value)
    if value is None or isinstance(value, (str, bytes, int, float, bool, Path)):
        return value
    try:
        return copy.deepcopy(value)
    except Exception as exc:  # pragma: no cover - defensive contract guard
        raise TypeError("persistence result is not detachable") from exc


class BoundedSyncExecutor:
    """Run blocking callables with a fixed worker count and bounded queue.

    ``ThreadPoolExecutor`` itself has an unbounded submission queue.  The
    semaphore limits the sum of running and queued submissions before a work
    item reaches that queue, which makes admission bounded and observable.
    Cancellation shields an already-submitted callable so its short database
    transaction can settle and release the slot safely.
    """

    def __init__(
        self,
        *,
        max_workers: int = 2,
        max_queue: int = 8,
        thread_name_prefix: str = "novelai-persistence",
        observation_limit: int = 256,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if max_queue < 0:
            raise ValueError("max_queue must not be negative")
        if observation_limit < 1:
            raise ValueError("observation_limit must be at least 1")
        self.max_workers = max_workers
        self.max_queue = max_queue
        self._slots = asyncio.BoundedSemaphore(max_workers + max_queue)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._lock = threading.Lock()
        self._closed = False
        self._active = 0
        self._futures: set[asyncio.Future[Any]] = set()
        self._observations: deque[PersistenceObservation] = deque(maxlen=observation_limit)

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    @property
    def observations(self) -> tuple[PersistenceObservation, ...]:
        with self._lock:
            return tuple(self._observations)

    async def run[T](
        self,
        operation_class: PersistenceOperation | str,
        function: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Run one blocking operation after bounded admission."""

        operation = str(operation_class)
        bound_owner = getattr(function, "__self__", None)
        if bound_owner is not None:
            _assert_boundary_value(bound_owner, path="callable")
        _validate_boundary_arguments(args, kwargs)
        wait_started = time.perf_counter()
        await self._slots.acquire()
        queue_wait_ms = (time.perf_counter() - wait_started) * 1000

        with self._lock:
            if self._closed:
                self._slots.release()
                raise RuntimeError("persistence executor is closed")
            self._active += 1

        started = time.perf_counter()
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._executor, _invoke, function, args, kwargs)
        self._futures.add(future)

        def finished(done: asyncio.Future[Any]) -> None:
            outcome = "completed"
            error = None
            if done.cancelled():
                outcome = "cancelled"
            else:
                try:
                    failure = done.exception()
                except BaseException as exc:  # defensive future-state guard
                    failure = exc
                if failure is not None:
                    outcome = "retryable_failure"
                    error = _error_code(failure)
            observation = PersistenceObservation(
                operation_class=operation,
                outcome=outcome,
                queue_wait_ms=queue_wait_ms,
                duration_ms=(time.perf_counter() - started) * 1000,
                error_code=error,
            )
            with self._lock:
                self._active = max(0, self._active - 1)
                self._futures.discard(done)
                self._observations.append(observation)
            self._slots.release()

        future.add_done_callback(finished)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # The worker future remains alive and its callback releases the
            # bounded slot after the underlying operation settles.
            raise

    def close(self, *, cancel_pending: bool = False) -> None:
        """Stop new submissions and begin executor shutdown."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=cancel_pending)

    async def drain(self, timeout_seconds: float = 30.0) -> bool:
        """Wait for submitted work up to a bounded shutdown deadline."""

        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must not be negative")
        with self._lock:
            futures = tuple(self._futures)
        if futures:
            done, _pending = await asyncio.wait(futures, timeout=timeout_seconds)
            drained = len(done) == len(futures)
        else:
            drained = True
        self.close()
        return drained


def _invoke[T](function: Callable[..., T], args: tuple[Any, ...], kwargs: dict[str, Any]) -> T:
    _validate_boundary_arguments(args, kwargs)
    return _detach(function(*args, **kwargs))


class TranslationPersistencePort:
    """Async-facing owner of synchronous storage operations.

    Storage client access is serialized inside the boundary until a client
    factory with a proven thread-safety contract is introduced.  Database
    sessions are still created by the called service inside this worker
    operation; this port never accepts a live session or ORM object.
    """

    _R2_READ_METHODS = {
        "load_chapter",
        "load_chapter_media_state",
        "load_glossary",
        "load_metadata",
        "load_metadata_for_crawl",
        "load_metadata_snapshot",
        "load_source_state",
        "load_translated_chapter",
        "load_translated_chapter_by_version_id",
        "resolve_active_generation_id",
    }
    _R2_WRITE_METHODS = {
        "save_chapter",
        "save_chapter_image_asset",
        "save_chapter_media_state",
        "save_edited_translation",
        "save_glossary",
        "save_metadata",
        "save_source_state",
        "save_translated_chapter",
    }
    _CHECKPOINT_METHODS = {"create_checkpoint", "save_checkpoint", "load_checkpoint", "delete_checkpoint"}

    def __init__(
        self,
        storage: Any,
        *,
        executor: BoundedSyncExecutor | None = None,
        max_workers: int | None = None,
        max_queue: int | None = None,
        observation_limit: int | None = None,
    ) -> None:
        self._storage = storage
        self._storage_lock = threading.RLock()
        if executor is not None:
            self.executor = executor
            return

        expansion_enabled = settings.TRANSLATION_PERSISTENCE_EXPANSION_ENABLED
        configured_workers = settings.TRANSLATION_PERSISTENCE_WORKERS if expansion_enabled else 1
        configured_queue = settings.TRANSLATION_PERSISTENCE_QUEUE_SIZE if expansion_enabled else 0
        self.executor = BoundedSyncExecutor(
            max_workers=configured_workers if max_workers is None else max_workers,
            max_queue=configured_queue if max_queue is None else max_queue,
            observation_limit=(
                settings.TRANSLATION_PERSISTENCE_OBSERVATION_LIMIT if observation_limit is None else observation_limit
            ),
        )

    async def call[T](
        self,
        operation_class: PersistenceOperation | str,
        function: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a plain callable through the bounded boundary."""

        return await self.executor.run(operation_class, function, *args, **kwargs)

    async def storage_call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke an owned storage facade method through the boundary."""

        operation = self._operation_for_method(method_name)
        return await self.executor.run(operation, self._invoke_storage, method_name, args, kwargs)

    async def storage_owned_call[T](
        self,
        operation_class: PersistenceOperation | str,
        function: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Run one short composite storage operation under the owned client lock.

        This is for bounded resume/preflight/QA persistence composites that
        must use several synchronous storage methods as one coordinator step.
        The callable still runs in the executor; it must not perform provider
        or retry waits while holding this lock.
        """

        return await self.executor.run(operation_class, self._invoke_owned, function, args, kwargs)

    async def persist_progress_batch(
        self,
        *,
        events: list[dict[str, Any]],
        chunk_states: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Persist replay-safe progress and event DTOs in one bounded step."""

        return await self.executor.run(
            PersistenceOperation.DB_WRITE_PROGRESS,
            self._persist_progress_batch,
            events,
            chunk_states,
        )

    async def save_checkpoint(self, checkpoint_dir: str | Path, payload: dict[str, Any]) -> None:
        """Serialize and save a checkpoint inside the runtime boundary."""

        await self.executor.run(PersistenceOperation.RUNTIME_CHECKPOINT, _save_checkpoint, str(checkpoint_dir), payload)

    async def delete_checkpoint(self, checkpoint_dir: str | Path, chapter_id: str) -> None:
        """Delete one disposable checkpoint inside the runtime boundary."""

        await self.executor.run(
            PersistenceOperation.RUNTIME_CHECKPOINT, _delete_checkpoint, str(checkpoint_dir), chapter_id
        )

    async def save_translation_run_manifest(self, novel_id: str, payload: dict[str, Any]) -> None:
        """Rebuild a manifest DTO in the worker before storage persistence."""

        await self.executor.run(
            PersistenceOperation.DB_WRITE_TERMINAL,
            self._save_manifest,
            novel_id,
            payload,
        )

    async def refresh_catalog_projection(self, novel_id: str, *, context: str) -> None:
        """Refresh the compact projection without blocking the coordinator."""

        await self.executor.run(
            PersistenceOperation.DB_WRITE_TERMINAL,
            self._refresh_catalog_projection,
            novel_id,
            context,
        )

    def _invoke_storage(self, method_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        with self._storage_lock:
            method = getattr(self._storage, method_name)
            return method(*args, **kwargs)

    def _invoke_owned(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        with self._storage_lock:
            return function(*args, **kwargs)

    def _persist_progress_batch(
        self,
        events: list[dict[str, Any]],
        chunk_states: list[dict[str, Any]],
    ) -> dict[str, int]:
        with self._storage_lock:
            stored_events = self._storage.append_pipeline_events(events) if events else []
            batch_upsert = getattr(self._storage, "upsert_chunk_states", None)
            if callable(batch_upsert):
                batch_result = batch_upsert(chunk_states) if chunk_states else []
                stored_chunk_states: list[Any] = batch_result if isinstance(batch_result, list) else []
            else:
                stored_chunk_states = [
                    self._storage.upsert_chunk_state(state) for state in chunk_states if isinstance(state, dict)
                ]
            return {
                "events": len(stored_events),
                "chunk_states": len(stored_chunk_states),
            }

    def _save_manifest(self, novel_id: str, payload: dict[str, Any]) -> None:
        with self._storage_lock:
            manifest = TranslationRunManifest.from_dict(payload)
            self._storage.save_translation_run_manifest(novel_id, manifest)

    def _refresh_catalog_projection(self, novel_id: str, context: str) -> None:
        with self._storage_lock:
            safely_refresh_catalog_projection_after_storage_write(
                novel_id,
                self._storage,
                context=context,
            )

    @classmethod
    def _operation_for_method(cls, method_name: str) -> PersistenceOperation:
        if method_name in cls._CHECKPOINT_METHODS:
            return PersistenceOperation.RUNTIME_CHECKPOINT
        if method_name in cls._R2_READ_METHODS:
            return PersistenceOperation.R2_EXACT_READ
        if method_name in cls._R2_WRITE_METHODS:
            return PersistenceOperation.R2_IMMUTABLE_WRITE
        if method_name.startswith(("load_", "resolve_", "get_", "query_")):
            return PersistenceOperation.DB_READ_BUNDLE
        if method_name.startswith(("save_", "append_", "upsert_", "update_", "activate_")):
            return PersistenceOperation.DB_WRITE_PROGRESS
        return PersistenceOperation.DB_WRITE_TERMINAL

    async def shutdown(self, timeout_seconds: float = 30.0) -> bool:
        return await self.executor.drain(timeout_seconds)


def _save_checkpoint(checkpoint_dir: str, payload: dict[str, Any]) -> None:
    manager = CheckpointManager(checkpoint_dir)
    manager.save(Checkpoint.from_dict(payload))


def _delete_checkpoint(checkpoint_dir: str, chapter_id: str) -> None:
    CheckpointManager(checkpoint_dir).delete(chapter_id)


__all__ = [
    "BoundaryOwnershipError",
    "BoundedSyncExecutor",
    "OperationClass",
    "PersistenceObservation",
    "PersistenceOperation",
    "TranslationPersistencePort",
]
