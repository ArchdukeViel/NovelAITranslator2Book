"""Workflow service for glossary management operations.

Encapsulates glossary CRUD, alias, provenance, QA, batch, sync, and
status transition operations behind a single service boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.glossary_status_service import GlossaryStatusService
from novelai.services.glossary_sync_service import GlossarySyncService
from novelai.storage.service import StorageService


class GlossaryWorkflowService:
    """Consolidated workflow service for glossary management.

    Wraps GlossaryRepository, GlossaryStatusService, GlossarySyncService,
    and direct DB/storage access behind a single boundary.
    """

    def __init__(
        self,
        *,
        storage: StorageService,
        db_session: Session,
        glossary_repository: GlossaryRepository | None = None,
    ) -> None:
        self._storage = storage
        self._db = db_session
        self._repo = glossary_repository or GlossaryRepository(db_session)
        self._last_sync_timestamps: dict[str, str] = {}

    # ── helpers ──

    def _require_novel(self, novel_ref: str) -> Novel:
        novel = self._db.execute(select(Novel).where(Novel.slug == novel_ref)).scalar_one_or_none()
        if novel is None and novel_ref.isdigit():
            novel = self._db.get(Novel, int(novel_ref))
        if novel is None:
            raise ValueError("Novel not found")
        return novel

    # ── entry CRUD ──

    def list_glossary_entries(
        self,
        novel_id: str,
        *,
        status: str | None = None,
        term_type: str | None = None,
        public_visible: bool | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.list_glossary_entries_for_novel(
            novel_key,
            status=status,
            term_type=term_type,
            public_visible=public_visible,
        )

    def create_glossary_entry(
        self,
        novel_id: str,
        *,
        scope: str,
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
        decision_source: str = "owner",
        rationale: str | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.create_glossary_entry(
            novel_id=novel_key,
            scope=scope,
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
            actor_user_id=actor_user_id,
            decision_source=decision_source,
            rationale=rationale,
        )

    def get_glossary_entry(self, novel_id: str, entry_id: int):
        novel_key = self._require_novel(novel_id).id
        entry = self._repo.get_glossary_entry(entry_id, novel_id=novel_key)
        if entry is None:
            raise LookupError("Glossary entry not found")
        return entry

    def update_glossary_entry(
        self,
        novel_id: str,
        entry_id: int,
        *,
        actor_user_id: int | None = None,
        **fields: Any,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.update_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            **fields,
        )

    def change_glossary_entry_status(
        self,
        novel_id: str,
        entry_id: int,
        *,
        status: str,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.change_glossary_entry_status(
            entry_id,
            novel_id=novel_key,
            status=status,
            actor_user_id=actor_user_id,
            rationale=rationale,
            decision_source="owner",
        )

    def lock_glossary_entry(
        self,
        novel_id: str,
        entry_id: int,
        *,
        rationale: str | None = None,
        actor_user_id: int | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.lock_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            rationale=rationale,
        )

    def unlock_glossary_entry(
        self,
        novel_id: str,
        entry_id: int,
        *,
        rationale: str | None = None,
        actor_user_id: int | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.unlock_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            rationale=rationale,
        )

    def deprecate_glossary_entry(
        self,
        novel_id: str,
        entry_id: int,
        *,
        rationale: str | None = None,
        actor_user_id: int | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.deprecate_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            rationale=rationale,
        )

    # ── approve translation change ──

    def approve_translation_change(
        self,
        novel_id: str,
        entry_id: int,
        *,
        new_translation: str,
        rationale: str | None = None,
        actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        novel_key = self._require_novel(novel_id).id
        from novelai.db.models.glossary import NovelGlossaryEntry

        entry = self._db.get(NovelGlossaryEntry, entry_id)
        if entry is None:
            raise LookupError("Glossary entry not found")
        if entry.scope == "novel" and entry.novel_id != novel_key:
            raise LookupError("Entry does not belong to this novel")
        if entry.owner_locked and actor_user_id is None:
            raise LookupError("Owner-locked entry requires owner permission")

        updated = self._repo.update_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            approved_translation=new_translation,
        )
        self._repo.create_decision_event(
            novel_id=novel_key,
            event_type="approve",
            glossary_entry_id=entry_id,
            actor_user_id=actor_user_id,
            old_value={"approved_translation": entry.approved_translation},
            new_value={"approved_translation": new_translation},
            rationale=rationale,
            decision_source="owner",
        )

        novel = self._db.get(Novel, novel_key)
        return {
            "entry": updated,
            "glossary_revision": int(novel.glossary_revision) if novel else None,
        }

    # ── alias operations ──

    def list_glossary_aliases(self, novel_id: str, entry_id: int):
        novel_key = self._require_novel(novel_id).id
        return self._repo.list_aliases_for_entry(entry_id, novel_id=novel_key)

    def add_glossary_alias(
        self,
        novel_id: str,
        entry_id: int,
        *,
        alias_text: str,
        alias_type: str = "observed",
        language: str | None = None,
        text_origin: str | None = None,
        applies_to: str | None = None,
        matching_policy: str | None = None,
        notes: str | None = None,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.add_glossary_alias(
            entry_id=entry_id,
            novel_id=novel_key,
            alias_text=alias_text,
            alias_type=alias_type,
            language=language,
            text_origin=text_origin,
            applies_to=applies_to,
            matching_policy=matching_policy,
            notes=notes,
            actor_user_id=actor_user_id,
            rationale=rationale,
        )

    def update_glossary_alias(
        self,
        novel_id: str,
        alias_id: int,
        *,
        actor_user_id: int | None = None,
        rationale: str | None = None,
        **fields: Any,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.update_glossary_alias(
            alias_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            rationale=rationale,
            **fields,
        )

    def deprecate_glossary_alias(
        self,
        novel_id: str,
        alias_id: int,
        *,
        rationale: str | None = None,
        actor_user_id: int | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.remove_or_deprecate_glossary_alias(
            alias_id,
            novel_id=novel_key,
            actor_user_id=actor_user_id,
            rationale=rationale,
        )

    # ── provenance operations ──

    def list_novel_provenance(self, novel_id: str):
        novel_key = self._require_novel(novel_id).id
        return self._repo.list_source_provenance_for_novel(novel_key)

    def list_entry_provenance(self, novel_id: str, entry_id: int):
        novel_key = self._require_novel(novel_id).id
        return self._repo.list_source_provenance_for_entry(entry_id, novel_id=novel_key)

    def add_provenance(self, novel_id: str, entry_id: int, *, source_site: str, source_adapter: str, **fields: Any):
        novel_key = self._require_novel(novel_id).id
        return self._repo.add_source_provenance(
            novel_id=novel_key,
            entry_id=entry_id,
            source_site=source_site,
            source_adapter=source_adapter,
            **fields,
        )

    # ── decision events ──

    def list_novel_decision_events(self, novel_id: str):
        novel_key = self._require_novel(novel_id).id
        return self._repo.list_decision_events_for_novel(novel_key)

    def list_entry_decision_events(self, novel_id: str, entry_id: int):
        novel_key = self._require_novel(novel_id).id
        return self._repo.list_decision_events_for_entry(entry_id, novel_id=novel_key)

    # ── QA operations ──

    def list_qa_findings(
        self,
        novel_id: str,
        *,
        chapter_id: int | None = None,
        status: str | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        if chapter_id is not None:
            return self._repo.list_qa_findings_for_chapter(chapter_id, novel_id=novel_key, status=status)
        return self._repo.list_qa_findings_for_novel(novel_key, status=status)

    def create_qa_finding(
        self,
        novel_id: str,
        *,
        finding_type: str,
        severity: str = "warning",
        status: str = "open",
        chapter_id: int | None = None,
        glossary_entry_id: int | None = None,
        matched_text: str | None = None,
        suggested_text: str | None = None,
        context_ref: str | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.create_qa_finding(
            novel_id=novel_key,
            finding_type=finding_type,
            severity=severity,
            status=status,
            chapter_id=chapter_id,
            glossary_entry_id=glossary_entry_id,
            matched_text=matched_text,
            suggested_text=suggested_text,
            context_ref=context_ref,
        )

    def update_qa_finding_status(
        self,
        novel_id: str,
        finding_id: int,
        *,
        status: str,
        reviewer_user_id: int | None = None,
        reviewer_notes: str | None = None,
    ):
        novel_key = self._require_novel(novel_id).id
        return self._repo.update_qa_finding_status(
            finding_id,
            novel_id=novel_key,
            status=status,
            reviewer_user_id=reviewer_user_id,
            reviewer_notes=reviewer_notes,
        )

    # ── batch operations ──

    def batch_approve_candidates(
        self,
        novel_id: str,
        *,
        rationale: str | None = None,
        actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        novel = self._require_novel(novel_id)
        approved_count = 0
        for entry in self._repo.list_glossary_entries_for_novel(novel.id):
            if entry.status not in {"candidate", "recommended"}:
                continue
            if not isinstance(entry.approved_translation, str) or not entry.approved_translation.strip():
                self._repo.update_glossary_entry(
                    entry.id,
                    novel_id=novel.id,
                    approved_translation=entry.canonical_term,
                    actor_user_id=actor_user_id,
                )
            self._repo.change_glossary_entry_status(
                entry.id,
                novel_id=novel.id,
                status="approved",
                actor_user_id=actor_user_id,
                rationale=rationale or "Owner approved all glossary candidates during onboarding.",
                decision_source="owner",
            )
            approved_count += 1
        updated = GlossaryStatusService(self._db).transition_status(
            novel.slug,
            target_status="glossary_ready",
            actor_user_id=actor_user_id,
        )
        return {
            "novel": updated,
            "approved_count": approved_count,
        }

    # ── status transition ──

    def transition_glossary_status(
        self,
        novel_id: str,
        *,
        target_status: str,
        actor_user_id: int | None = None,
    ):
        return GlossaryStatusService(self._db).transition_status(
            novel_id,
            target_status=target_status,
            actor_user_id=actor_user_id,
        )

    # ── sync operations ──

    def sync_from_file(self, novel_id: str, *, dry_run: bool = False):
        if self._storage.load_metadata(novel_id) is None:
            raise LookupError("Novel not found in storage")
        return GlossarySyncService(self._repo, self._storage).sync_from_file(novel_id, dry_run=dry_run)

    def record_sync_timestamp(self, novel_id: str) -> None:
        self._last_sync_timestamps[novel_id] = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def get_last_sync_timestamp(self, novel_id: str) -> str | None:
        return self._last_sync_timestamps.get(novel_id)

    def get_sync_status(self, novel_id: str) -> dict[str, Any]:
        from novelai.db.models.novel import Novel

        file_entries = self._storage.load_glossary(novel_id)
        file_approved_count = sum(
            1
            for e in file_entries
            if isinstance(e, dict) and str(e.get("status") or "").strip().lower() == "approved"
        )
        novel_row = self._db.query(Novel).filter(Novel.slug == novel_id).one_or_none()
        db_approved_count = 0
        if novel_row is not None:
            db_approved_count = len(self._repo.list_glossary_entries_for_novel(novel_row.id, status="approved"))
        in_sync = file_approved_count == db_approved_count and db_approved_count > 0

        if in_sync:
            recommendation = "healthy"
        elif file_approved_count > 0 and db_approved_count == 0:
            recommendation = "sync_required"
        elif file_approved_count == 0 and db_approved_count == 0:
            recommendation = "empty"
        else:
            recommendation = "sync_required"

        return {
            "novel_id": novel_id,
            "file_approved_count": file_approved_count,
            "db_approved_count": db_approved_count,
            "in_sync": in_sync,
            "last_sync_at": self._last_sync_timestamps.get(novel_id),
            "recommendation": recommendation,
        }

    # ── global glossary operations ──

    def list_global_glossary_entries(
        self,
        *,
        status: str | None = None,
        term_type: str | None = None,
        public_visible: bool | None = None,
    ):
        return self._repo.list_glossary_entries_global(
            status=status,
            term_type=term_type,
            public_visible=public_visible,
        )

    def create_global_glossary_entry(
        self,
        *,
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
        decision_source: str = "owner",
        rationale: str | None = None,
    ):
        return self._repo.create_glossary_entry(
            novel_id=None,
            scope="global",
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
            actor_user_id=actor_user_id,
            decision_source=decision_source,
            rationale=rationale,
        )

    def get_global_glossary_entry(self, entry_id: int):
        return self._repo._require_entry_global(entry_id)

    def update_global_glossary_entry(
        self,
        entry_id: int,
        *,
        actor_user_id: int | None = None,
        **fields: Any,
    ):
        return self._repo.update_glossary_entry(
            entry_id,
            novel_id=None,
            actor_user_id=actor_user_id,
            **fields,
        )

    def change_global_glossary_entry_status(
        self,
        entry_id: int,
        *,
        status: str,
        actor_user_id: int | None = None,
        rationale: str | None = None,
    ):
        return self._repo.change_glossary_entry_status(
            entry_id,
            novel_id=None,
            status=status,
            actor_user_id=actor_user_id,
            rationale=rationale,
        )
