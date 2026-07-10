"""Read-only novel query helpers for routers that need DB-level metadata.

This service exists so routers don't import ``db.models.*`` directly.
Routers should call these helpers instead of querying ORM models.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel


def get_glossary_revision(session: Session, novel_ref: str) -> int | None:
    """Resolve the current glossary_revision for a novel by slug or numeric ID.

    Returns None if the novel is not found.
    """
    novel = session.execute(select(Novel).where(Novel.slug == novel_ref)).scalar_one_or_none()
    if novel is None and novel_ref.isdigit():
        novel = session.get(Novel, int(novel_ref))
    if novel is None:
        return None
    return int(novel.glossary_revision or 0)
