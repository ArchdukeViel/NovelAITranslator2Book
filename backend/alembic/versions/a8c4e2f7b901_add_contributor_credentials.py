"""add contributor credentials and usage ledger

Revision ID: a8c4e2f7b901
Revises: d7e4f9a1c2b3
Create Date: 2026-08-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c4e2f7b901"
down_revision: str | Sequence[str] | None = "d7e4f9a1c2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contributor_credentials",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=255), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last4", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="invalid"),
        sa.Column("validation_status", sa.String(length=32), nullable=False, server_default="unchecked"),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("consent_version", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "provider_key", name="uq_contributor_credentials_owner_provider"),
    )
    op.create_index("ix_contributor_credentials_owner_user_id", "contributor_credentials", ["owner_user_id"])
    op.create_index("ix_contributor_credentials_provider_key", "contributor_credentials", ["provider_key"])
    op.create_index("ix_contributor_credentials_key_fingerprint", "contributor_credentials", ["key_fingerprint"])
    op.create_index("ix_contributor_credentials_status", "contributor_credentials", ["status"])
    op.create_index(
        "ix_contributor_credentials_status_provider",
        "contributor_credentials",
        ["status", "provider_key"],
    )

    op.create_table(
        "contributor_usage_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=64), nullable=False),
        sa.Column("credential_owner_user_id", sa.Integer(), nullable=False),
        sa.Column("requesting_user_id", sa.Integer(), nullable=True),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=255), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("job_id", sa.String(length=255), nullable=True),
        sa.Column("activity_id", sa.String(length=255), nullable=True),
        sa.Column("contribution_mode", sa.String(length=64), nullable=False, server_default="contributor"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contributor_usage_ledger_credential_created",
        "contributor_usage_ledger",
        ["credential_id", "created_at"],
    )
    op.create_index(
        "ix_contributor_usage_ledger_owner_created",
        "contributor_usage_ledger",
        ["credential_owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_contributor_usage_ledger_requesting_created",
        "contributor_usage_ledger",
        ["requesting_user_id", "created_at"],
    )
    op.create_index("ix_contributor_usage_ledger_created_at", "contributor_usage_ledger", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contributor_usage_ledger_created_at", table_name="contributor_usage_ledger")
    op.drop_index("ix_contributor_usage_ledger_requesting_created", table_name="contributor_usage_ledger")
    op.drop_index("ix_contributor_usage_ledger_owner_created", table_name="contributor_usage_ledger")
    op.drop_index("ix_contributor_usage_ledger_credential_created", table_name="contributor_usage_ledger")
    op.drop_table("contributor_usage_ledger")
    op.drop_index("ix_contributor_credentials_status_provider", table_name="contributor_credentials")
    op.drop_index("ix_contributor_credentials_status", table_name="contributor_credentials")
    op.drop_index("ix_contributor_credentials_key_fingerprint", table_name="contributor_credentials")
    op.drop_index("ix_contributor_credentials_provider_key", table_name="contributor_credentials")
    op.drop_index("ix_contributor_credentials_owner_user_id", table_name="contributor_credentials")
    op.drop_table("contributor_credentials")
