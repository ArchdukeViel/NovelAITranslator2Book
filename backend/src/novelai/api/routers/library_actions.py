"""Library action endpoints: source metadata, chapters, reader, progress, checkpoints.

Extracted from library.py to keep the core CRT router focused on novel
list/create/get/delete operations.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.response_helpers import translated_chapter_response
from novelai.api.routers.dependencies import (
    get_storage,
    metadata_chapters,
    reader_author,
    reader_title,
)
from novelai.api.routers.library import (
    ChapterCheckpointFile,
    ChapterCheckpoints,
    NovelCheckpointsResponse,
)
from novelai.services.library_service import (
    _sanitize_metadata_snapshot,
    _source_metadata_inspection_payload,
    _source_metadata_warnings,
)
from novelai.storage.service import StorageService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])
logger = logging.getLogger(__name__)


class ChapterSummary(BaseModel):
    id: str
    title: str | None = None
    translated: bool = False


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
    source_key: str | None = None
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


_DIFF_MAX_CHANGED_FIELDS = 50


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
            storage, novel_id, from_snapshot,
        )
        to_snapshot_entry, to_metadata, to_warnings = _load_sanitized_metadata_snapshot(
            storage, novel_id, to_snapshot,
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
        chapters.append({
            "id": chapter_id,
            "num": chapter.get("num"),
            "title": chapter.get("translated_title") or chapter.get("title"),
            "source_title": chapter.get("title"),
            "translated": chapter_id in translated_ids,
        })

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


@router.get("/{novel_id}/checkpoints", response_model=NovelCheckpointsResponse)
async def list_novel_checkpoints(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> NovelCheckpointsResponse:
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
