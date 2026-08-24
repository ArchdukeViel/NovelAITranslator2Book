"""Focused tests for the bounded synchronous translation boundary."""

from __future__ import annotations

import asyncio
import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, defer
from sqlalchemy.orm.exc import DetachedInstanceError

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.engine import session_scope
from novelai.db.models.activity import ActivityRecord
from novelai.services.orchestration.translation_persistence import (
    BoundaryOwnershipError,
    BoundedSyncExecutor,
    PersistenceOperation,
    TranslationPersistencePort,
)
from novelai.storage.service import StorageService


class _BlockingStorage:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[tuple[str, int]] = []
        self.result: dict[str, str] | None = None

    def load_metadata(self, novel_id: str) -> dict[str, str]:
        self.calls.append((novel_id, threading.get_ident()))
        self.started.set()
        self.release.wait()
        self.result = {"novel_id": novel_id, "mutable": "detached"}
        return self.result


@pytest.mark.asyncio
async def test_storage_call_leaves_event_loop_and_returns_detached_value() -> None:
    storage = _BlockingStorage()
    port = TranslationPersistencePort(storage, max_workers=1, max_queue=1)

    operation = asyncio.create_task(port.storage_call("load_metadata", "novel-1"))
    try:
        async with asyncio.timeout(2):
            await asyncio.to_thread(storage.started.wait)
            storage.release.set()
            result = await operation
    finally:
        storage.release.set()
        if not operation.done():
            await operation
        await port.shutdown()

    assert result == {"novel_id": "novel-1", "mutable": "detached"}
    assert storage.calls
    assert storage.calls[0][1] != threading.get_ident()

    result["mutable"] = "changed"
    assert storage.result == {"novel_id": "novel-1", "mutable": "detached"}


@pytest.mark.asyncio
async def test_executor_bounds_running_and_queued_operations() -> None:
    executor = BoundedSyncExecutor(max_workers=1, max_queue=1)
    started = threading.Event()
    release = threading.Event()

    def blocking(value: str) -> str:
        started.set()
        release.wait()
        return value

    tasks = [
        asyncio.create_task(executor.run(PersistenceOperation.DB_READ_SCALAR, blocking, value))
        for value in ("one", "two", "three")
    ]
    try:
        async with asyncio.timeout(2):
            await asyncio.to_thread(started.wait)
            await asyncio.sleep(0)
            assert executor.active_count == 2
            assert not tasks[2].done()
            release.set()
            assert await asyncio.gather(*tasks) == ["one", "two", "three"]
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                await task
        await executor.drain()

    observations = executor.observations
    assert len(observations) == 3
    assert all(observation.queue_wait_ms >= 0 for observation in observations)
    assert all(observation.duration_ms >= 0 for observation in observations)


@pytest.mark.asyncio
async def test_cancelled_boundary_call_drains_underlying_operation() -> None:
    executor = BoundedSyncExecutor(max_workers=1, max_queue=0)
    started = threading.Event()
    release = threading.Event()

    def blocking() -> str:
        started.set()
        release.wait()
        return "completed"

    task = asyncio.create_task(executor.run(PersistenceOperation.DB_WRITE_PROGRESS, blocking))
    try:
        async with asyncio.timeout(2):
            await asyncio.to_thread(started.wait)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert executor.active_count == 1
            release.set()
            assert await executor.drain(timeout_seconds=2)
    finally:
        release.set()
        if not task.done():
            await task
        if executor.active_count:
            await executor.drain(timeout_seconds=2)


@pytest.mark.asyncio
async def test_failed_operation_records_category_without_exception_text() -> None:
    executor = BoundedSyncExecutor(max_workers=1, max_queue=0)

    def fail() -> None:
        raise ValueError("secret-provider-response")

    with pytest.raises(ValueError, match="secret-provider-response"):
        await executor.run(PersistenceOperation.R2_EXACT_READ, fail)
    await asyncio.sleep(0)

    observation = executor.observations[-1]
    assert observation.outcome == "retryable_failure"
    assert observation.error_code == "ValueError"
    assert "secret-provider-response" not in str(observation.to_dict())
    assert executor.active_count == 0
    await executor.drain()


@pytest.mark.asyncio
async def test_boundary_rejects_live_session_and_orm_arguments() -> None:
    port = TranslationPersistencePort(_BlockingStorage(), max_workers=1, max_queue=0)
    live_session = Session()
    orm_record = ActivityRecord(
        activity_id="activity-boundary",
        type="translation",
        kind="translation",
        novel_id="novel-boundary",
        status="pending",
    )
    try:
        with pytest.raises(BoundaryOwnershipError, match="database resource"):
            await port.call(PersistenceOperation.DB_READ_SCALAR, lambda value: value, live_session)
        with pytest.raises(BoundaryOwnershipError, match="ORM object"):
            await port.call(PersistenceOperation.DB_READ_SCALAR, lambda value: value, orm_record)
        assert port.executor.active_count == 0
    finally:
        live_session.close()
        await port.shutdown()


@pytest.mark.asyncio
async def test_boundary_rejects_orm_result_before_it_can_cross() -> None:
    port = TranslationPersistencePort(_BlockingStorage(), max_workers=1, max_queue=0)
    orm_record = ActivityRecord(
        activity_id="activity-result-boundary",
        type="translation",
        kind="translation",
        novel_id="novel-boundary",
        status="pending",
    )
    try:
        with pytest.raises(BoundaryOwnershipError, match="ORM object"):
            await port.call(PersistenceOperation.DB_READ_BUNDLE, lambda: orm_record)
        await asyncio.sleep(0)
        assert port.executor.active_count == 0
        assert port.executor.observations[-1].error_code == "BoundaryOwnershipError"
    finally:
        await port.shutdown()


def test_session_scope_rolls_back_and_does_not_allow_lazy_access_after_close(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'boundary.sqlite').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    activity_id = "activity-rollback-boundary"
    try:
        with pytest.raises(RuntimeError, match="synthetic rollback"), session_scope(database_url) as session:
            session.add(
                ActivityRecord(
                    activity_id=activity_id,
                    type="translation",
                    kind="translation",
                    novel_id="novel-boundary",
                    status="pending",
                )
            )
            raise RuntimeError("synthetic rollback")

        with Session(engine) as session:
            assert session.get(ActivityRecord, activity_id) is None

        with session_scope(database_url) as session:
            session.add(
                ActivityRecord(
                    activity_id="activity-detached-boundary",
                    type="translation",
                    kind="translation",
                    novel_id="novel-boundary",
                    status="pending",
                    error="detached-value",
                )
            )

        with session_scope(database_url) as session:
            detached = session.scalar(
                select(ActivityRecord)
                .options(defer(ActivityRecord.error))
                .where(ActivityRecord.activity_id == "activity-detached-boundary")
            )
            assert detached is not None

        with pytest.raises(DetachedInstanceError):
            _ = detached.error
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_progress_batch_is_bounded_and_replay_safe(tmp_path) -> None:
    storage = StorageService(base_dir=tmp_path)
    port = TranslationPersistencePort(storage, max_workers=1, max_queue=0)
    events = [
        {
            "event_id": "event-progress-1",
            "novel_id": "novel-progress",
            "chapter_id": "chapter-1",
            "translation_run_id": "run-progress",
            "status_after": "translated",
        }
    ]
    chunk_states = [
        {
            "novel_id": "novel-progress",
            "chapter_id": "chapter-1",
            "chunk_id": "chunk-1",
            "translation_run_id": "run-progress",
            "status": "translated",
        }
    ]
    try:
        first = await port.persist_progress_batch(events=events, chunk_states=chunk_states)
        replay = await port.persist_progress_batch(events=events, chunk_states=chunk_states)
    finally:
        await port.shutdown()

    assert first == {"events": 1, "chunk_states": 1}
    assert replay == first
    assert len(storage.list_pipeline_events(novel_id="novel-progress")) == 1
    assert len(storage.load_chunk_states(novel_id="novel-progress", translation_run_id="run-progress")) == 1
    assert len(port.executor.observations) == 2
    assert all(
        observation.operation_class == PersistenceOperation.DB_WRITE_PROGRESS
        for observation in port.executor.observations
    )


@pytest.mark.asyncio
async def test_persistence_expansion_gate_has_serialized_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_PERSISTENCE_EXPANSION_ENABLED", False)
    monkeypatch.setattr(settings, "TRANSLATION_PERSISTENCE_WORKERS", 4)
    monkeypatch.setattr(settings, "TRANSLATION_PERSISTENCE_QUEUE_SIZE", 16)
    rollback_port = TranslationPersistencePort(_BlockingStorage())

    try:
        assert rollback_port.executor.max_workers == 1
        assert rollback_port.executor.max_queue == 0
    finally:
        await rollback_port.shutdown()

    monkeypatch.setattr(settings, "TRANSLATION_PERSISTENCE_EXPANSION_ENABLED", True)
    expanded_port = TranslationPersistencePort(_BlockingStorage())
    try:
        assert expanded_port.executor.max_workers == 4
        assert expanded_port.executor.max_queue == 16
    finally:
        await expanded_port.shutdown()
