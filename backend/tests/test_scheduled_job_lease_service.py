from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker

from novelai.db.models.system import ScheduledJobLease
from novelai.services.scheduled_job_lease_service import ScheduledJobLeaseService


def test_lease_contention_and_expiry() -> None:
    engine = create_engine("sqlite:///:memory:")
    cast(Table, ScheduledJobLease.__table__).create(engine)
    maker = sessionmaker(bind=engine)

    @contextmanager
    def scope():
        session: Session = maker()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    service = ScheduledJobLeaseService(scope)
    assert service.acquire("backup", "one", 60) is True
    assert service.acquire("backup", "two", 60) is False
    with scope() as session:
        lease = session.get(ScheduledJobLease, "backup")
        assert lease is not None
        lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert service.acquire("backup", "two", 60) is True
    service.release("backup", "two")
    assert service.acquire("backup", "three", 60) is True
