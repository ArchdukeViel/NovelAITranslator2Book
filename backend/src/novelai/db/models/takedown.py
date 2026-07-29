"""Takedown request model (DMCA / copyright infringement).

Stores incoming takedown notices and their review status.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from novelai.db.base import Base


class TakedownRequest(Base):
    __tablename__ = "takedown_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Complainant info
    complainant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    complainant_email: Mapped[str] = mapped_column(String(255), nullable=False)
    complainant_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Infringing material
    infringing_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Original work
    original_work_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_work_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Status
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="pending | reviewing | approved | rejected | expired",
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Signature
    signature: Mapped[str] = mapped_column(Text, nullable=False, comment="Digital signature or typed legal name.")

    # --- Metadata
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
