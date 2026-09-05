"""Add tuned autovacuum storage parameters for high-churn tables.

Revision ID: 2026-09-05_a1b2c3d4e5f6
Revises: d4e5f6a7b8c9
Create Date: 2026-09-05 00:00:00.000000

Reference: REQ-015 / F-15 (postgres-database-hardening-and-security).
Applies lowered autovacuum scale factors (0.01) to prevent dead-tuple bloat on
high-churn worker queues and lease tracking tables.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only applies to PostgreSQL engines; SQLite ignores or fails on ALTER TABLE ... SET
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE activity_records SET (
                autovacuum_vacuum_scale_factor = 0.01,
                autovacuum_vacuum_threshold = 50,
                autovacuum_vacuum_cost_limit = 2000
            );
            """
        )
        op.execute(
            """
            ALTER TABLE scheduled_job_leases SET (
                autovacuum_vacuum_scale_factor = 0.01,
                autovacuum_vacuum_threshold = 50,
                autovacuum_vacuum_cost_limit = 2000
            );
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE activity_records RESET (
                autovacuum_vacuum_scale_factor,
                autovacuum_vacuum_threshold,
                autovacuum_vacuum_cost_limit
            );
            """
        )
        op.execute(
            """
            ALTER TABLE scheduled_job_leases RESET (
                autovacuum_vacuum_scale_factor,
                autovacuum_vacuum_threshold,
                autovacuum_vacuum_cost_limit
            );
            """
        )
