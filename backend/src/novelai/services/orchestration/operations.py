from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.activity.queue import ActivityQueueService
from novelai.config.settings import settings
from novelai.core.errors import TranslationInProgressError
from novelai.services.catalog_service import CatalogService
from novelai.services.export_manifest_service import (
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    build_manifest,
    write_manifest,
)
from novelai.services.export_service import ExportService, UnsupportedExportFormatError
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration.operations_helpers import (
    ExportOperationResult,
    OperationError,
    get_novel_translation_lock,
    require_novel_meta,
)
from novelai.services.orchestration.preliminary import (
    chapter_count,
    chapter_rows,
    preliminary_failure_code,
    preliminary_failure_explanation,
    preliminary_metadata_is_usable,
    preliminary_source_attempts,
)
from novelai.sources.registry import get_registry
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)


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
        detected_adapter = get_registry().get_adapter(url)
        resolved_source_key = detected_adapter.source_key if detected_adapter is not None else source_key or "generic"
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
            "onboarding_status": meta.get("onboarding_status"),
            "body_scrape_required": meta.get("body_scrape_required", False),
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
        require_novel_meta(self.storage, novel_id)

        # Novel-level concurrency guard
        novel_lock = get_novel_translation_lock(novel_id)
        if novel_lock.locked():
            raise OperationError(409, f"Translation already in progress for novel {novel_id}")
        await novel_lock.acquire()

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
        except TranslationInProgressError as exc:
            raise OperationError(409, str(exc)) from exc
        finally:
            novel_lock.release()
        return {"novel_id": novel_id, "status": "ok"}

    def get_translation_status(
        self,
        *,
        novel_id: str,
    ) -> dict[str, Any]:
        """Return per-chapter translation state summary."""
        meta = require_novel_meta(self.storage, novel_id)

        chapters: list[dict[str, Any]] = []
        for chapter in meta.get("chapters", []):
            chapter_id = str(chapter.get("id"))
            state = self.storage.load_chapter_state(novel_id, chapter_id)
            translated = self.storage.load_translated_chapter(novel_id, chapter_id)
            chapters.append(
                {
                    "id": chapter_id,
                    "title": chapter.get("title"),
                    "translated": translated is not None,
                    "state": state["current_state"].value if state else "pending",
                    "translation_state": state["current_state"].value if state else "pending",
                    "error_count": state.get("error_count", 0) if state else 0,
                }
            )

        translated_count = sum(1 for c in chapters if c["translated"])
        failed_count = sum(1 for c in chapters if c["state"] == "failed")
        in_progress_count = sum(1 for c in chapters if c["state"] in ("translating", "queued"))
        if failed_count > 0:
            overall_state = "failed"
        elif translated_count == len(chapters) and len(chapters) > 0:
            overall_state = "completed"
        else:
            overall_state = "pending"
        return {
            "novel_id": novel_id,
            "total_chapters": len(chapters),
            "completed_chapters": translated_count,
            "failed_chapters": failed_count,
            "in_progress_chapters": in_progress_count,
            "overall_state": overall_state,
            "chapters": chapters,
        }

    def export_novel(self, *, novel_id: str, export_format: str) -> ExportOperationResult:
        meta = require_novel_meta(self.storage, novel_id)

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

        # Create pending manifest
        manifest = build_manifest(
            novel_id=novel_id,
            export_format=export_format,
            status="pending",
            source_chapter_count=len(meta.get("chapters", [])),
            chapter_count=len(chapters),
            glossary_revision=meta.get("glossary_revision"),
            glossary_hash=meta.get("glossary_hash"),
            novel_updated_at=meta.get("updated_at"),
        )
        write_manifest(self.storage, novel_id, manifest)

        try:
            output_path = str(self.storage.build_export_path(novel_id, export_format))
            self.export_service.export(
                export_format,
                novel_id=novel_id,
                chapters=chapters,
                output_path=output_path,
            )

            # Update manifest to succeeded
            output_file = Path(output_path)
            updated = build_manifest(
                novel_id=novel_id,
                export_format=export_format,
                status=STATUS_SUCCEEDED,
                output_filename=output_file.name,
                source_chapter_count=len(meta.get("chapters", [])),
                chapter_count=len(chapters),
                file_size_bytes=output_file.stat().st_size if output_file.exists() else None,
                glossary_revision=meta.get("glossary_revision"),
                glossary_hash=meta.get("glossary_hash"),
                novel_updated_at=meta.get("updated_at"),
                previous_manifest_key=manifest["manifest_key"],
            )
            write_manifest(self.storage, novel_id, updated)

            return ExportOperationResult(
                path=output_path,
                media_type="application/epub+zip" if export_format == "epub" else "application/octet-stream",
                filename=f"{novel_id}.{export_format}",
            )
        except UnsupportedExportFormatError as exc:
            failed = build_manifest(
                novel_id=novel_id,
                export_format=export_format,
                status=STATUS_FAILED,
                failure_code=exc.error_code,
                failure_message=exc.detail[:200],
                source_chapter_count=len(meta.get("chapters", [])),
                chapter_count=len(chapters),
                previous_manifest_key=manifest["manifest_key"],
            )
            write_manifest(self.storage, novel_id, failed)
            raise OperationError(400, {"error": exc.error_code, "format": exc.format, "message": exc.detail}) from exc
        except Exception as exc:
            failed = build_manifest(
                novel_id=novel_id,
                export_format=export_format,
                status=STATUS_FAILED,
                failure_code="render_error",
                failure_message=str(exc)[:200],
                source_chapter_count=len(meta.get("chapters", [])),
                chapter_count=len(chapters),
                previous_manifest_key=manifest["manifest_key"],
            )
            write_manifest(self.storage, novel_id, failed)
            raise

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
        error_text = (
            "; ".join(errors) if errors else "Preliminary crawl failed before any source adapter returned metadata."
        )
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

    async def resume_onboarding(
        self,
        *,
        novel_id: str,
        chapters: str = "all",
    ) -> dict[str, Any]:
        meta = require_novel_meta(self.storage, novel_id)

        current_status = self.storage.resolve_onboarding_status(novel_id)
        if current_status in ("ready_for_translation", "cancelled"):
            raise OperationError(
                409,
                {
                    "error": f"Cannot resume onboarding in state {current_status!r}.",
                    "novel_id": novel_id,
                    "current_status": current_status,
                },
            )

        resolved_source_key = meta.get("source_key") or meta.get("input_adapter_key") or "generic"
        timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
        activity_id: str | None = None
        try:
            from novelai.core.platform import CrawlJobKind

            activity = self.activity_log.create_crawl_activity(
                novel_id=novel_id,
                source_key=resolved_source_key,
                kind=CrawlJobKind.CHAPTERS,
                chapters=chapters,
                source_url=meta.get("source_url"),
                metadata={
                    "activity_subtype": "crawling",
                    "activity_phase": "resume_onboarding",
                    "resumed_from_status": current_status,
                    "identifier": meta.get("source_url") or novel_id,
                    "selected_source_key": resolved_source_key,
                },
            )
            activity_id = activity.get("id")
        except Exception:
            logger.warning("Failed to record resume activity.", exc_info=True)

        try:
            await asyncio.wait_for(
                self.orchestrator.scrape_chapters(
                    resolved_source_key,
                    novel_id,
                    chapters,
                    mode="update",
                ),
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise OperationError(504, "Resume operation timed out") from exc
        except RuntimeError as exc:
            self.storage.update_onboarding_status(
                novel_id,
                "failed",
                error_code="scrape_locked",
                error_message=str(exc)[:500],
            )
            raise OperationError(409, {"error": str(exc), "novel_id": novel_id}) from exc
        except Exception as exc:
            self.storage.update_onboarding_status(
                novel_id,
                "failed",
                error_code="resume_error",
                error_message=f"Resume failed: {exc.__class__.__name__}",
            )
            raise

        return {
            "novel_id": novel_id,
            "onboarding_status": self.storage.resolve_onboarding_status(novel_id),
            "activity_id": activity_id,
        }

    def cancel_onboarding(self, *, novel_id: str) -> dict[str, Any]:
        require_novel_meta(self.storage, novel_id)

        current_status = self.storage.resolve_onboarding_status(novel_id)
        cancellable = {"metadata_discovered", "glossary_pending", "chapters_pending", "failed"}
        if current_status not in cancellable:
            raise OperationError(
                409,
                {
                    "error": f"Cannot cancel onboarding in state {current_status!r}.",
                    "novel_id": novel_id,
                    "current_status": current_status,
                },
            )

        self.storage.update_onboarding_status(novel_id, "cancelled")
        return {
            "novel_id": novel_id,
            "onboarding_status": "cancelled",
        }

    async def retranslate_stale(
        self,
        *,
        novel_id: str,
        chapter_ids: list[str] | None = None,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> dict[str, Any]:
        from novelai.translation.glossary_freshness import (
            FRESHNESS_STALE,
            GlossarySnapshot,
            compute_glossary_freshness,
        )

        meta = require_novel_meta(self.storage, novel_id)
        source_key = str(meta.get("source_key") or "")
        if not source_key.strip():
            raise OperationError(400, {"error": "Novel has no source_key in metadata", "novel_id": novel_id})

        chapters = meta.get("chapters", [])
        if not isinstance(chapters, list):
            raise OperationError(400, {"error": "Novel has no chapters metadata"})

        # Resolve current glossary snapshot from metadata
        snapshot = None
        revision = meta.get("glossary_revision")
        if isinstance(revision, int):
            snapshot = GlossarySnapshot(
                revision=revision,
                hash=meta.get("glossary_hash"),
            )

        stale_chapter_ids: list[str] = []
        for ch in chapters:
            ch_id = str(ch.get("id", ""))
            if not ch_id:
                continue
            if chapter_ids is not None and ch_id not in chapter_ids:
                continue
            translated = self.storage.load_translated_chapter(novel_id, ch_id)
            if not isinstance(translated, dict):
                continue
            freshness = compute_glossary_freshness(translated, snapshot)
            state = freshness.get("glossary_freshness")
            if state == FRESHNESS_STALE:
                stale_chapter_ids.append(ch_id)

        target_ids = stale_chapter_ids
        if not target_ids:
            return {
                "novel_id": novel_id,
                "stale_chapter_count": len(stale_chapter_ids),
                "scheduled_chapter_count": 0,
                "activity_id": None,
            }

        chapters_str = ",".join(sorted(target_ids, key=int))
        await self.orchestrator.translate_chapters(
            source_key,
            novel_id,
            chapters_str,
            provider_key=provider_key,
            provider_model=provider_model,
            force=True,
        )

        return {
            "novel_id": novel_id,
            "stale_chapter_count": len(stale_chapter_ids),
            "scheduled_chapter_count": len(target_ids),
            "activity_id": None,
        }
