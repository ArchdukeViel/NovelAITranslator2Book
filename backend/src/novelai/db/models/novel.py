"""Novel ORM model.

Represents a novel (source metadata + catalog entry). Heavy content
(raw/translated chapter text, covers, exports) lives in file/object storage;
this table stores metadata, storage keys, and checksums only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novelai.db.base import Base

if TYPE_CHECKING:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.genre import Genre
    from novelai.db.models.tag import Tag


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Novel(Base):
    """A novel entry in the catalog."""

    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_site: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="ja")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    publication_status: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chapter_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    translated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_chapter_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latest_chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_chapter_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    latest_chapter_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_published: Mapped[bool] = mapped_column(nullable=False, default=False)
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

    # Relationships
    chapters: Mapped[list[Chapter]] = relationship(
        "Chapter", back_populates="novel", cascade="all, delete-orphan"
    )
    genres: Mapped[list[Genre]] = relationship(
        "Genre",
        secondary="novel_genres",
        lazy="selectin",
    )
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary="novel_tags",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Novel id={self.id} slug={self.slug!r} title={self.title!r}>"


# Bottom import registers Chapter with the mapper registry so the
# string-based relationship("Chapter") can resolve at configuration time.
from novelai.db.models.chapter import Chapter  # noqa: E402, F401
