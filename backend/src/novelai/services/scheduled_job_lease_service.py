"""Database-backed leases for cross-instance scheduled work."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from novelai.db.models.system import ScheduledJobLease


class ScheduledJobLeaseService:
    def __init__(self, session_scope_factory: Any) -> None:
        self._session_scope_factory = session_scope_factory

    def acquire(self, job_name: str, holder_id: str, lease_seconds: int) -> bool:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=lease_seconds)
        try:
            with self._session_scope_factory() as session:
                lease = session.execute(
                    select(ScheduledJobLease)
                    .where(ScheduledJobLease.job_name == job_name)
                    .with_for_update()
                ).scalar_one_or_none()
                if lease is None:
                    session.add(
                        ScheduledJobLease(
                            job_name=job_name,
                            holder_id=holder_id,
                            acquired_at=now,
                            heartbeat_at=now,
                            expires_at=expires_at,
                        )
                    )
                    return True
                lease_expires_at = lease.expires_at
                if lease_expires_at.tzinfo is None:
                    lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
                if lease.holder_id != holder_id and lease_expires_at > now:
                    return False
                lease.holder_id = holder_id
                lease.acquired_at = now
                lease.heartbeat_at = now
                lease.expires_at = expires_at
                return True
        except IntegrityError:
            return False

    def renew(self, job_name: str, holder_id: str, lease_seconds: int) -> bool:
        now = datetime.now(UTC)
        with self._session_scope_factory() as session:
            lease = session.get(ScheduledJobLease, job_name)
            if lease is None or lease.holder_id != holder_id:
                return False
            lease_expires_at = lease.expires_at
            if lease_expires_at.tzinfo is None:
                lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
            if lease_expires_at <= now:
                return False
            lease.heartbeat_at = now
            lease.expires_at = now + timedelta(seconds=lease_seconds)
            return True

    def release(self, job_name: str, holder_id: str) -> None:
        with self._session_scope_factory() as session:
            lease = session.get(ScheduledJobLease, job_name)
            if lease is not None and lease.holder_id == holder_id:
                session.delete(lease)
