from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.response_helpers import translated_chapter_response
from novelai.api.routers.dependencies import (
    _rate_limit,
    get_db_session,
    get_storage,
    metadata_chapters,
    reader_author,
    reader_title,
)
from novelai.db.models.novel import Novel
from novelai.services.catalog_service import CatalogService
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])
logger = logging.getLogger(__name__)


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    author: str | None = None
    source: str | None = None
    source_url: str | None = None
    publication_status: str = "unknown"
    chapter_count: int = 0
    scraped_count: int = 0
    translated_count: int = 0


class SourceMetadataExtraction(BaseModel):
    publication_status: str
    source_title: str | None = None
    synopsis_present: bool = False
    author_present: bool = False


class SourceMetadataInspection(BaseModel):
    novel_id: str
    title: str | None = None
    source_title: str | None = None
    author: str | None = None
    source: str | None = None
    source_url: str | None = None
    publication_status: str = "unknown"
    raw_status: str | None = None
    synopsis: str | None = None
    language: str | None = None
    last_scraped_at: str | None = None
    updated_at: str | None = None
    chapter_count: int = 0
    source_metadata_keys: list[str] = []
    extraction: SourceMetadataExtraction
    warnings: list[str] = []


class CatalogProjectionRefreshResponse(BaseModel):
    novel_id: str
    created: bool
    changed_fields: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any]


class ChapterSummary(BaseModel):
    id: str
    title: str | None = None
    translated: bool = False


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _metadata_chapter_count(meta: dict[str, Any]) -> int:
    chapters = meta.get("chapters")
    return len(chapters) if isinstance(chapters, list) else 0


_INSPECTION_EXCLUDED_KEY_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)
_INSPECTION_EXCLUDED_KEYS = {
    "html",
    "page_html",
    "raw_html",
    "raw_source_html",
    "source_html",
}


def _safe_metadata_keys(meta: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in meta:
        key_text = str(key)
        lowered = key_text.lower()
        if lowered in _INSPECTION_EXCLUDED_KEYS:
            continue
        if any(part in lowered for part in _INSPECTION_EXCLUDED_KEY_PARTS):
            continue
        keys.append(key_text)
    return sorted(keys)


def _source_metadata_warnings(meta: dict[str, Any], *, metadata_missing: bool) -> list[str]:
    warnings: list[str] = []
    publication_status = normalize_publication_status(meta.get("publication_status") or meta.get("status"))
    if metadata_missing:
        warnings.append("metadata_missing")
    if not _optional_string(meta.get("source_url")):
        warnings.append("missing_source_url")
    if publication_status == "unknown":
        warnings.append("unknown_publication_status")
    if not (_optional_string(meta.get("description")) or _optional_string(meta.get("synopsis"))):
        warnings.append("missing_synopsis")
    if _metadata_chapter_count(meta) == 0:
        warnings.append("no_chapters")
    return warnings


def _source_metadata_inspection_payload(
    novel_id: str,
    meta: dict[str, Any],
    *,
    metadata_missing: bool,
) -> SourceMetadataInspection:
    publication_status = normalize_publication_status(meta.get("publication_status") or meta.get("status"))
    source_title = _optional_string(meta.get("title"))
    synopsis = _optional_string(meta.get("description")) or _optional_string(meta.get("synopsis"))
    author = _optional_string(meta.get("translated_author")) or _optional_string(meta.get("author"))
    display_title = _optional_string(meta.get("translated_title")) or source_title or novel_id
    return SourceMetadataInspection(
        novel_id=novel_id,
        title=display_title,
        source_title=source_title,
        author=author,
        source=_optional_string(meta.get("source")),
        source_url=_optional_string(meta.get("source_url")),
        publication_status=publication_status,
        raw_status=_optional_string(meta.get("source_publication_status")) or _optional_string(meta.get("raw_status")),
        synopsis=synopsis,
        language=_optional_string(meta.get("language")),
        last_scraped_at=_optional_string(meta.get("scraped_at")),
        updated_at=_optional_string(meta.get("updated_at")),
        chapter_count=_metadata_chapter_count(meta),
        source_metadata_keys=_safe_metadata_keys(meta),
        extraction=SourceMetadataExtraction(
            publication_status=publication_status,
            source_title=source_title,
            synopsis_present=synopsis is not None,
            author_present=author is not None,
        ),
        warnings=_source_metadata_warnings(meta, metadata_missing=metadata_missing),
    )


def _db_novel_summary(novel: Novel) -> NovelSummary:
    publication_status = normalize_publication_status(novel.publication_status or novel.status)
    return NovelSummary(
        novel_id=novel.slug,
        title=_optional_string(novel.title) or novel.slug,
        author=_optional_string(novel.author),
        source=_optional_string(novel.source_site),
        source_url=_optional_string(novel.source_url),
        publication_status=publication_status,
        chapter_count=novel.chapter_count,
        scraped_count=novel.chapter_count,
        translated_count=novel.translated_count,
    )


def _storage_novel_summary(
    novel_id: str,
    meta: dict[str, Any],
    storage: StorageService,
) -> NovelSummary:
    scraped_count = storage.count_stored_chapters(novel_id)
    translated_count = storage.count_translated_chapters(novel_id)
    chapter_count = _metadata_chapter_count(meta) or max(scraped_count, translated_count)
    publication_status = normalize_publication_status(meta.get("publication_status") or meta.get("status"))
    if not meta:
        logger.info("Listing novel %s from files because metadata is missing or unreadable.", novel_id)
    return NovelSummary(
        novel_id=novel_id,
        title=_optional_string(meta.get("translated_title")) or _optional_string(meta.get("title")) or novel_id,
        author=_optional_string(meta.get("translated_author")) or _optional_string(meta.get("author")),
        source=_optional_string(meta.get("source")),
        source_url=_optional_string(meta.get("source_url")),
        publication_status=publication_status,
        chapter_count=chapter_count,
        scraped_count=scraped_count,
        translated_count=translated_count,
    )


@router.get("/", response_model=list[NovelSummary])
async def list_novels(
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> list[NovelSummary]:
    query = db.query(Novel).order_by(Novel.updated_at.desc(), Novel.id.desc())
    if query.count() > 0:
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return [_db_novel_summary(novel) for novel in query.all()]

    summaries: list[NovelSummary] = []
    for novel_id in storage.list_novels():
        meta = storage.load_metadata(novel_id) or {}
        summaries.append(_storage_novel_summary(novel_id, meta, storage))
    start = offset
    end = start + limit if limit is not None else None
    return summaries[start:end]


@router.get("/{novel_id}/source-metadata", response_model=SourceMetadataInspection)
async def inspect_source_metadata(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> SourceMetadataInspection:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        if novel_id not in storage.list_novels():
            raise HTTPException(status_code=404, detail="Novel not found")
        return _source_metadata_inspection_payload(novel_id, {}, metadata_missing=True)
    return _source_metadata_inspection_payload(novel_id, meta, metadata_missing=False)


@router.post(
    "/{novel_id}/refresh-catalog-projection",
    response_model=CatalogProjectionRefreshResponse,
)
async def refresh_catalog_projection(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogProjectionRefreshResponse:
    result = CatalogService(storage=storage, session=db).reconcile_catalog_projection(novel_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return CatalogProjectionRefreshResponse(
        novel_id=result.novel_id,
        created=result.created,
        changed_fields=result.changed_fields,
        before=result.before,
        after=result.after,
    )


@router.get("/{novel_id}")
async def get_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
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
    _owner=Depends(require_role("owner")),
) -> None:
    _rate_limit(request, "delete")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    storage.delete_novel(novel_id)


@router.get("/{novel_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
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
    _owner=Depends(require_role("owner")),
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
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return translated_chapter_response(novel_id, chapter_id, translated)


@router.get("/{novel_id}/reader")
async def get_reader_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
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
    _owner=Depends(require_role("owner")),
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
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    total = len(meta.get("chapters", []))
    scraped = storage.count_stored_chapters(novel_id)
    translated = storage.count_translated_chapters(novel_id)
    return {"novel_id": novel_id, "total": total, "scraped": scraped, "translated": translated}
