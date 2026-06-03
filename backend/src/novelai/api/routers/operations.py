from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from novelai.activity.queue import ActivityQueueService
from novelai.config.settings import settings
from novelai.api.routers.dependencies import _rate_limit, get_activity_log, get_orchestrator, get_storage, verify_api_key
from novelai.runtime.container import container
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.storage.service import StorageService
from novelai.sources.registry import detect_source

router = APIRouter()
logger = logging.getLogger(__name__)

_NCODE_ID_PATTERN = r"^n\d{4}[a-z]{2}$"
_SYOSETU_SOURCE_PAIR = ("novel18_syosetu", "syosetu_ncode")


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


def _preliminary_source_attempts(identifier: str, requested_source_key: str | None) -> list[str]:
    detected_source = detect_source(identifier)
    requested = requested_source_key.strip() if isinstance(requested_source_key, str) else None
    if requested == "":
        requested = None

    if detected_source in _SYOSETU_SOURCE_PAIR:
        fallback = "syosetu_ncode" if detected_source == "novel18_syosetu" else "novel18_syosetu"
        return [detected_source, fallback]

    if _looks_like_ncode_id(identifier) and requested in {None, "syosetu_ncode", "novel18_syosetu"}:
        return list(_SYOSETU_SOURCE_PAIR)

    if requested in _SYOSETU_SOURCE_PAIR:
        fallback = "syosetu_ncode" if requested == "novel18_syosetu" else "novel18_syosetu"
        return [requested, fallback]

    if detected_source:
        return [detected_source]

    if _looks_like_ncode_id(identifier):
        if requested is None:
            return list(_SYOSETU_SOURCE_PAIR)
        assert requested is not None
        return [requested]

    return [_resolved_preliminary_source(identifier, requested_source_key)]


def _preliminary_failure_code(errors: list[str]) -> str:
    if not errors:
        return "PRELIMINARY_CRAWL_FAILED"
    normalized = [error.lower() for error in errors]
    timeout_count = sum("timed out" in error for error in normalized)
    no_metadata_count = sum("no metadata or chapters detected" in error for error in normalized)
    if timeout_count == len(normalized):
        return "PRELIMINARY_CRAWL_TIMEOUT"
    if timeout_count > 0:
        return "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT"
    if no_metadata_count == len(normalized):
        return "PRELIMINARY_CRAWL_NO_METADATA"
    return "PRELIMINARY_CRAWL_FAILED"


def _preliminary_failure_explanation(code: str) -> str:
    explanations = {
        "PRELIMINARY_CRAWL_TIMEOUT": (
            "Every attempted source timed out before metadata could be detected. Try again later, "
            "check the source website, or increase the backend request timeout."
        ),
        "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT": (
            "At least one source timed out, and the fallback source did not return usable metadata. "
            "Open Activity Log details to see which source timed out and which fallback returned nothing."
        ),
        "PRELIMINARY_CRAWL_NO_METADATA": (
            "The crawler reached the attempted source pages, but none returned usable metadata or chapters. "
            "Check whether the ID belongs to a different source or requires an exact URL."
        ),
    }
    return explanations.get(
        code,
        "The crawler tried every configured source fallback for this input, but none returned usable novel metadata or chapters.",
    )


def _record_preliminary_crawl_failure(
    activity_log: ActivityQueueService,
    *,
    novel_id: str,
    identifier: str,
    requested_source_key: str | None,
    attempts: list[str],
    errors: list[str],
) -> dict[str, Any]:
    source_key = attempts[0] if attempts else requested_source_key or "auto"
    failure_code = _preliminary_failure_code(errors)
    failure_explanation = _preliminary_failure_explanation(failure_code)
    activity = activity_log.create_crawl_activity(
        novel_id=novel_id,
        source_key=source_key,
        kind="metadata",
        chapters=None,
        source_url=identifier if identifier.startswith(("http://", "https://")) else None,
        metadata={
            "activity_subtype": "crawling",
            "activity_phase": "preliminary_crawl",
            "preliminary_crawl": True,
            "identifier": identifier,
            "requested_source_key": requested_source_key,
            "attempted_sources": attempts,
            "attempt_errors": errors,
            "failure_code": failure_code,
            "failure_category": "crawler",
            "failure_explanation": failure_explanation,
        },
    )
    error_text = "; ".join(errors) if errors else "Preliminary crawl failed before any source adapter returned metadata."
    failed = activity_log.update_activity_status(activity["id"], "failed", error=error_text)
    return failed or activity


def _record_preliminary_crawl_success(
    activity_log: ActivityQueueService,
    *,
    novel_id: str,
    identifier: str,
    requested_source_key: str | None,
    attempts: list[str],
    source_key: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    chapter_count = _chapter_count(metadata)
    source_url = metadata.get("source_url")
    activity_source_url: str | None = None
    if isinstance(source_url, str):
        activity_source_url = source_url
    elif identifier.startswith(("http://", "https://")):
        activity_source_url = identifier

    activity = activity_log.create_crawl_activity(
        novel_id=novel_id,
        source_key=source_key,
        kind="metadata",
        chapters=None,
        source_url=activity_source_url,
        metadata={
            "activity_subtype": "crawling",
            "activity_phase": "preliminary_crawl",
            "preliminary_crawl": True,
            "identifier": identifier,
            "requested_source_key": requested_source_key,
            "attempted_sources": attempts,
            "selected_source_key": source_key,
            "chapter_count": chapter_count,
            "source_url": activity_source_url,
            "title": metadata.get("title"),
            "translated_title": metadata.get("translated_title"),
            "author": metadata.get("author"),
            "translated_author": metadata.get("translated_author"),
            "metadata_translation_status": metadata.get("metadata_translation_status"),
            "metadata_translation_error": metadata.get("metadata_translation_error"),
        },
    )
    completed = activity_log.update_activity_status(
        activity["id"],
        "completed",
        metadata={
            "result": {
                "chapter_count": chapter_count,
                "source_key": source_key,
                "source_url": activity_source_url,
            }
        },
    )
    return completed or activity


def _chapter_count(metadata: dict[str, Any]) -> int:
    chapters = metadata.get("chapters")
    return len(chapters) if isinstance(chapters, list) else 0


def _preliminary_metadata_is_usable(metadata: dict[str, Any]) -> bool:
    if _chapter_count(metadata) > 0:
        return True
    for key in ("title", "author", "synopsis", "description", "summary"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


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
    source_language: str | None = None
    target_language: str | None = "English"


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
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    identifier = body.identifier.strip()
    if not identifier:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "NOVEL_IDENTIFIER_REQUIRED",
                "message": "Novel link or ID is required.",
                "explanation": "Enter either the source URL or the source novel ID before starting preliminary crawl.",
            },
        )

    attempts = _preliminary_source_attempts(identifier, body.source_key)
    timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
    errors: list[str] = []
    meta: dict[str, Any] | None = None
    source_key: str | None = None
    for attempt_source_key in attempts:
        try:
            meta = await asyncio.wait_for(
                _scrape_preliminary_metadata(
                    orchestrator,
                    source_key=attempt_source_key,
                    novel_id=novel_id,
                    mode=body.mode,
                    max_chapter=body.max_chapter,
                    identifier=identifier,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            errors.append(f"{attempt_source_key}: operation timed out")
            activity_log.record_source_health(attempt_source_key, success=False, error="preliminary crawl timed out")
            continue
        except Exception as exc:
            errors.append(f"{attempt_source_key}: {exc}")
            activity_log.record_source_health(attempt_source_key, success=False, error=str(exc))
            continue

        if _preliminary_metadata_is_usable(meta):
            source_key = attempt_source_key
            activity_log.record_source_health(attempt_source_key, success=True)
            break
        errors.append(f"{attempt_source_key}: no metadata or chapters detected")
        activity_log.record_source_health(attempt_source_key, success=False, error="no metadata or chapters detected")
        meta = None

    if meta is None or source_key is None:
        joined_errors = "; ".join(errors) if errors else "no source adapters were attempted"
        failed_job = _record_preliminary_crawl_failure(
            activity_log,
            novel_id=novel_id,
            identifier=identifier,
            requested_source_key=body.source_key,
            attempts=attempts,
            errors=errors,
        )
        failure_code = _preliminary_failure_code(errors)
        raise HTTPException(
            status_code=502,
            detail={
                "code": failure_code,
                "message": f"Preliminary crawl failed: {joined_errors}. Activity log: {failed_job.get('id')}",
                "explanation": _preliminary_failure_explanation(failure_code),
                "details": {
                    "activity_log_job_id": failed_job.get("id"),
                    "identifier": identifier,
                    "requested_source_key": body.source_key,
                    "attempted_sources": attempts,
                    "attempt_errors": errors,
                    "failure_category": "crawler",
                },
            },
        )

    detected_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    synopsis = meta.get("synopsis") or meta.get("description") or meta.get("summary")
    activity_job: dict[str, Any] | None = None
    try:
        activity_job = _record_preliminary_crawl_success(
            activity_log,
            novel_id=novel_id,
            identifier=identifier,
            requested_source_key=body.source_key,
            attempts=attempts,
            source_key=source_key,
            metadata=meta,
        )
    except Exception:
        logger.warning("Failed to record preliminary crawl success activity.", exc_info=True)
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
        "metadata_translation_status": meta.get("metadata_translation_status"),
        "metadata_translation_error": meta.get("metadata_translation_error"),
        "activity_log_job_id": activity_job.get("id") if activity_job else None,
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
                source_language=body.source_language,
                target_language=body.target_language or settings.TRANSLATION_TARGET_LANGUAGE,
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
