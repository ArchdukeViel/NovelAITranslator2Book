from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from novelai.activity.queue import ActivityQueueService
from novelai.config.settings import settings
from novelai.services.export_service import ExportService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.sources.registry import detect_source
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

NCODE_ID_PATTERN = r"^n\d{4}[a-z]{2}$"
SYOSETU_SOURCE_PAIR = ("novel18_syosetu", "syosetu_ncode")


@dataclass(frozen=True)
class ExportOperationResult:
    path: str
    media_type: str
    filename: str


class OperationError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class OperationsService:
    def __init__(
        self,
        *,
        orchestrator: NovelOrchestrationService,
        activity_log: ActivityQueueService,
        storage: StorageService,
        export_service: ExportService,
    ) -> None:
        self.orchestrator = orchestrator
        self.activity_log = activity_log
        self.storage = storage
        self.export_service = export_service

    async def scrape_novel(
        self,
        *,
        novel_id: str,
        source_key: str | None,
        url: str,
        chapters: str,
        mode: str,
        max_chapter: int | None,
    ) -> dict[str, Any]:
        resolved_source_key = detect_source(url) or source_key or "generic"
        timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
        try:
            meta = await asyncio.wait_for(
                self.orchestrator.scrape_metadata(
                    resolved_source_key,
                    novel_id,
                    mode=mode,
                    max_chapter=max_chapter,
                    source_identifier=url,
                ),
                timeout=timeout,
            )
            await asyncio.wait_for(
                self.orchestrator.scrape_chapters(
                    resolved_source_key,
                    novel_id,
                    chapters,
                    mode=mode,
                ),
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise OperationError(504, "Operation timed out") from exc

        # Best-effort post-scrape DB reconciliation (REQ-2.1)
        try:
            from novelai.db.engine import session_scope

            with session_scope() as session:
                CatalogService(storage=self.storage, session=session).reconcile_catalog_projection(novel_id)
        except Exception:
            logger.warning(
                "Post-scrape catalog projection reconciliation failed for %s",
                novel_id,
                exc_info=True,
            )

        return {"novel_id": novel_id, "source_key": resolved_source_key, "chapters": len(meta.get("chapters", []))}

    async def preliminary_crawl_novel(
        self,
        *,
        novel_id: str,
        identifier: str,
        requested_source_key: str | None,
        mode: str,
        max_chapter: int | None,
    ) -> dict[str, Any]:
        clean_identifier = identifier.strip()
        if not clean_identifier:
            raise OperationError(
                400,
                {
                    "code": "NOVEL_IDENTIFIER_REQUIRED",
                    "message": "Novel link or ID is required.",
                    "explanation": "Enter either the source URL or the source novel ID before starting preliminary crawl.",
                },
            )

        attempts = preliminary_source_attempts(clean_identifier, requested_source_key)
        timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
        errors: list[str] = []
        meta: dict[str, Any] | None = None
        source_key: str | None = None
        for attempt_source_key in attempts:
            try:
                meta = await asyncio.wait_for(
                    self.scrape_preliminary_metadata(
                        source_key=attempt_source_key,
                        novel_id=novel_id,
                        mode=mode,
                        max_chapter=max_chapter,
                        identifier=clean_identifier,
                    ),
                    timeout=timeout,
                )
            except TimeoutError:
                errors.append(f"{attempt_source_key}: operation timed out")
                self.activity_log.record_source_health(
                    attempt_source_key,
                    success=False,
                    error="preliminary crawl timed out",
                )
                continue
            except Exception as exc:
                errors.append(f"{attempt_source_key}: {exc}")
                self.activity_log.record_source_health(attempt_source_key, success=False, error=str(exc))
                continue

            if preliminary_metadata_is_usable(meta):
                source_key = attempt_source_key
                self.activity_log.record_source_health(attempt_source_key, success=True)
                break
            errors.append(f"{attempt_source_key}: no metadata or chapters detected")
            self.activity_log.record_source_health(
                attempt_source_key,
                success=False,
                error="no metadata or chapters detected",
            )
            meta = None

        if meta is None or source_key is None:
            joined_errors = "; ".join(errors) if errors else "no source adapters were attempted"
            failed_job = self.record_preliminary_crawl_failure(
                novel_id=novel_id,
                identifier=clean_identifier,
                requested_source_key=requested_source_key,
                attempts=attempts,
                errors=errors,
            )
            failure_code = preliminary_failure_code(errors)
            raise OperationError(
                502,
                {
                    "code": failure_code,
                    "message": f"Preliminary crawl failed: {joined_errors}. Activity log: {failed_job.get('id')}",
                    "explanation": preliminary_failure_explanation(failure_code),
                    "details": {
                        "activity_log_job_id": failed_job.get("id"),
                        "identifier": clean_identifier,
                        "requested_source_key": requested_source_key,
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
            activity_job = self.record_preliminary_crawl_success(
                novel_id=novel_id,
                identifier=clean_identifier,
                requested_source_key=requested_source_key,
                attempts=attempts,
                source_key=source_key,
                metadata=meta,
            )
        except Exception:
            logger.warning("Failed to record preliminary crawl success activity.", exc_info=True)

        # Best-effort post-preliminary-crawl DB reconciliation (REQ-2.3)
        try:
            from novelai.db.engine import session_scope

            with session_scope() as session:
                CatalogService(storage=self.storage, session=session).reconcile_catalog_projection(novel_id)
        except Exception:
            logger.warning(
                "Post-preliminary-crawl catalog projection reconciliation failed for %s",
                novel_id,
                exc_info=True,
            )

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
            "bootstrap_candidate_count": int(meta.get("bootstrap_candidate_count") or 0),
            "activity_log_job_id": activity_job.get("id") if activity_job else None,
            "detected_at": detected_at,
            "chapters": chapter_count(meta),
            "chapter_list": chapter_rows(meta),
        }

    async def scrape_preliminary_metadata(
        self,
        *,
        source_key: str,
        novel_id: str,
        identifier: str,
        mode: str,
        max_chapter: int | None,
    ) -> dict[str, Any]:
        return await self.orchestrator.scrape_metadata(
            source_key,
            novel_id,
            mode=mode,
            max_chapter=max_chapter,
            source_identifier=identifier,
        )

    async def import_document(
        self,
        *,
        novel_id: str,
        adapter_key: str,
        source: str,
        max_units: int | None,
    ) -> dict[str, Any]:
        try:
            metadata = await asyncio.wait_for(
                self.orchestrator.import_document(
                    adapter_key,
                    novel_id,
                    source,
                    max_units=max_units,
                ),
                timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise OperationError(504, "Operation timed out") from exc
        return {
            "novel_id": novel_id,
            "adapter_key": adapter_key,
            "chapters": len(metadata.get("chapters", [])),
            "document_type": metadata.get("document_type"),
        }

    async def translate_novel(
        self,
        *,
        novel_id: str,
        source_key: str,
        chapters: str,
        provider_key: str | None,
        provider_model: str | None,
        force: bool,
        source_language: str | None,
        target_language: str | None,
        allow_cross_provider_fallback: bool = True,
        skip_glossary_gate: bool = False,
    ) -> dict[str, str]:
        # Guard: novel must exist before translation (REQ-3.1, REQ-3.2)
        if self.storage.load_metadata(novel_id) is None:
            raise OperationError(404, {"error": "Novel not found", "novel_id": novel_id})
        try:
            await asyncio.wait_for(
                self.orchestrator.translate_chapters(
                    source_key,
                    novel_id,
                    chapters,
                    provider_key=provider_key,
                    provider_model=provider_model,
                    force=force,
                    source_language=source_language,
                    target_language=target_language or settings.TRANSLATION_TARGET_LANGUAGE,
                    allow_cross_provider_fallback=allow_cross_provider_fallback,
                    skip_glossary_gate=skip_glossary_gate,
                ),
                timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise OperationError(504, "Operation timed out") from exc
        return {"novel_id": novel_id, "status": "ok"}

    def export_novel(self, *, novel_id: str, export_format: str) -> ExportOperationResult:
        meta = self.storage.load_metadata(novel_id)
        if meta is None:
            raise OperationError(404, "Novel not found")

        chapters: list[dict[str, Any]] = []
        for chapter in meta.get("chapters", []):
            chapter_id = str(chapter.get("id"))
            translated = self.storage.load_translated_chapter(novel_id, chapter_id)
            if not translated:
                continue
            chapters.append(
                {
                    "title": chapter.get("title"),
                    "text": translated.get("text"),
                    "images": self.storage.load_chapter_export_images(novel_id, chapter_id),
                }
            )

        if not chapters:
            raise OperationError(400, "No translated chapters available for export")

        output_path = str(self.storage.build_export_path(novel_id, export_format))
        self.export_service.export(
            export_format,
            novel_id=novel_id,
            chapters=chapters,
            output_path=output_path,
        )
        return ExportOperationResult(
            path=output_path,
            media_type="application/epub+zip" if export_format == "epub" else "application/octet-stream",
            filename=f"{novel_id}.{export_format}",
        )

    def record_preliminary_crawl_failure(
        self,
        *,
        novel_id: str,
        identifier: str,
        requested_source_key: str | None,
        attempts: list[str],
        errors: list[str],
    ) -> dict[str, Any]:
        source_key = attempts[0] if attempts else requested_source_key or "auto"
        failure_code = preliminary_failure_code(errors)
        failure_explanation = preliminary_failure_explanation(failure_code)
        activity = self.activity_log.create_crawl_activity(
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
        failed = self.activity_log.update_activity_status(activity["id"], "failed", error=error_text)
        return failed or activity

    def record_preliminary_crawl_success(
        self,
        *,
        novel_id: str,
        identifier: str,
        requested_source_key: str | None,
        attempts: list[str],
        source_key: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        count = chapter_count(metadata)
        source_url = metadata.get("source_url")
        activity_source_url: str | None = None
        if isinstance(source_url, str):
            activity_source_url = source_url
        elif identifier.startswith(("http://", "https://")):
            activity_source_url = identifier

        activity = self.activity_log.create_crawl_activity(
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
                "chapter_count": count,
                "source_url": activity_source_url,
                "title": metadata.get("title"),
                "translated_title": metadata.get("translated_title"),
                "author": metadata.get("author"),
                "translated_author": metadata.get("translated_author"),
                "metadata_translation_status": metadata.get("metadata_translation_status"),
                "metadata_translation_error": metadata.get("metadata_translation_error"),
            },
        )
        completed = self.activity_log.update_activity_status(
            activity["id"],
            "completed",
            metadata={
                "result": {
                    "chapter_count": count,
                    "source_key": source_key,
                    "source_url": activity_source_url,
                }
            },
        )
        return completed or activity


def looks_like_ncode_id(identifier: str) -> bool:
    return re.fullmatch(NCODE_ID_PATTERN, identifier.strip(), flags=re.IGNORECASE) is not None


def resolved_preliminary_source(identifier: str, requested_source_key: str | None) -> str:
    detected_source = detect_source(identifier)
    if detected_source:
        return detected_source
    if requested_source_key:
        return requested_source_key
    if looks_like_ncode_id(identifier):
        return "syosetu_ncode"
    if identifier.strip().isdigit() and len(identifier.strip()) >= 12:
        return "kakuyomu"
    return "generic"


def preliminary_source_attempts(identifier: str, requested_source_key: str | None) -> list[str]:
    detected_source = detect_source(identifier)
    requested = requested_source_key.strip() if isinstance(requested_source_key, str) else None
    if requested == "":
        requested = None

    if detected_source in SYOSETU_SOURCE_PAIR:
        fallback = "syosetu_ncode" if detected_source == "novel18_syosetu" else "novel18_syosetu"
        return [detected_source, fallback]

    if looks_like_ncode_id(identifier) and requested in {None, "syosetu_ncode", "novel18_syosetu"}:
        return list(SYOSETU_SOURCE_PAIR)

    if requested in SYOSETU_SOURCE_PAIR:
        fallback = "syosetu_ncode" if requested == "novel18_syosetu" else "novel18_syosetu"
        return [requested, fallback]

    if detected_source:
        return [detected_source]

    if looks_like_ncode_id(identifier):
        if requested is None:
            return list(SYOSETU_SOURCE_PAIR)
        return [requested]

    return [resolved_preliminary_source(identifier, requested_source_key)]


def preliminary_failure_code(errors: list[str]) -> str:
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


def preliminary_failure_explanation(code: str) -> str:
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


def chapter_count(metadata: dict[str, Any]) -> int:
    chapters = metadata.get("chapters")
    return len(chapters) if isinstance(chapters, list) else 0


def preliminary_metadata_is_usable(metadata: dict[str, Any]) -> bool:
    if chapter_count(metadata) > 0:
        return True
    for key in ("title", "author", "synopsis", "description", "summary"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def chapter_rows(metadata: dict[str, Any]) -> list[dict[str, Any]]:
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
