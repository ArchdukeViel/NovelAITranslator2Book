from __future__ import annotations

from typing import Any

from novelai.core.platform import CrawlJobKind, JobStatus, TranslationJobKind
from novelai.services.job_queue_service import JobQueueService
from novelai.services.novel_orchestration_service import NovelOrchestrationService


class JobWorkerService:
    """Executes queued crawl and translation jobs through the orchestrator."""

    def __init__(self, jobs: JobQueueService, orchestrator: NovelOrchestrationService) -> None:
        self.jobs = jobs
        self.orchestrator = orchestrator

    @staticmethod
    def _job_metadata(job: dict[str, Any]) -> dict[str, Any]:
        metadata = job.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}

    def _resolve_translation_source_key(self, job: dict[str, Any]) -> str:
        source_key = job.get("source_key")
        if isinstance(source_key, str) and source_key.strip():
            return source_key.strip()

        novel_id = str(job.get("novel_id") or "")
        metadata = self.orchestrator.storage.load_metadata(novel_id) or {}
        metadata_source = metadata.get("source")
        if isinstance(metadata_source, str) and metadata_source.strip():
            return metadata_source.strip()

        raise ValueError("Translation job requires source_key or stored metadata.source.")

    async def _run_crawl_job(self, job: dict[str, Any]) -> dict[str, Any]:
        kind = str(job.get("kind") or "")
        metadata = self._job_metadata(job)
        novel_id = str(job.get("novel_id") or "")
        source_key = str(job.get("source_key") or "")
        if not novel_id.strip():
            raise ValueError("Crawl job is missing novel_id.")
        if not source_key.strip():
            raise ValueError("Crawl job is missing source_key.")

        mode = str(metadata.get("mode") or "update")
        if kind == CrawlJobKind.METADATA.value:
            max_chapter = metadata.get("max_chapter")
            if not isinstance(max_chapter, int):
                max_chapter = None
            result = await self.orchestrator.scrape_metadata(
                source_key,
                novel_id,
                mode=mode,
                max_chapter=max_chapter,
            )
            return {"chapter_count": len(result.get("chapters", [])) if isinstance(result, dict) else 0}

        if kind in {CrawlJobKind.CHAPTERS.value, CrawlJobKind.RECRAWL_CHAPTER.value}:
            chapters = job.get("chapters")
            if not isinstance(chapters, str) or not chapters.strip():
                chapters = str(metadata.get("chapter_id") or "all")
            await self.orchestrator.scrape_chapters(
                source_key,
                novel_id,
                chapters,
                mode=mode,
            )
            return {"chapters": chapters}

        raise ValueError(f"Unsupported crawl job kind: {kind}")

    async def _run_translation_job(self, job: dict[str, Any]) -> dict[str, Any]:
        kind = str(job.get("kind") or "")
        if kind not in {item.value for item in TranslationJobKind}:
            raise ValueError(f"Unsupported translation job kind: {kind}")

        metadata = self._job_metadata(job)
        novel_id = str(job.get("novel_id") or "")
        if not novel_id.strip():
            raise ValueError("Translation job is missing novel_id.")

        chapters = job.get("chapters")
        if not isinstance(chapters, str) or not chapters.strip():
            chapters = "all"

        provider = job.get("provider") if isinstance(job.get("provider"), str) else None
        model = job.get("model") if isinstance(job.get("model"), str) else None
        force = bool(metadata.get("force")) or kind in {
            TranslationJobKind.RETRANSLATE.value,
            TranslationJobKind.BATCH_RETRANSLATE.value,
        }

        await self.orchestrator.translate_chapters(
            self._resolve_translation_source_key(job),
            novel_id,
            chapters,
            provider_key=provider,
            provider_model=model,
            force=force,
        )
        return {"chapters": chapters, "force": force}

    async def run_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.jobs.get_job(job_id)
        if job is None:
            return None

        if job.get("status") in {JobStatus.RUNNING.value, JobStatus.COMPLETED.value, JobStatus.CANCELLED.value}:
            raise ValueError(f"Job cannot be run from status: {job.get('status')}")

        self.jobs.update_job_status(job_id, JobStatus.RUNNING)
        try:
            if job.get("type") == "crawl":
                result_metadata = await self._run_crawl_job(job)
                self.jobs.record_source_health(str(job.get("source_key") or ""), success=True)
            elif job.get("type") == "translation":
                result_metadata = await self._run_translation_job(job)
            else:
                raise ValueError(f"Unsupported job type: {job.get('type')}")
        except Exception as exc:
            if (
                job.get("type") == "crawl"
                and isinstance(job.get("source_key"), str)
                and str(job.get("source_key") or "").strip()
            ):
                self.jobs.record_source_health(str(job.get("source_key") or ""), success=False, error=str(exc))
            failed = self.jobs.update_job_status(job_id, JobStatus.FAILED, error=str(exc))
            if failed is None:
                raise
            return failed

        completed = self.jobs.update_job_status(job_id, JobStatus.COMPLETED, metadata={"result": result_metadata})
        return completed

    async def run_next(self, *, job_type: str | None = None) -> dict[str, Any] | None:
        job = self.jobs.next_pending_job(job_type=job_type)
        if job is None:
            return None
        return await self.run_job(str(job["id"]))
