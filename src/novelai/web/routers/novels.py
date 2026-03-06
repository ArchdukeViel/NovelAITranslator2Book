from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from novelai.services.storage_service import StorageService

router = APIRouter()
storage = StorageService()


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None


@router.get("/", response_model=list[NovelSummary])
async def list_novels() -> list[NovelSummary]:
    novel_ids = storage.list_novels()
    return [NovelSummary(novel_id=n) for n in novel_ids]


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(novel_id: str, chapter_id: str) -> dict[str, str]:
    text = storage.load_chapter(novel_id, chapter_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"novel_id": novel_id, "chapter_id": chapter_id, "text": text}
