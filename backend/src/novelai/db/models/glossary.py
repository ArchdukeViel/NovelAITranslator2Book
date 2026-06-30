"""Source-agnostic per-novel glossary ORM models.

These tables store owner/admin glossary decisions, aliases, provenance,
decision history, QA findings, and optional user display overrides. They do not
store translated chapter repairs or mutate canonical chapter text.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class NovelGlossaryEntry(Base):
    """Canonical or candidate glossary term for one platform novel."""

    __tablename__ = "novel_glossary_entries"
    __table_args__ = (
        UniqueConstraint("novel_id", "canonical_term", name="uq_novel_glossary_entries_novel_term"),
        Index("ix_novel_glossary_entries_novel_id_status", "novel_id", "status"),
        Index("ix_novel_glossary_entries_novel_id_term_type", "novel_id", "term_type"),
        Index("ix_novel_glossary_entries_novel_id_public_visible", "novel_id", "public_visible"),
        Index("ix_novel_glossary_entries_novel_id_canonical_term", "novel_id", "canonical_term"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_term: Mapped[str] = mapped_column(String(255), nullable=False)
    term_type: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_translation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    enforcement_level: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    owner_locked: Mapped[bool] = mapped_column(nullable=False, default=False)
    public_visible: Mapped[bool] = mapped_column(nullable=False, default=False)
    public_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    replacement_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="preview_required")
    matching_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="exact_phrase")
    first_seen_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    first_seen_chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    last_seen_chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    aliases: Mapped[list[NovelGlossaryAlias]] = relationship(
        "NovelGlossaryAlias", back_populates="entry", cascade="all, delete-orphan"
    )
    provenance_records: Mapped[list[NovelGlossarySourceProvenance]] = relationship(
        "NovelGlossarySourceProvenance", back_populates="entry"
    )
    decision_events: Mapped[list[NovelGlossaryDecisionEvent]] = relationship(
        "NovelGlossaryDecisionEvent", back_populates="entry"
    )
    qa_findings: Mapped[list[NovelGlossaryQAFinding]] = relationship(
        "NovelGlossaryQAFinding", back_populates="entry"
    )
    display_overrides: Mapped[list[UserGlossaryDisplayOverride]] = relationship(
        "UserGlossaryDisplayOverride", back_populates="entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NovelGlossaryEntry id={self.id} novel_id={self.novel_id} term={self.canonical_term!r}>"


class NovelGlossaryAlias(Base):
    """Observed, allowed, or rejected alias for a glossary entry."""

    __tablename__ = "novel_glossary_aliases"
    __table_args__ = (
        Index("ix_novel_glossary_aliases_entry_type", "glossary_entry_id", "alias_type"),
        Index("ix_novel_glossary_aliases_novel_alias_type", "novel_id", "alias_text", "alias_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    glossary_entry_id: Mapped[int] = mapped_column(
        ForeignKey("novel_glossary_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(32), nullable=False, default="observed")
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    text_origin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applies_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    matching_policy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )

    entry: Mapped[NovelGlossaryEntry] = relationship("NovelGlossaryEntry", back_populates="aliases")

    def __repr__(self) -> str:
        return f"<NovelGlossaryAlias id={self.id} alias={self.alias_text!r} type={self.alias_type!r}>"


class NovelGlossarySourceProvenance(Base):
    """Source/evidence reference for glossary candidates and decisions."""

    __tablename__ = "novel_glossary_source_provenance"
    __table_args__ = (
        Index("ix_novel_glossary_source_provenance_novel_source", "novel_id", "source_site", "source_novel_id"),
        Index("ix_novel_glossary_source_provenance_entry_source", "glossary_entry_id", "source_site"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    glossary_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("novel_glossary_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_site: Mapped[str] = mapped_column(String(64), nullable=False)
    source_adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    source_novel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chapter_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_source_term: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observed_translated_term: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    local_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    evidence_quality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )

    entry: Mapped[NovelGlossaryEntry | None] = relationship(
        "NovelGlossaryEntry", back_populates="provenance_records"
    )

    def __repr__(self) -> str:
        return f"<NovelGlossarySourceProvenance id={self.id} source={self.source_site!r}>"


class NovelGlossaryDecisionEvent(Base):
    """Audit/history event for glossary decisions."""

    __tablename__ = "novel_glossary_decision_events"
    __table_args__ = (
        Index("ix_novel_glossary_decision_events_novel_created", "novel_id", "created_at"),
        Index("ix_novel_glossary_decision_events_entry_created", "glossary_entry_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    glossary_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("novel_glossary_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    alias_id: Mapped[int | None] = mapped_column(
        ForeignKey("novel_glossary_aliases.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_source: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )

    entry: Mapped[NovelGlossaryEntry | None] = relationship(
        "NovelGlossaryEntry", back_populates="decision_events"
    )

    def __repr__(self) -> str:
        return f"<NovelGlossaryDecisionEvent id={self.id} type={self.event_type!r}>"


class NovelGlossaryQAFinding(Base):
    """Structured glossary QA finding for review and repair planning."""

    __tablename__ = "novel_glossary_qa_findings"
    __table_args__ = (
        Index("ix_novel_glossary_qa_findings_novel_status_severity", "novel_id", "status", "severity"),
        Index("ix_novel_glossary_qa_findings_chapter_status", "chapter_id", "status"),
        Index("ix_novel_glossary_qa_findings_entry_status", "glossary_entry_id", "status"),
        Index("ix_novel_glossary_qa_findings_type_severity", "finding_type", "severity"),
        Index("ix_novel_glossary_qa_findings_novel_chapter_status_severity", "novel_id", "chapter_id", "status", "severity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    glossary_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("novel_glossary_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="warning")
    matched_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    suggested_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    context_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    reviewer_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entry: Mapped[NovelGlossaryEntry | None] = relationship("NovelGlossaryEntry", back_populates="qa_findings")

    def __repr__(self) -> str:
        return f"<NovelGlossaryQAFinding id={self.id} type={self.finding_type!r} severity={self.severity!r}>"


class UserGlossaryDisplayOverride(Base):
    """Per-user reader display override for a glossary entry.

    Overrides are presentation-layer only and must not mutate stored chapter
    translations or owner-approved glossary decisions.
    """

    __tablename__ = "user_glossary_display_overrides"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "novel_id",
            "glossary_entry_id",
            name="uq_user_glossary_display_overrides_user_novel_entry",
        ),
        Index("ix_user_glossary_display_overrides_novel_entry", "novel_id", "glossary_entry_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    glossary_entry_id: Mapped[int] = mapped_column(
        ForeignKey("novel_glossary_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_term: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow, onupdate=_utcnow
    )

    entry: Mapped[NovelGlossaryEntry] = relationship("NovelGlossaryEntry", back_populates="display_overrides")

    def __repr__(self) -> str:
        return f"<UserGlossaryDisplayOverride id={self.id} user_id={self.user_id} entry_id={self.glossary_entry_id}>"
