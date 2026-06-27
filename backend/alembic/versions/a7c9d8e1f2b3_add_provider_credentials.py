"""add provider credentials

Revision ID: a7c9d8e1f2b3
Revises: f6a1b2c3d4e5
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c9d8e1f2b3'
down_revision: Union[str, Sequence[str], None] = 'f6a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create encrypted provider credential storage."""
    op.create_table(
        'provider_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('encrypted_api_key', sa.Text(), nullable=False),
        sa.Column('key_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('last4', sa.String(length=16), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('validation_status', sa.String(length=32), nullable=False),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', name='uq_provider_credentials_provider'),
    )
    op.create_index('ix_provider_credentials_provider', 'provider_credentials', ['provider'], unique=False)
    op.create_index('ix_provider_credentials_key_fingerprint', 'provider_credentials', ['key_fingerprint'], unique=False)


def downgrade() -> None:
    """Drop encrypted provider credential storage."""
    op.drop_index('ix_provider_credentials_key_fingerprint', table_name='provider_credentials')
    op.drop_index('ix_provider_credentials_provider', table_name='provider_credentials')
    op.drop_table('provider_credentials')
