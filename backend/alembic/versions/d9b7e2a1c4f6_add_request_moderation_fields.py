"""add request moderation fields

Revision ID: d9b7e2a1c4f6
Revises: c7d2a91f4b8e
Create Date: 2026-06-19 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9b7e2a1c4f6'
down_revision: str | Sequence[str] | None = 'c7d2a91f4b8e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add durable DB-backed request moderation fields."""
    with op.batch_alter_table('novel_requests') as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('approved_novel_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f('fk_novel_requests_approved_novel_id_novels'),
            'novels',
            ['approved_novel_id'],
            ['id'],
            ondelete='SET NULL',
        )

    op.execute("UPDATE novel_requests SET updated_at = created_at WHERE updated_at IS NULL")

    with op.batch_alter_table('novel_requests') as batch_op:
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
        )


def downgrade() -> None:
    """Remove DB-backed request moderation fields."""
    with op.batch_alter_table('novel_requests') as batch_op:
        batch_op.drop_constraint(
            op.f('fk_novel_requests_approved_novel_id_novels'),
            type_='foreignkey',
        )
        batch_op.drop_column('approved_novel_id')
        batch_op.drop_column('rejection_reason')
        batch_op.drop_column('updated_at')
