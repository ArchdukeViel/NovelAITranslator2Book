from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from novelai.api.routers.dependencies import _rate_limit, get_storage, verify_api_key
from novelai.storage.service import StorageService

router = APIRouter()


class TranslationEditRequest(BaseModel):
    text: str
    editor: str | None = None
    note: str | None = None


class TranslationRollbackRequest(BaseModel):
    version_id: str
    editor: str | None = None
    note: str | None = None


def _translation_provider_response(item: dict[str, Any]) -> dict[str, Any]:
    response = dict(item)
    if "provider" in response:
        response["provider_key"] = response["provider"]
    if "model" in response:
        response["provider_model"] = response["model"]
    return response


def _translated_chapter_response(novel_id: str, chapter_id: str, translated: dict[str, Any]) -> dict[str, Any]:
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        **_translation_provider_response(translated),
    }


@router.get("/{novel_id}/chapters/{chapter_id}/translated/versions")
async def list_translated_chapter_versions(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    versions = storage.list_translated_chapter_versions(novel_id, chapter_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "versions": [_translation_provider_response(version) for version in versions],
    }


@router.get("/{novel_id}/chapters/{chapter_id}/translated/edit-history")
async def get_translation_edit_history(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
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


@router.put("/{novel_id}/chapters/{chapter_id}/translated")
async def update_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationEditRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if storage.load_chapter(novel_id, chapter_id) is None and storage.load_translated_chapter(novel_id, chapter_id) is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Translated text cannot be empty")

    storage.save_edited_translation(
        novel_id,
        chapter_id,
        text,
        editor=body.editor,
        note=body.note,
    )
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=500, detail="Edited translation could not be loaded")
    return _translated_chapter_response(novel_id, chapter_id, translated)


@router.post("/{novel_id}/chapters/{chapter_id}/translated/rollback")
async def rollback_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationRollbackRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
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
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=500, detail="Rolled back translation could not be loaded")
    return _translated_chapter_response(novel_id, chapter_id, translated)
