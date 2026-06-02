from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from novelai.interfaces.web.routers.dependencies import (
    _rate_limit,
    get_storage,
    metadata_chapters,
    reader_author,
    reader_title,
    verify_api_key,
)
from novelai.services.storage_service import StorageService

router = APIRouter()


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    author: str | None = None
    chapter_count: int = 0


class ChapterSummary(BaseModel):
    id: str
    title: str | None = None
    translated: bool = False


@router.get("/", response_model=list[NovelSummary])
async def list_novels(
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> list[NovelSummary]:
    summaries: list[NovelSummary] = []
    for novel_id in storage.list_novels():
        meta = storage.load_metadata(novel_id) or {}
        summaries.append(
            NovelSummary(
                novel_id=novel_id,
                title=meta.get("title"),
                author=meta.get("author"),
                chapter_count=len(meta.get("chapters", [])),
            )
        )
    return summaries


@router.get("/{novel_id}")
async def get_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return meta


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> None:
    _rate_limit(request, "delete")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    storage.delete_novel(novel_id)


@router.get("/{novel_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> list[ChapterSummary]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    translated_ids = set(storage.list_translated_chapters(novel_id))
    return [
        ChapterSummary(
            id=str(chapter.get("id")),
            title=chapter.get("title") or chapter.get("translated_title"),
            translated=str(chapter.get("id")) in translated_ids,
        )
        for chapter in meta.get("chapters", [])
        if isinstance(chapter, dict)
    ]


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    chapter = storage.load_chapter(novel_id, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    text = chapter.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=500, detail="Stored chapter is malformed")
    return {"novel_id": novel_id, "chapter_id": chapter_id, "text": text}


@router.get("/{novel_id}/chapters/{chapter_id}/translated")
async def get_translated_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {"novel_id": novel_id, "chapter_id": chapter_id, **translated}


@router.get("/{novel_id}/reader")
async def get_reader_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    translated_ids = set(storage.list_translated_chapters(novel_id))
    chapters = []
    for chapter in metadata_chapters(meta):
        chapter_id = str(chapter.get("id"))
        chapters.append(
            {
                "id": chapter_id,
                "num": chapter.get("num"),
                "title": chapter.get("translated_title") or chapter.get("title"),
                "source_title": chapter.get("title"),
                "translated": chapter_id in translated_ids,
            }
        )

    return {
        "novel_id": novel_id,
        "title": reader_title(meta),
        "source_title": meta.get("title"),
        "author": reader_author(meta),
        "source_author": meta.get("author"),
        "source": meta.get("source"),
        "source_url": meta.get("source_url"),
        "chapter_count": len(chapters),
        "translated_count": len(translated_ids),
        "chapters": chapters,
    }


@router.get("/{novel_id}/reader/chapters/{chapter_id}")
async def get_reader_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    chapters = metadata_chapters(meta)
    chapter_ids = [str(chapter.get("id")) for chapter in chapters]
    if chapter_id not in chapter_ids:
        raise HTTPException(status_code=404, detail="Chapter not found")

    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None or not isinstance(translated.get("text"), str):
        raise HTTPException(status_code=404, detail="Translated chapter not found")

    index = chapter_ids.index(chapter_id)
    chapter = chapters[index]
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "novel_title": reader_title(meta),
        "title": chapter.get("translated_title") or chapter.get("title"),
        "source_title": chapter.get("title"),
        "text": translated.get("text"),
        "version_id": translated.get("version_id"),
        "version_kind": translated.get("version_kind"),
        "previous_chapter_id": chapter_ids[index - 1] if index > 0 else None,
        "next_chapter_id": chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None,
    }


@router.get("/{novel_id}/progress")
async def get_progress(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    total = len(meta.get("chapters", []))
    scraped = storage.count_stored_chapters(novel_id)
    translated = storage.count_translated_chapters(novel_id)
    return {"novel_id": novel_id, "total": total, "scraped": scraped, "translated": translated}
