"""merge translation state and glossary status heads

Revision ID: cea7d090afbc
Revises: a0b1c2d3e4f5, e1a2b3c4d5f6
Create Date: 2026-07-03 23:13:22.094053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cea7d090afbc'
down_revision: Union[str, Sequence[str], None] = ('a0b1c2d3e4f5', 'e1a2b3c4d5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
