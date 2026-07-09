from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.response_helpers import translated_chapter_response, translation_provider_response
from novelai.api.routers.dependencies import _rate_limit, get_db_session, get_storage
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

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


class TranslationEditRequest(BaseModel):
    text: str
    editor: str | None = None
    note: str | None = None
    lint: bool | None = None
    source_text: str | None = None
    glossary_override: dict[str, Any] | None = None


class TranslationRollbackRequest(BaseModel):
    version_id: str
    editor: str | None = None
    note: str | None = None


class GlossaryLintRequest(BaseModel):
    text: str
    source_text: str | None = None
    max_terms: int | None = Field(default=None, ge=1, le=500)


def _resolve_platform_novel_id(db: Session, novel_slug: str) -> int | None:
    """Resolve slug to platform novel ID via DB. Returns None if not found."""
    try:
        from sqlalchemy import select

        from novelai.db.models.novel import Novel

        novel = db.execute(select(Novel).where(Novel.slug == novel_slug)).scalar_one_or_none()
        if novel is not None:
            return int(novel.id)
        if novel_slug.isdigit():
            novel = db.get(Novel, int(novel_slug))
            if novel is not None:
                return int(novel.id)
    except Exception:
        return None
    return None


def _run_qa(
    db: Session,
    novel_slug: str,
    chapter_id: str,
    edited_text: str,
    source_text: str | None,
    max_terms: int = 50,
) -> GlossaryQAResult:
    """Run glossary QA, returning an advisory result if glossary is unavailable."""
    platform_id = _resolve_platform_novel_id(db, novel_slug)
    if platform_id is None:
        return make_advisory_unavailable(novel_slug, chapter_id)

    repo = GlossaryRepository(db)
    service = GlossaryEditorQAService(repository=repo)
    return service.check_edit(
        platform_novel_id=platform_id,
        novel_slug=novel_slug,
        chapter_id=chapter_id,
        edited_text=edited_text,
        source_text=source_text,
        max_terms=max_terms,
    )


def _log_qa_event(
    novel_slug: str,
    chapter_id: str,
    platform_id: int | None,
    result: GlossaryQAResult,
    elapsed_ms: int,
) -> None:
    """Log a structured QA event without leaking text content."""
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


def _validate_override(override: dict[str, Any] | None) -> tuple[bool, str]:
    """Validate override payload shape. Returns (valid, reason)."""
    if not isinstance(override, dict):
        return False, "Override payload must be an object."
    reason = override.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False, "Override reason is required."
    issue_ids = override.get("issue_ids")
    if issue_ids is not None and not isinstance(issue_ids, list):
        return False, "Override issue_ids must be a list."
    return True, ""


def _compact_qa_summary(result: GlossaryQAResult) -> dict[str, Any]:
    """Build a compact QA summary for persistence (no full text)."""
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


@router.get("/{novel_id}/chapters/{chapter_id}/translated/versions")
async def list_translated_chapter_versions(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    versions = storage.list_translated_chapter_versions(novel_id, chapter_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "versions": [translation_provider_response(version) for version in versions],
    }


@router.get("/{novel_id}/chapters/{chapter_id}/translated/edit-history")
async def get_translation_edit_history(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if storage.load_translated_chapter(novel_id, chapter_id) is None:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "history": storage.load_translation_edit_history(novel_id, chapter_id),
    }


@router.post("/{novel_id}/chapters/{chapter_id}/translated/lint")
async def lint_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: GlossaryLintRequest,
    db: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    """Preview glossary QA without saving."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    start = time.monotonic()
    result = _run_qa(
        db, novel_id, chapter_id, body.text, body.source_text,
        max_terms=body.max_terms or 50,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    _log_qa_event(novel_id, chapter_id, result.platform_novel_id, result, elapsed_ms)
    return {"glossary_qa": result.to_dict()}


@router.put("/{novel_id}/chapters/{chapter_id}/translated")
async def update_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationEditRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if storage.load_chapter(novel_id, chapter_id) is None and storage.load_translated_chapter(novel_id, chapter_id) is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Translated text cannot be empty")

    # Run QA if lint requested or override provided
    qa_result: GlossaryQAResult | None = None
    if body.lint or body.glossary_override:
        start = time.monotonic()
        qa_result = _run_qa(db, novel_id, chapter_id, text, body.source_text)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log_qa_event(novel_id, chapter_id, qa_result.platform_novel_id, qa_result, elapsed_ms)

        # Validate override payload
        if body.glossary_override is not None:
            valid, reason = _validate_override(body.glossary_override)
            if not valid:
                raise HTTPException(status_code=400, detail=reason)

        # Check blocking
        if qa_result.status == STATUS_BLOCKED:
            if body.glossary_override is None:
                logger.warning(
                    "glossary_editor_qa_blocked",
                    extra={
                        "event": "glossary_editor_qa_blocked",
                        "novel_id": novel_id,
                        "chapter_id": chapter_id,
                        "issue_count": qa_result.issue_count,
                    },
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Glossary QA blocked save.",
                        "glossary_qa": qa_result.to_dict(),
                    },
                )
            # Authorized override: mark as overridden
            qa_result = GlossaryEditorQAService().apply_override(qa_result)
            logger.info(
                "glossary_editor_qa_override",
                extra={
                    "event": "glossary_editor_qa_override",
                    "novel_id": novel_id,
                    "chapter_id": chapter_id,
                    "actor_user_id": getattr(owner, "user_id", None),
                    "reason": body.glossary_override.get("reason", "")[:200],
                },
            )

    # Build QA summary for persistence
    qa_summary: dict[str, Any] | None = None
    glossary_revision: int | None = None
    if qa_result is not None:
        qa_summary = _compact_qa_summary(qa_result)
        glossary_revision = qa_result.glossary_revision
        if body.glossary_override and qa_result.status == STATUS_OVERRIDDEN:
            qa_summary["override"] = {
                "user_id": getattr(owner, "user_id", None),
                "reason": body.glossary_override.get("reason", ""),
                "issue_ids": body.glossary_override.get("issue_ids", []),
                "created_at": utc_now_iso(),
            }

    storage.save_edited_translation(
        novel_id,
        chapter_id,
        text,
        editor=body.editor,
        note=body.note,
        glossary_qa=qa_summary,
        glossary_revision=glossary_revision,
    )
    safely_refresh_catalog_projection_after_storage_write(
        novel_id,
        storage,
        context="editor_update_translation",
        session=db,
    )
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=500, detail="Edited translation could not be loaded")
    response = translated_chapter_response(novel_id, chapter_id, translated)
    if qa_result is not None and body.lint:
        response["glossary_qa"] = qa_result.to_dict()
    return response


@router.post("/{novel_id}/chapters/{chapter_id}/translated/rollback")
async def rollback_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationRollbackRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if not storage.activate_translated_chapter_version(
        novel_id,
        chapter_id,
        body.version_id,
        editor=body.editor,
        note=body.note,
    ):
        raise HTTPException(status_code=404, detail="Translation version not found")
    safely_refresh_catalog_projection_after_storage_write(
        novel_id,
        storage,
        context="editor_rollback_translation",
        session=db,
    )
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=500, detail="Rolled back translation could not be loaded")
    return translated_chapter_response(novel_id, chapter_id, translated)
