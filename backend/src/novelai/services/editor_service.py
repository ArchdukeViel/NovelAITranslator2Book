"""Translation editor orchestration — editing, QA, versioning, rollback.

Separated from the HTTP adapter to keep editing logic testable
without a running server.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.glossary_editor_qa_service import (
    STATUS_BLOCKED,
    STATUS_OVERRIDDEN,
    GlossaryEditorQAService,
    GlossaryQAResult,
    make_advisory_unavailable,
    utc_now_iso,
)
from novelai.services.glossary_repository import GlossaryRepository
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)


class EditorService:
    """Business logic for translation editing, QA, versioning, and rollback."""

    def __init__(
        self, *, storage: StorageService, db_session: Session | None = None
    ) -> None:
        self.storage = storage
        self.db_session = db_session

    # -- platform novel ID resolution -------------------------------------------

    def resolve_platform_novel_id(self, novel_slug: str) -> int | None:
        if self.db_session is None:
            return None
        try:
            novel = self.db_session.execute(
                select(Novel).where(Novel.slug == novel_slug)
            ).scalar_one_or_none()
            if novel is not None:
                return int(novel.id)
            if novel_slug.isdigit():
                novel = self.db_session.get(Novel, int(novel_slug))
                if novel is not None:
                    return int(novel.id)
        except Exception:
            return None
        return None

    # -- QA orchestration -------------------------------------------------------

    def check_edit(
        self,
        novel_slug: str,
        chapter_id: str,
        edited_text: str,
        source_text: str | None,
        max_terms: int = 50,
    ) -> GlossaryQAResult:
        platform_id = self.resolve_platform_novel_id(novel_slug)
        if platform_id is None:
            return make_advisory_unavailable(novel_slug, chapter_id)
        if self.db_session is None:
            return make_advisory_unavailable(novel_slug, chapter_id)
        repo = GlossaryRepository(self.db_session)
        service = GlossaryEditorQAService(repository=repo)
        return service.check_edit(
            platform_novel_id=platform_id,
            novel_slug=novel_slug,
            chapter_id=chapter_id,
            edited_text=edited_text,
            source_text=source_text,
            max_terms=max_terms,
        )

    def log_qa_event(
        self,
        novel_slug: str,
        chapter_id: str,
        platform_id: int | None,
        result: GlossaryQAResult,
        elapsed_ms: int,
    ) -> None:
        logger.info(
            "glossary_editor_qa",
            extra={
                "event": "glossary_editor_qa",
                "novel_id": novel_slug,
                "chapter_id": chapter_id,
                "platform_novel_id": platform_id,
                "glossary_revision": result.glossary_revision,
                "checked_terms": result.checked_terms,
                "issue_count": result.issue_count,
                "status": result.status,
                "elapsed_ms": elapsed_ms,
            },
        )

    @staticmethod
    def validate_override(override: dict[str, Any] | None) -> tuple[bool, str]:
        if not isinstance(override, dict):
            return False, "Override payload must be an object."
        reason = override.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return False, "Override reason is required."
        issue_ids = override.get("issue_ids")
        if issue_ids is not None and not isinstance(issue_ids, list):
            return False, "Override issue_ids must be a list."
        return True, ""

    @staticmethod
    def compact_qa_summary(result: GlossaryQAResult) -> dict[str, Any]:
        return {
            "status": result.status,
            "glossary_revision": result.glossary_revision,
            "checked_terms": result.checked_terms,
            "issue_count": result.issue_count,
            "has_errors": result.has_errors,
            "has_warnings": result.has_warnings,
            "issues": [
                {
                    "issue_id": i.issue_id,
                    "entry_id": i.entry_id,
                    "canonical_term": i.canonical_term,
                    "approved_translation": i.approved_translation,
                    "severity": i.severity,
                    "code": i.code,
                }
                for i in result.issues
            ],
        }

    # -- storage operations -----------------------------------------------------

    def get_translated_chapter_versions(
        self, novel_id: str, chapter_id: str
    ) -> dict[str, Any] | None:
        if self.storage.load_metadata(novel_id) is None:
            return None
        versions = self.storage.list_translated_chapter_versions(novel_id, chapter_id)
        if not versions:
            return None
        return {
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "versions": versions,
        }

    def get_translation_edit_history(
        self, novel_id: str, chapter_id: str
    ) -> dict[str, Any] | None:
        if self.storage.load_metadata(novel_id) is None:
            return None
        if self.storage.load_translated_chapter(novel_id, chapter_id) is None:
            return None
        return {
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "history": self.storage.load_translation_edit_history(novel_id, chapter_id),
        }

    def update_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        *,
        editor: str | None = None,
        note: str | None = None,
        lint: bool | None = None,
        source_text: str | None = None,
        glossary_override: dict[str, Any] | None = None,
        owner_user_id: int | None = None,
    ) -> dict[str, Any]:
        if self.storage.load_metadata(novel_id) is None:
            raise ValueError("Novel not found")
        if (
            self.storage.load_chapter(novel_id, chapter_id) is None
            and self.storage.load_translated_chapter(novel_id, chapter_id) is None
        ):
            raise ValueError("Chapter not found")

        text = text.strip()
        if not text:
            raise ValueError("Translated text cannot be empty")

        qa_result: GlossaryQAResult | None = None
        if lint or glossary_override:
            start = time.monotonic()
            qa_result = self.check_edit(novel_id, chapter_id, text, source_text)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.log_qa_event(
                novel_id, chapter_id,
                qa_result.platform_novel_id, qa_result, elapsed_ms,
            )

            if glossary_override is not None:
                valid, reason = self.validate_override(glossary_override)
                if not valid:
                    raise ValueError(reason)

            if qa_result.status == STATUS_BLOCKED:
                if glossary_override is None:
                    logger.warning(
                        "glossary_editor_qa_blocked",
                        extra={
                            "event": "glossary_editor_qa_blocked",
                            "novel_id": novel_id,
                            "chapter_id": chapter_id,
                            "issue_count": qa_result.issue_count,
                        },
                    )
                    raise ValueError({
                        "message": "Glossary QA blocked save.",
                        "glossary_qa": qa_result.to_dict(),
                    })

                qa_result = GlossaryEditorQAService().apply_override(qa_result)
                logger.info(
                    "glossary_editor_qa_override",
                    extra={
                        "event": "glossary_editor_qa_override",
                        "novel_id": novel_id,
                        "chapter_id": chapter_id,
                        "actor_user_id": owner_user_id,
                        "reason": glossary_override.get("reason", "")[:200],
                    },
                )

        qa_summary: dict[str, Any] | None = None
        glossary_revision: int | None = None
        if qa_result is not None:
            qa_summary = self.compact_qa_summary(qa_result)
            glossary_revision = qa_result.glossary_revision
            if glossary_override and qa_result.status == STATUS_OVERRIDDEN:
                qa_summary["override"] = {
                    "user_id": owner_user_id,
                    "reason": glossary_override.get("reason", ""),
                    "issue_ids": glossary_override.get("issue_ids", []),
                    "created_at": utc_now_iso(),
                }

        self.storage.save_edited_translation(
            novel_id, chapter_id, text,
            editor=editor, note=note,
            glossary_qa=qa_summary,
            glossary_revision=glossary_revision,
        )
        safely_refresh_catalog_projection_after_storage_write(
            novel_id, self.storage,
            context="editor_update_translation",
            session=self.db_session,
        )

        translated = self.storage.load_translated_chapter(novel_id, chapter_id)
        if translated is None:
            raise ValueError("Edited translation could not be loaded")

        response: dict[str, Any] = translated
        if qa_result is not None and lint:
            response["glossary_qa"] = qa_result.to_dict()
        return response

    def rollback_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        version_id: str,
        *,
        editor: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        if self.storage.load_metadata(novel_id) is None:
            raise ValueError("Novel not found")
        if not self.storage.activate_translated_chapter_version(
            novel_id, chapter_id, version_id,
            editor=editor, note=note,
        ):
            raise ValueError("Translation version not found")
        safely_refresh_catalog_projection_after_storage_write(
            novel_id, self.storage,
            context="editor_rollback_translation",
            session=self.db_session,
        )
        translated = self.storage.load_translated_chapter(novel_id, chapter_id)
        if translated is None:
            raise ValueError("Rolled back translation could not be loaded")
        return translated
