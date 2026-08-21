"""Project the public reader unavailable policy into the catalog."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f7a9c1d3b2"
down_revision: str | Sequence[str] | None = "d9f3a1b7c5e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the optional per-novel public reader policy projection field."""
    op.add_column(
        "novels",
        sa.Column("public_reader_unavailable_policy", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    """Remove the per-novel public reader policy projection field."""
    op.drop_column("novels", "public_reader_unavailable_policy")
