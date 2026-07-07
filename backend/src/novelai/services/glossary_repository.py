"""Repository-style data access for source-agnostic per-novel glossary records.

This module intentionally stops at database access. API authorization,
translation prompt injection, QA scanning, chapter repair, and public rendering
belong to later phases.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.glossary import (
    NovelGlossaryAlias,
    NovelGlossaryDecisionEvent,
    NovelGlossaryEntry,
    NovelGlossaryQAFinding,
    NovelGlossarySourceProvenance,
    UserGlossaryDisplayOverride,
)

ENTRY_STATUSES = {"candidate", "recommended", "approved", "rejected", "deprecated"}
ALIAS_TYPES = {"allowed", "rejected", "banned", "deprecated", "observed", "source_variant"}
DECISION_EVENT_TYPES = {
    "create",
    "approve",
    "recommend",
    "reject",
    "deprecate",
    "lock",
    "unlock",
    "alias_change",
    "qa_status_change",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _json_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class GlossaryRepository:
    """SQLAlchemy-backed glossary data access scoped to platform `novel_id`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_glossary_entries_for_novel(
        self,
        novel_id: int,
        *,
        status: str | None = None,
        term_type: str | None = None,
        public_visible: bool | None = None,
    ) -> list[NovelGlossaryEntry]:
        stmt = select(NovelGlossaryEntry).where(NovelGlossaryEntry.novel_id == novel_id)
        if status is not None:
            stmt = stmt.where(NovelGlossaryEntry.status == status)
        if term_type is not None:
            stmt = stmt.where(NovelGlossaryEntry.term_type == term_type)
        if public_visible is not None:
            stmt = stmt.where(NovelGlossaryEntry.public_visible == public_visible)
        stmt = stmt.order_by(NovelGlossaryEntry.canonical_term, NovelGlossaryEntry.id)
        return list(self.db.scalars(stmt))

    def list_glossary_entries_global(
        self,
        *,
        status: str | None = None,
        term_type: str | None = None,
        public_visible: bool | None = None,
    ) -> list[NovelGlossaryEntry]:
        """List global-scope entries with optional filters."""
        stmt = select(NovelGlossaryEntry).where(
            NovelGlossaryEntry.scope == NovelGlossaryEntry.SCOPE_GLOBAL
        )
        if status is not None:
            stmt = stmt.where(NovelGlossaryEntry.status == status)
        if term_type is not None:
            stmt = stmt.where(NovelGlossaryEntry.term_type == term_type)
        if public_visible is not None:
            stmt = stmt.where(NovelGlossaryEntry.public_visible == public_visible)
        stmt = stmt.order_by(NovelGlossaryEntry.canonical_term, NovelGlossaryEntry.id)
        return list(self.db.scalars(stmt))

    def list_approved_global_entries(self) -> list[NovelGlossaryEntry]:
        """Return all approved entries with scope='global'.

        Used by GlossaryResolver to build the base global glossary before
        applying novel overrides.
        """
        stmt = (
            select(NovelGlossaryEntry)
            .where(
                NovelGlossaryEntry.scope == NovelGlossaryEntry.SCOPE_GLOBAL,
                NovelGlossaryEntry.status == "approved",
            )
            .order_by(NovelGlossaryEntry.canonical_term, NovelGlossaryEntry.id)
        )
        return list(self.db.scalars(stmt))

    def get_glossary_entry(self, entry_id: int, *, novel_id: int | None = None) -> NovelGlossaryEntry | None:
        stmt = select(NovelGlossaryEntry).where(NovelGlossaryEntry.id == entry_id)
        if novel_id is not None:
            stmt = stmt.where(NovelGlossaryEntry.novel_id == novel_id)
        else:
            # When novel_id is None, only match global-scope entries.
            stmt = stmt.where(NovelGlossaryEntry.scope == NovelGlossaryEntry.SCOPE_GLOBAL)
        return self.db.scalar(stmt)

    def create_glossary_entry(
        self,
        *,
        novel_id: int | None,
        canonical_term: str,
        term_type: str,
        approved_translation: str | None = None,
        status: str = "candidate",
        enforcement_level: str = "none",
        owner_locked: bool = False,
        public_visible: bool = False,
        public_description: str | None = None,
        admin_notes: str | None = None,
        confidence: float | None = None,
        replacement_policy: str = "preview_required",
        matching_policy: str = "exact_phrase",
        first_seen_chapter_id: int | None = None,
        first_seen_chapter_number: int | None = None,
        last_seen_chapter_id: int | None = None,
        last_seen_chapter_number: int | None = None,
        actor_user_id: int | None = None,
        decision_source: str = "system",
        rationale: str | None = None,
        scope: str = "novel",
    ) -> NovelGlossaryEntry:
        self._validate_entry_status(status)
        entry = NovelGlossaryEntry(
            scope=scope,
            novel_id=novel_id,
            canonical_term=canonical_term,
            term_type=term_type,
            approved_translation=approved_translation,
            status=status,
            enforcement_level=enforcement_level,
            owner_locked=owner_locked,
            public_visible=public_visible,
            public_description=public_description,
            admin_notes=admin_notes,
            confidence=confidence,
            replacement_policy=replacement_policy,
            matching_policy=matching_policy,
            first_seen_chapter_id=first_seen_chapter_id,
            first_seen_chapter_number=first_seen_chapter_number,
            last_seen_chapter_id=last_seen_chapter_id,
            last_seen_chapter_number=last_seen_chapter_number,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        self.db.add(entry)
        self.db.flush()
        if novel_id is not None:
            self.create_decision_event(
                novel_id=novel_id,
                glossary_entry_id=entry.id,
                actor_user_id=actor_user_id,
                event_type="create",
                new_value={"status": status, "canonical_term": canonical_term, "scope": scope},
                rationale=rationale,
                decision_source=decision_source,
            )
        if status == "approved" and novel_id is not None:
            self._increment_glossary_revision(novel_id)
        return entry

    def update_glossary_entry(
        self,
        entry_id: int,
        *,
        novel_id: int | None = None,
        actor_user_id: int | None = None,
        **fields: Any,
    ) -> NovelGlossaryEntry:
        """Update a glossary entry by ID.

        If novel_id is None, treats it as a global entry lookup.
        """
        entry = self._require_entry(entry_id, novel_id=novel_id)
        allowed = {
            "canonical_term",
            "term_type",
            "approved_translation",
            "enforcement_level",
            "public_visible",
            "public_description",
            "admin_notes",
            "confidence",
            "replacement_policy",
            "matching_policy",
            "first_seen_chapter_id",
            "first_seen_chapter_number",
            "last_seen_chapter_id",
            "last_seen_chapter_number",
            "scope",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unsupported glossary entry field(s): {', '.join(sorted(unknown))}")
        # Capture status before any mutations so the increment check is accurate.
        entry_status_before_update = entry.status
        for name, value in fields.items():
            setattr(entry, name, value)
        entry.updated_by_user_id = actor_user_id
        # Only increment when the entry is currently approved — candidate/recommended changes
        # do not affect the vetted glossary set (Req 8.2, 8.4).
        if entry_status_before_update == "approved" and novel_id is not None:
            self._increment_glossary_revision(novel_id)
        self.db.flush()
        return entry

    def change_glossary_entry_status(
        self,
        entry_id: int,
        *,
        novel_id: int | None = None,
        status: str,
        actor_user_id: int | None = None,
        rationale: str | None = None,
        decision_source: str = "owner",
    ) -> NovelGlossaryEntry:
        self._validate_entry_status(status)
        entry = self._require_entry(entry_id, novel_id=novel_id)
        old_status = entry.status
        entry.status = status
        entry.updated_by_user_id = actor_user_id
        if status == "deprecated":
            entry.deprecated_at = _utcnow()
        event_type = {
            "approved": "approve",
            "recommended": "recommend",
            "rejected": "reject",
            "deprecated": "deprecate",
        }.get(status, "create")
        self.create_decision_event(
            novel_id=novel_id,
            glossary_entry_id=entry.id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            old_value={"status": old_status},
            new_value={"status": status},
            rationale=rationale,
            decision_source=decision_source,
        )
        # Increment glossary_revision when approving an entry, or when an
        # approved entry is deprecated or rejected (the active set changed).
        if (status == "approved" or (old_status == "approved" and status in {"deprecated", "rejected"})) and novel_id is not None:
            self._increment_glossary_revision(novel_id)
        self.db.flush()
        return entry

    def lock_glossary_entry(
        self,
        entry_id: int,
        *,
        novel_id: int,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ) -> NovelGlossaryEntry:
        entry = self._require_entry(entry_id, novel_id=novel_id)
        old_value = entry.owner_locked
        entry.owner_locked = True
        entry.updated_by_user_id = actor_user_id
        self.create_decision_event(
            novel_id=novel_id,
            glossary_entry_id=entry.id,
            actor_user_id=actor_user_id,
            event_type="lock",
            old_value={"owner_locked": old_value},
            new_value={"owner_locked": True},
            rationale=rationale,
            decision_source="owner",
        )
        self.db.flush()
        return entry

    def unlock_glossary_entry(
        self,
        entry_id: int,
        *,
        novel_id: int,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ) -> NovelGlossaryEntry:
        entry = self._require_entry(entry_id, novel_id=novel_id)
        old_value = entry.owner_locked
        entry.owner_locked = False
        entry.updated_by_user_id = actor_user_id
        self.create_decision_event(
            novel_id=novel_id,
            glossary_entry_id=entry.id,
            actor_user_id=actor_user_id,
            event_type="unlock",
            old_value={"owner_locked": old_value},
            new_value={"owner_locked": False},
            rationale=rationale,
            decision_source="owner",
        )
        self.db.flush()
        return entry

    def deprecate_glossary_entry(
        self,
        entry_id: int,
        *,
        novel_id: int,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ) -> NovelGlossaryEntry:
        return self.change_glossary_entry_status(
            entry_id,
            novel_id=novel_id,
            status="deprecated",
            actor_user_id=actor_user_id,
            rationale=rationale,
            decision_source="owner",
        )

    def list_aliases_for_entry(self, entry_id: int, *, novel_id: int | None = None) -> list[NovelGlossaryAlias]:
        entry = self._require_entry(entry_id, novel_id=novel_id)
        stmt = (
            select(NovelGlossaryAlias)
            .where(NovelGlossaryAlias.glossary_entry_id == entry.id)
            .order_by(NovelGlossaryAlias.alias_text, NovelGlossaryAlias.id)
        )
        return list(self.db.scalars(stmt))

    def add_glossary_alias(
        self,
        *,
        entry_id: int,
        novel_id: int,
        alias_text: str,
        alias_type: str = "observed",
        language: str | None = None,
        text_origin: str | None = None,
        applies_to: str | None = None,
        matching_policy: str | None = None,
        notes: str | None = None,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ) -> NovelGlossaryAlias:
        self._validate_alias_type(alias_type)
        entry = self._require_entry(entry_id, novel_id=novel_id)
        alias = NovelGlossaryAlias(
            glossary_entry_id=entry.id,
            novel_id=entry.novel_id,
            alias_text=alias_text,
            alias_type=alias_type,
            language=language,
            text_origin=text_origin,
            applies_to=applies_to,
            matching_policy=matching_policy,
            notes=notes,
        )
        self.db.add(alias)
        self.db.flush()
        self.create_decision_event(
            novel_id=entry.novel_id,
            glossary_entry_id=entry.id,
            alias_id=alias.id,
            actor_user_id=actor_user_id,
            event_type="alias_change",
            new_value={"alias_text": alias_text, "alias_type": alias_type},
            rationale=rationale,
            decision_source="owner" if actor_user_id is not None else "system",
        )
        return alias

    def update_glossary_alias(
        self,
        alias_id: int,
        *,
        novel_id: int,
        actor_user_id: int | None = None,
        rationale: str | None = None,
        **fields: Any,
    ) -> NovelGlossaryAlias:
        alias = self._require_alias(alias_id, novel_id=novel_id)
        allowed = {"alias_text", "alias_type", "language", "text_origin", "applies_to", "matching_policy", "notes"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unsupported glossary alias field(s): {', '.join(sorted(unknown))}")
        if "alias_type" in fields:
            self._validate_alias_type(fields["alias_type"])
        old_value = {name: getattr(alias, name) for name in fields}
        for name, value in fields.items():
            setattr(alias, name, value)
        self.create_decision_event(
            novel_id=alias.novel_id,
            glossary_entry_id=alias.glossary_entry_id,
            alias_id=alias.id,
            actor_user_id=actor_user_id,
            event_type="alias_change",
            old_value=old_value,
            new_value=fields,
            rationale=rationale,
            decision_source="owner" if actor_user_id is not None else "system",
        )
        self.db.flush()
        return alias

    def remove_or_deprecate_glossary_alias(
        self,
        alias_id: int,
        *,
        novel_id: int,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ) -> NovelGlossaryAlias:
        return self.update_glossary_alias(
            alias_id,
            novel_id=novel_id,
            alias_type="deprecated",
            actor_user_id=actor_user_id,
            rationale=rationale,
        )

    def add_source_provenance(
        self,
        *,
        novel_id: int,
        source_site: str,
        source_adapter: str,
        entry_id: int | None = None,
        source_novel_id: str | None = None,
        source_url: str | None = None,
        source_chapter_id: str | None = None,
        source_chapter_number: int | None = None,
        chapter_id: int | None = None,
        raw_source_term: str | None = None,
        observed_translated_term: str | None = None,
        evidence_ref: str | None = None,
        local_reference: str | None = None,
        evidence_quality: str | None = None,
        confidence: float | None = None,
    ) -> NovelGlossarySourceProvenance:
        if entry_id is not None:
            self._require_entry(entry_id, novel_id=novel_id)
        provenance = NovelGlossarySourceProvenance(
            glossary_entry_id=entry_id,
            novel_id=novel_id,
            source_site=source_site,
            source_adapter=source_adapter,
            source_novel_id=source_novel_id,
            source_url=source_url,
            source_chapter_id=source_chapter_id,
            source_chapter_number=source_chapter_number,
            chapter_id=chapter_id,
            raw_source_term=raw_source_term,
            observed_translated_term=observed_translated_term,
            evidence_ref=evidence_ref,
            local_reference=local_reference,
            evidence_quality=evidence_quality,
            confidence=confidence,
        )
        self.db.add(provenance)
        self.db.flush()
        return provenance

    def list_source_provenance_for_entry(
        self,
        entry_id: int,
        *,
        novel_id: int | None = None,
    ) -> list[NovelGlossarySourceProvenance]:
        entry = self._require_entry(entry_id, novel_id=novel_id)
        stmt = (
            select(NovelGlossarySourceProvenance)
            .where(NovelGlossarySourceProvenance.glossary_entry_id == entry.id)
            .order_by(NovelGlossarySourceProvenance.id)
        )
        return list(self.db.scalars(stmt))

    def list_source_provenance_for_novel(self, novel_id: int) -> list[NovelGlossarySourceProvenance]:
        stmt = (
            select(NovelGlossarySourceProvenance)
            .where(NovelGlossarySourceProvenance.novel_id == novel_id)
            .order_by(NovelGlossarySourceProvenance.id)
        )
        return list(self.db.scalars(stmt))

    def create_decision_event(
        self,
        *,
        novel_id: int | None,
        event_type: str,
        glossary_entry_id: int | None = None,
        alias_id: int | None = None,
        actor_user_id: int | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        rationale: str | None = None,
        decision_source: str = "system",
    ) -> NovelGlossaryDecisionEvent:
        if event_type not in DECISION_EVENT_TYPES:
            raise ValueError(f"Unsupported glossary decision event type: {event_type}")
        event = NovelGlossaryDecisionEvent(
            novel_id=novel_id,
            glossary_entry_id=glossary_entry_id,
            alias_id=alias_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            old_value_json=_json_payload(old_value),
            new_value_json=_json_payload(new_value),
            rationale=rationale,
            decision_source=decision_source,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_decision_events_for_novel(self, novel_id: int) -> list[NovelGlossaryDecisionEvent]:
        stmt = (
            select(NovelGlossaryDecisionEvent)
            .where(NovelGlossaryDecisionEvent.novel_id == novel_id)
            .order_by(NovelGlossaryDecisionEvent.created_at, NovelGlossaryDecisionEvent.id)
        )
        return list(self.db.scalars(stmt))

    def list_decision_events_for_entry(
        self,
        entry_id: int,
        *,
        novel_id: int | None = None,
    ) -> list[NovelGlossaryDecisionEvent]:
        entry = self._require_entry(entry_id, novel_id=novel_id)
        stmt = (
            select(NovelGlossaryDecisionEvent)
            .where(NovelGlossaryDecisionEvent.glossary_entry_id == entry.id)
            .order_by(NovelGlossaryDecisionEvent.created_at, NovelGlossaryDecisionEvent.id)
        )
        return list(self.db.scalars(stmt))

    def create_qa_finding(
        self,
        *,
        novel_id: int,
        finding_type: str,
        severity: str = "warning",
        status: str = "open",
        chapter_id: int | None = None,
        glossary_entry_id: int | None = None,
        matched_text: str | None = None,
        suggested_text: str | None = None,
        context_ref: str | None = None,
    ) -> NovelGlossaryQAFinding:
        if glossary_entry_id is not None:
            self._require_entry(glossary_entry_id, novel_id=novel_id)
        finding = NovelGlossaryQAFinding(
            novel_id=novel_id,
            chapter_id=chapter_id,
            glossary_entry_id=glossary_entry_id,
            finding_type=finding_type,
            severity=severity,
            matched_text=matched_text,
            suggested_text=suggested_text,
            context_ref=context_ref,
            status=status,
        )
        self.db.add(finding)
        self.db.flush()
        return finding

    def list_qa_findings_for_novel(
        self,
        novel_id: int,
        *,
        status: str | None = None,
    ) -> list[NovelGlossaryQAFinding]:
        stmt = select(NovelGlossaryQAFinding).where(NovelGlossaryQAFinding.novel_id == novel_id)
        if status is not None:
            stmt = stmt.where(NovelGlossaryQAFinding.status == status)
        stmt = stmt.order_by(NovelGlossaryQAFinding.id)
        return list(self.db.scalars(stmt))

    def list_qa_findings_for_chapter(
        self,
        chapter_id: int,
        *,
        novel_id: int | None = None,
        status: str | None = None,
    ) -> list[NovelGlossaryQAFinding]:
        stmt = select(NovelGlossaryQAFinding).where(NovelGlossaryQAFinding.chapter_id == chapter_id)
        if novel_id is not None:
            stmt = stmt.where(NovelGlossaryQAFinding.novel_id == novel_id)
        if status is not None:
            stmt = stmt.where(NovelGlossaryQAFinding.status == status)
        stmt = stmt.order_by(NovelGlossaryQAFinding.id)
        return list(self.db.scalars(stmt))

    def update_qa_finding_status(
        self,
        finding_id: int,
        *,
        novel_id: int,
        status: str,
        reviewer_user_id: int | None = None,
        reviewer_notes: str | None = None,
    ) -> NovelGlossaryQAFinding:
        finding = self.db.scalar(
            select(NovelGlossaryQAFinding).where(
                NovelGlossaryQAFinding.id == finding_id,
                NovelGlossaryQAFinding.novel_id == novel_id,
            )
        )
        if finding is None:
            raise LookupError(f"Glossary QA finding {finding_id} was not found for novel {novel_id}")
        finding.status = status
        finding.reviewer_user_id = reviewer_user_id
        finding.reviewer_notes = reviewer_notes
        finding.resolved_at = None if status == "open" else _utcnow()
        self.db.flush()
        return finding

    def set_user_display_override(
        self,
        *,
        user_id: int,
        novel_id: int,
        entry_id: int,
        display_term: str,
        enabled: bool = True,
    ) -> UserGlossaryDisplayOverride:
        self._require_entry(entry_id, novel_id=novel_id)
        override = self.db.scalar(
            select(UserGlossaryDisplayOverride).where(
                UserGlossaryDisplayOverride.user_id == user_id,
                UserGlossaryDisplayOverride.novel_id == novel_id,
                UserGlossaryDisplayOverride.glossary_entry_id == entry_id,
            )
        )
        if override is None:
            override = UserGlossaryDisplayOverride(
                user_id=user_id,
                novel_id=novel_id,
                glossary_entry_id=entry_id,
                display_term=display_term,
                enabled=enabled,
            )
            self.db.add(override)
        else:
            override.display_term = display_term
            override.enabled = enabled
        self.db.flush()
        return override

    def get_user_display_overrides_for_novel(
        self,
        *,
        user_id: int,
        novel_id: int,
        enabled: bool | None = None,
    ) -> list[UserGlossaryDisplayOverride]:
        stmt = select(UserGlossaryDisplayOverride).where(
            UserGlossaryDisplayOverride.user_id == user_id,
            UserGlossaryDisplayOverride.novel_id == novel_id,
        )
        if enabled is not None:
            stmt = stmt.where(UserGlossaryDisplayOverride.enabled == enabled)
        stmt = stmt.order_by(UserGlossaryDisplayOverride.glossary_entry_id)
        return list(self.db.scalars(stmt))

    def disable_user_display_override(
        self,
        *,
        user_id: int,
        novel_id: int,
        entry_id: int,
    ) -> UserGlossaryDisplayOverride | None:
        override = self.db.scalar(
            select(UserGlossaryDisplayOverride).where(
                UserGlossaryDisplayOverride.user_id == user_id,
                UserGlossaryDisplayOverride.novel_id == novel_id,
                UserGlossaryDisplayOverride.glossary_entry_id == entry_id,
            )
        )
        if override is None:
            return None
        override.enabled = False
        self.db.flush()
        return override

    def _increment_glossary_revision(self, novel_id: int) -> None:
        """Increment novels.glossary_revision within the current transaction.

        Raises LookupError if the novel row is not found so that the entire
        caller's transaction is rolled back rather than silently leaving the
        revision out of sync.
        """
        from novelai.db.models.novel import Novel
        from novelai.services.glossary_service import GlossaryService

        novel = self.db.get(Novel, novel_id)
        if novel is None:
            raise LookupError(f"Novel {novel_id} not found during revision increment")
        novel.glossary_revision += 1
        self.db.flush()

        # Invalidate translation cache for this novel
        GlossaryService.invalidate(str(novel_id))

    def _require_entry(self, entry_id: int, *, novel_id: int | None = None) -> NovelGlossaryEntry:
        entry = self.get_glossary_entry(entry_id, novel_id=novel_id)
        if entry is None:
            scope = f" for novel {novel_id}" if novel_id is not None else ""
            raise LookupError(f"Glossary entry {entry_id} was not found{scope}")
        return entry

    def _require_entry_global(self, entry_id: int) -> NovelGlossaryEntry:
        """Fetch a global-scope entry by ID, checking scope matches."""
        entry = self.db.get(NovelGlossaryEntry, entry_id)
        if entry is None or entry.scope != NovelGlossaryEntry.SCOPE_GLOBAL:
            raise LookupError(f"Global glossary entry {entry_id} was not found")
        return entry

    def _require_alias(self, alias_id: int, *, novel_id: int) -> NovelGlossaryAlias:
        alias = self.db.scalar(
            select(NovelGlossaryAlias).where(
                NovelGlossaryAlias.id == alias_id,
                NovelGlossaryAlias.novel_id == novel_id,
            )
        )
        if alias is None:
            raise LookupError(f"Glossary alias {alias_id} was not found for novel {novel_id}")
        return alias

    @staticmethod
    def _validate_entry_status(status: str) -> None:
        if status not in ENTRY_STATUSES:
            raise ValueError(f"Unsupported glossary entry status: {status}")

    @staticmethod
    def _validate_alias_type(alias_type: str) -> None:
        if alias_type not in ALIAS_TYPES:
            raise ValueError(f"Unsupported glossary alias type: {alias_type}")
