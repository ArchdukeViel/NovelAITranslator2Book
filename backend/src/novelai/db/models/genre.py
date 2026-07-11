"""Genre ORM model and novel_genres association table.

Genres are a curated, closed-vocabulary classification for Japanese web novels.
Stored in Japanese with optional English display labels.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Association table: novel_genres
# ---------------------------------------------------------------------------

novel_genres = Table(
    "novel_genres",
    Base.metadata,
    Column(
        "novel_id",
        Integer,
        ForeignKey("novels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "genre_id",
        Integer,
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_by",
        String(32),
        nullable=False,
        default="system",
        server_default="system",
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    ),
)


# ---------------------------------------------------------------------------
# Genre model
# ---------------------------------------------------------------------------

class Genre(Base):
    """A curated genre classification for Japanese web novels."""

    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name_ja: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_adult: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return f"<Genre id={self.id} slug={self.slug!r} name_ja={self.name_ja!r}>"
