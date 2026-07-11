"""merge provider credentials and email verification heads

Revision ID: c1d2e3f4a5b6
Revises: a7c9d8e1f2b3, b2e6d4c8f1a9
Create Date: 2026-06-28 00:00:00.000000

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: str | Sequence[str] | None = ('a7c9d8e1f2b3', 'b2e6d4c8f1a9')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge migration branches without schema changes."""


def downgrade() -> None:
    """Unmerge migration branches without schema changes."""
