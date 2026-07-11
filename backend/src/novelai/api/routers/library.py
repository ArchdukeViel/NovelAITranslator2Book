"""Admin library CRT endpoints: novel list, create, get, delete.
Source metadata, chapters, reader, progress, and checkpoints are in
``library_actions.py``. Catalog projection and health are in ``library_detail.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import (
    _rate_limit,
    get_db_session,
    get_storage,
)
from novelai.core.security import redact_sensitive
from novelai.db.models.chapter import Chapter as ChapterModel
from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.services.catalog_service import CatalogService
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])
logger = logging.getLogger(__name__)


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    source_title: str | None = None
    author: str | None = None
    source_key: str | None = None
    source_url: str | None = None
    publication_status: str = "unknown"
    chapter_count: int = 0
    scraped_count: int = 0
    translated_count: int = 0
    is_published: bool = False
    latest_chapter_id: str | None = None
    latest_chapter_number: int | None = None
    latest_chapter_title: str | None = None
    glossary_status: str = "glossary_pending"
    glossary_revision: int = 0
    glossary_pending_count: int = 0
    onboarding_status: str | None = None
    onboarding_updated_at: str | None = None
    onboarding_error_code: str | None = None
    onboarding_error_message: str | None = None
    body_scrape_required: bool | None = None


class ChapterCheckpointFile(BaseModel):
    name: str
    timestamp: str | None = None


class ChapterCheckpoints(BaseModel):
    chapter_id: str
    checkpoints: list[ChapterCheckpointFile]


class NovelCheckpointsResponse(BaseModel):
    novel_id: str
    chapters: list[ChapterCheckpoints]


class NovelCreateRequest(BaseModel):
    novel_id: str
    title: str
    source_url: str | None = None
    source_key: str | None = None
    language: str = "ja"


class NovelCreateResponse(BaseModel):
    novel_id: str
    title: str
    source_url: str | None = None
    source_key: str | None = None
    language: str
    created_at: str
    db_id: int


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _metadata_chapter_count(meta: dict[str, Any]) -> int:
    chapters = meta.get("chapters")
    return len(chapters) if isinstance(chapters, list) else 0


_INSPECTION_EXCLUDED_KEY_PARTS = (
    "api_key", "authorization", "credential", "cookie", "password", "secret", "session", "token",
)
_INSPECTION_EXCLUDED_KEYS = {
    "html", "page_html", "raw_html", "raw_payload", "raw_source", "raw_source_html",
    "response_body", "source_body", "source_html",
}
_DETAIL_MAX_STRING_LENGTH = 1000
_DETAIL_MAX_LIST_ITEMS = 25
_DETAIL_MAX_DICT_ITEMS = 50
_DETAIL_MAX_DEPTH = 4


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


def _is_sensitive_metadata_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _INSPECTION_EXCLUDED_KEY_PARTS)


def _is_raw_payload_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in _INSPECTION_EXCLUDED_KEYS or (
        ("html" in lowered or "payload" in lowered or "source_body" in lowered) and "title" not in lowered
    )


def _sanitize_metadata_value(
    key: str, value: Any, *, warnings: list[str], path: str, depth: int = 0,
) -> Any:
    if _is_sensitive_metadata_key(key):
        warnings.append(f"redacted:{path}")
        return None
    if _is_raw_payload_key(key):
        warnings.append(f"omitted_raw_payload:{path}")
        return None
    value = redact_sensitive(value)
    if isinstance(value, str):
        if "<html" in value.lower() or "<!doctype" in value.lower():
            warnings.append(f"omitted_raw_payload:{path}")
            return None
        if len(value) > _DETAIL_MAX_STRING_LENGTH:
            warnings.append(f"truncated:{path}")
            return f"{value[:_DETAIL_MAX_STRING_LENGTH]}... [truncated]"
        return value
    if isinstance(value, list):
        if depth >= _DETAIL_MAX_DEPTH:
            warnings.append(f"truncated:{path}")
            return "[TRUNCATED]"
        items = value[:_DETAIL_MAX_LIST_ITEMS]
        if len(value) > _DETAIL_MAX_LIST_ITEMS:
            warnings.append(f"truncated:{path}")
        return [
            _sanitize_metadata_value(str(index), item, warnings=warnings, path=f"{path}.{index}", depth=depth + 1)
            for index, item in enumerate(items)
        ]
    if isinstance(value, dict):
        if depth >= _DETAIL_MAX_DEPTH:
            warnings.append(f"truncated:{path}")
            return "[TRUNCATED]"
        sanitized: dict[str, Any] = {}
        items = list(value.items())
        if len(items) > _DETAIL_MAX_DICT_ITEMS:
            warnings.append(f"truncated:{path}")
        for child_key, child_value in items[:_DETAIL_MAX_DICT_ITEMS]:
            child_key_text = str(child_key)
            child_path = f"{path}.{child_key_text}"
            sanitized_value = _sanitize_metadata_value(
                child_key_text, child_value, warnings=warnings, path=child_path, depth=depth + 1,
            )
            if sanitized_value is not None:
                sanitized[child_key_text] = sanitized_value
        return sanitized
    return value


def _sanitize_metadata_snapshot(meta: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    sanitized: dict[str, Any] = {}
    for key, value in meta.items():
        key_text = str(key)
        sanitized_value = _sanitize_metadata_value(key_text, value, warnings=warnings, path=key_text)
        if sanitized_value is not None:
            sanitized[key_text] = sanitized_value
    return sanitized, sorted(sanitized.keys()), sorted(set(warnings))


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
    novel_id: str, meta: dict[str, Any], *, metadata_missing: bool,
) -> dict[str, Any]:
    publication_status = normalize_publication_status(meta.get("publication_status") or meta.get("status"))
    source_title = _optional_string(meta.get("title"))
    synopsis = _optional_string(meta.get("description")) or _optional_string(meta.get("synopsis"))
    author = _optional_string(meta.get("translated_author")) or _optional_string(meta.get("author"))
    display_title = _optional_string(meta.get("translated_title")) or source_title or novel_id
    return {
        "novel_id": novel_id,
        "title": display_title,
        "source_title": source_title,
        "author": author,
        "source_key": _optional_string(meta.get("source")),
        "source_url": _optional_string(meta.get("source_url")),
        "publication_status": publication_status,
        "raw_status": _optional_string(meta.get("source_publication_status")) or _optional_string(meta.get("raw_status")),
        "synopsis": synopsis,
        "language": _optional_string(meta.get("language")),
        "last_scraped_at": _optional_string(meta.get("scraped_at")),
        "updated_at": _optional_string(meta.get("updated_at")),
        "chapter_count": _metadata_chapter_count(meta),
        "source_metadata_keys": _safe_metadata_keys(meta),
        "extraction": {
            "publication_status": publication_status,
            "source_title": source_title,
            "synopsis_present": synopsis is not None,
            "author_present": author is not None,
        },
        "warnings": _source_metadata_warnings(meta, metadata_missing=metadata_missing),
    }


def _db_novel_summary(novel: Novel, storage: StorageService) -> NovelSummary:
    publication_status = normalize_publication_status(novel.publication_status or novel.status)
    meta = storage.load_metadata(novel.slug) or {}
    return NovelSummary(
        novel_id=novel.slug,
        title=_optional_string(novel.title) or novel.slug,
        source_title=_optional_string(novel.original_title),
        author=_optional_string(novel.author),
        source_key=_optional_string(novel.source_site),
        source_url=_optional_string(novel.source_url),
        publication_status=publication_status,
        chapter_count=novel.chapter_count,
        scraped_count=novel.chapter_count,
        translated_count=novel.translated_count,
        is_published=novel.is_published,
        latest_chapter_id=novel.latest_chapter_id,
        latest_chapter_number=novel.latest_chapter_number,
        latest_chapter_title=novel.latest_chapter_title,
        glossary_status=novel.glossary_status,
        glossary_revision=novel.glossary_revision,
        glossary_pending_count=_pending_glossary_count(novel),
        onboarding_status=meta.get("onboarding_status"),
        onboarding_updated_at=meta.get("onboarding_updated_at"),
        onboarding_error_code=meta.get("onboarding_error_code"),
        onboarding_error_message=meta.get("onboarding_error_message"),
        body_scrape_required=meta.get("body_scrape_required"),
    )


def _pending_glossary_count(novel: Novel) -> int:
    session = object_session(novel)
    if session is None or novel.id is None:
        return 0
    stmt = (
        select(func.count())
        .select_from(NovelGlossaryEntry)
        .where(NovelGlossaryEntry.novel_id == novel.id, NovelGlossaryEntry.status.in_(("candidate", "recommended")))
    )
    return int(session.scalar(stmt) or 0)


def _validate_novel_id(novel_id: str) -> str:
    cleaned = novel_id.strip()
    if not cleaned:
        raise ValueError("novel_id must not be empty")
    import re
    if not re.match(r"^[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?$", cleaned):
        raise ValueError(
            "novel_id must be lowercase alphanumeric, may contain hyphens and underscores, "
            "and must not start or end with a hyphen or underscore"
        )
    return cleaned


def _storage_novel_summary(novel_id: str, meta: dict[str, Any], storage: StorageService) -> NovelSummary:
    scraped_count = storage.count_stored_chapters(novel_id)
    translated_count = storage.count_translated_chapters(novel_id)
    chapter_count = _metadata_chapter_count(meta) or max(scraped_count, translated_count)
    publication_status = normalize_publication_status(meta.get("publication_status") or meta.get("status"))
    if not meta:
        logger.info("Listing novel %s from files because metadata is missing or unreadable.", novel_id)
    return NovelSummary(
        novel_id=novel_id,
        title=_optional_string(meta.get("translated_title")) or _optional_string(meta.get("title")) or novel_id,
        source_title=_optional_string(meta.get("title")),
        author=_optional_string(meta.get("translated_author")) or _optional_string(meta.get("author")),
        source_key=_optional_string(meta.get("source")),
        source_url=_optional_string(meta.get("source_url")),
        publication_status=publication_status,
        chapter_count=chapter_count,
        scraped_count=scraped_count,
        translated_count=translated_count,
        onboarding_status=meta.get("onboarding_status"),
        onboarding_updated_at=meta.get("onboarding_updated_at"),
        onboarding_error_code=meta.get("onboarding_error_code"),
        onboarding_error_message=meta.get("onboarding_error_message"),
        body_scrape_required=meta.get("body_scrape_required"),
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
        return [_db_novel_summary(novel, storage) for novel in query.all()]
    summaries: list[NovelSummary] = []
    for novel_id in storage.list_novels():
        meta = storage.load_metadata(novel_id) or {}
        summaries.append(_storage_novel_summary(novel_id, meta, storage))
    start = offset
    end = start + limit if limit is not None else None
    return summaries[start:end]


@router.post("/", response_model=NovelCreateResponse, status_code=201)
async def create_novel(
    body: NovelCreateRequest,
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> NovelCreateResponse:
    try:
        novel_id = _validate_novel_id(body.novel_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing_meta = storage.load_metadata(novel_id)
    existing_db = db.query(Novel).filter_by(slug=novel_id).one_or_none()
    if existing_meta is not None or existing_db is not None:
        raise HTTPException(status_code=409, detail="Novel already exists")
    minimal_meta: dict[str, Any] = {
        "title": body.title.strip(),
        "source_url": body.source_url,
        "source_key": body.source_key,
        "language": body.language,
        "origin_type": "url" if body.source_url else "library",
        "chapters": [],
    }
    storage.save_metadata(novel_id, minimal_meta)
    novel = CatalogService(storage=storage, session=db).get_or_create_novel(novel_id, minimal_meta)
    db.flush()
    return NovelCreateResponse(
        novel_id=novel_id,
        title=novel.title or body.title,
        source_url=body.source_url,
        source_key=body.source_key,
        language=novel.language,
        created_at=novel.created_at.isoformat(),
        db_id=novel.id,
    )


@router.get("/{novel_id}")
async def get_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    payload = dict(meta)
    novel = db.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is not None:
        payload["glossary_status"] = novel.glossary_status
        payload["glossary_revision"] = novel.glossary_revision
        payload["glossary_pending_count"] = _pending_glossary_count(novel)
        chapter_records = {
            c.chapter_number: c
            for c in db.query(ChapterModel).filter(ChapterModel.novel_id == novel.id).all()
        }
        enriched_chapters = []
        for ch in payload.get("chapters", []):
            ch_id = ch.get("id")
            if ch_id is not None and int(ch_id) in chapter_records:
                rec = chapter_records[int(ch_id)]
                ch["translation_state"] = rec.translation_state
                ch["translation_error"] = rec.translation_error
            enriched_chapters.append(ch)
        payload["chapters"] = enriched_chapters
    else:
        payload.setdefault("glossary_status", "glossary_pending")
        payload.setdefault("glossary_revision", 0)
        payload.setdefault("glossary_pending_count", 0)
    return payload


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
