from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from novelai.app.container import container
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.storage_service import StorageService
from novelai.sources.registry import available_sources, detect_source

router = APIRouter()


def get_storage() -> StorageService:
    """FastAPI dependency for storage service (uses container singleton)."""
    return container.storage


def get_orchestrator() -> NovelOrchestrationService:
    return container.orchestrator


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    author: str | None = None
    chapter_count: int = 0


class ChapterSummary(BaseModel):
    id: str
    title: str | None = None
    translated: bool = False


class ScrapeRequest(BaseModel):
    source_key: str | None = None
    url: str
    chapters: str = "all"
    mode: str = "update"
    max_chapter: int | None = None


class TranslateRequest(BaseModel):
    source_key: str
    chapters: str = "all"
    provider_key: str | None = None
    provider_model: str | None = None
    force: bool = False


class ExportRequest(BaseModel):
    format: str = "epub"
    chapters: str | None = None


# ---------------------------------------------------------------------------
# List / Detail
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[NovelSummary])
async def list_novels(storage: StorageService = Depends(get_storage)) -> list[NovelSummary]:
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
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return meta


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
) -> None:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    storage.delete_novel(novel_id)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------

@router.get("/{novel_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
) -> list[ChapterSummary]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    translated_ids = set(storage.list_translated_chapters(novel_id))
    return [
        ChapterSummary(
            id=str(c.get("id")),
            title=c.get("title") or c.get("translated_title"),
            translated=str(c.get("id")) in translated_ids,
        )
        for c in meta.get("chapters", [])
        if isinstance(c, dict)
    ]


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
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
) -> dict[str, Any]:
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {"novel_id": novel_id, "chapter_id": chapter_id, **translated}


# ---------------------------------------------------------------------------
# Scrape / Translate / Export  (long-running — kept simple for now)
# ---------------------------------------------------------------------------

@router.post("/{novel_id}/scrape")
async def scrape_novel(
    novel_id: str,
    body: ScrapeRequest,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
) -> dict[str, Any]:
    source_key = body.source_key or detect_source(body.url) or "generic"
    meta = await orchestrator.scrape_metadata(
        source_key, novel_id, mode=body.mode, max_chapter=body.max_chapter,
    )
    await orchestrator.scrape_chapters(
        source_key, novel_id, body.chapters, mode=body.mode,
    )
    return {"novel_id": novel_id, "source_key": source_key, "chapters": len(meta.get("chapters", []))}


@router.post("/{novel_id}/translate")
async def translate_novel(
    novel_id: str,
    body: TranslateRequest,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
) -> dict[str, str]:
    await orchestrator.translate_chapters(
        body.source_key,
        novel_id,
        body.chapters,
        provider_key=body.provider_key,
        provider_model=body.provider_model,
        force=body.force,
    )
    return {"novel_id": novel_id, "status": "ok"}


@router.post("/{novel_id}/export")
async def export_novel(
    novel_id: str,
    body: ExportRequest,
    storage: StorageService = Depends(get_storage),
) -> FileResponse:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    chapters: list[dict[str, Any]] = []
    for chap in meta.get("chapters", []):
        chap_id = str(chap.get("id"))
        translated = storage.load_translated_chapter(novel_id, chap_id)
        if not translated:
            continue
        chapters.append(
            {
                "title": chap.get("title"),
                "text": translated.get("text"),
                "images": storage.load_chapter_export_images(novel_id, chap_id),
            }
        )

    if not chapters:
        raise HTTPException(status_code=400, detail="No translated chapters available for export")

    output_path = str(storage.build_export_path(novel_id, body.format))
    container.export.export(
        body.format,
        novel_id=novel_id,
        chapters=chapters,
        output_path=output_path,
    )
    return FileResponse(
        output_path,
        media_type="application/epub+zip" if body.format == "epub" else "application/octet-stream",
        filename=f"{novel_id}.{body.format}",
    )


# ---------------------------------------------------------------------------
# Progress / Sources
# ---------------------------------------------------------------------------

@router.get("/{novel_id}/progress")
async def get_progress(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    total = len(meta.get("chapters", []))
    scraped = storage.count_stored_chapters(novel_id)
    translated = storage.count_translated_chapters(novel_id)
    return {"novel_id": novel_id, "total": total, "scraped": scraped, "translated": translated}


@router.get("/sources", response_model=list[str])
async def list_sources() -> list[str]:
    return available_sources()
