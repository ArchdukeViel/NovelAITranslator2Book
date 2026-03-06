from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from novelai.app.container import container
from novelai.services.storage_service import StorageService

router = APIRouter()


def get_storage() -> StorageService:
    """FastAPI dependency for storage service (uses container singleton)."""
    return container.storage


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None


@router.get("/", response_model=list[NovelSummary])
async def list_novels(storage: StorageService = Depends(get_storage)) -> list[NovelSummary]:
    novel_ids = storage.list_novels()
    return [NovelSummary(novel_id=n) for n in novel_ids]


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
) -> dict[str, str]:
    chapter = storage.load_chapter(novel_id, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    text = chapter.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=500, detail="Stored chapter is malformed")
    return {"novel_id": novel_id, "chapter_id": chapter_id, "text": text}
