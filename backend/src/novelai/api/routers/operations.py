from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from novelai.config.settings import settings
from novelai.api.routers.dependencies import _rate_limit, get_orchestrator, get_storage, verify_api_key
from novelai.runtime.container import container
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.storage.service import StorageService
from novelai.sources.registry import detect_source

router = APIRouter()

_NCODE_ID_PATTERN = r"^n\d{4}[a-z]{2}$"


class ScrapeRequest(BaseModel):
    source_key: str | None = None
    url: str
    chapters: str = "all"
    mode: str = "update"
    max_chapter: int | None = None


class PreliminaryCrawlRequest(BaseModel):
    source_key: str | None = None
    identifier: str
    mode: str = "update"
    max_chapter: int | None = None


def _looks_like_ncode_id(identifier: str) -> bool:
    import re

    return re.fullmatch(_NCODE_ID_PATTERN, identifier.strip(), flags=re.IGNORECASE) is not None


def _resolved_preliminary_source(identifier: str, requested_source_key: str | None) -> str:
    detected_source = detect_source(identifier)
    if detected_source:
        return detected_source
    if requested_source_key:
        return requested_source_key
    if _looks_like_ncode_id(identifier):
        return "syosetu_ncode"
    if identifier.strip().isdigit() and len(identifier.strip()) >= 12:
        return "kakuyomu"
    return "generic"


def _chapter_count(metadata: dict[str, Any]) -> int:
    chapters = metadata.get("chapters")
    return len(chapters) if isinstance(chapters, list) else 0


def _chapter_rows(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = metadata.get("chapters")
    if not isinstance(chapters, list):
        return []
    rows: list[dict[str, Any]] = []
    fallback_date = metadata.get("updated_at") or metadata.get("published_at")
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        row = dict(chapter)
        date_added = chapter.get("date_added") or chapter.get("updated_at") or chapter.get("published_at") or fallback_date
        if date_added:
            row.setdefault("date_added", date_added)
        rows.append(row)
    return rows


async def _scrape_preliminary_metadata(
    orchestrator: NovelOrchestrationService,
    *,
    source_key: str,
    novel_id: str,
    identifier: str,
    mode: str,
    max_chapter: int | None,
) -> dict[str, Any]:
    return await orchestrator.scrape_metadata(
        source_key,
        novel_id,
        mode=mode,
        max_chapter=max_chapter,
        source_identifier=identifier,
    )


class TranslateRequest(BaseModel):
    source_key: str
    chapters: str = "all"
    provider_key: str | None = None
    provider_model: str | None = None
    force: bool = False


class ExportRequest(BaseModel):
    format: str = "epub"
    chapters: str | None = None


class ImportRequest(BaseModel):
    adapter_key: str
    source: str
    max_units: int | None = None


@router.post("/{novel_id}/scrape")
async def scrape_novel(
    novel_id: str,
    body: ScrapeRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    source_key = detect_source(body.url) or body.source_key or "generic"
    timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
    try:
        meta = await asyncio.wait_for(
            orchestrator.scrape_metadata(
                source_key,
                novel_id,
                mode=body.mode,
                max_chapter=body.max_chapter,
                source_identifier=body.url,
            ),
            timeout=timeout,
        )
        await asyncio.wait_for(
            orchestrator.scrape_chapters(
                source_key,
                novel_id,
                body.chapters,
                mode=body.mode,
            ),
            timeout=timeout,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    return {"novel_id": novel_id, "source_key": source_key, "chapters": len(meta.get("chapters", []))}


@router.post("/{novel_id}/preliminary-crawl")
async def preliminary_crawl_novel(
    novel_id: str,
    body: PreliminaryCrawlRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    identifier = body.identifier.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Novel link or ID is required")

    source_key = _resolved_preliminary_source(identifier, body.source_key)
    timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
    try:
        meta = await asyncio.wait_for(
            _scrape_preliminary_metadata(
                orchestrator,
                source_key=source_key,
                novel_id=novel_id,
                mode=body.mode,
                max_chapter=body.max_chapter,
                identifier=identifier,
            ),
            timeout=timeout,
        )
        if source_key == "syosetu_ncode" and _looks_like_ncode_id(identifier) and _chapter_count(meta) == 0:
            fallback_meta = await asyncio.wait_for(
                _scrape_preliminary_metadata(
                    orchestrator,
                    source_key="novel18_syosetu",
                    novel_id=novel_id,
                    mode=body.mode,
                    max_chapter=body.max_chapter,
                    identifier=identifier,
                ),
                timeout=timeout,
            )
            if _chapter_count(fallback_meta) > 0:
                source_key = "novel18_syosetu"
                meta = fallback_meta
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    except Exception as exc:
        if source_key != "syosetu_ncode" or not _looks_like_ncode_id(identifier):
            raise
        try:
            meta = await asyncio.wait_for(
                _scrape_preliminary_metadata(
                    orchestrator,
                    source_key="novel18_syosetu",
                    novel_id=novel_id,
                    mode=body.mode,
                    max_chapter=body.max_chapter,
                    identifier=identifier,
                ),
                timeout=timeout,
            )
            source_key = "novel18_syosetu"
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Operation timed out") from None
        except Exception:
            raise exc

    detected_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    synopsis = meta.get("synopsis") or meta.get("description") or meta.get("summary")
    return {
        "novel_id": novel_id,
        "source_key": source_key,
        "source_url": meta.get("source_url"),
        "title": meta.get("title"),
        "translated_title": meta.get("translated_title"),
        "author": meta.get("author"),
        "translated_author": meta.get("translated_author"),
        "synopsis": synopsis,
        "translated_synopsis": meta.get("translated_synopsis"),
        "detected_at": detected_at,
        "chapters": _chapter_count(meta),
        "chapter_list": _chapter_rows(meta),
    }


@router.post("/{novel_id}/import")
async def import_document(
    novel_id: str,
    body: ImportRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    try:
        metadata = await asyncio.wait_for(
            orchestrator.import_document(
                body.adapter_key,
                novel_id,
                body.source,
                max_units=body.max_units,
            ),
            timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    return {
        "novel_id": novel_id,
        "adapter_key": body.adapter_key,
        "chapters": len(metadata.get("chapters", [])),
        "document_type": metadata.get("document_type"),
    }


@router.post("/{novel_id}/translate")
async def translate_novel(
    novel_id: str,
    body: TranslateRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, str]:
    _rate_limit(request, "translate")
    try:
        await asyncio.wait_for(
            orchestrator.translate_chapters(
                body.source_key,
                novel_id,
                body.chapters,
                provider_key=body.provider_key,
                provider_model=body.provider_model,
                force=body.force,
            ),
            timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    return {"novel_id": novel_id, "status": "ok"}


@router.post("/{novel_id}/export")
async def export_novel(
    novel_id: str,
    body: ExportRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> FileResponse:
    _rate_limit(request, "export")
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    chapters: list[dict[str, Any]] = []
    for chapter in meta.get("chapters", []):
        chapter_id = str(chapter.get("id"))
        translated = storage.load_translated_chapter(novel_id, chapter_id)
        if not translated:
            continue
        chapters.append(
            {
                "title": chapter.get("title"),
                "text": translated.get("text"),
                "images": storage.load_chapter_export_images(novel_id, chapter_id),
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
