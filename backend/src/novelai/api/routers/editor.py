from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.response_helpers import translated_chapter_response
from novelai.api.routers.dependencies import _rate_limit, get_editor_service
from novelai.services.editor_service import EditorService

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


@router.get("/{novel_id}/chapters/{chapter_id}/translated/versions")
async def list_translated_chapter_versions(
    novel_id: str,
    chapter_id: str,
    service: EditorService = Depends(get_editor_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    result = service.get_translated_chapter_versions(novel_id, chapter_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "versions": result["versions"],
    }


@router.get("/{novel_id}/chapters/{chapter_id}/translated/edit-history")
async def get_translation_edit_history(
    novel_id: str,
    chapter_id: str,
    service: EditorService = Depends(get_editor_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    result = service.get_translation_edit_history(novel_id, chapter_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return result


@router.post("/{novel_id}/chapters/{chapter_id}/translated/lint")
async def lint_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: GlossaryLintRequest,
    service: EditorService = Depends(get_editor_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    result = service.check_edit(
        novel_id,
        chapter_id,
        body.text,
        body.source_text,
        max_terms=body.max_terms or 50,
    )
    return {"glossary_qa": result.to_dict()}


@router.put("/{novel_id}/chapters/{chapter_id}/translated")
async def update_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationEditRequest,
    request: Request,
    service: EditorService = Depends(get_editor_service),
    owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    try:
        result = service.update_translated_chapter(
            novel_id,
            chapter_id,
            body.text,
            editor=body.editor,
            note=body.note,
            lint=body.lint,
            source_text=body.source_text,
            glossary_override=body.glossary_override,
            owner_user_id=getattr(owner, "user_id", None),
        )
    except ValueError as exc:
        detail = exc.args[0]
        if isinstance(detail, dict) and "glossary_qa" in detail:
            raise HTTPException(status_code=409, detail=detail) from exc
        status = 404 if "not found" in str(detail).lower() else 400
        raise HTTPException(status_code=status, detail=str(detail)) from exc

    glossary_qa = result.pop("glossary_qa", None)
    response = translated_chapter_response(novel_id, chapter_id, result)
    if glossary_qa is not None:
        response["glossary_qa"] = glossary_qa
    return response


@router.post("/{novel_id}/chapters/{chapter_id}/translated/rollback")
async def rollback_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationRollbackRequest,
    request: Request,
    service: EditorService = Depends(get_editor_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    try:
        translated = service.rollback_translated_chapter(
            novel_id,
            chapter_id,
            body.version_id,
            editor=body.editor,
            note=body.note,
        )
    except ValueError as exc:
        status = 404 if "not found" in exc.args[0].lower() else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return translated_chapter_response(novel_id, chapter_id, translated)
