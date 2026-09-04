"""Chapter ORM model.

Stores chapter metadata and storage keys. Heavy content (raw/translated text)
lives in file/object storage; this table stores the keys and status only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novelai.core.chapter_state import TranslationState
from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Chapter(Base):
    """A chapter belonging to a Novel."""

    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint(
            "raw_status IN ('pending', 'fetched', 'crawled', 'failed', 'ready')",
            name="ck_chapters_raw_status",
        ),
        CheckConstraint(
            "translation_status IN ('pending', 'in_progress', 'translated', 'completed', 'failed', 'approved')",
            name="ck_chapters_translation_status",
        ),
        Index("ix_chapters_novel_id_chapter_number", "novel_id", "chapter_number"),
        Index("ix_chapters_novel_id_logical_chapter_id", "novel_id", "logical_chapter_id", unique=True),
        Index("ix_chapters_novel_id_source_episode_id", "novel_id", "source_episode_id"),
        Index("ix_chapters_novel_id_sequence_number", "novel_id", "sequence_number"),
        Index("ix_chapters_novel_id_translation_status_updated_at", "novel_id", "translation_status", "updated_at"),
        Index("ix_chapters_novel_toc_ordering", "novel_id", "sequence_number", "chapter_number", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Section 2 stable identity. ``logical_chapter_id`` is the canonical
    # key used by orchestrator, translation lineage, and the raw
    # generation index; ``chapter_number`` is retained as a
    # presentation/sequence compatibility field. The DB contract is
    # UNIQUE(novel_id, logical_chapter_id) with a NOT NULL column — the
    # migration and this ORM model agree exactly.
    logical_chapter_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source_episode_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    section_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Storage keys — paths/keys into file or object storage
    raw_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    translated_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    media_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    translated_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_state_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    translation_versions_json: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    translation_edit_history_json: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)

    # Status fields
    raw_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    translation_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")

    # Translation pipeline state (tracked by TranslationService)
    translation_state: Mapped[str] = mapped_column(String(32), nullable=False, default=TranslationState.PENDING.value)
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
    novel: Mapped[Novel] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Novel", back_populates="chapters"
    )

    def __repr__(self) -> str:
        return (
            f"<Chapter id={self.id} novel_id={self.novel_id}"
            f" logical_chapter_id={self.logical_chapter_id}"
            f" chapter_number={self.chapter_number}>"
        )
