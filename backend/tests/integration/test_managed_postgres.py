"""Opt-in checks against the hosted PostgreSQL project.

Set ``MANAGED_DATABASE_TEST_URL`` to a privileged psycopg SQLAlchemy URL.
The test uses a unique lease row and removes it before returning.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from novelai.services.scheduled_job_lease_service import ScheduledJobLeaseService


@pytest.fixture(scope="module")
def managed_engine() -> Any:
    database_url = os.environ.get("MANAGED_DATABASE_TEST_URL")
    if not database_url:
        pytest.skip("MANAGED_DATABASE_TEST_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"prepare_threshold": None})
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.integration
def test_managed_postgres_operational_contracts(managed_engine: Any) -> None:
    with managed_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT current_setting('statement_timeout') AS statement_timeout, "
                "current_setting('lock_timeout') AS lock_timeout, "
                "current_setting('idle_in_transaction_session_timeout') AS idle_timeout, "
                "(SELECT version_num FROM public.alembic_version) AS alembic_head"
            )
        ).mappings().one()
        assert row["alembic_head"] == "8b7f3d1a2c4e"
        assert row["statement_timeout"]
        assert row["lock_timeout"]
        assert row["idle_timeout"]
        privileges = connection.execute(
            text(
                "SELECT has_table_privilege('anon', 'public.scheduled_job_leases', "
                "'select,insert,update,delete') AS anon_dml, "
                "has_table_privilege('authenticated', 'public.scheduled_job_leases', "
                "'select,insert,update,delete') AS authenticated_dml"
            )
        ).mappings().one()
        assert privileges == {"anon_dml": False, "authenticated_dml": False}

    managed_engine.dispose()
    with managed_engine.connect() as recovered:
        assert recovered.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.integration
def test_managed_postgres_lease_contention(managed_engine: Any) -> None:
    job_name = f"integration-{uuid.uuid4().hex}"

    @contextmanager
    def session_scope():
        with Session(managed_engine) as session, session.begin():
            yield session

    service = ScheduledJobLeaseService(session_scope)
    try:
        assert service.acquire(job_name, "holder-a", 60) is True
        assert service.acquire(job_name, "holder-b", 60) is False
        assert service.renew(job_name, "holder-a", 60) is True
    finally:
        service.release(job_name, "holder-a")
