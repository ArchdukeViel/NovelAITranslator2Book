"""Sync bridge between file-glossary and DB-glossary systems.

Promotes reviewed/approved file-glossary entries into the DB
NovelGlossaryEntry table so TranslateStage can inject them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

# Fields from file glossary entries that are promoted to DB entries.
# File glossary entries are dicts with at least: source, target, status.
_FILE_STATUS_APPROVED = "approved"
_FILE_STATUS_NEEDS_REVIEW = "needs_manual_review"
_ELIGIBLE_STATUSES = {_FILE_STATUS_APPROVED, _FILE_STATUS_NEEDS_REVIEW}


@dataclass
class GlossarySyncResult:
    """Result of a single sync_from_file call."""

    novel_id: str
    dry_run: bool
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    synced_terms: list[str] = field(default_factory=list)


class GlossarySyncService:
    """Promote file-glossary entries into the DB glossary table."""

    def __init__(
        self, repository: GlossaryRepository, storage: StorageService
    ) -> None:
        self.repository = repository
        self.storage = storage

    def sync_from_file(
        self,
        novel_id: str,
        *,
        actor_user_id: int | None = None,
        dry_run: bool = False,
    ) -> GlossarySyncResult:
        """Sync eligible file-glossary entries into the DB.

        Args:
            novel_id: The novel slug (string identifier used in file storage).
            actor_user_id: Optional user ID for audit trail.
            dry_run: When True, count operations without writing.

        Returns:
            GlossarySyncResult with counts of created/updated/skipped/errors.

        Raises:
            ValueError: When the novel slug does not have a DB row
                (``novel_not_in_db``).
        """
        # Load file entries
        entries = self.storage.load_glossary(novel_id)

        # Resolve platform_novel_id
        session: Session = self.repository.db
        novel_row: Novel | None = (
            session.query(Novel).filter(Novel.slug == novel_id).one_or_none()
        )
        if novel_row is None:
            raise ValueError("novel_not_in_db")

        platform_novel_id = novel_row.id

        result = GlossarySyncResult(novel_id=novel_id, dry_run=dry_run)

        # Pre-load existing DB entries for this novel
        existing_db_entries = {
            entry.canonical_term: entry
            for entry in self.repository.list_glossary_entries_for_novel(
                platform_novel_id
            )
        }

        # Filter and process eligible entries
        for entry in entries:
            if not isinstance(entry, dict):
                result.skipped += 1
                continue

            source = str(entry.get("source") or "").strip()
            if not source:
                result.skipped += 1
                continue

            file_status = str(entry.get("status") or "").strip().lower()
            if file_status not in _ELIGIBLE_STATUSES:
                result.skipped += 1
                continue

            try:
                existing = existing_db_entries.get(source)

                if existing is not None:
                    # Upsert path
                    if dry_run:
                        result.updated += 1
                        result.synced_terms.append(source)
                        continue

                    self._upsert_entry(existing, entry, file_status, actor_user_id)
                    result.updated += 1
                    result.synced_terms.append(source)
                else:
                    # Create path
                    if dry_run:
                        result.created += 1
                        result.synced_terms.append(source)
                        continue

                    self._create_entry(
                        platform_novel_id, entry, file_status, actor_user_id
                    )
                    result.created += 1
                    result.synced_terms.append(source)

            except Exception as exc:
                logger.warning("Sync error for term %r: %s", source, exc)
                result.errors.append({"term": source, "error": str(exc)})

        # Increment glossary revision once if any changes were made
        if not dry_run and (result.created + result.updated) > 0:
            self.repository._increment_glossary_revision(platform_novel_id)

        return result

    def _create_entry(
        self,
        platform_novel_id: int,
        file_entry: dict[str, Any],
        file_status: str,
        actor_user_id: int | None,
    ) -> None:
        """Create a new DB glossary entry from a file entry."""
        source = str(file_entry.get("source") or "").strip()
        target = str(file_entry.get("target") or "").strip()
        confidence_raw = file_entry.get("confidence")
        notes_raw = file_entry.get("notes")

        db_status = (
            "approved" if file_status == _FILE_STATUS_APPROVED else "candidate"
        )

        kwargs: dict[str, Any] = {
            "novel_id": platform_novel_id,
            "canonical_term": source,
            "term_type": "extracted",
            "approved_translation": target or None,
            "status": db_status,
            "admin_notes": str(notes_raw).strip() if notes_raw else None,
            "actor_user_id": actor_user_id,
            "decision_source": "file_glossary_sync",
            "rationale": "Promoted from file glossary review",
        }

        if isinstance(confidence_raw, (int, float)):
            kwargs["confidence"] = float(confidence_raw)

        self.repository.create_glossary_entry(**kwargs)

    def _upsert_entry(
        self,
        existing: Any,
        file_entry: dict[str, Any],
        file_status: str,
        actor_user_id: int | None,
    ) -> None:
        """Update an existing DB entry from a file entry (no downgrade)."""
        target = str(file_entry.get("target") or "").strip()
        confidence_raw = file_entry.get("confidence")
        notes_raw = file_entry.get("notes")

        fields: dict[str, Any] = {}

        if target:
            fields["approved_translation"] = target

        if notes_raw:
            fields["admin_notes"] = str(notes_raw).strip()

        if isinstance(confidence_raw, (int, float)):
            fields["confidence"] = float(confidence_raw)

        if fields:
            self.repository.update_glossary_entry(
                existing.id,
                novel_id=existing.novel_id,
                actor_user_id=actor_user_id,
                **fields,
            )

        # Handle status separately — update_glossary_entry rejects "status".
        # Only update status if existing is "candidate" — never downgrade
        # approved → candidate.  Set field directly rather than calling
        # change_glossary_entry_status so revision is bumped exactly once
        # (at the end of sync_from_file) not once per entry.
        needs_status_change = False
        if file_status == _FILE_STATUS_APPROVED:
            if existing.status != "approved":
                needs_status_change = True
        elif file_status == _FILE_STATUS_NEEDS_REVIEW and existing.status == "candidate":
            needs_status_change = True

        if needs_status_change:
            db_status = (
                "approved" if file_status == _FILE_STATUS_APPROVED else "candidate"
            )
            existing.status = db_status
            existing.updated_by_user_id = actor_user_id
            self.repository.db.flush()
