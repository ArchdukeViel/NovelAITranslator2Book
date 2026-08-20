from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine

from novelai.activity.queue import ActivityQueueService
from novelai.db.base import Base
from novelai.db.engine import session_scope
from novelai.db.models.activity import ActivityRecord


def _database_queue(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'activities.sqlite').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    def factory():
        return session_scope(database_url)

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
