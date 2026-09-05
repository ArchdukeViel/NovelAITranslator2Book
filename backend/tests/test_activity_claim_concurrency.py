"""Test verifying ActivityDatabase claim concurrency uses FOR UPDATE SKIP LOCKED.

Reference: REQ-014 / F-14 (postgres-database-hardening-and-security).
Ensures claim_next_activity uses with_for_update(skip_locked=True) for non-blocking worker concurrency.
"""

from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql

from novelai.activity.database import ActivityDatabaseBackend


def test_claim_update_statement_contains_skip_locked() -> None:
    now = datetime.now(UTC)
    stmt = ActivityDatabaseBackend._claim_update_statement(
        now=now,
        lease_id="test-lease-id",
        activity_type="translate",
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in compiled.upper()
