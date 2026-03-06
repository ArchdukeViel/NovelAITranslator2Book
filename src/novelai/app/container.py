from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from novelai.providers.registry import get_provider
from novelai.services.export_service import ExportService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService


@dataclass
class Container:
    """Application dependency container.

    This is a simple, explicit DI container used to create and reuse shared
    services throughout the application (CLI, TUI, web).
    
    All services are singletons: instantiated once and reused.
    """

    _storage: Optional[StorageService] = None
    _translation_cache: Optional[TranslationCache] = None
    _settings: Optional[SettingsService] = None
    _preferences: Optional[PreferencesService] = None
    _usage: Optional[UsageService] = None
    _translation: Optional[TranslationService] = None
    _export: Optional[ExportService] = None
    _orchestrator: Optional[NovelOrchestrationService] = None

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
    def settings(self) -> SettingsService:
        if self._settings is None:
            self._settings = SettingsService()
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
    def translation(self) -> TranslationService:
        if self._translation is None:
            # Build translation service with all dependencies
            from novelai.pipeline.pipeline import TranslationPipeline
            from novelai.pipeline.stages.fetch import FetchStage
            from novelai.pipeline.stages.parse import ParseStage
            from novelai.pipeline.stages.segment import SegmentStage
            from novelai.pipeline.stages.translate import TranslateStage
            from novelai.pipeline.stages.post_process import PostProcessStage

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
