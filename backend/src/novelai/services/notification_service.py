"""Pluggable notification service with a configurable backend.

Default: ``NoopNotificationBackend`` logs at INFO level.
In production, swap to an SMTP backend by providing ``SMTP_*`` settings.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from novelai.config.settings import settings
from novelai.db.models.notification import Notification, NotificationDelivery, NotificationPreference
from novelai.db.models.users import User

logger = logging.getLogger(__name__)


_EVENT_TYPES = frozenset({"translation.completed", "translation.failed", "translation.requires_review"})
_SEVERITIES = frozenset({"info", "success", "warning", "error"})
_CHANNELS = frozenset({"in_app", "email"})
# Allowlist of safe delivery statuses used in structured delivery logs.
# Never log raw exception text; emit only this bounded enum.
_DELIVERY_STATUSES = frozenset({"sent", "failed", "skipped_preferences", "skipped_no_address", "skipped_disabled"})
_ALLOWED_LOG_KEYS = frozenset({"recipient_user_id", "event_type", "channel", "status", "error_category"})
_SOURCE_REF = re.compile(r"^[A-Za-z0-9._:-]+$")
_MAX_TITLE_LENGTH = 255
_MAX_BODY_LENGTH = 4_000
_MAX_DEDUPE_KEY_LENGTH = 255
_MAX_PAGE_SIZE = 100


def _emit_event(event: str, **fields: object) -> None:
    """Emit one structured observability event.

    Only allowlisted identifiers and bounded enum values are forwarded. No
    title/body/email/address/error text/action URL/secrets/private payload
    ever reach the log stream.
    """
    safe = {k: v for k, v in fields.items() if k in _ALLOWED_LOG_KEYS}
    if "status" in safe and safe["status"] not in _DELIVERY_STATUSES:
        safe.pop("status")
    if "channel" in safe and safe["channel"] not in _CHANNELS:
        safe.pop("channel")
    logger.info("event=%s %s", event, " ".join(f"{k}={v}" for k, v in sorted(safe.items())))


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------


class NotificationBackend(Protocol):
    """Minimal notification contract.

    Implementations must handle their own batching, rate-limiting, and
    credential management.
    """

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        """Deliver a notification."""


# ---------------------------------------------------------------------------
# Noop backend  (default)
# ---------------------------------------------------------------------------


class NoopNotificationBackend:
    """Default backend: log at INFO.

    Records the notification to the application log.  Replace with a
    real SMTP/HTTP backend when production credentials are configured.
    """

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        logger.info("Notification dispatched (noop backend)")


# ---------------------------------------------------------------------------
# SMTP backend   (used only when SMTP_HOST is set)
# ---------------------------------------------------------------------------


class SmtpNotificationBackend:
    """SMTP-based delivery backend.

    Reads SMTP_* settings at send-time so environment changes take effect
    without a restart.

    ponytail: No queue or retry. Add a durable delivery queue when production
    volume requires retry and dead-letter handling.
    """

    def __init__(self) -> None:
        host = settings.SMTP_HOST
        if not host:
            raise ValueError("SMTP_HOST is not configured")
        self._host: str = host
        self._port = settings.SMTP_PORT
        self._username = settings.SMTP_USERNAME
        pwd_secret = settings.SMTP_PASSWORD
        self._password: str | None = pwd_secret.get_secret_value() if pwd_secret else None  # type: ignore[reportConstantRedefinition]
        self._from_addr = settings.SMTP_FROM_ADDRESS
        self._use_ssl = settings.SMTP_USE_SSL
        self._starttls = settings.SMTP_STARTTLS
        self._timeout = settings.SMTP_TIMEOUT_SECONDS

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        import smtplib
        from email.message import EmailMessage

        to = recipient or self._from_addr
        msg = EmailMessage()
        msg.set_content(message)
        msg["Subject"] = subject
        msg["From"] = self._from_addr
        msg["To"] = to

        smtp_class = smtplib.SMTP_SSL if self._use_ssl else smtplib.SMTP
        with smtp_class(self._host, self._port, timeout=self._timeout) as smtp:
            if self._starttls and not self._use_ssl:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)

        logger.info("SMTP notification sent")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _detect_backend() -> NotificationBackend:
    """Return ``SmtpNotificationBackend`` if SMTP is configured, else noop."""
    if settings.SMTP_HOST and settings.SMTP_PORT:
        return SmtpNotificationBackend()
    return NoopNotificationBackend()


class NotificationService:
    """High-level notification dispatcher.

    Usage::

        svc = NotificationService()
        svc.notify("Backup failed", "…", recipient="admin@…")
    """

    def __init__(self, backend: NotificationBackend | None = None, *, db_session: Session | None = None) -> None:
        self._backend = backend if backend is not None else _detect_backend()
        self._persistence = (
            NotificationPersistenceService(db_session, self._backend) if db_session is not None else None
        )

    def notify(self, subject: str, message: str, recipient: str | None = None) -> None:
        """Send a notification through the configured back-end."""
        self._backend.send(subject, message, recipient)

    def persistence(self) -> NotificationPersistenceService:
        """Return configured notification persistence boundary."""
        if self._persistence is None:
            raise RuntimeError("NotificationService requires db_session for persistence")
        return self._persistence


class NotificationPersistenceService:
    """Recipient-scoped durable notifications and optional email delivery."""

    def __init__(self, db_session: Session, backend: NotificationBackend) -> None:
        self._db = db_session
        self._backend = backend

    def create(
        self,
        *,
        recipient_user_id: int,
        event_type: str,
        title: str,
        body: str,
        severity: str,
        dedupe_key: str,
        action_url: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, object] | None:
        """Create one safe in-app notification; duplicate keys return existing row."""
        self._validate_create(
            event_type=event_type,
            title=title,
            body=body,
            severity=severity,
            dedupe_key=dedupe_key,
            action_url=action_url,
            source_type=source_type,
            source_id=source_id,
        )
        recipient = self._db.get(User, recipient_user_id)
        if recipient is None or not recipient.is_active:
            raise ValueError("recipient is not active")
        if not self._enabled(recipient_user_id, event_type, "in_app"):
            _emit_event(
                "notification.skipped_preferences",
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                channel="in_app",
                status="skipped_preferences",
            )
            return None
        notification = Notification(
            recipient_user_id=recipient_user_id,
            event_type=event_type,
            title=title,
            body=body,
            severity=severity,
            action_url=action_url,
            source_type=source_type,
            source_id=source_id,
            dedupe_key=dedupe_key,
        )
        try:
            with self._db.begin_nested():
                self._db.add(notification)
                self._db.flush()
        except IntegrityError:
            existing = self._db.scalar(
                select(Notification).where(
                    Notification.recipient_user_id == recipient_user_id,
                    Notification.dedupe_key == dedupe_key,
                )
            )
            if existing is None:  # pragma: no cover - concurrent transaction retry boundary
                raise
            return self._safe_notification(existing)
        else:
            self._db.commit()
            _emit_event(
                "notification.created",
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                channel="in_app",
            )
            try:
                self._deliver_email(notification, recipient)
            except Exception:
                logger.warning(
                    "Email delivery failed for notification %s",
                    notification.id,
                )
            return self._safe_notification(notification)

    def get_preferences(self, *, requesting_user_id: int) -> list[dict[str, object]]:
        stored = {
            (preference.event_type, preference.channel): preference.enabled
            for preference in self._db.scalars(
                select(NotificationPreference).where(NotificationPreference.user_id == requesting_user_id)
            )
        }
        return [
            {
                "event_type": event_type,
                "channel": channel,
                "enabled": stored.get((event_type, channel), channel == "in_app"),
            }
            for event_type in sorted(_EVENT_TYPES)
            for channel in ("in_app", "email")
        ]

    def update_preference(
        self, *, requesting_user_id: int, event_type: str, channel: str, enabled: bool
    ) -> dict[str, object]:
        self._validate_preference(event_type, channel)
        preference = self._db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id == requesting_user_id,
                NotificationPreference.event_type == event_type,
                NotificationPreference.channel == channel,
            )
        )
        if preference is None:
            preference = NotificationPreference(
                user_id=requesting_user_id, event_type=event_type, channel=channel, enabled=enabled
            )
            self._db.add(preference)
        else:
            preference.enabled = enabled
        self._db.commit()
        _emit_event(
            "notification.preferences_updated",
            recipient_user_id=requesting_user_id,
            event_type=event_type,
            channel=channel,
        )
        return {"event_type": event_type, "channel": channel, "enabled": enabled}

    def list(
        self,
        *,
        requesting_user_id: int,
        page: int = 1,
        page_size: int = 25,
        status: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        if page < 1 or not 1 <= page_size <= _MAX_PAGE_SIZE:
            raise ValueError("invalid pagination")
        if status is not None and status not in {"unread", "read", "archived"}:
            raise ValueError("invalid status")
        if event_type is not None and event_type not in _EVENT_TYPES:
            raise ValueError("invalid event_type")
        filters = [Notification.recipient_user_id == requesting_user_id]
        if status is not None:
            filters.append(Notification.status == status)
        if event_type is not None:
            filters.append(Notification.event_type == event_type)
        total = self._db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
        rows = self._db.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [self._safe_notification(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def unread_count(self, *, requesting_user_id: int) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.recipient_user_id == requesting_user_id, Notification.status == "unread")
            )
            or 0
        )

    def get(self, *, requesting_user_id: int, notification_id: int) -> dict[str, object] | None:
        """Return one recipient-owned notification without exposing ownership."""
        notification = self._owned_notification(requesting_user_id, notification_id)
        return self._safe_notification(notification) if notification is not None else None

    def mark_read(self, *, requesting_user_id: int, notification_id: int) -> bool:
        notification = self._owned_notification(requesting_user_id, notification_id)
        if notification is None or notification.status == "archived":
            return False
        if notification.status == "unread":
            notification.status = "read"
            notification.read_at = datetime.now(UTC)
            self._db.commit()
        return True

    def mark_all_read(self, *, requesting_user_id: int) -> int:
        rows = self._db.scalars(
            select(Notification).where(
                Notification.recipient_user_id == requesting_user_id, Notification.status == "unread"
            )
        ).all()
        now = datetime.now(UTC)
        for notification in rows:
            notification.status = "read"
            notification.read_at = now
        if rows:
            self._db.commit()
        return len(rows)

    def archive(self, *, requesting_user_id: int, notification_id: int) -> bool:
        notification = self._owned_notification(requesting_user_id, notification_id)
        if notification is None:
            return False
        if notification.status != "archived":
            now = datetime.now(UTC)
            notification.status = "archived"
            notification.archived_at = now
            notification.read_at = notification.read_at or now
            self._db.commit()
        return True

    def cleanup_retention(self, *, older_than_days: int, batch_size: int = 500) -> int:
        if older_than_days < 1 or not 1 <= batch_size <= 1_000:
            raise ValueError("invalid retention bounds")
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        notification_ids = self._db.scalars(
            select(Notification.id)
            .where(Notification.created_at < cutoff, Notification.status == "archived")
            .order_by(Notification.id)
            .limit(batch_size)
        ).all()
        if notification_ids:
            self._db.execute(delete(Notification).where(Notification.id.in_(notification_ids)))
            self._db.commit()
        return len(notification_ids)

    def _enabled(self, user_id: int, event_type: str, channel: str) -> bool:
        enabled = self._db.scalar(
            select(NotificationPreference.enabled).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type,
                NotificationPreference.channel == channel,
            )
        )
        return channel == "in_app" if enabled is None else enabled

    def _deliver_email(self, notification: Notification, recipient: User) -> None:
        # ponytail: delivery is synchronous; no durable queue. When a worker-backed
        # queue is introduced, emit notification.delivery_queued here with the
        # allowlisted identifiers below and consume it from the worker.
        if not self._enabled(recipient.id, notification.event_type, "email"):
            self._record_delivery(notification.id, "skipped_preferences")
            return
        if not recipient.email_verified_at:
            self._record_delivery(notification.id, "skipped_no_address")
            return
        if isinstance(self._backend, NoopNotificationBackend):
            self._record_delivery(notification.id, "skipped_disabled")
            return
        try:
            self._backend.send(notification.title, notification.body, recipient.email)
        except Exception:  # delivery failure must not discard in-app notification
            _emit_event(
                "notification.delivery_failed",
                recipient_user_id=recipient.id,
                event_type=notification.event_type,
                channel="email",
                status="failed",
                error_category="delivery_failed",
            )
            self._record_delivery(notification.id, "failed", error_category="delivery_failed")
            return
        self._record_delivery(notification.id, "sent")
        _emit_event(
            "notification.delivery_sent",
            recipient_user_id=recipient.id,
            event_type=notification.event_type,
            channel="email",
            status="sent",
        )

    def _record_delivery(self, notification_id: int, status: str, error_category: str | None = None) -> None:
        now = datetime.now(UTC)
        self._db.add(
            NotificationDelivery(
                notification_id=notification_id,
                channel="email",
                status=status,
                attempt_count=1 if status in {"sent", "failed"} else 0,
                sent_at=now if status == "sent" else None,
                failed_at=now if status == "failed" else None,
                error_category=error_category,
            )
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            logger.warning("Failed to persist delivery record")

    def _owned_notification(self, user_id: int, notification_id: int) -> Notification | None:
        return self._db.scalar(
            select(Notification).where(Notification.id == notification_id, Notification.recipient_user_id == user_id)
        )

    @staticmethod
    def _safe_notification(notification: Notification) -> dict[str, object]:
        return {
            "id": notification.id,
            "event_type": notification.event_type,
            "title": notification.title,
            "body": notification.body,
            "severity": notification.severity,
            "status": notification.status,
            "action_url": notification.action_url,
            "created_at": notification.created_at,
            "read_at": notification.read_at,
        }

    @staticmethod
    def _validate_create(**values: str | None) -> None:
        if values["event_type"] not in _EVENT_TYPES or values["severity"] not in _SEVERITIES:
            raise ValueError("unsupported notification type")
        for key, maximum in (
            ("title", _MAX_TITLE_LENGTH),
            ("body", _MAX_BODY_LENGTH),
            ("dedupe_key", _MAX_DEDUPE_KEY_LENGTH),
        ):
            value = values[key]
            if not value or len(value) > maximum:
                raise ValueError(f"invalid {key}")
        action_url = values["action_url"]
        if action_url is not None and (
            len(action_url) > 2048 or not action_url.startswith("/") or action_url.startswith("//")
        ):
            raise ValueError("action_url must be an internal path")
        source_type, source_id = values["source_type"], values["source_id"]
        if (
            bool(source_type) != bool(source_id)
            or (source_type is not None and (len(source_type) > 64 or not _SOURCE_REF.fullmatch(source_type)))
            or (source_id is not None and (len(source_id) > 255 or not _SOURCE_REF.fullmatch(source_id)))
        ):
            raise ValueError("invalid source reference")

    @staticmethod
    def _validate_preference(event_type: str, channel: str) -> None:
        if event_type not in _EVENT_TYPES or channel not in _CHANNELS:
            raise ValueError("unsupported notification preference")


# ---------------------------------------------------------------------------
# Event bus (DEBT-009): typed publish/subscribe for cross-component alerts.
# ---------------------------------------------------------------------------

# Default operator recipient when no override is supplied.
_DEFAULT_RECIPIENT: str | None = None


def set_default_recipient(email: str | None) -> None:
    """Override the default email recipient used by ``publish``."""
    global _DEFAULT_RECIPIENT
    _DEFAULT_RECIPIENT = email


_KNOWN_EVENTS: tuple[str, ...] = (
    "backup.failed",
    "backup.succeeded",
    "crawl.failed",
    "translation.failed",
    "scheduler.stale",
)


class NotificationEventBus:
    """In-process pub/sub for notification triggering (DEBT-009).

    Subscribers receive a typed event payload (str subject, str message, str
    recipient). The bus never raises into the publisher — subscribers that
    throw are logged and discarded, so a misbehaving channel cannot break
    the producer. This is a best-effort fan-out, not durable.
    """

    def __init__(self, service: NotificationService | None = None) -> None:
        self._service = service or NotificationService()
        self._subscribers: dict[str, list] = {}

    def subscribe(self, event_type: str, callback) -> None:
        """Register ``callback(event_type, subject, message, recipient)``."""
        if event_type not in _KNOWN_EVENTS:
            raise ValueError(f"Unknown event_type: {event_type!r}")
        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback) -> None:
        bucket = self._subscribers.get(event_type, [])
        if callback in bucket:
            bucket.remove(callback)

    def publish(
        self,
        event_type: str,
        *,
        subject: str,
        message: str,
        recipient: str | None = None,
    ) -> None:
        """Fan out the event to subscribers, falling back to the default backend."""
        if event_type not in _KNOWN_EVENTS:
            logger.warning("publish ignored unknown event_type=%s", event_type)
            return
        effective_recipient = recipient or _DEFAULT_RECIPIENT
        for callback in list(self._subscribers.get(event_type, [])):
            try:
                callback(event_type, subject, message, effective_recipient)
            except Exception as exc:  # pragma: no cover - subscriber resilience
                logger.warning("Subscriber for %s raised %s", event_type, exc.__class__.__name__)
        self._service.notify(subject, message, effective_recipient)


_default_bus: NotificationEventBus | None = None


def get_event_bus() -> NotificationEventBus:
    """Return the process-wide ``NotificationEventBus`` singleton."""
    global _default_bus
    if _default_bus is None:
        _default_bus = NotificationEventBus()
    return _default_bus


def reset_event_bus() -> None:
    """Drop the singleton so tests can swap subscribers (private seam)."""
    global _default_bus
    _default_bus = None
