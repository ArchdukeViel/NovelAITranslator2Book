"""Admin glossary suggestion endpoints — extracted from admin_glossary.py.

Suggestion review endpoints (list/accept/reject/accept-all/reject-all).
CRUD, candidates, apply, and provider endpoints are in other split files.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.api.schemas.admin_glossary import _owner_user_id, _repo, _require_novel

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


class SuggestionResponse(BaseModel):
    id: str
    source_term: str
    occurrence_count: int
    chapter_count: int
    context_snippets: list[str] = Field(default_factory=list)
    source: str = "frequency"
    status: str = "pending"
    term_type: str = "character"
    confidence: float = 0.5
    approved_translation: str | None = None
    rejection_reason: str | None = None
    created_at: str = ""
    updated_at: str | None = None


class SuggestionAcceptRequest(BaseModel):
    modified_translation: str | None = None


class SuggestionRejectRequest(BaseModel):
    reason: str | None = None


class BulkActionResult(BaseModel):
    count: int
    items: list[SuggestionResponse]


def _suggestion_service(storage: Any = Depends(get_storage)) -> Any:
    from novelai.services.glossary.suggestion_service import GlossarySuggestionService

    return GlossarySuggestionService(base_dir=storage.base_dir)


@router.get("/novels/{novel_id}/glossary/suggestions", response_model=list[SuggestionResponse])
async def list_glossary_suggestions(
    novel_id: str,
    status: str | None = None,
    source: str | None = None,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> list[SuggestionResponse]:
    """List glossary suggestions for a novel with optional status/source filter."""
    _require_novel(session, novel_id)
    suggestions = sug_svc.list_suggestions(
        novel_id,
        status=status if status in ("pending", "accepted", "rejected") else None,
        source=source if source in ("frequency", "llm") else None,
    )
    return [SuggestionResponse(**s.model_dump(exclude_none=False)) for s in suggestions]


@router.post("/novels/{novel_id}/glossary/suggestions/{suggestion_id}/accept", response_model=SuggestionResponse)
async def accept_glossary_suggestion(
    novel_id: str,
    suggestion_id: str,
    body: SuggestionAcceptRequest,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    storage: Any = Depends(get_storage),
    owner=Depends(require_role("owner")),
) -> SuggestionResponse:
    """Accept a suggestion and add it as a glossary entry."""
    novel = _require_novel(session, novel_id)
    result = sug_svc.accept(novel_id, suggestion_id, modified_translation=body.modified_translation)
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")

    translation = result.approved_translation or result.source_term
    try:
        repo = _repo(session)
        repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term=result.source_term,
            term_type=result.term_type,
            approved_translation=translation,
            status="approved",
            confidence=result.confidence,
            actor_user_id=_owner_user_id(owner),
            decision_source="owner",
        )
        from novelai.services.translation_cache import TranslationCacheService
        with suppress(Exception):
            TranslationCacheService().invalidate(novel_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create glossary entry: {exc}") from exc

    return SuggestionResponse(**result.model_dump(exclude_none=False))


@router.post("/novels/{novel_id}/glossary/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
async def reject_glossary_suggestion(
    novel_id: str,
    suggestion_id: str,
    body: SuggestionRejectRequest,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> SuggestionResponse:
    """Reject a suggestion."""
    _require_novel(session, novel_id)
    result = sug_svc.reject(novel_id, suggestion_id, reason=body.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")
    return SuggestionResponse(**result.model_dump(exclude_none=False))


@router.post("/novels/{novel_id}/glossary/suggestions/accept-all", response_model=BulkActionResult)
async def accept_all_glossary_suggestions(
    novel_id: str,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> BulkActionResult:
    """Accept all pending suggestions."""
    _require_novel(session, novel_id)
    results = sug_svc.accept_all(novel_id)
    return BulkActionResult(
        count=len(results),
        items=[SuggestionResponse(**r.model_dump(exclude_none=False)) for r in results],
    )


@router.post("/novels/{novel_id}/glossary/suggestions/reject-all", response_model=BulkActionResult)
async def reject_all_glossary_suggestions(
    novel_id: str,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> BulkActionResult:
    """Reject all pending suggestions."""
    _require_novel(session, novel_id)
    results = sug_svc.reject_all(novel_id)
    return BulkActionResult(
        count=len(results),
        items=[SuggestionResponse(**r.model_dump(exclude_none=False)) for r in results],
    )
