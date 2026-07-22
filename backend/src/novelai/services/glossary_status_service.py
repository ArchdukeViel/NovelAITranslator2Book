"""Service for novel glossary-status transitions.

Handles the business logic for PATCH /api/admin/novels/{novel_id}/glossary-status.
endpoint: loading the novel, mutating status and revision, writing a
NovelGlossaryDecisionEvent, and flushing within the caller's transaction.

This is kept separate from GlossaryRepository because it mutates both the
Novel row and the decision-event table — a use-case concern rather than pure
data access.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from novelai.db.models.glossary import NovelGlossaryDecisionEvent
from novelai.db.models.novel import Novel

logger = logging.getLogger(__name__)

_EVENT_TYPE_NOVEL_STATUS_CHANGE = "novel_glossary_status_change"


class GlossaryStatusService:
    """Transitions a novel's glossary_status and writes an audit event."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def transition_status(
        self,
        novel_id: str,
        *,
        target_status: str,
        actor_user_id: int | None,
    ) -> Novel:
        """Set glossary_status; increment revision if target is glossary_ready.

        Writes a NovelGlossaryDecisionEvent capturing old/new status, the
        actor user ID, and an ISO 8601 timestamp.

        Args:
            novel_id: The novel's slug (string identifier used throughout the
                API layer).
            target_status: One of ``glossary_pending``, ``glossary_ready``, or
                ``glossary_skipped``.  Validated by the Novel ORM validator
                which raises ``ValueError`` for unrecognised values.
            actor_user_id: The integer PK of the user performing the action, or
                ``None`` for system-initiated transitions.

        Returns:
            The updated ``Novel`` instance (still within the caller's session).

        Raises:
            LookupError: If no novel with the given slug exists.
        """
        session = self._session

        novel: Novel | None = session.query(Novel).filter(Novel.slug == novel_id).one_or_none()
        if novel is None:
            raise LookupError(f"Novel with slug {novel_id!r} not found.")

        old_status: str = novel.glossary_status

        # The ORM validator on Novel.glossary_status raises ValueError for
        # unrecognised values, so no extra check is needed here.
        novel.glossary_status = target_status

        if target_status == "glossary_ready":
            novel.glossary_revision += 1

        # Write the audit event directly — we bypass GlossaryRepository
        # .create_decision_event because that method validates event_type
        # against an entry-level event-type set that does not include
        # novel-level status transitions.
        event = NovelGlossaryDecisionEvent(
            novel_id=novel.id,
            glossary_entry_id=None,
            alias_id=None,
            actor_user_id=actor_user_id,
            event_type=_EVENT_TYPE_NOVEL_STATUS_CHANGE,
            old_value_json=json.dumps({"glossary_status": old_status}, sort_keys=True, separators=(",", ":")),
            new_value_json=json.dumps({"glossary_status": target_status}, sort_keys=True, separators=(",", ":")),
            rationale=None,
            decision_source="owner",
            created_at=datetime.now(UTC),
        )
        session.add(event)
        session.flush()

        logger.info(
            "Novel %r glossary_status transitioned %r → %r by actor_user_id=%r; glossary_revision=%d",
            novel_id,
            old_status,
            target_status,
            actor_user_id,
            novel.glossary_revision,
        )

        return novel
