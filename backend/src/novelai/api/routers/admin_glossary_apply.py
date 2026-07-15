"""Admin glossary apply endpoints — extracted from admin_glossary.py.

Apply preview/commit/rollback and chapter version activation endpoints.
CRUD, candidates, provider, and suggestion endpoints are in other split files.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session, get_orchestrator, get_storage
from novelai.api.schemas.admin_glossary import (
    ChapterApplyResultResponse,
    ChapterVersionActivateResponse,
    GlossaryApplyCommitRequest,
    GlossaryApplyCommitResponse,
    GlossaryApplyPreviewRequest,
    GlossaryApplyPreviewResponse,
    GlossaryApplyRollbackRequest,
    GlossaryApplyRollbackResponse,
    GlossaryChapterApplyPreviewResponse,
    GlossaryReplacementPreviewResponse,
    _require_novel,
)
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewRequest as ApplyPreviewServiceRequest,
)
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewResult as ApplyPreviewServiceResult,
)
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewService,
)
from novelai.services.library_summary_service import best_effort_invalidate

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


def _apply_preview_response(result: ApplyPreviewServiceResult) -> GlossaryApplyPreviewResponse:
    return GlossaryApplyPreviewResponse(
        novel_id=result.novel_id,
        scanned_chapter_count=result.scanned_chapter_count,
        matched_chapter_count=result.matched_chapter_count,
        skipped_chapter_count=result.skipped_chapter_count,
        total_match_count=result.total_match_count,
        safe_match_count=result.safe_match_count,
        needs_review_match_count=result.needs_review_match_count,
        blocked_match_count=result.blocked_match_count,
        entry_count=result.entry_count,
        warnings=result.warnings,
        chapters=[
            GlossaryChapterApplyPreviewResponse(
                chapter_storage_id=chapter.chapter_storage_id,
                chapter_id=chapter.chapter_id,
                chapter_number=chapter.chapter_number,
                replacement_count=chapter.replacement_count,
                safe_count=chapter.safe_count,
                needs_review_count=chapter.needs_review_count,
                blocked_count=chapter.blocked_count,
                replacements=[
                    GlossaryReplacementPreviewResponse(
                        glossary_entry_id=replacement.glossary_entry_id,
                        canonical_term=replacement.canonical_term,
                        old_text=replacement.old_text,
                        new_text=replacement.new_text,
                        risk_status=replacement.risk_status,
                        reason_codes=replacement.reason_codes,
                        note=replacement.note,
                        start_offset=replacement.start_offset,
                        end_offset=replacement.end_offset,
                        before_snippet=replacement.before_snippet,
                        after_snippet=replacement.after_snippet,
                    )
                    for replacement in chapter.replacements
                ],
                delta_fraction=chapter.delta_fraction,
            )
            for chapter in result.chapters
        ],
    )


@router.post(
    "/novels/{novel_id}/glossary/apply/preview",
    response_model=GlossaryApplyPreviewResponse,
)
async def preview_glossary_apply(
    novel_id: str,
    body: GlossaryApplyPreviewRequest,
    session: Session = Depends(get_db_session),
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyPreviewResponse:
    if not body.entry_ids and not body.include_all_approved:
        raise HTTPException(status_code=422, detail="entry_ids or include_all_approved is required.")
    novel = _require_novel(session, novel_id)
    try:
        result = GlossaryApplyPreviewService(session, storage).preview(
            novel.id,
            ApplyPreviewServiceRequest(
                entry_ids=body.entry_ids,
                include_all_approved=body.include_all_approved,
                chapter_numbers=body.chapter_numbers,
                chapter_start=body.chapter_start,
                chapter_end=body.chapter_end,
                max_chapters=body.max_chapters,
                max_matches=body.max_matches,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _apply_preview_response(result)


@router.post(
    "/novels/{novel_id}/glossary/apply/commit",
    response_model=GlossaryApplyCommitResponse,
)
async def commit_glossary_apply(
    novel_id: str,
    body: GlossaryApplyCommitRequest,
    session: Session = Depends(get_db_session),
    storage: Any = Depends(get_storage),
    orchestrator=Depends(get_orchestrator),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyCommitResponse:
    if not body.entry_ids and not body.include_all_approved:
        raise HTTPException(status_code=422, detail="entry_ids or include_all_approved is required.")
    novel = _require_novel(session, novel_id)
    try:
        result = GlossaryApplyPreviewService(session, storage).preview(
            novel.id,
            ApplyPreviewServiceRequest(
                entry_ids=body.entry_ids,
                include_all_approved=body.include_all_approved,
                chapter_numbers=body.chapter_numbers,
                chapter_start=body.chapter_start,
                chapter_end=body.chapter_end,
                max_chapters=body.max_chapters,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.dry_run:
        return GlossaryApplyCommitResponse(
            novel_id=novel_id,
            dry_run=True,
            batch_id=body.batch_id,
            glossary_revision=getattr(novel, "glossary_revision", 0) or 0,
            chapters=[
                ChapterApplyResultResponse(
                    chapter_id=ch.chapter_storage_id,
                    status="skipped" if ch.safe_count == 0 else "applied",
                    replacements_made=max(ch.safe_count, ch.needs_review_count),
                    delta_fraction=ch.delta_fraction,
                )
                for ch in result.chapters
            ],
            total_applied=sum(1 for ch in result.chapters if ch.safe_count > 0),
            total_skipped=sum(1 for ch in result.chapters if ch.safe_count == 0),
            total_blocked=0,
            total_failed=0,
            message="Dry-run completed. Set dry_run=false to apply.",
        )

    apply_result = await orchestrator.apply_glossary_to_chapters(
        novel_id,
        entry_ids=body.entry_ids,
        include_all_approved=body.include_all_approved,
        chapter_numbers=body.chapter_numbers,
        chapter_start=body.chapter_start,
        chapter_end=body.chapter_end,
        max_chapters=body.max_chapters,
        dry_run=False,
        max_delta_fraction=body.max_delta_fraction,
        force_needs_review=body.force_needs_review,
        batch_id=body.batch_id,
    )

    return GlossaryApplyCommitResponse(
        novel_id=apply_result.novel_id,
        dry_run=False,
        batch_id=apply_result.batch_id,
        glossary_revision=apply_result.glossary_revision,
        chapters=[
            ChapterApplyResultResponse(
                chapter_id=ch.chapter_id,
                status=ch.status,
                replacements_made=ch.replacements_made,
                delta_fraction=ch.delta_fraction,
                new_version_id=ch.new_version_id,
                previous_version_id=ch.previous_version_id,
                block_reason=ch.block_reason,
                error=ch.error,
            )
            for ch in apply_result.chapters
        ],
        total_applied=apply_result.total_applied,
        total_skipped=apply_result.total_skipped,
        total_blocked=apply_result.total_blocked,
        total_failed=apply_result.total_failed,
        message="Glossary apply completed.",
    )


@router.post(
    "/novels/{novel_id}/glossary/apply/rollback",
    response_model=GlossaryApplyRollbackResponse,
)
async def rollback_glossary_apply(
    novel_id: str,
    body: GlossaryApplyRollbackRequest,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyRollbackResponse:
    """Revert all glossary-apply versions created in a given batch.

    Uses batch_id that was recorded when the apply was committed.
    """
    from novelai.core.platform import ChapterVersionKind

    meta = storage.load_metadata(novel_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Novel metadata not found.")

    chapter_ids = meta.get("chapter_ids", []) if isinstance(meta, dict) else []
    reverted: list[ChapterApplyResultResponse] = []

    for ch_id in chapter_ids:
        translated = storage.load_translated_chapter(novel_id, ch_id)
        if not translated:
            continue
        batch_id = translated.get("batch_id")
        if batch_id != body.batch_id:
            continue
        version_kind = translated.get("version_kind")
        if version_kind != ChapterVersionKind.GLOSSARY_APPLY.value:
            continue
        prev_version_id = translated.get("base_version_id") or translated.get("previous_version_id")
        if prev_version_id:
            try:
                storage.activate_translated_chapter_version(
                    novel_id,
                    ch_id,
                    prev_version_id,
                )
                reverted.append(
                    ChapterApplyResultResponse(
                        chapter_id=ch_id,
                        status="reverted",
                        replacements_made=0,
                        delta_fraction=0.0,
                        new_version_id=prev_version_id,
                        previous_version_id=translated.get("version_id"),
                    )
                )
            except Exception as exc:
                reverted.append(
                    ChapterApplyResultResponse(
                        chapter_id=ch_id,
                        status="failed",
                        replacements_made=0,
                        delta_fraction=0.0,
                        error=str(exc),
                    )
                )

    return GlossaryApplyRollbackResponse(
        novel_id=novel_id,
        batch_id=body.batch_id,
        reverted_chapters=reverted,
        total_reverted=len(reverted),
        message=f"Rollback completed. {len(reverted)} chapters reverted.",
    )


@router.post(
    "/novels/{novel_id}/glossary/apply/chapters/{chapter_id}/versions/{version_id}/activate",
    response_model=ChapterVersionActivateResponse,
)
async def activate_chapter_version(
    novel_id: str,
    chapter_id: str,
    version_id: str,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> ChapterVersionActivateResponse:
    """Activate a specific translation version for a chapter."""
    try:
        storage.activate_translated_chapter_version(novel_id, chapter_id, version_id)
        # Invalidate library summary cache after successful activation
        best_effort_invalidate()
        return ChapterVersionActivateResponse(
            novel_id=novel_id,
            chapter_storage_id=chapter_id,
            version_id=version_id,
            activated=True,
            message="Version activated.",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
