"""Job and provider-request ORM models.

CrawlJob, TranslationJob, and ProviderRequest map existing file-backed
job/activity concepts onto Postgres rows. File-backed code runs in
parallel during the transition; these tables become the system of record
once the cutover is complete.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CrawlJob(Base):
    """A crawl job for fetching novel metadata and chapters."""

    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int | None] = mapped_column(
        ForeignKey("novels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<CrawlJob id={self.id} status={self.status!r}>"


class TranslationJob(Base):
    """A translation job for a chapter."""

    __tablename__ = "translation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int | None] = mapped_column(
        ForeignKey("novels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to provider requests
    provider_requests: Mapped[list[ProviderRequest]] = relationship(
        "ProviderRequest", back_populates="translation_job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TranslationJob id={self.id} status={self.status!r}>"


class ProviderRequest(Base):
    """A single LLM provider API request record.

    Raw API keys, authorization headers, and secrets must never be stored here.
    """

    __tablename__ = "provider_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("translation_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )

    translation_job: Mapped[TranslationJob | None] = relationship(
        "TranslationJob", back_populates="provider_requests"
    )

    def __repr__(self) -> str:
        return f"<ProviderRequest id={self.id} provider={self.provider_key!r} status={self.status!r}>"
