"""add user password hash

Revision ID: c7d2a91f4b8e
Revises: a3f7c91d4e2b
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2a91f4b8e'
down_revision: Union[str, Sequence[str], None] = 'a3f7c91d4e2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable password credentials for public email/password users."""
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove public email/password credentials."""
    op.drop_column('users', 'password_hash')
