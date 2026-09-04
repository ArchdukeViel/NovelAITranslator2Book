"""alter chapters title column from varchar(512) to text

Allows long web novel chapter titles (e.g. Syosetu / Kakuyomu episode headers
containing author notes and long subtitles) without StringDataRightTruncation errors.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "chapters",
        "title",
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "chapters",
        "title",
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
