from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from novelai.activity.queue import ActivityQueueService
from novelai.db.base import Base
from novelai.db.engine import session_scope
from novelai.db.models.activity import ActivityRecord


def _database_queue(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'activities.sqlite').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    @contextmanager
    def factory():
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return (
        ActivityQueueService(db_session_scope_factory=factory),
        ActivityQueueService(db_session_scope_factory=factory),
        engine,
    )


def test_database_activity_queue_is_idempotent_and_row_locked(tmp_path) -> None:
    first, second, engine = _database_queue(tmp_path)
    try:
        activity = first.create_translation_activity(
            novel_id="novel-1",
            source_key="source",
            chapters="all",
            provider_key="gemini",
            provider_model="model",
            idempotency_key="request-1",
        )
        duplicate = second.create_translation_activity(
            novel_id="novel-1",
            source_key="source",
            chapters="all",
            provider_key="gemini",
            provider_model="model",
            idempotency_key="request-1",
        )

        assert duplicate["activity_id"] == activity["activity_id"]
        claimed = first.claim_next_activity(activity_type="translation")
        assert claimed is not None
        assert claimed["status"] == "running"
        assert second.claim_next_activity(activity_type="translation") is None

        assert first.renew_activity_lease(claimed["activity_id"], claimed["lease_id"]) is True
        assert second.renew_activity_lease(claimed["activity_id"], "wrong-lease") is False

        completed = first.update_activity_status(activity["activity_id"], "completed", lease_id=claimed["lease_id"])
        assert completed is not None
        after_completion = second.create_translation_activity(
            novel_id="novel-1",
            source_key="source",
            chapters="all",
            provider_key="gemini",
            provider_model="model",
            idempotency_key="request-1",
        )
        assert after_completion["activity_id"] == activity["activity_id"]
        assert after_completion["status"] == "completed"
    finally:
        engine.dispose()


def test_database_activity_queue_recovers_expired_lease_and_reports_stats(tmp_path) -> None:
    first, second, engine = _database_queue(tmp_path)
    try:
        activity = first.create_crawl_activity(novel_id="novel-2", source_key="source")
        claimed = first.claim_activity(activity["activity_id"])
        assert claimed is not None

        with session_scope(f"sqlite:///{(tmp_path / 'activities.sqlite').as_posix()}") as session:
            row = session.get(ActivityRecord, activity["activity_id"])
            assert row is not None
            row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

        recovered = second.claim_next_activity(activity_type="crawl")
        assert recovered is not None
        assert recovered["activity_id"] == activity["activity_id"]
        assert recovered["status"] == "running"
        stats = second.queue_stats()
        assert stats["backend"] == "database"
        assert "operations" in stats
    finally:
        engine.dispose()


def test_database_claim_activity_reclaims_expired_lease_in_one_call(tmp_path) -> None:
    queue, _, engine = _database_queue(tmp_path)
    try:
        activity = queue.create_crawl_activity(novel_id="novel-lease", source_key="source")
        first_claim = queue.claim_activity(activity["activity_id"])
        assert first_claim is not None

        with session_scope(f"sqlite:///{(tmp_path / 'activities.sqlite').as_posix()}") as session:
            row = session.get(ActivityRecord, activity["activity_id"])
            assert row is not None
            row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

        reclaimed = queue.claim_activity(activity["activity_id"])
        assert reclaimed is not None
        assert reclaimed["activity_id"] == activity["activity_id"]
        assert reclaimed["status"] == "running"
        assert reclaimed["lease_id"] != first_claim["lease_id"]
    finally:
        engine.dispose()


def test_database_claim_uses_returning_update(tmp_path) -> None:
    queue, _, engine = _database_queue(tmp_path)
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        queue.create_crawl_activity(novel_id="novel-3", source_key="source")
        claimed = queue.claim_next_activity(activity_type="crawl")
        assert claimed is not None
        claim_updates = [
            statement.upper() for statement in statements if "UPDATE ACTIVITY_RECORDS" in statement.upper()
        ]
        assert claim_updates
        assert any("RETURNING" in statement for statement in claim_updates)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        engine.dispose()


def test_database_heartbeat_is_timestamp_only_update(tmp_path) -> None:
    queue, _, engine = _database_queue(tmp_path)
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:
        statements.append(statement)

    try:
        activity = queue.create_crawl_activity(novel_id="novel-4", source_key="source")
        claimed = queue.claim_activity(activity["activity_id"])
        assert claimed is not None
        event.listen(engine, "before_cursor_execute", capture)
        assert queue.renew_activity_lease(claimed["activity_id"], claimed["lease_id"]) is True
        assert statements
        assert not any(statement.lstrip().upper().startswith("SELECT") for statement in statements)
        assert any(statement.lstrip().upper().startswith("UPDATE") for statement in statements)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        engine.dispose()
