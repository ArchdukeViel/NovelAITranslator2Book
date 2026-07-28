"""AnalyticsEvent ORM model (DEBT-009).

Stores privacy-safe aggregate product usage events. Content-sensitive fields
(prompts, definitions, notification body, query text, IP, credentials) are
explicitly excluded by the schema and sanitization layer.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AnalyticsEvent(Base):
    """A single privacy-safe analytics event record."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    novel_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    chapter_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<AnalyticsEvent id={self.id} name={self.event_name!r}"
            f" novel={self.novel_id!r} chapter={self.chapter_id!r}>"
        )
