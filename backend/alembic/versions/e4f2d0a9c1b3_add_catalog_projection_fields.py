"""add catalog projection fields

Revision ID: e4f2d0a9c1b3
Revises: d9b7e2a1c4f6
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f2d0a9c1b3'
down_revision: Union[str, Sequence[str], None] = 'd9b7e2a1c4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add denormalized catalog summary fields to novels."""
    with op.batch_alter_table('novels') as batch_op:
        batch_op.add_column(
            sa.Column(
                'publication_status',
                sa.String(length=64),
                nullable=False,
                server_default='unknown',
            )
        )
        batch_op.add_column(sa.Column('source_updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column('chapter_count', sa.Integer(), nullable=False, server_default='0')
        )
        batch_op.add_column(
            sa.Column('translated_count', sa.Integer(), nullable=False, server_default='0')
        )
        batch_op.add_column(sa.Column('latest_chapter_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('latest_chapter_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('latest_chapter_title', sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column('latest_chapter_updated_at', sa.DateTime(timezone=True), nullable=True)
        )

    op.execute(
        """
        UPDATE novels
        SET publication_status = CASE
            WHEN lower(coalesce(status, '')) IN ('ongoing', 'completed', 'hiatus', 'unknown')
                THEN lower(status)
            ELSE 'unknown'
        END
        """
    )


def downgrade() -> None:
    """Remove denormalized catalog summary fields from novels."""
    with op.batch_alter_table('novels') as batch_op:
        batch_op.drop_column('latest_chapter_updated_at')
        batch_op.drop_column('latest_chapter_title')
        batch_op.drop_column('latest_chapter_number')
        batch_op.drop_column('latest_chapter_id')
        batch_op.drop_column('translated_count')
        batch_op.drop_column('chapter_count')
        batch_op.drop_column('source_updated_at')
        batch_op.drop_column('publication_status')
