"""Tag ORM model and novel_tags association table.

Tags are an open-vocabulary classification, typically imported from source
sites (Syosetu keywords, Kakuyomu tags) or assigned by admin curation.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Association table: novel_tags
# ---------------------------------------------------------------------------

novel_tags = Table(
    "novel_tags",
    Base.metadata,
    Column(
        "novel_id",
        Integer,
        ForeignKey("novels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        Integer,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "origin",
        String(32),
        nullable=False,
        default="unknown",
        server_default="unknown",
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
# Tag model
# ---------------------------------------------------------------------------

class Tag(Base):
    """A tag — open-vocabulary label for novel classification."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name_ja: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_adult: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return f"<Tag id={self.id} name={self.name!r}>"
