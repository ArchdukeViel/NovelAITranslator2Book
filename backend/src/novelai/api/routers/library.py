from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

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
from novelai.core.security import redact_sensitive
from novelai.db.models.chapter import Chapter as ChapterModel
from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.services.catalog_service import CatalogService, get_projection_refresh_failures
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])
logger = logging.getLogger(__name__)

_last_bulk_reconciliation_at: str | None = None


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    source_title: str | None = None
    author: str | None = None
    source: str | None = None
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


class SourceMetadataHistoryEntry(BaseModel):
    snapshot_id: str
    created_at: str | None = None
    size_bytes: int = 0
    is_current: bool = False
    publication_status: str = "unknown"
    title: str | None = None
    source_title: str | None = None
    author: str | None = None


class SourceMetadataHistoryResponse(BaseModel):
    novel_id: str
    entries: list[SourceMetadataHistoryEntry]
    limit: int


class SourceMetadataSnapshotDetail(BaseModel):
    novel_id: str
    snapshot_id: str
    is_current: bool
    created_at: str | None = None
    size_bytes: int = 0
    metadata: dict[str, Any]
    metadata_keys: list[str]
    warnings: list[str] = []


class SourceMetadataChangedField(BaseModel):
    key: str
    before: Any = None
    after: Any = None


class SourceMetadataSnapshotDiff(BaseModel):
    novel_id: str
    from_snapshot: str
    to_snapshot: str
    added_keys: list[str]
    removed_keys: list[str]
    changed: list[SourceMetadataChangedField]
    unchanged_count: int = 0
    warnings: list[str] = []
    truncated: bool = False


class CatalogProjectionRefreshResponse(BaseModel):
    novel_id: str
    created: bool
    changed_fields: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any]


class CatalogProjectionFailureResponse(BaseModel):
    novel_id: str
    error: str


class CatalogProjectionBulkChangedResponse(BaseModel):
    novel_id: str
    created: bool
    changed_fields: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any]


class CatalogProjectionBulkRefreshResponse(BaseModel):
    dry_run: bool
    scanned: int
    created: int
    updated: int
    unchanged: int
    failed: int
    changed: list[CatalogProjectionBulkChangedResponse]
    failures: list[CatalogProjectionFailureResponse]
    details_truncated: bool = False


class CatalogHealthResponse(BaseModel):
    total_novels: int
    projection_stale_count: int
    missing_projection_count: int
    last_bulk_reconciliation_at: str | None = None
    recommendations: list[str]
    projection_refresh_errors: list[dict]


class NovelProjectionHealthResponse(BaseModel):
    novel_id: str
    db_has_row: bool
    db_chapter_count: int
    storage_translated_count: int
    in_sync: bool
    recommended_action: str

class ChapterCheckpointFile(BaseModel):
    name: str
    timestamp: str | None = None

class ChapterCheckpoints(BaseModel):
    chapter_id: str
    checkpoints: list[ChapterCheckpointFile]

class NovelCheckpointsResponse(BaseModel):
    novel_id: str
    chapters: list[ChapterCheckpoints]


class CatalogPublicationResponse(BaseModel):
    novel_id: str
    title: str
    source_title: str | None = None
    is_published: bool
    chapter_count: int
    translated_count: int
    latest_chapter_id: str | None = None
    latest_chapter_number: int | None = None
    latest_chapter_title: str | None = None
    publication_status: str
    visibility_warnings: list[str] = []


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
    "credential",
    "cookie",
    "password",
    "secret",
    "session",
    "token",
)
_INSPECTION_EXCLUDED_KEYS = {
    "html",
    "page_html",
    "raw_html",
    "raw_payload",
    "raw_source",
    "raw_source_html",
    "response_body",
    "source_body",
    "source_html",
}
_DETAIL_MAX_STRING_LENGTH = 1000
_DETAIL_MAX_LIST_ITEMS = 25
_DETAIL_MAX_DICT_ITEMS = 50
_DETAIL_MAX_DEPTH = 4
_DIFF_MAX_CHANGED_FIELDS = 50


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
    key: str,
    value: Any,
    *,
    warnings: list[str],
    path: str,
    depth: int = 0,
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
                child_key_text,
                child_value,
                warnings=warnings,
                path=child_path,
                depth=depth + 1,
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


def _load_sanitized_metadata_snapshot(
    storage: StorageService,
    novel_id: str,
    snapshot_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    snapshot = storage.load_metadata_snapshot(novel_id, snapshot_id)
    if snapshot is None:
        return None, None, []
    raw_metadata_raw = snapshot.get("metadata")
    raw_metadata: dict[str, Any] = raw_metadata_raw if isinstance(raw_metadata_raw, dict) else {}
    sanitized_metadata, _metadata_keys, sanitize_warnings = _sanitize_metadata_snapshot(raw_metadata)
    return snapshot, sanitized_metadata, sanitize_warnings


def _metadata_snapshot_diff(
    novel_id: str,
    from_snapshot_id: str,
    from_metadata: dict[str, Any],
    to_snapshot_id: str,
    to_metadata: dict[str, Any],
    warnings: list[str],
) -> SourceMetadataSnapshotDiff:
    from_keys = set(from_metadata)
    to_keys = set(to_metadata)
    added_keys = sorted(to_keys - from_keys)
    removed_keys = sorted(from_keys - to_keys)
    changed_keys = sorted(key for key in from_keys & to_keys if from_metadata[key] != to_metadata[key])
    unchanged_count = len([key for key in from_keys & to_keys if from_metadata[key] == to_metadata[key]])
    truncated = len(changed_keys) > _DIFF_MAX_CHANGED_FIELDS
    if truncated:
        warnings.append("truncated:changed_fields")
    safe_warnings: list[str] = []
    for warning in warnings:
        if warning.startswith("redacted:"):
            safe_warnings.append("redacted_sensitive_fields")
        elif warning.startswith("omitted_raw_payload:"):
            safe_warnings.append("omitted_raw_payload_fields")
        else:
            safe_warnings.append(warning)
    changed = [
        SourceMetadataChangedField(
            key=key,
            before=from_metadata[key],
            after=to_metadata[key],
        )
        for key in changed_keys[:_DIFF_MAX_CHANGED_FIELDS]
    ]
    return SourceMetadataSnapshotDiff(
        novel_id=novel_id,
        from_snapshot=from_snapshot_id,
        to_snapshot=to_snapshot_id,
        added_keys=added_keys,
        removed_keys=removed_keys,
        changed=changed,
        unchanged_count=unchanged_count,
        warnings=sorted(set(safe_warnings)),
        truncated=truncated,
    )


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
        source_title=_optional_string(novel.original_title),
        author=_optional_string(novel.author),
        source=_optional_string(novel.source_site),
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
    )


def _pending_glossary_count(novel: Novel) -> int:
    session = object_session(novel)
    if session is None or novel.id is None:
        return 0
    stmt = (
        select(func.count())
        .select_from(NovelGlossaryEntry)
        .where(
            NovelGlossaryEntry.novel_id == novel.id,
            NovelGlossaryEntry.status.in_(("candidate", "recommended")),
        )
    )
    return int(session.scalar(stmt) or 0)


def _catalog_publication_response(
    novel: Novel,
    *,
    visibility_warnings: list[str] | None = None,
) -> CatalogPublicationResponse:
    source_title = novel.original_title if novel.original_title and novel.original_title != novel.title else None
    publication_status = normalize_publication_status(novel.publication_status or novel.status)
    return CatalogPublicationResponse(
        novel_id=novel.slug,
        title=_optional_string(novel.title) or novel.slug,
        source_title=source_title,
        is_published=novel.is_published,
        chapter_count=novel.chapter_count,
        translated_count=novel.translated_count,
        latest_chapter_id=novel.latest_chapter_id,
        latest_chapter_number=novel.latest_chapter_number,
        latest_chapter_title=novel.latest_chapter_title,
        publication_status=publication_status,
        visibility_warnings=visibility_warnings or [],
    )


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


def _validate_novel_id(novel_id: str) -> str:
    """Validate and normalise a novel_id slug.

    Allows lowercase alphanumeric, hyphens, and underscores.
    Rejects: empty, path traversal attempts, uppercase, special chars.
    """
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
        source_title=_optional_string(meta.get("title")),
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


@router.post("/", response_model=NovelCreateResponse, status_code=201)
async def create_novel(
    body: NovelCreateRequest,
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> NovelCreateResponse:
    """Create a new novel with minimal metadata (REQ-1.1)."""
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

    novel = CatalogService(storage=storage, session=db).get_or_create_novel(
        novel_id, minimal_meta
    )
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


@router.post(
    "/refresh-catalog-projections",
    response_model=CatalogProjectionBulkRefreshResponse,
)
async def refresh_catalog_projections(
    dry_run: bool = Query(default=True),
    limit: int | None = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogProjectionBulkRefreshResponse:
    result = CatalogService(storage=storage, session=db).reconcile_all_catalog_projections(
        dry_run=dry_run,
        limit=limit,
        offset=offset,
    )
    if not dry_run:
        global _last_bulk_reconciliation_at
        _last_bulk_reconciliation_at = datetime.utcnow().isoformat()
    return CatalogProjectionBulkRefreshResponse(
        dry_run=result.dry_run,
        scanned=result.scanned,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        failed=result.failed,
        changed=[
            CatalogProjectionBulkChangedResponse(
                novel_id=item.novel_id,
                created=item.created,
                changed_fields=item.changed_fields,
                before=item.before,
                after=item.after,
            )
            for item in result.changed
        ],
        failures=[
            CatalogProjectionFailureResponse(
                novel_id=item.novel_id,
                error=item.error,
            )
            for item in result.failures
        ],
        details_truncated=result.details_truncated,
    )


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


@router.get("/{novel_id}/source-metadata/history", response_model=SourceMetadataHistoryResponse)
async def inspect_source_metadata_history(
    novel_id: str,
    limit: int = Query(default=10, ge=1, le=25),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> SourceMetadataHistoryResponse:
    entries = storage.list_metadata_history(novel_id, limit=limit)
    if not entries and novel_id not in storage.list_novels():
        raise HTTPException(status_code=404, detail="Novel not found")
    return SourceMetadataHistoryResponse(
        novel_id=novel_id,
        entries=[SourceMetadataHistoryEntry(**entry) for entry in entries],
        limit=limit,
    )


@router.get("/{novel_id}/source-metadata/history/diff", response_model=SourceMetadataSnapshotDiff)
async def diff_source_metadata_history_snapshots(
    novel_id: str,
    from_snapshot: str = Query(...),
    to_snapshot: str = Query(default="current"),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> SourceMetadataSnapshotDiff:
    try:
        from_snapshot_entry, from_metadata, from_warnings = _load_sanitized_metadata_snapshot(
            storage,
            novel_id,
            from_snapshot,
        )
        to_snapshot_entry, to_metadata, to_warnings = _load_sanitized_metadata_snapshot(
            storage,
            novel_id,
            to_snapshot,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot id") from None

    if from_snapshot_entry is None or to_snapshot_entry is None:
        if novel_id not in storage.list_novels():
            raise HTTPException(status_code=404, detail="Novel not found")
        raise HTTPException(status_code=404, detail="Metadata snapshot not found")

    return _metadata_snapshot_diff(
        novel_id,
        str(from_snapshot_entry["snapshot_id"]),
        from_metadata or {},
        str(to_snapshot_entry["snapshot_id"]),
        to_metadata or {},
        [*from_warnings, *to_warnings],
    )


@router.get("/{novel_id}/source-metadata/history/{snapshot_id}", response_model=SourceMetadataSnapshotDetail)
async def inspect_source_metadata_snapshot_detail(
    novel_id: str,
    snapshot_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> SourceMetadataSnapshotDetail:
    try:
        snapshot = storage.load_metadata_snapshot(novel_id, snapshot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot id") from None

    if snapshot is None:
        if novel_id not in storage.list_novels():
            raise HTTPException(status_code=404, detail="Novel not found")
        raise HTTPException(status_code=404, detail="Metadata snapshot not found")

    raw_metadata: dict[str, Any] = snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else {}
    if raw_metadata is None:
        raw_metadata = {}
    sanitized_metadata, metadata_keys, sanitize_warnings = _sanitize_metadata_snapshot(raw_metadata)
    warnings = sorted(
        set(sanitize_warnings)
        | set(_source_metadata_warnings(raw_metadata, metadata_missing=False))
    )
    return SourceMetadataSnapshotDetail(
        novel_id=novel_id,
        snapshot_id=str(snapshot["snapshot_id"]),
        is_current=bool(snapshot["is_current"]),
        created_at=snapshot.get("created_at") if isinstance(snapshot.get("created_at"), str) else None,
        size_bytes=int(snapshot.get("size_bytes", 0) or 0),
        metadata=sanitized_metadata,
        metadata_keys=metadata_keys,
        warnings=warnings,
    )


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


@router.post("/{novel_id}/publish", response_model=CatalogPublicationResponse)
async def publish_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogPublicationResponse:
    try:
        result = CatalogService(storage=storage, session=db).set_publication_state(
            novel_id,
            is_published=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return _catalog_publication_response(
        result.novel,
        visibility_warnings=result.visibility_warnings,
    )


@router.post("/{novel_id}/unpublish", response_model=CatalogPublicationResponse)
async def unpublish_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogPublicationResponse:
    result = CatalogService(storage=storage, session=db).set_publication_state(
        novel_id,
        is_published=False,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return _catalog_publication_response(
        result.novel,
        visibility_warnings=result.visibility_warnings,
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

        # Enrich chapters with DB-level translation state
        chapter_records = {
            c.chapter_number: c
            for c in db.query(ChapterModel).filter(
                ChapterModel.novel_id == novel.id
            ).all()
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


@router.get("/catalog-health", response_model=CatalogHealthResponse)
async def catalog_health(
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogHealthResponse:
    """Read-only catalog health inspection. No storage writes."""
    total_novels = db.query(func.count(Novel.id)).scalar() or 0
    stale_threshold = datetime.utcnow() - timedelta(hours=24)
    stale_count = db.query(func.count(Novel.id)).filter(
        Novel.updated_at < stale_threshold
    ).scalar() or 0

    storage_ids = set(storage.list_novels())
    db_slugs = {row[0] for row in db.query(Novel.slug).all()}
    missing_projection_count = len(storage_ids - db_slugs)

    recommendations: list[str] = []
    if missing_projection_count > 0:
        recommendations.append(
            f"POST /refresh-catalog-projections?dry_run=false "
            f"to create projections for {missing_projection_count} novel(s)"
        )
    if stale_count > 0:
        recommendations.append(
            f"{stale_count} stale projection(s) — run bulk reconciliation"
        )
    if not recommendations:
        recommendations.append("All catalog projections healthy")

    errors = get_projection_refresh_failures()

    return CatalogHealthResponse(
        total_novels=total_novels,
        projection_stale_count=stale_count,
        missing_projection_count=missing_projection_count,
        last_bulk_reconciliation_at=_last_bulk_reconciliation_at,
        recommendations=recommendations,
        projection_refresh_errors=errors,
    )


@router.get("/{novel_id}/catalog-projection-health", response_model=NovelProjectionHealthResponse)
async def novel_projection_health(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> NovelProjectionHealthResponse:
    """Per-novel projection health check. Read-only."""
    novel = db.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found in DB")

    storage_count = storage.count_translated_chapters(novel_id)
    db_count = novel.translated_count or 0
    in_sync = storage_count == db_count

    if in_sync:
        recommended_action = "None — in sync"
    elif storage_count > db_count:
        recommended_action = (
            f"Refresh projection: storage has {storage_count} translated, "
            f"DB shows {db_count}"
        )
    else:
        recommended_action = (
            f"Investigate: DB has {db_count} translated but storage has "
            f"{storage_count} — possible orphaned DB records"
        )

    return NovelProjectionHealthResponse(
        novel_id=novel_id,
        db_has_row=True,
        db_chapter_count=db_count,
        storage_translated_count=storage_count,
        in_sync=in_sync,
        recommended_action=recommended_action,
    )


@router.get("/{novel_id}/checkpoints", response_model=NovelCheckpointsResponse)
async def list_novel_checkpoints(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> NovelCheckpointsResponse:
    """List all checkpoints per chapter for a novel. Read-only."""
    chapters: list[ChapterCheckpoints] = []
    for chapter_id in storage.list_stored_chapters(novel_id):
        cps = storage.list_checkpoints(novel_id, chapter_id)
        if cps:
            chapters.append(
                ChapterCheckpoints(
                    chapter_id=chapter_id,
                    checkpoints=[
                        ChapterCheckpointFile(name=cp["checkpoint_name"], timestamp=cp.get("timestamp"))
                        for cp in cps
                    ],
                )
            )
    return NovelCheckpointsResponse(novel_id=novel_id, chapters=chapters)
