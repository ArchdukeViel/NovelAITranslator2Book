"""Chapter ORM model.

Stores chapter metadata and storage keys. Heavy content (raw/translated text)
lives in file/object storage; this table stores the keys and status only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novelai.core.chapter_state import TranslationState
from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Chapter(Base):
    """A chapter belonging to a Novel."""

    __tablename__ = "chapters"
    __table_args__ = (
        Index("ix_chapters_novel_id_chapter_number", "novel_id", "chapter_number"),
        Index("ix_chapters_novel_id_translation_status_updated_at", "novel_id", "translation_status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Storage keys — paths/keys into file or object storage
    raw_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    translated_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Status fields
    raw_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    translation_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")

    # Translation pipeline state (tracked by TranslationService)
    translation_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TranslationState.PENDING.value
    )
    translation_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

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

    # Relationship back to Novel
    novel: Mapped["Novel"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Novel", back_populates="chapters"
    )

    def __repr__(self) -> str:
        return (
            f"<Chapter id={self.id} novel_id={self.novel_id}"
            f" chapter_number={self.chapter_number}>"
        )
