"""unify owner and contributor provider credentials

Revision ID: d4e6f8a2b1c3
Revises: c9d1e3f5a7b9
Create Date: 2026-08-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6f8a2b1c3"
down_revision: str | Sequence[str] | None = "c9d1e3f5a7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _provider_table() -> sa.TableClause:
    return sa.table(
        "provider_credentials",
        sa.column("id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("label", sa.String()),
        sa.column("encrypted_api_key", sa.Text()),
        sa.column("key_fingerprint", sa.String()),
        sa.column("last4", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("status", sa.String()),
        sa.column("validation_status", sa.String()),
        sa.column("validation_message", sa.Text()),
        sa.column("notes", sa.Text()),
        sa.column("model", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("last_validated_at", sa.DateTime(timezone=True)),
        sa.column("credential_owner_user_id", sa.Integer()),
        sa.column("source", sa.String()),
        sa.column("owner_job_eligible", sa.Boolean()),
        sa.column("contributor_pool_eligible", sa.Boolean()),
        sa.column("consent_version", sa.String()),
        sa.column("consent_at", sa.DateTime(timezone=True)),
        sa.column("consent_revoked_at", sa.DateTime(timezone=True)),
        sa.column("failure_count", sa.Integer()),
        sa.column("last_used_at", sa.DateTime(timezone=True)),
        sa.column("last_failure_at", sa.DateTime(timezone=True)),
        sa.column("revoked_at", sa.DateTime(timezone=True)),
    )


def _contributor_table() -> sa.TableClause:
    return sa.table(
        "contributor_credentials",
        sa.column("id", sa.String()),
        sa.column("owner_user_id", sa.Integer()),
        sa.column("provider_key", sa.String()),
        sa.column("provider_model", sa.String()),
        sa.column("encrypted_api_key", sa.Text()),
        sa.column("key_fingerprint", sa.String()),
        sa.column("last4", sa.String()),
        sa.column("status", sa.String()),
        sa.column("validation_status", sa.String()),
        sa.column("validation_message", sa.Text()),
        sa.column("consent_version", sa.String()),
        sa.column("failure_count", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("last_validated_at", sa.DateTime(timezone=True)),
        sa.column("last_used_at", sa.DateTime(timezone=True)),
        sa.column("last_failure_at", sa.DateTime(timezone=True)),
        sa.column("revoked_at", sa.DateTime(timezone=True)),
    )


def _ledger_table() -> sa.TableClause:
    return sa.table(
        "contributor_usage_ledger",
        sa.column("credential_id", sa.String()),
    )


def _copy_contributor_rows(connection: sa.Connection) -> None:
    provider = _provider_table()
    contributor = _contributor_table()
    ledger = _ledger_table()
    rows = connection.execute(sa.select(*contributor.c)).mappings().all()
    for row in rows:
        old_id = str(row["id"])
        result = connection.execute(
            provider.insert()
            .values(
                provider=row["provider_key"],
                label="User contributor Gemini",
                encrypted_api_key=row["encrypted_api_key"],
                key_fingerprint=row["key_fingerprint"],
                last4=row["last4"],
                is_active=row["status"] == "active",
                status=row["status"] if row["status"] in {"active", "paused", "invalid", "revoked"} else "invalid",
                validation_status=row["validation_status"],
                validation_message=row["validation_message"],
                notes=None,
                model=row["provider_model"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_validated_at=row["last_validated_at"],
                credential_owner_user_id=row["owner_user_id"],
                source="user_contribution",
                owner_job_eligible=False,
                contributor_pool_eligible=row["status"] == "active" and row["validation_status"] == "valid",
                consent_version=row["consent_version"],
                consent_at=row["created_at"],
                consent_revoked_at=None,
                failure_count=row["failure_count"] or 0,
                last_used_at=row["last_used_at"],
                last_failure_at=row["last_failure_at"],
                revoked_at=row["revoked_at"],
            )
            .returning(provider.c.id)
        )
        new_id = result.scalar_one()
        connection.execute(ledger.update().where(ledger.c.credential_id == old_id).values(credential_id=str(new_id)))


def upgrade() -> None:
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_constraint("uq_provider_credentials_provider", type_="unique")
        batch.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
        batch.add_column(sa.Column("credential_owner_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source", sa.String(length=32), nullable=False, server_default="owner_admin"))
        batch.add_column(sa.Column("owner_job_eligible", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(
            sa.Column("contributor_pool_eligible", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("consent_version", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("consent_revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_provider_credentials_owner_user",
            "users",
            ["credential_owner_user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_index(
        "ix_provider_credentials_credential_owner_user_id",
        "provider_credentials",
        ["credential_owner_user_id"],
    )
    op.create_index("ix_provider_credentials_status", "provider_credentials", ["status"])
    op.create_index(
        "ix_provider_credentials_owner_provider",
        "provider_credentials",
        ["credential_owner_user_id", "provider"],
    )
    op.create_index(
        "ix_provider_credentials_pool_status",
        "provider_credentials",
        ["provider", "contributor_pool_eligible", "status", "last_used_at"],
    )

    connection = op.get_bind()
    provider = _provider_table()
    users = sa.table("users", sa.column("id", sa.Integer()), sa.column("role", sa.String()))
    owner_id = connection.execute(sa.select(users.c.id).where(users.c.role == "owner").order_by(users.c.id)).scalar()
    provider_rows = connection.execute(sa.select(provider.c.id, provider.c.is_active)).mappings().all()
    for row in provider_rows:
        connection.execute(
            provider.update()
            .where(provider.c.id == row["id"])
            .values(
                status="active" if row["is_active"] else "paused",
                source="owner_legacy",
                owner_job_eligible=True,
                contributor_pool_eligible=False,
                credential_owner_user_id=owner_id,
                failure_count=0,
            )
        )
    _copy_contributor_rows(connection)

    with op.batch_alter_table("contributor_usage_ledger") as batch:
        batch.alter_column(
            "credential_owner_user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    for index_name in (
        "ix_contributor_credentials_status_provider",
        "ix_contributor_credentials_status",
        "ix_contributor_credentials_key_fingerprint",
        "ix_contributor_credentials_provider_key",
        "ix_contributor_credentials_owner_user_id",
    ):
        op.drop_index(index_name, table_name="contributor_credentials")
    op.drop_table("contributor_credentials")


def downgrade() -> None:
    connection = op.get_bind()
    provider = _provider_table()
    contributor = _contributor_table()
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
    for index_name, columns in (
        ("ix_contributor_credentials_owner_user_id", ["owner_user_id"]),
        ("ix_contributor_credentials_provider_key", ["provider_key"]),
        ("ix_contributor_credentials_key_fingerprint", ["key_fingerprint"]),
        ("ix_contributor_credentials_status", ["status"]),
        ("ix_contributor_credentials_status_provider", ["status", "provider_key"]),
    ):
        op.create_index(index_name, "contributor_credentials", columns)

    rows = connection.execute(sa.select(*provider.c).where(provider.c.source == "user_contribution")).mappings().all()
    for row in rows:
        old_id = uuid4().hex
        connection.execute(
            contributor.insert().values(
                id=old_id,
                owner_user_id=row["credential_owner_user_id"],
                provider_key=row["provider"],
                provider_model=row["model"] or "gemini-3.5-flash-lite",
                encrypted_api_key=row["encrypted_api_key"],
                key_fingerprint=row["key_fingerprint"],
                last4=row["last4"],
                status=row["status"],
                validation_status=row["validation_status"],
                validation_message=row["validation_message"],
                consent_version=row["consent_version"] or "legacy",
                failure_count=row["failure_count"] or 0,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_validated_at=row["last_validated_at"],
                last_used_at=row["last_used_at"],
                last_failure_at=row["last_failure_at"],
                revoked_at=row["revoked_at"],
            )
        )
        connection.execute(
            sa.table("contributor_usage_ledger", sa.column("credential_id", sa.String()))
            .update()
            .where(sa.column("credential_id", sa.String()) == str(row["id"]))
            .values(credential_id=old_id)
        )
    connection.execute(provider.delete().where(provider.c.source == "user_contribution"))

    for index_name in (
        "ix_provider_credentials_pool_status",
        "ix_provider_credentials_owner_provider",
        "ix_provider_credentials_status",
        "ix_provider_credentials_credential_owner_user_id",
    ):
        op.drop_index(index_name, table_name="provider_credentials")
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_constraint("fk_provider_credentials_owner_user", type_="foreignkey")
        for column in (
            "revoked_at",
            "last_failure_at",
            "last_used_at",
            "failure_count",
            "consent_revoked_at",
            "consent_at",
            "consent_version",
            "contributor_pool_eligible",
            "owner_job_eligible",
            "source",
            "credential_owner_user_id",
            "status",
        ):
            batch.drop_column(column)
        batch.create_unique_constraint("uq_provider_credentials_provider", ["provider"])

    with op.batch_alter_table("contributor_usage_ledger") as batch:
        batch.alter_column(
            "credential_owner_user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
