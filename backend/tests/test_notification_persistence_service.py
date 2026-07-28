"""Focused tests for recipient-scoped notification persistence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.notification import Notification, NotificationDelivery
from novelai.db.models.users import User
from novelai.services.notification_service import NoopNotificationBackend, NotificationPersistenceService


class _EmailBackend:
    def __init__(self, fails: bool = False) -> None:
        self.fails = fails
        self.sent: list[tuple[str, str, str | None]] = []

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        if self.fails:
            raise RuntimeError("private provider detail")
        self.sent.append((subject, message, recipient))


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()
    Base.metadata.drop_all(engine)


def _capture(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "novelai.services.notification_service" and record.levelno == logging.INFO
    ]


def _sensitive_sentinels() -> list[str]:
    return [
        "Translation completed",
        "Translation ready",
        "activity@example.com",
        "failure@example.com",
        "private provider detail",
        "/activities/1",
        "activity:1:v1",
        "secret-token",
        "192.168.0.1",
    ]


def _user(session, email: str, verified: bool = True) -> User:
    user = User(email=email, role="user", email_verified_at=datetime.now(UTC) if verified else None)
    session.add(user)
    session.commit()
    return user


def _create(
    service: NotificationPersistenceService, user: User, key: str = "activity:1:v1"
) -> dict[str, object] | None:
    return service.create(
        recipient_user_id=user.id,
        event_type="translation.completed",
        title="Translation completed",
        body="Translation ready.",
        severity="success",
        dedupe_key=key,
        action_url="/activities/1",
        source_type="activity",
        source_id="1",
    )


def test_create_dedupes_and_validates_safe_inputs(session) -> None:
    user = _user(session, "one@example.com")
    service = NotificationPersistenceService(session, NoopNotificationBackend())
    first = _create(service, user)
    duplicate = _create(service, user)

    assert first is not None
    assert duplicate is not None
    assert duplicate["id"] == first["id"]
    assert session.query(Notification).count() == 1
    with pytest.raises(ValueError):
        service.create(
            recipient_user_id=user.id, event_type="other", title="x", body="x", severity="info", dedupe_key="x"
        )
    with pytest.raises(ValueError):
        service.create(
            recipient_user_id=user.id,
            event_type="translation.completed",
            title="x",
            body="x",
            severity="info",
            dedupe_key="x",
            action_url="https://bad",
        )
    with pytest.raises(ValueError):
        service.create(
            recipient_user_id=user.id,
            event_type="translation.completed",
            title="x" * 256,
            body="x",
            severity="info",
            dedupe_key="x",
        )
    with pytest.raises(ValueError):
        service.create(
            recipient_user_id=user.id,
            event_type="translation.completed",
            title="x",
            body="x",
            severity="fatal",
            dedupe_key="x",
        )


def test_list_scope_pagination_filter_and_state_changes(session) -> None:
    first_user = _user(session, "first@example.com")
    second_user = _user(session, "second@example.com")
    service = NotificationPersistenceService(session, NoopNotificationBackend())
    first = _create(service, first_user, "activity:1:v1")
    second = _create(service, first_user, "activity:2:v1")
    other = _create(service, second_user, "activity:1:v1")
    assert first is not None and second is not None and other is not None

    page = service.list(requesting_user_id=first_user.id, page=1, page_size=1, event_type="translation.completed")
    assert page["total"] == 2
    assert isinstance(page["items"], list)
    assert len(page["items"]) == 1
    assert service.unread_count(requesting_user_id=first_user.id) == 2
    assert isinstance(other["id"], int)
    assert not service.mark_read(requesting_user_id=first_user.id, notification_id=other["id"])
    assert isinstance(first["id"], int)
    assert service.mark_read(requesting_user_id=first_user.id, notification_id=first["id"])
    assert service.mark_all_read(requesting_user_id=first_user.id) == 1
    assert isinstance(second["id"], int)
    assert service.archive(requesting_user_id=first_user.id, notification_id=second["id"])
    archived = service.list(requesting_user_id=first_user.id, status="archived")
    assert archived["total"] == 1
    assert service.unread_count(requesting_user_id=first_user.id) == 0


def test_preferences_defaults_and_email_delivery_states(session) -> None:
    user = _user(session, "email@example.com")
    backend = _EmailBackend()
    service = NotificationPersistenceService(session, backend)

    defaults = service.get_preferences(requesting_user_id=user.id)
    assert {
        (item["channel"], item["enabled"]) for item in defaults if item["event_type"] == "translation.completed"
    } == {("in_app", True), ("email", False)}
    _create(service, user)
    assert session.query(NotificationDelivery).one().status == "skipped_preferences"
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )
    _create(service, user, "activity:2:v1")
    delivery = session.query(NotificationDelivery).order_by(NotificationDelivery.id.desc()).first()
    assert delivery is not None and delivery.status == "sent" and delivery.attempt_count == 1
    assert backend.sent[-1][-1] == user.email


def test_email_requires_active_verified_recipient(session) -> None:
    unverified = _user(session, "unverified@example.com", verified=False)
    service = NotificationPersistenceService(session, _EmailBackend())
    service.update_preference(
        requesting_user_id=unverified.id, event_type="translation.completed", channel="email", enabled=True
    )
    assert _create(service, unverified) is not None
    assert session.query(NotificationDelivery).one().status == "skipped_no_address"

    inactive = _user(session, "inactive@example.com")
    inactive.is_active = False
    session.commit()
    with pytest.raises(ValueError, match="recipient is not active"):
        _create(service, inactive)


def test_email_failure_isolated_and_retention_is_bounded(session) -> None:
    user = _user(session, "failure@example.com")
    service = NotificationPersistenceService(session, _EmailBackend(fails=True))
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )
    created = _create(service, user)
    assert created is not None
    delivery = session.query(NotificationDelivery).one()
    assert delivery.status == "failed" and delivery.error_category == "delivery_failed"
    assert isinstance(created["id"], int)
    notification = session.get(Notification, created["id"])
    assert notification is not None and notification.status == "unread"
    notification.status = "archived"
    notification.created_at = datetime.now(UTC) - timedelta(days=31)
    session.commit()
    assert service.cleanup_retention(older_than_days=30, batch_size=1) == 1
    assert session.query(Notification).count() == 0


def test_create_persists_across_separate_sessions() -> None:
    """Notification created inside a session_scope is visible from a
    separate session — proves the production callback's session_scope
    (commit+close) does not lose the row."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # Session A: create user + notification (mimics session_scope pattern)
    session_a = Session()
    user = User(email="cross@session.test", role="user")
    session_a.add(user)
    session_a.commit()
    user_id = user.id

    service_a = NotificationPersistenceService(session_a, NoopNotificationBackend())
    result = service_a.create(
        recipient_user_id=user_id,
        event_type="translation.completed",
        title="Cross-session test",
        body="Should persist.",
        severity="success",
        dedupe_key="cross:session:1",
    )
    assert result is not None
    session_a.close()

    # Session B: same engine, new session — notification must be visible
    session_b = Session()
    service_b = NotificationPersistenceService(session_b, NoopNotificationBackend())
    page = service_b.list(requesting_user_id=user_id)
    session_b.close()

    assert page["total"] == 1
    assert page["items"][0]["event_type"] == "translation.completed"
    assert page["items"][0]["title"] == "Cross-session test"
    assert page["items"][0]["body"] == "Should persist."

    engine.dispose()


def test_first_commit_failure_no_email_no_notification(session, monkeypatch, caplog) -> None:
    """First-commit failure must not send email, emit created, or persist row."""
    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")
    user = _user(session, "commitfail@example.com")
    backend = _EmailBackend()
    service = NotificationPersistenceService(session, backend)
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )
    caplog.clear()

    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("DB down")))

    with pytest.raises(RuntimeError):
        service.create(
            recipient_user_id=user.id,
            event_type="translation.completed",
            title="Should not persist",
            body="Should not exist",
            severity="success",
            dedupe_key="commit:fail:v1",
        )

    assert len(backend.sent) == 0
    lines = _capture(caplog)
    assert not any("event=notification.created" in line for line in lines)


def test_delivery_record_commit_failure_preserves_notification(session, monkeypatch) -> None:
    """Delivery-record commit failure must not rollback notification or block caller."""
    user = _user(session, "delrecfail@example.com")
    backend = _EmailBackend()
    service = NotificationPersistenceService(session, backend)
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )

    orig_commit = session.commit
    call_n = [0]

    def _failing_commit():
        call_n[0] += 1
        if call_n[0] == 2:
            raise RuntimeError("delivery commit failure")
        return orig_commit()

    monkeypatch.setattr(session, "commit", _failing_commit)

    result = service.create(
        recipient_user_id=user.id,
        event_type="translation.completed",
        title="Notification preserved",
        body="Delivery record failed but notification OK",
        severity="success",
        dedupe_key="delivery:fails:v1",
    )

    assert result is not None
    assert session.query(Notification).count() == 1
    assert len(backend.sent) == 1


def test_structured_log_events_for_create_sent_failed_skipped_and_preferences(
    session, caplog: pytest.LogCaptureFixture
) -> None:
    """Create + email sent/failed + skipped + preferences update emit safe events only."""
    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")

    # --- 1) create + email sent ---
    sent_user = _user(session, "activity@example.com")
    sent_backend = _EmailBackend()
    sent_service = NotificationPersistenceService(session, sent_backend)
    sent_service.update_preference(
        requesting_user_id=sent_user.id, event_type="translation.completed", channel="email", enabled=True
    )
    caplog.clear()
    _create(sent_service, sent_user, "activity:sent:v1")
    sent_lines = _capture(caplog)
    assert any("event=notification.created" in line for line in sent_lines)
    assert any(
        "event=notification.created" in line
        and f"recipient_user_id={sent_user.id}" in line
        and "event_type=translation.completed" in line
        and "channel=in_app" in line
        for line in sent_lines
    )
    assert any("event=notification.delivery_sent" in line for line in sent_lines)
    assert any(
        "event=notification.delivery_sent" in line
        and f"recipient_user_id={sent_user.id}" in line
        and "channel=email" in line
        and "status=sent" in line
        for line in sent_lines
    )
    assert not any("event=notification.delivery_queued" in line for line in sent_lines)

    # --- 2) email failed ---
    failed_user = _user(session, "failure@example.com")
    failed_service = NotificationPersistenceService(session, _EmailBackend(fails=True))
    failed_service.update_preference(
        requesting_user_id=failed_user.id, event_type="translation.completed", channel="email", enabled=True
    )
    caplog.clear()
    _create(failed_service, failed_user, "activity:failed:v1")
    failed_lines = _capture(caplog)
    assert any("event=notification.delivery_failed" in line for line in failed_lines)
    assert any(
        "event=notification.delivery_failed" in line
        and f"recipient_user_id={failed_user.id}" in line
        and "channel=email" in line
        and "status=failed" in line
        and "error_category=delivery_failed" in line
        for line in failed_lines
    )

    # --- 3) skipped_preferences (in_app preference disabled) ---
    skipped_user = _user(session, "skipper@example.com")
    skipped_service = NotificationPersistenceService(session, NoopNotificationBackend())
    skipped_service.update_preference(
        requesting_user_id=skipped_user.id, event_type="translation.completed", channel="in_app", enabled=False
    )
    caplog.clear()
    result = _create(skipped_service, skipped_user, "activity:skipped:v1")
    assert result is None
    skipped_lines = _capture(caplog)
    assert any("event=notification.skipped_preferences" in line for line in skipped_lines)
    assert any(
        "event=notification.skipped_preferences" in line
        and f"recipient_user_id={skipped_user.id}" in line
        and "channel=in_app" in line
        and "status=skipped_preferences" in line
        for line in skipped_lines
    )
    # create event must NOT fire when skipped
    assert not any("event=notification.created" in line for line in skipped_lines)

    # --- 4) preferences_updated ---
    pref_user = _user(session, "prefs@example.com")
    pref_service = NotificationPersistenceService(session, NoopNotificationBackend())
    caplog.clear()
    pref_service.update_preference(
        requesting_user_id=pref_user.id,
        event_type="translation.completed",
        channel="email",
        enabled=True,
    )
    pref_lines = _capture(caplog)
    assert any("event=notification.preferences_updated" in line for line in pref_lines)
    assert any(
        "event=notification.preferences_updated" in line
        and f"recipient_user_id={pref_user.id}" in line
        and "event_type=translation.completed" in line
        and "channel=email" in line
        for line in pref_lines
    )

    # --- 5) no sensitive content ever reaches the log stream ---
    all_lines = sent_lines + failed_lines + skipped_lines + pref_lines
    for sentinel in _sensitive_sentinels():
        for line in all_lines:
            assert sentinel not in line, f"sensitive value {sentinel!r} leaked into log: {line!r}"


def test_structured_log_keys_are_allowlisted_only(session, caplog: pytest.LogCaptureFixture) -> None:
    """Any field beyond the allowlist (title/body/email/address/error text/...) is dropped."""
    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")
    user = _user(session, "allowlist@example.com")
    service = NotificationPersistenceService(session, _EmailBackend())
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )
    caplog.clear()
    _create(service, user, "activity:allowlist:v1")

    forbidden_keys = (
        "title=",
        "body=",
        "email=",
        "address=",
        "action_url=",
        "dedupe_key=",
        "source_type=",
        "source_id=",
        "error_text=",
        "message=",
        "subject=",
        "token=",
        "secret=",
    )
    for line in _capture(caplog):
        for forbidden in forbidden_keys:
            assert forbidden not in line, f"forbidden key {forbidden!r} in log: {line!r}"


def test_happy_path_emits_created_and_delivers_email(session, caplog: pytest.LogCaptureFixture) -> None:
    """First creation must reach email delivery, commit, and emit notification.created."""
    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")
    user = _user(session, "happy@example.com")
    backend = _EmailBackend()
    service = NotificationPersistenceService(session, backend)
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )
    caplog.clear()

    result = _create(service, user, "happy:path:v1")

    assert result is not None
    assert result["event_type"] == "translation.completed"
    # Email must have been delivered
    assert len(backend.sent) == 1
    assert backend.sent[0][-1] == user.email
    # notification.created event must be in logs
    lines = _capture(caplog)
    assert any("event=notification.created" in line for line in lines)
    assert any(
        "event=notification.created" in line
        and f"recipient_user_id={user.id}" in line
        and "event_type=translation.completed" in line
        and "channel=in_app" in line
        for line in lines
    )
    # In-app notification must be persisted (committed)
    assert session.query(Notification).count() == 1
    assert session.query(NotificationDelivery).one().status == "sent"


def test_dedupe_does_not_reemit_or_redeliver(session, caplog: pytest.LogCaptureFixture) -> None:
    """Duplicate creation must NOT emit notification.created or redeliver email."""
    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")
    user = _user(session, "dedupe@example.com")
    backend = _EmailBackend()
    service = NotificationPersistenceService(session, backend)
    service.update_preference(
        requesting_user_id=user.id, event_type="translation.completed", channel="email", enabled=True
    )
    caplog.clear()

    first = _create(service, user, "dedupe:check:v1")
    assert first is not None
    assert len(backend.sent) == 1  # email sent once
    assert session.query(Notification).count() == 1

    caplog.clear()
    backend.sent.clear()

    duplicate = _create(service, user, "dedupe:check:v1")
    assert duplicate is not None
    assert duplicate["id"] == first["id"]  # same row
    assert len(backend.sent) == 0  # NO redelivery
    assert session.query(Notification).count() == 1  # NO second row

    lines = _capture(caplog)
    # Must NOT have notification.created
    assert not any("event=notification.created" in line for line in lines), (
        "duplicate must not emit notification.created"
    )
    # Must NOT have delivery events
    assert not any("event=notification.delivery_sent" in line for line in lines), "duplicate must not send email"
