"""add audit log canonical filter columns

Revision ID: a4d8b6c2f1e3
Revises: d8a2f6c1e9b4
Create Date: 2026-07-27 12:00:00.000000

DEBT-054 / admin-audit-log-viewer.

Adds nullable canonical columns to ``audit_logs`` so the viewer can index/filter
on owner-relevant attributes without forcing producers to fork ``metadata_json``:

* ``status``      — completed outcome (succeeded | failed | denied | partial | unknown)
* ``severity``    — operational impact (info | warning | critical)
* ``request_id``  — inbound request correlation id (exact match filter)
* ``correlation_id`` — cross-process correlation id (exact match filter)

All columns are NULL-tolerant so existing rows remain valid and legacy writers
that only fill ``metadata_json`` continue to function. Indexes are added only
for fields the viewer filters on directly: ``status``, ``request_id``,
``correlation_id`` (``actor_user_id`` and ``action`` are already indexed).
``severity`` has no high-cardinality index because it is filtered together with
status in practice.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4d8b6c2f1e3"
down_revision: str | Sequence[str] | None = "d8a2f6c1e9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add canonical viewer filter columns to ``audit_logs``."""
    op.add_column(
        "audit_logs",
        sa.Column("status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("severity", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("request_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_audit_logs_status"),
        "audit_logs",
        ["status"],
    )
    op.create_index(
        op.f("ix_audit_logs_request_id"),
        "audit_logs",
        ["request_id"],
    )
    op.create_index(
        op.f("ix_audit_logs_correlation_id"),
        "audit_logs",
        ["correlation_id"],
    )


def downgrade() -> None:
    """Drop canonical viewer filter columns and their indexes."""
    op.drop_index(op.f("ix_audit_logs_correlation_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_request_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_status"), table_name="audit_logs")
    op.drop_column("audit_logs", "correlation_id")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "severity")
    op.drop_column("audit_logs", "status")
