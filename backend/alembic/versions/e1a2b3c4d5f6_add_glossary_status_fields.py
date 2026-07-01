"""add glossary status fields

Revision ID: e1a2b3c4d5f6
Revises: 9f3b2c1d0e7a
Create Date: 2026-07-01 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5f6'
down_revision: str | Sequence[str] | None = '9f3b2c1d0e7a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add glossary_status and glossary_revision columns to novels table."""
    op.add_column(
        'novels',
        sa.Column(
            'glossary_status',
            sa.String(32),
            nullable=False,
            server_default='glossary_pending',
        ),
    )
    op.add_column(
        'novels',
        sa.Column(
            'glossary_revision',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.create_index('ix_novels_glossary_status', 'novels', ['glossary_status'], unique=False)


def downgrade() -> None:
    """Remove glossary_status and glossary_revision columns from novels table."""
    op.drop_index('ix_novels_glossary_status', table_name='novels')
    op.drop_column('novels', 'glossary_revision')
    op.drop_column('novels', 'glossary_status')
