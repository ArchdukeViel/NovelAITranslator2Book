"""Database-backed activity queue implementation.

The legacy file queue remains available only when an explicit test/legacy
storage directory is supplied without a configured database. Production
containers use this backend so claims, leases, and updates are row-locked and
safe across worker processes.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from novelai.config.settings import settings
from novelai.core.platform import JobStatus
from novelai.db.models.activity import ActivityRecord

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _json_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _decode_metadata(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except TypeError, ValueError:
        return {}
    return _json_metadata(decoded)


def _metadata_text(value: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Activity metadata must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > settings.ACTIVITY_METADATA_MAX_BYTES:
        raise ValueError("Activity metadata exceeds the configured size limit")
    return encoded


class ActivityDatabaseBackend:
    """Row-locked database implementation for ``ActivityQueueService``."""

    ACTIVE_STATUSES = {
        JobStatus.PENDING.value,
        JobStatus.RUNNING.value,
        JobStatus.PAUSED.value,
        JobStatus.PAUSED_UNTIL_COOLDOWN.value,
        JobStatus.PAUSED_UNTIL_QUOTA_RESET.value,
    }
    TERMINAL_STATUSES = {
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    }
    LEASE_SECONDS = 300

    def __init__(
        self,
        session_scope_factory: Callable[[], AbstractContextManager[Session]],
        *,
        legacy_queue_file: Path,
    ) -> None:
        self._session_scope_factory = session_scope_factory
        self._legacy_queue_file = legacy_queue_file
        self._stats: dict[str, dict[str, float]] = {}
        self._migrate_legacy_file()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with self._session_scope_factory() as session:
            yield session

    @contextmanager
    def _timed(self, operation: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            entry = self._stats.setdefault(operation, {"count": 0.0, "total_ms": 0.0})
            entry["count"] += 1
            entry["total_ms"] += (time.perf_counter() - started) * 1000

    @classmethod
    def _lease_deadline(cls, now: datetime | None = None) -> datetime:
        return (now or _utc_now()) + timedelta(seconds=cls.LEASE_SECONDS)

    @classmethod
    def _lease_expired(cls, row: ActivityRecord, now: datetime) -> bool:
        expires = row.lease_expires_at
        if expires is not None:
            normalized = expires if expires.tzinfo is not None else expires.replace(tzinfo=UTC)
            return normalized <= now
        started = row.started_at
        if started is None:
            return True
        normalized_started = started if started.tzinfo is not None else started.replace(tzinfo=UTC)
        return normalized_started + timedelta(seconds=cls.LEASE_SECONDS) <= now

    @staticmethod
    def _row_to_dict(row: ActivityRecord) -> dict[str, Any]:
        return {
            "activity_id": row.activity_id,
            "type": row.type,
            "kind": row.kind,
            "novel_id": row.novel_id,
            "source_key": row.source_key,
            "chapters": row.chapters,
            "source_url": row.source_url,
            "provider_key": row.provider_key,
            "provider_model": row.provider_model,
            "status": row.status,
            "created_at": _iso(row.created_at),
            "started_at": _iso(row.started_at),
            "finished_at": _iso(row.finished_at),
            "lease_id": row.lease_id,
            "lease_expires_at": _iso(row.lease_expires_at),
            "retry_count": int(row.retry_count or 0),
            "error": row.error,
            "metadata": _decode_metadata(row.metadata_json),
        }

    @staticmethod
    def _row_values(row: ActivityRecord, activity: dict[str, Any]) -> None:
        row.type = str(activity.get("type") or "")
        row.kind = str(activity.get("kind") or "")
        row.novel_id = str(activity.get("novel_id") or "")
        row.source_key = activity.get("source_key") if isinstance(activity.get("source_key"), str) else None
        row.chapters = activity.get("chapters") if isinstance(activity.get("chapters"), str) else None
        row.source_url = activity.get("source_url") if isinstance(activity.get("source_url"), str) else None
        row.provider_key = activity.get("provider_key") if isinstance(activity.get("provider_key"), str) else None
        row.provider_model = activity.get("provider_model") if isinstance(activity.get("provider_model"), str) else None
        row.status = str(activity.get("status") or JobStatus.PENDING.value)
        row.created_at = _datetime(activity.get("created_at")) or _utc_now()
        row.started_at = _datetime(activity.get("started_at"))
        row.finished_at = _datetime(activity.get("finished_at"))
        row.lease_id = activity.get("lease_id") if isinstance(activity.get("lease_id"), str) else None
        row.lease_expires_at = _datetime(activity.get("lease_expires_at"))
        row.retry_count = int(activity.get("retry_count", 0) or 0)
        row.error = activity.get("error") if isinstance(activity.get("error"), str) else None
        metadata = _json_metadata(activity.get("metadata"))
        row.metadata_json = _metadata_text(metadata)
        row.updated_at = _utc_now()

    def _migrate_legacy_file(self) -> None:
        """Import a legacy queue once without deleting its audit copy."""
        if not self._legacy_queue_file.exists():
            return
        try:
            payload = json.loads(self._legacy_queue_file.read_text(encoding="utf-8"))
            activities = payload if isinstance(payload, list) else []
            if not activities:
                return
            with self._session() as session:
                existing_ids = set(
                    session.scalars(
                        select(ActivityRecord.activity_id).where(
                            ActivityRecord.activity_id.in_([str(item.get("activity_id")) for item in activities])
                        )
                    ).all()
                )
                imported = 0
                for item in activities:
                    if not isinstance(item, dict):
                        continue
                    activity_id = item.get("activity_id")
                    if not isinstance(activity_id, str) or not activity_id or activity_id in existing_ids:
                        continue
                    row = ActivityRecord(activity_id=activity_id)
                    self._row_values(row, item)
                    session.add(row)
                    imported += 1
                if imported:
                    logger.info("Imported %d legacy activity records into the database", imported)
        except Exception as exc:
            logger.warning("Legacy activity queue import deferred (%s)", type(exc).__name__)

    def _load_activity(self) -> list[dict[str, Any]]:
        with self._timed("list"), self._session() as session:
            rows = session.scalars(
                select(ActivityRecord)
                .order_by(ActivityRecord.created_at.desc())
                .limit(settings.ACTIVITY_HISTORY_MAX_ENTRIES)
            ).all()
            return [self._row_to_dict(row) for row in rows]

    def _persist_activity(self, activities: list[dict[str, Any]]) -> None:
        """Replace rows only for explicit legacy/test migration helpers."""
        with self._session() as session:
            session.execute(delete(ActivityRecord))
            for activity in activities:
                activity_id = activity.get("activity_id")
                if not isinstance(activity_id, str) or not activity_id:
                    continue
                row = ActivityRecord(activity_id=activity_id)
                self._row_values(row, activity)
                session.add(row)

    def _new_row(self, activity: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        activity_id = str(activity["activity_id"])
        with self._session() as session:
            if idempotency_key:
                existing = session.scalar(
                    select(ActivityRecord).where(
                        ActivityRecord.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return self._row_to_dict(existing)
            row = ActivityRecord(activity_id=activity_id)
            self._row_values(row, activity)
            row.idempotency_key = idempotency_key[:255] if idempotency_key else None
            session.add(row)
            try:
                session.flush()
            except IntegrityError:
                if not idempotency_key:
                    raise
                # A concurrent request may have won the unique-key insert
                # between the lookup above and this flush. Roll back the
                # losing savepoint, then return the committed winner.
                session.rollback()
                existing = session.scalar(
                    select(ActivityRecord).where(ActivityRecord.idempotency_key == idempotency_key)
                )
                if existing is None:
                    raise
                return self._row_to_dict(existing)
            return self._row_to_dict(row)

    def create_crawl_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        return self._new_row(activity)

    def create_translation_activity(
        self, activity: dict[str, Any], *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self._new_row(activity, idempotency_key=idempotency_key)

    def list_activity(
        self,
        *,
        status: str | None = None,
        activity_type: str | None = None,
        novel_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._timed("list"), self._session() as session:
            stmt = select(ActivityRecord)
            if status is not None:
                stmt = stmt.where(ActivityRecord.status == status)
            if activity_type is not None:
                stmt = stmt.where(ActivityRecord.type == activity_type)
            if novel_id:
                stmt = stmt.where(ActivityRecord.novel_id == novel_id)
            priority = case(
                (ActivityRecord.status == JobStatus.RUNNING.value, 0),
                (
                    ActivityRecord.status.in_(
                        (
                            JobStatus.PAUSED.value,
                            JobStatus.PAUSED_UNTIL_COOLDOWN.value,
                            JobStatus.PAUSED_UNTIL_QUOTA_RESET.value,
                        )
                    ),
                    1,
                ),
                (ActivityRecord.status == JobStatus.PENDING.value, 2),
                (ActivityRecord.status == JobStatus.FAILED.value, 3),
                (ActivityRecord.status == JobStatus.COMPLETED.value, 4),
                (ActivityRecord.status == JobStatus.CANCELLED.value, 5),
                else_=99,
            )
            stmt = stmt.order_by(priority, ActivityRecord.created_at)
            stmt = (
                stmt.limit(max(0, int(limit)))
                if limit is not None
                else stmt.limit(settings.ACTIVITY_HISTORY_MAX_ENTRIES)
            )
            return [self._row_to_dict(row) for row in session.scalars(stmt).all()]

    def get_activity(self, activity_id: str) -> dict[str, Any] | None:
        with self._timed("get"), self._session() as session:
            row = session.get(ActivityRecord, activity_id)
            return self._row_to_dict(row) if row is not None else None

    def delete_activity(self, activity_id: str) -> bool:
        with self._session() as session:
            row = session.get(ActivityRecord, activity_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def _load_locked(self, session: Session, activity_id: str) -> ActivityRecord | None:
        return session.scalar(select(ActivityRecord).where(ActivityRecord.activity_id == activity_id).with_for_update())

    def _recover_expired(self, session: Session) -> None:
        now = _utc_now()
        rows = session.scalars(select(ActivityRecord).where(ActivityRecord.status == JobStatus.RUNNING.value)).all()
        for row in rows:
            if not self._lease_expired(row, now):
                continue
            metadata = _decode_metadata(row.metadata_json)
            metadata["lease_recovered_at"] = _iso(now)
            metadata["current_stage"] = "queued"
            row.status = JobStatus.PENDING.value
            row.started_at = None
            row.lease_id = None
            row.lease_expires_at = None
            row.last_heartbeat_at = None
            row.error = "Recovered expired activity lease"
            row.metadata_json = _metadata_text(metadata)
            row.updated_at = now

    def update_activity_status(
        self,
        activity_id: str,
        status: str,
        *,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
        lease_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._timed("update"), self._session() as session:
            row = self._load_locked(session, activity_id)
            if row is None or (lease_id is not None and row.lease_id != lease_id):
                return None
            now = _utc_now()
            previous = row.status
            row.status = status
            if status == JobStatus.RUNNING.value and previous != JobStatus.RUNNING.value:
                row.started_at = row.started_at or now
                row.claimed_at = row.claimed_at or now
                row.lease_id = row.lease_id or uuid4().hex
                row.lease_expires_at = self._lease_deadline(now)
                row.last_heartbeat_at = now
            if status in self.TERMINAL_STATUSES:
                row.finished_at = now
                row.lease_id = None
                row.lease_expires_at = None
            if status in {
                JobStatus.PAUSED.value,
                JobStatus.PAUSED_UNTIL_COOLDOWN.value,
                JobStatus.PAUSED_UNTIL_QUOTA_RESET.value,
            }:
                row.lease_id = None
                row.lease_expires_at = None
            if status == JobStatus.FAILED.value:
                row.retry_count = int(row.retry_count or 0) + 1
            row.error = error
            if isinstance(metadata, dict):
                current = _decode_metadata(row.metadata_json)
                current.update(metadata)
                row.metadata_json = _metadata_text(current)
            row.updated_at = now
            session.flush()
            return self._row_to_dict(row)

    def update_activity_metadata(self, activity_id: str, patch: dict[str, Any], *, lease_id: str | None = None) -> bool:
        with self._timed("update"), self._session() as session:
            row = self._load_locked(session, activity_id)
            if row is None:
                return False
            if lease_id is not None and row.status == JobStatus.RUNNING.value and row.lease_id != lease_id:
                return False
            current = _decode_metadata(row.metadata_json)
            patch = dict(patch or {})
            if isinstance(patch.get("progress"), dict):
                progress = _json_metadata(current.get("progress"))
                progress.update(patch["progress"])
                patch["progress"] = progress
            current.update(patch)
            row.metadata_json = _metadata_text(current)
            row.updated_at = _utc_now()
            return True

    def retry_activity(self, activity_id: str) -> dict[str, Any] | None:
        with self._timed("update"), self._session() as session:
            row = self._load_locked(session, activity_id)
            if row is None:
                return None
            if row.status not in {JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                raise ValueError(f"Activity cannot be retried from status: {row.status}")
            current = _decode_metadata(row.metadata_json)
            history_value = current.get("retry_history")
            history: list[Any] = list(history_value) if isinstance(history_value, list) else []
            previous = dict(current)
            previous.pop("retry_history", None)
            history.append(
                {
                    "status": row.status,
                    "error": row.error,
                    "finished_at": _iso(row.finished_at),
                    "retry_count": int(row.retry_count or 0),
                    "metadata": previous,
                }
            )
            history = history[-settings.ACTIVITY_RETRY_HISTORY_MAX_ENTRIES :]
            current["retry_history"] = history
            current["current_stage"] = "queued"
            current["current_label"] = None
            current["errors"] = []
            current["paused_reason"] = None
            current["resume_after"] = None
            for key in (
                "failure_code",
                "failure_category",
                "failure_explanation",
                "provider_error",
                "provider_error_code",
                "retry_after_seconds",
                "cooldown_until",
                "exhausted_until",
            ):
                current.pop(key, None)
            row.status = JobStatus.PENDING.value
            row.started_at = None
            row.finished_at = None
            row.lease_id = None
            row.lease_expires_at = None
            row.last_heartbeat_at = None
            row.retry_count = int(row.retry_count or 0) + 1
            row.error = None
            row.metadata_json = _metadata_text(current)
            row.updated_at = _utc_now()
            session.flush()
            return self._row_to_dict(row)

    def next_pending_activity(self, *, activity_type: str | None = None) -> dict[str, Any] | None:
        items = self.list_activity(status=JobStatus.PENDING.value, activity_type=activity_type, limit=1)
        return items[0] if items else None

    def _claim_row(self, row: ActivityRecord, now: datetime) -> dict[str, Any]:
        row.status = JobStatus.RUNNING.value
        row.started_at = row.started_at or now
        row.claimed_at = now
        row.last_heartbeat_at = now
        row.lease_id = uuid4().hex
        row.lease_expires_at = self._lease_deadline(now)
        row.updated_at = now
        return self._row_to_dict(row)

    def claim_activity(self, activity_id: str) -> dict[str, Any] | None:
        with self._timed("claim"), self._session() as session:
            self._recover_expired(session)
            row = self._load_locked(session, activity_id)
            if row is None or row.status != JobStatus.PENDING.value:
                return None
            result = self._claim_row(row, _utc_now())
            session.flush()
            return result

    def claim_next_activity(self, *, activity_type: str | None = None) -> dict[str, Any] | None:
        with self._timed("claim"), self._session() as session:
            self._recover_expired(session)
            session.flush()
            stmt = select(ActivityRecord).where(ActivityRecord.status == JobStatus.PENDING.value)
            if activity_type is not None:
                stmt = stmt.where(ActivityRecord.type == activity_type)
            stmt = stmt.order_by(ActivityRecord.created_at).limit(1).with_for_update(skip_locked=True)
            row = session.scalar(stmt)
            if row is None:
                return None
            result = self._claim_row(row, _utc_now())
            session.flush()
            return result

    def renew_activity_lease(self, activity_id: str, lease_id: str) -> bool:
        with self._timed("heartbeat"), self._session() as session:
            row = self._load_locked(session, activity_id)
            if row is None or row.status != JobStatus.RUNNING.value or row.lease_id != lease_id:
                return False
            now = _utc_now()
            row.lease_expires_at = self._lease_deadline(now)
            row.last_heartbeat_at = now
            row.updated_at = now
            return True

    def find_active_translation(
        self,
        *,
        novel_id: str,
        kind: str,
        chapters: str,
        provider_key: str | None,
        provider_model: str | None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any] | None:
        with self._session() as session:
            stmt = select(ActivityRecord).where(
                ActivityRecord.type == "translation",
                ActivityRecord.status.in_(self.ACTIVE_STATUSES),
            )
            if idempotency_key:
                stmt = stmt.where(ActivityRecord.idempotency_key == idempotency_key)
            else:
                stmt = stmt.where(
                    ActivityRecord.novel_id == novel_id,
                    ActivityRecord.kind == kind,
                    ActivityRecord.chapters == chapters,
                    ActivityRecord.provider_key == provider_key,
                    ActivityRecord.provider_model == provider_model,
                )
            row = session.scalar(stmt.order_by(ActivityRecord.created_at))
            return self._row_to_dict(row) if row is not None else None

    def prune_activity_log(self, *, keep_completed: int, keep_failed: int, dry_run: bool) -> dict[str, Any]:
        with self._session() as session:
            completed = session.scalars(
                select(ActivityRecord)
                .where(ActivityRecord.status == JobStatus.COMPLETED.value)
                .order_by(ActivityRecord.finished_at.desc(), ActivityRecord.created_at.desc())
            ).all()
            failed = session.scalars(
                select(ActivityRecord)
                .where(ActivityRecord.status.in_((JobStatus.FAILED.value, JobStatus.CANCELLED.value)))
                .order_by(ActivityRecord.finished_at.desc(), ActivityRecord.created_at.desc())
            ).all()
            candidates = [*completed[max(0, int(keep_completed)) :], *failed[max(0, int(keep_failed)) :]]
            ids = {row.activity_id for row in candidates}
            if not dry_run and ids:
                session.execute(delete(ActivityRecord).where(ActivityRecord.activity_id.in_(ids)))
            remaining = session.scalar(select(func.count(ActivityRecord.activity_id)))
            return {
                "dry_run": dry_run,
                "deleted": 0 if dry_run else len(ids),
                "candidates": [self._row_to_dict(row) for row in candidates],
                "kept": int(remaining or 0),
            }

    def stats(self) -> dict[str, Any]:
        with self._session() as session:
            pending = session.scalars(
                select(ActivityRecord)
                .where(ActivityRecord.status == JobStatus.PENDING.value)
                .order_by(ActivityRecord.created_at)
                .limit(1)
            ).first()
            queue_age = None
            if pending is not None and pending.created_at is not None:
                created = (
                    pending.created_at
                    if pending.created_at.tzinfo is not None
                    else pending.created_at.replace(tzinfo=UTC)
                )
                queue_age = max(0.0, (_utc_now() - created).total_seconds())
            pending_count = session.scalar(
                select(func.count(ActivityRecord.activity_id)).where(ActivityRecord.status == JobStatus.PENDING.value)
            )
            return {
                "backend": "database",
                "pending_count": int(pending_count or 0),
                "queue_age_seconds": queue_age,
                "operations": {
                    key: {"count": int(value["count"]), "total_ms": round(value["total_ms"], 3)}
                    for key, value in self._stats.items()
                },
            }
