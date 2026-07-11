"""add translation_state and translation_error to chapters

Revision ID: a0b1c2d3e4f5
Revises: f6a1b2c3d4e5
Create Date: 2026-07-02 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f5'
down_revision: str | Sequence[str] | None = 'f6a1b2c3d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column(
        'chapters',
        sa.Column('translation_state', sa.String(32), nullable=False, server_default='pending'),
    )
    op.add_column(
        'chapters',
        sa.Column('translation_error', sa.String(1024), nullable=True),
    )
    op.create_index(
        'ix_chapters_translation_state',
        'chapters',
        ['translation_state'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_chapters_translation_state', table_name='chapters')
    op.drop_column('chapters', 'translation_error')
    op.drop_column('chapters', 'translation_state')
