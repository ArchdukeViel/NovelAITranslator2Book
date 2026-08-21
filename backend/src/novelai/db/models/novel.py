"""Novel ORM model.

Represents a novel (source metadata + catalog entry). Heavy content
(raw/translated chapter text, covers, exports) lives in Cloudflare R2;
this table stores metadata, storage keys, and checksums only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from novelai.db.base import Base

if TYPE_CHECKING:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.genre import Genre
    from novelai.db.models.tag import Tag


GLOSSARY_STATUS_VALUES: frozenset[str] = frozenset(
    {
        "glossary_pending",
        "glossary_ready",
        "glossary_skipped",
    }
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Novel(Base):
    """A novel entry in the catalog."""

    __tablename__ = "novels"
    __table_args__ = (
        Index("ix_novels_is_published_updated_at", "is_published", "updated_at"),
        Index("ix_novels_is_published_publication_status", "is_published", "publication_status"),
        Index("ix_novels_language", "language"),
        Index("ix_novels_source_site", "source_site"),
        Index("ix_novels_source_updated_at", "source_updated_at"),
        Index("ix_novels_chapter_count", "chapter_count"),
        Index("ix_novels_translated_count", "translated_count"),
        Index("ix_novels_latest_chapter_updated_at", "latest_chapter_updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    public_slug: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_site: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="ja")
    publication_status: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    public_reader_unavailable_policy: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    # R2-only activation truth. The manifest key is stored exactly so a
    # reader never reconstructs or lists a generation pointer object.
    active_generation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_generation_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # PostgreSQL owns the mutable source/catalog metadata.  Object storage
    # contains immutable chapter, translation, media, asset, and generation
    # artifacts; this JSON document is only the small operational/catalog
    # projection needed to reconstruct crawl handoffs without a metadata file.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metadata_history_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source_state_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_published: Mapped[bool] = mapped_column(nullable=False, default=False)
    glossary_status: Mapped[str] = mapped_column(String(32), nullable=False, default="glossary_pending")
    glossary_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
    chapters: Mapped[list[Chapter]] = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
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

    @validates("glossary_status")
    def _validate_glossary_status(self, key: str, value: str) -> str:
        if value not in GLOSSARY_STATUS_VALUES:
            raise ValueError(f"Invalid glossary_status {value!r}. Must be one of {sorted(GLOSSARY_STATUS_VALUES)}.")
        return value

    def __repr__(self) -> str:
        return f"<Novel id={self.id} slug={self.slug!r} title={self.title!r}>"


# Bottom import registers Chapter with the mapper registry so the
# string-based relationship("Chapter") can resolve at configuration time.
from novelai.db.models.chapter import Chapter  # noqa: E402
