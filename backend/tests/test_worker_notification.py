"""Focused tests for ActivityWorkerService notification callbacks.

Covers:
- Recipient from metadata.requesting_user_id only
- Safe skip on malformed/missing metadata
- Three lifecycle event types from explicit status/review state
- Exact {activity_id}:{event_type} dedupe and distinct failed->completed
- Privacy-safe constants (no raw errors/content/secrets)
- Failure isolation (callback exceptions don't propagate)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.db.base import Base
from novelai.db.models.users import User
from novelai.services.notification_service import (
    NoopNotificationBackend,
    NotificationPersistenceService,
)
from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def notification_service(db_session):
    return NotificationPersistenceService(db_session, NoopNotificationBackend())


@pytest.fixture()
def worker_env(notification_service):
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / "worker_notification_test"
    data_dir.mkdir(parents=True, exist_ok=True)
    storage = StorageService(data_dir)
    activity_log = ActivityQueueService(data_dir)
    orchestrator = Mock()
    orchestrator.storage = storage
    orchestrator.scrape_metadata = AsyncMock(return_value={"chapters": [{"id": "1"}]})
    orchestrator.scrape_chapters = AsyncMock(
        return_value={"succeeded": 1, "skipped": 0, "failed": 0, "failures": [], "image_download_failures": 0}
    )
    orchestrator.translate_chapters = AsyncMock(
        return_value={
            "succeeded": 1,
            "failed": 0,
            "skipped": 0,
            "total": 1,
            "chapter_progress": {"1": {"status": "completed"}},
        }
    )

    # Mirror test_job_worker_service.save_metadata pattern so translation
    # activities can resolve source_key without raising.
    storage.save_metadata("novel-1", {"source_key": "syosetu_ncode", "chapters": [{"id": "1"}]})

    def notify_callback(payload: dict[str, object]) -> object:
        return notification_service.create(**payload)

    worker = ActivityWorkerService(activity_log, orchestrator, notify_callback=notify_callback)
    yield worker, activity_log, notification_service
    import shutil

    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture()
def save_novel_metadata(worker_env):
    """Save source_key to storage for the test novel."""
    worker, _activity_log, _notif_service = worker_env
    worker.orchestrator.storage.save_metadata("novel-1", {"source_key": "syosetu_ncode", "chapters": [{"id": "1"}]})
    return worker_env


def _make_user(db_session, user_id: int, email: str = "test@example.com") -> User:
    user = User(id=user_id, email=email, role="user", email_verified_at=None)
    db_session.add(user)
    db_session.commit()
    return user


class TestWorkerNotificationRecipient:
    """Recipient solely from metadata.requesting_user_id."""

    @pytest.mark.asyncio
    async def test_notification_uses_requesting_user_id_from_metadata(self, save_novel_metadata, db_session):
        worker, activity_log, notif_service = save_novel_metadata
        _make_user(db_session, 42)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 42, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=42)
        assert notifications["total"] == 1
        assert notifications["items"][0]["event_type"] == "translation.completed"

    @pytest.mark.asyncio
    async def test_notification_skipped_when_requesting_user_id_missing(self, save_novel_metadata, db_session):
        worker, activity_log, notif_service = save_novel_metadata
        _make_user(db_session, 99)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=99)
        assert notifications["total"] == 0

    @pytest.mark.asyncio
    async def test_notification_skipped_when_requesting_user_id_invalid_type(self, save_novel_metadata, db_session):
        worker, activity_log, notif_service = save_novel_metadata
        _make_user(db_session, 100)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": "not-an-int", "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=100)
        assert notifications["total"] == 0

    @pytest.mark.asyncio
    async def test_notification_skipped_when_requesting_user_id_non_positive(self, save_novel_metadata, db_session):
        worker, activity_log, notif_service = save_novel_metadata
        _make_user(db_session, 101)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 0, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=101)
        assert notifications["total"] == 0

    @pytest.mark.asyncio
    async def test_notification_skipped_for_crawl_activities(self, save_novel_metadata, db_session):
        worker, activity_log, notif_service = save_novel_metadata
        _make_user(db_session, 200)

        activity = activity_log.create_crawl_activity(
            novel_id="novel-1",
            source_key="syosetu_ncode",
            kind="metadata",
            metadata={"requesting_user_id": 200, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=200)
        assert notifications["total"] == 0


class TestWorkerNotificationEventTypes:
    """Three lifecycle event types from explicit status/review state."""

    @pytest.mark.asyncio
    async def test_completed_without_review_emits_translation_completed(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 300)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 300, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=300)
        assert notifications["total"] == 1
        notif = notifications["items"][0]
        assert notif["event_type"] == "translation.completed"
        assert notif["severity"] == "success"
        assert notif["title"] == "Translation completed"
        assert notif["body"] == "Translation activity completed successfully."

    @pytest.mark.asyncio
    async def test_completed_with_review_chapters_emits_translation_requires_review(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 301)

        # Mock translate_chapters to return requires_review status
        worker.orchestrator.translate_chapters = AsyncMock(
            return_value={
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "chapter_progress": {"1": {"status": "requires_review"}},
            }
        )

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 301, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=301)
        assert notifications["total"] == 1
        notif = notifications["items"][0]
        assert notif["event_type"] == "translation.requires_review"
        assert notif["severity"] == "warning"
        assert notif["title"] == "Translation requires review"
        assert notif["body"] == "Translation activity completed with chapters requiring review."

    @pytest.mark.asyncio
    async def test_failed_emits_translation_failed(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 302)

        worker.orchestrator.translate_chapters = AsyncMock(side_effect=RuntimeError("translation failed"))

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 302, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=302)
        assert notifications["total"] == 1
        notif = notifications["items"][0]
        assert notif["event_type"] == "translation.failed"
        assert notif["severity"] == "error"
        assert notif["title"] == "Translation failed"
        assert notif["body"] == "Translation activity failed."


class TestWorkerNotificationDedupe:
    """Exact {activity_id}:{event_type} dedupe and distinct failed->completed."""

    @pytest.mark.asyncio
    async def test_dedupe_key_exact_activity_id_event_type(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 400)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 400, "source_key": "syosetu_ncode"},
        )
        activity_id = activity["activity_id"]

        # Run twice - second run should be deduped. Reset to pending between
        # runs so the worker accepts the retry (mirrors the distinct
        # failed->completed pattern below).
        await worker.run_activity(activity_id)
        activity_log.update_activity_status(activity_id, "pending", metadata={})
        await worker.run_activity(activity_id)

        notifications = notif_service.list(requesting_user_id=400)
        assert notifications["total"] == 1
        notif = notifications["items"][0]
        # action_url embeds activity_id (frontend owner route), proving
        # dedupe kept the original {activity_id}:{event_type} payload.
        assert notif["action_url"].endswith(f"/admin/activity/{activity_id}")
        assert notif["event_type"] == "translation.completed"

    @pytest.mark.asyncio
    async def test_distinct_failed_then_completed_creates_two_notifications(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 401)

        # First run: failure
        worker.orchestrator.translate_chapters = AsyncMock(side_effect=RuntimeError("translation failed"))
        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 401, "source_key": "syosetu_ncode"},
        )
        activity_id = activity["activity_id"]

        await worker.run_activity(activity_id)

        notifications = notif_service.list(requesting_user_id=401)
        assert notifications["total"] == 1
        assert notifications["items"][0]["event_type"] == "translation.failed"

        # Reset activity to pending for retry (simulate retry flow)
        activity_log.update_activity_status(activity_id, "pending", metadata={})

        # Second run: success
        worker.orchestrator.translate_chapters = AsyncMock(
            return_value={
                "succeeded": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "chapter_progress": {"1": {"status": "completed"}},
            }
        )

        await worker.run_activity(activity_id)

        notifications = notif_service.list(requesting_user_id=401)
        assert notifications["total"] == 2
        event_types = {n["event_type"] for n in notifications["items"]}
        assert event_types == {"translation.failed", "translation.completed"}


class TestWorkerNotificationPrivacy:
    """Privacy-safe constants; no raw errors/content/secrets."""

    @pytest.mark.asyncio
    async def test_notification_body_uses_constant_no_raw_error(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 500)

        worker.orchestrator.translate_chapters = AsyncMock(side_effect=RuntimeError("secret-api-key-12345"))

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 500, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=500)
        assert notifications["total"] == 1
        body = notifications["items"][0]["body"]
        assert body == "Translation activity failed."
        assert "secret-api-key" not in body
        assert "12345" not in body

    @pytest.mark.asyncio
    async def test_notification_title_uses_constant(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 501)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 501, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=501)
        assert notifications["items"][0]["title"] == "Translation completed"

    @pytest.mark.asyncio
    async def test_notification_action_url_internal_path_only(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 502)

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 502, "source_key": "syosetu_ncode"},
        )

        await worker.run_activity(activity["activity_id"])

        notifications = notif_service.list(requesting_user_id=502)
        action_url = notifications["items"][0]["action_url"]
        assert action_url is not None
        # Internal frontend owner route (proven via
        # frontend/app/(admin)/admin/activity/[activityId]/page.tsx), not the
        # backend API path.
        assert action_url.startswith("/admin/activity/")
        assert not action_url.startswith("http")
        assert not action_url.startswith("//")


class TestWorkerNotificationFailureIsolation:
    """Callback exceptions don't propagate."""

    @pytest.mark.asyncio
    async def test_callback_exception_isolated(self, worker_env, db_session):
        worker, activity_log, _notif_service = worker_env
        _make_user(db_session, 600)

        # Wrap callback to raise
        original_callback = worker._notify_callback

        def failing_callback(payload: dict[str, object]) -> object:
            raise RuntimeError("callback boom")

        worker._notify_callback = failing_callback

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 600, "source_key": "syosetu_ncode"},
        )

        # Should not raise
        result = await worker.run_activity(activity["activity_id"])

        assert result is not None
        assert result["status"] == "completed"

        # Restore
        worker._notify_callback = original_callback

    @pytest.mark.asyncio
    async def test_none_callback_no_op(self, worker_env, db_session):
        worker, activity_log, notif_service = worker_env
        _make_user(db_session, 601)

        worker._notify_callback = None

        activity = activity_log.create_translation_activity(
            novel_id="novel-1",
            chapters="1",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            metadata={"requesting_user_id": 601, "source_key": "syosetu_ncode"},
        )

        result = await worker.run_activity(activity["activity_id"])

        assert result is not None
        assert result["status"] == "completed"
        notifications = notif_service.list(requesting_user_id=601)
        assert notifications["total"] == 0
