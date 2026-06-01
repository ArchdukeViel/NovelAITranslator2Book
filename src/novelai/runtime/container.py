from __future__ import annotations

from dataclasses import dataclass

from novelai.config.settings import settings
from novelai.providers.registry import get_provider
from novelai.services.export_service import ExportService
from novelai.services.job_queue_service import JobQueueService
from novelai.services.job_runner_service import BackgroundJobRunner
from novelai.services.job_worker_service import JobWorkerService
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService


@dataclass
class Container:
    """Application dependency container.

    This is a simple, explicit DI container used to create and reuse shared
    services throughout the application (CLI, desktop, TUI, web).

    All services are singletons: instantiated once and reused.
    """

    _storage: StorageService | None = None
    _translation_cache: TranslationCache | None = None
    _settings: PreferencesService | None = None
    _preferences: PreferencesService | None = None
    _usage: UsageService | None = None
    _jobs: JobQueueService | None = None
    _requests: NovelRequestService | None = None
    _translation: TranslationService | None = None
    _export: ExportService | None = None
    _orchestrator: NovelOrchestrationService | None = None
    _job_worker: JobWorkerService | None = None
    _job_runner: BackgroundJobRunner | None = None

    @property
    def storage(self) -> StorageService:
        if self._storage is None:
            self._storage = StorageService()
        return self._storage

    @property
    def translation_cache(self) -> TranslationCache:
        if self._translation_cache is None:
            self._translation_cache = TranslationCache()
        return self._translation_cache

    @property
    def settings(self) -> PreferencesService:
        if self._settings is None:
            self._settings = PreferencesService()
        return self._settings

    @property
    def preferences(self) -> PreferencesService:
        if self._preferences is None:
            self._preferences = PreferencesService()
        return self._preferences

    @property
    def usage(self) -> UsageService:
        if self._usage is None:
            self._usage = UsageService()
        return self._usage

    @property
    def jobs(self) -> JobQueueService:
        if self._jobs is None:
            self._jobs = JobQueueService()
        return self._jobs

    @property
    def requests(self) -> NovelRequestService:
        if self._requests is None:
            self._requests = NovelRequestService()
        return self._requests

    @property
    def job_worker(self) -> JobWorkerService:
        if self._job_worker is None:
            self._job_worker = JobWorkerService(self.jobs, self.orchestrator)
        return self._job_worker

    @property
    def job_runner(self) -> BackgroundJobRunner:
        if self._job_runner is None:
            self._job_runner = BackgroundJobRunner(
                self.job_worker,
                poll_seconds=settings.JOB_WORKER_POLL_SECONDS,
            )
        return self._job_runner

    @property
    def translation(self) -> TranslationService:
        if self._translation is None:
            # Build translation service with all dependencies
            from novelai.pipeline.pipeline import TranslationPipeline
            from novelai.pipeline.stages.fetch import FetchStage
            from novelai.pipeline.stages.parse import ParseStage
            from novelai.pipeline.stages.post_process import PostProcessStage
            from novelai.pipeline.stages.segment import SegmentStage
            from novelai.pipeline.stages.translate import TranslateStage

            stages = [
                FetchStage(),
                ParseStage(),
                SegmentStage(),
                TranslateStage(
                    provider_factory=get_provider,
                    cache=self.translation_cache,
                    settings_service=self.settings,
                    usage_service=self.usage,
                ),
                PostProcessStage(),
            ]
            self._translation = TranslationService(pipeline=TranslationPipeline(stages=stages))
        return self._translation

    @property
    def export(self) -> ExportService:
        if self._export is None:
            self._export = ExportService()
        return self._export

    @property
    def orchestrator(self) -> NovelOrchestrationService:
        if self._orchestrator is None:
            from novelai.sources.registry import get_source
            self._orchestrator = NovelOrchestrationService(
                storage=self.storage,
                translation=self.translation,
                source_factory=get_source,
            )
        return self._orchestrator


# Global singleton container used by application entrypoints.
container = Container()
