"""Focused persistence tests for privacy-safe notification ORM models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.notification import Notification, NotificationDelivery, NotificationPreference
from novelai.db.models.users import User


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_fk_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def create_user(session, email: str) -> User:
    user = User(email=email, role="user")
    session.add(user)
    session.commit()
    return user


def create_notification(session, user: User, dedupe_key: str = "activity:1:completed") -> Notification:
    notification = Notification(
        recipient_user_id=user.id,
        event_type="translation.completed",
        title="Translation completed",
        body="Translation ready.",
        action_url="/activities/1",
        source_type="activity",
        source_id="1",
        dedupe_key=dedupe_key,
    )
    session.add(notification)
    session.commit()
    return notification


def test_notification_defaults_and_safe_fields(session) -> None:
    user = create_user(session, "notification@example.com")
    notification = create_notification(session, user)

    assert notification.status == "unread"
    assert notification.severity == "info"
    assert notification.created_at is not None
    assert notification.read_at is None
    assert notification.archived_at is None
    assert notification.action_url == "/activities/1"
    assert {"secret", "private_text", "error_message"}.isdisjoint(Notification.__table__.columns.keys())


@pytest.mark.parametrize("action_url", ["https://example.com/activity", "//example.com/activity", "activity/1"])
def test_notification_rejects_non_internal_action_url(session, action_url: str) -> None:
    user = create_user(session, f"url-{action_url[0]}-{len(action_url)}@example.com")

    with pytest.raises(ValueError, match="internal path"):
        Notification(
            recipient_user_id=user.id,
            event_type="translation.failed",
            title="Translation failed",
            body="Retry available.",
            action_url=action_url,
            dedupe_key=f"url:{action_url}",
        )


def test_notification_dedupe_is_unique_per_recipient(session) -> None:
    first_user = create_user(session, "first@example.com")
    second_user = create_user(session, "second@example.com")
    create_notification(session, first_user, "activity:1:completed")
    create_notification(session, second_user, "activity:1:completed")
    session.add(
        Notification(
            recipient_user_id=first_user.id,
            event_type="translation.completed",
            title="Duplicate",
            body="Duplicate.",
            dedupe_key="activity:1:completed",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_notification_recipient_fk_owns_notification_and_delivery(session) -> None:
    user = create_user(session, "owner@example.com")
    notification = create_notification(session, user)
    delivery = NotificationDelivery(notification_id=notification.id, channel="email")
    session.add(delivery)
    session.commit()

    session.delete(user)
    session.commit()

    assert session.query(Notification).count() == 0
    assert session.query(NotificationDelivery).count() == 0


def test_notification_read_and_archive_timestamps_persist(session) -> None:
    user = create_user(session, "timestamps@example.com")
    notification = create_notification(session, user)
    now = datetime.now(UTC)
    notification.status = "archived"
    notification.read_at = now
    notification.archived_at = now
    session.commit()

    stored = session.get(Notification, notification.id)
    assert stored is not None
    assert stored.status == "archived"
    assert stored.read_at is not None
    assert stored.archived_at is not None
    assert stored.read_at.replace(tzinfo=UTC) == now
    assert stored.archived_at.replace(tzinfo=UTC) == now


def test_notification_preference_is_unique_per_user_event_and_channel(session) -> None:
    user = create_user(session, "preference@example.com")
    preference = NotificationPreference(user_id=user.id, event_type="translation.failed", channel="in_app")
    session.add(preference)
    session.commit()
    assert preference.enabled is True
    session.add(NotificationPreference(user_id=user.id, event_type="translation.failed", channel="in_app"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_notification_delivery_defaults_and_safe_error_category(session) -> None:
    user = create_user(session, "delivery@example.com")
    notification = create_notification(session, user)
    pending_delivery = NotificationDelivery(notification_id=notification.id, channel="email")
    session.add(pending_delivery)
    session.commit()
    assert pending_delivery.status == "pending"
    assert pending_delivery.attempt_count == 0

    sent_at = datetime.now(UTC)
    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel="email",
        status="sent",
        attempt_count=2,
        sent_at=sent_at,
        error_category="provider_unavailable",
    )
    session.add(delivery)
    session.commit()

    stored = session.get(NotificationDelivery, delivery.id)
    assert stored is not None
    assert stored.channel == "email"
    assert stored.status == "sent"
    assert stored.attempt_count == 2
    assert stored.sent_at is not None
    assert stored.sent_at.replace(tzinfo=UTC) == sent_at
    assert stored.failed_at is None
    assert stored.error_category == "provider_unavailable"
    assert {"error_message", "provider_response", "secret"}.isdisjoint(NotificationDelivery.__table__.columns.keys())
