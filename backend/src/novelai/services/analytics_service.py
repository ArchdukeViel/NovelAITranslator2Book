"""Privacy-safe analytics event recording and summary (DEBT-009).

Supports allowlisted event names, metadata sanitization (drops unsupported keys,
truncates oversized values), DB-backed persistence, admin aggregate summary with
configurable time windows, and failure isolation (recording never fails primary).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from novelai.config.settings import settings
from novelai.db.models.analytics_event import AnalyticsEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event name allowlist (stable, privacy-reviewed)
# ---------------------------------------------------------------------------
ALLOWED_EVENTS: frozenset[str] = frozenset(
    {
        "public_novel.view",
        "public_chapter.view",
        "reader.chapter_next",
        "reader.chapter_previous",
        "search.performed",
        "glossary_annotation.opened",
        "notification.opened",
        "notification.action_clicked",
    }
)

# Per-event maximum metadata values (keys with larger values are truncated).
# Keys not listed here are dropped during sanitization.
# Each entry maps key -> max_str_length.
_ALLOWED_METADATA: dict[str, dict[str, int]] = {
    "public_novel.view": {
        "novel_id": 255,
    },
    "public_chapter.view": {
        "novel_id": 255,
        "chapter_id": 255,
    },
    "reader.chapter_next": {
        "novel_id": 255,
        "chapter_id": 255,
    },
    "reader.chapter_previous": {
        "novel_id": 255,
        "chapter_id": 255,
    },
    "search.performed": {
        "scope": 64,
        "result_count": 16,
        "filter_count": 16,
    },
    "glossary_annotation.opened": {
        "match_type": 32,
        "annotation_count": 16,
    },
    "notification.opened": {
        "event_type": 64,
        "severity": 32,
        "channel": 32,
    },
    "notification.action_clicked": {
        "event_type": 64,
        "severity": 32,
        "channel": 32,
    },
}

_MAX_METADATA_KEYS = 20
_MAX_METADATA_JSON_LENGTH = 4096

_WINDOW_SECONDS: dict[str, int] = {
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}


def sanitize_metadata(event_name: str, raw: dict[str, Any] | None) -> str | None:
    """Sanitize metadata dict for *event_name*.

    - Drops keys not in the per-event allowlist.
    - Truncates string values to the per-key max length.
    - Converts non-string values to strings.
    - Caps total key count.
    - Returns JSON string (or None if empty).
    """
    if not raw:
        return None
    schema = _ALLOWED_METADATA.get(event_name, {})
    cleaned: dict[str, str] = {}
    for key in raw:
        if key not in schema:
            continue
        if len(cleaned) >= _MAX_METADATA_KEYS:
            break
        value = raw[key]
        if value is None:
            continue
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                continue
        max_len = schema[key]
        if max_len > 0 and len(value) > max_len:
            value = value[:max_len]
        cleaned[key] = value
    if not cleaned:
        return None
    result = json.dumps(cleaned, ensure_ascii=False, default=str)
    if len(result) > _MAX_METADATA_JSON_LENGTH:
        result = result[:_MAX_METADATA_JSON_LENGTH]
    return result


def validate_event_name(name: str) -> bool:
    """Return True if *name* is an allowed analytics event."""
    return name in ALLOWED_EVENTS


def record_server_event(event_name: str, **kwargs: Any) -> None:
    """Record trusted workflow event without affecting its primary action."""
    try:
        AnalyticsService().record_event_best_effort(event_name, **kwargs)
    except Exception:
        logger.debug("Analytics server event failed for %s (suppressed)", event_name)


class AnalyticsService:
    """Privacy-safe analytics event recording and summary.

    All recording methods are best-effort: exceptions are logged but never
    propagated to callers.
    """

    def __init__(self) -> None:
        self._enabled: bool = settings.ANALYTICS_ENABLED

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_event(
        self,
        db_session: Session,
        event_name: str,
        *,
        user_id: int | None = None,
        session_id: str | None = None,
        novel_id: str | None = None,
        chapter_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Record a single analytics event (best-effort).

        Returns immediately if analytics are disabled. Logs and suppresses
        exceptions — never raises.
        """
        if not self._enabled:
            return
        if not validate_event_name(event_name):
            logger.debug("Dropped unknown analytics event: %s", event_name)
            return

        try:
            meta_json = sanitize_metadata(event_name, metadata)
            event = AnalyticsEvent(
                event_name=event_name,
                user_id=user_id,
                session_id=_safe_str(session_id, 255),
                novel_id=_safe_str(novel_id, 255),
                chapter_id=_safe_str(chapter_id, 255),
                metadata_json=meta_json,
                created_at=created_at or datetime.now(UTC),
            )
            db_session.add(event)
            db_session.flush()
        except Exception:
            logger.debug("Analytics record_event failed for %s (suppressed)", event_name)

    def record_event_best_effort(
        self,
        event_name: str,
        **kwargs: Any,
    ) -> None:
        """Record an event in an isolated transaction without affecting caller work."""
        if not self._enabled:
            return
        try:
            from novelai.db.engine import session_scope

            with session_scope() as db_session:
                self.record_event(db_session, event_name, **kwargs)
        except Exception:
            logger.debug("Analytics isolated record failed for %s (suppressed)", event_name)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(
        self,
        db_session: Session,
        window: str = "24h",
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Return aggregate analytics summary for *window*.

        Returns empty groups for unknown/unavailable events rather than
        failing. Partial failure returns available groups.
        """
        try:
            output_timezone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unsupported timezone: {timezone!r}") from exc
        cutoff = _window_cutoff(window)
        if cutoff is None:
            raise ValueError(f"Unsupported window: {window!r}")

        generated_at = _format_timestamp(datetime.now(UTC), output_timezone)

        groups: dict[str, Any] = {}
        failures: list[str] = []

        # Views
        try:
            groups["views"] = self._count_events(db_session, ALLOWED_EVENTS_VIEWS, cutoff)
        except Exception as exc:
            logger.warning("Analytics summary views failed: %s", exc)
            groups["views"] = _empty_counts(ALLOWED_EVENTS_VIEWS)
            failures.append("views")

        # Search
        try:
            groups["search"] = self._count_events(db_session, ALLOWED_EVENTS_SEARCH, cutoff)
        except Exception as exc:
            logger.warning("Analytics summary search failed: %s", exc)
            groups["search"] = _empty_counts(ALLOWED_EVENTS_SEARCH)
            failures.append("search")

        # Features (glossary, notification)
        try:
            groups["features"] = self._count_events(db_session, ALLOWED_EVENTS_FEATURES, cutoff)
        except Exception as exc:
            logger.warning("Analytics summary features failed: %s", exc)
            groups["features"] = _empty_counts(ALLOWED_EVENTS_FEATURES)
            failures.append("features")

        # Top novels by views
        try:
            groups["top_novels"] = self._top_novels(db_session, ALLOWED_EVENTS_VIEWS, cutoff, limit=20)
        except Exception as exc:
            logger.warning("Analytics summary top_novels failed: %s", exc)
            groups["top_novels"] = []

        status = "ok" if not failures else ("partial" if len(failures) < 4 else "unavailable")

        return {
            "enabled": self._enabled,
            "window": window,
            "timezone": timezone,
            "generated_at": generated_at,
            "cutoff_at": _format_timestamp(cutoff, output_timezone) if cutoff else None,
            "status": status,
            "groups": groups,
            "failed_groups": failures,
        }

    def _count_events(
        self,
        db_session: Session,
        event_names: Sequence[str],
        cutoff: datetime,
    ) -> dict[str, int]:
        """Return dict of event_name -> count within window."""
        if not event_names:
            return {}
        rows = (
            db_session.query(AnalyticsEvent.event_name, sa_func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.event_name.in_(event_names))
            .filter(AnalyticsEvent.created_at >= cutoff)
            .group_by(AnalyticsEvent.event_name)
            .all()
        )
        counts: dict[str, int] = {name: 0 for name in event_names}
        for name, count in rows:
            counts[name] = count
        return counts

    def _top_novels(
        self,
        db_session: Session,
        event_names: Sequence[str],
        cutoff: datetime,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return top novels by view events within window."""
        if not event_names:
            return []
        rows = (
            db_session.query(
                AnalyticsEvent.novel_id,
                sa_func.count(AnalyticsEvent.id).label("views"),
            )
            .filter(AnalyticsEvent.event_name.in_(event_names))
            .filter(AnalyticsEvent.novel_id.isnot(None))
            .filter(AnalyticsEvent.created_at >= cutoff)
            .group_by(AnalyticsEvent.novel_id)
            .order_by(sa_func.count(AnalyticsEvent.id).desc())
            .limit(limit)
            .all()
        )
        return [{"novel_id": row.novel_id, "views": row.views} for row in rows if row.novel_id]

    def cleanup_old_events(
        self,
        db_session: Session | None = None,
        *,
        ttl_days: int,
        batch_size: int | None = None,
    ) -> int:
        """Delete expired events in bounded batches. Returns deleted row count."""
        batch_size = batch_size or settings.ANALYTICS_RETENTION_BATCH_SIZE
        cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
        if db_session is not None:
            return self._cleanup_old_events_batch(db_session, cutoff, batch_size)
        try:
            from novelai.db.engine import session_scope

            deleted = 0
            while True:
                with session_scope() as session:
                    batch = self._cleanup_old_events_batch(session, cutoff, batch_size)
                deleted += batch
                if batch < batch_size:
                    return deleted
        except Exception:
            logger.warning("Analytics cleanup failed")
            return 0

    @staticmethod
    def _cleanup_old_events_batch(db_session: Session, cutoff: datetime, batch_size: int) -> int:
        event_ids = db_session.scalars(
            select(AnalyticsEvent.id)
            .where(AnalyticsEvent.created_at < cutoff)
            .order_by(AnalyticsEvent.id)
            .limit(batch_size)
        ).all()
        if not event_ids:
            return 0
        db_session.execute(delete(AnalyticsEvent).where(AnalyticsEvent.id.in_(event_ids)))
        db_session.flush()
        return len(event_ids)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

ALLOWED_EVENTS_VIEWS: tuple[str, ...] = (
    "public_novel.view",
    "public_chapter.view",
)
ALLOWED_EVENTS_SEARCH: tuple[str, ...] = ("search.performed",)
ALLOWED_EVENTS_FEATURES: tuple[str, ...] = (
    "glossary_annotation.opened",
    "notification.opened",
    "notification.action_clicked",
)


def _window_cutoff(window: str) -> datetime | None:
    seconds = _WINDOW_SECONDS.get(window)
    if seconds is None:
        return None
    return datetime.now(UTC) - timedelta(seconds=seconds)


def _empty_counts(names: Sequence[str]) -> dict[str, int]:
    return {name: 0 for name in names}


def _safe_str(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _format_timestamp(value: datetime, timezone: ZoneInfo) -> str:
    return value.astimezone(timezone).isoformat().replace("+00:00", "Z")
