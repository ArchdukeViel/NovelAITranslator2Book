from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from novelai.services.export_service import ExportService
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService


@dataclass
class Container:
    """Application dependency container.

    This is a simple, explicit DI container used to create and reuse shared
    services throughout the application (CLI, TUI, web).
    """

    _storage: Optional[StorageService] = None
    _translation: Optional[TranslationService] = None
    _export: Optional[ExportService] = None
    _settings: Optional[SettingsService] = None
    _usage: Optional[UsageService] = None

    @property
    def storage(self) -> StorageService:
        if self._storage is None:
            self._storage = StorageService()
        return self._storage

    @property
    def translation(self) -> TranslationService:
        if self._translation is None:
            self._translation = TranslationService()
        return self._translation

    @property
    def export(self) -> ExportService:
        if self._export is None:
            self._export = ExportService()
        return self._export

    @property
    def settings(self) -> SettingsService:
        if self._settings is None:
            self._settings = SettingsService()
        return self._settings

    @property
    def usage(self) -> UsageService:
        if self._usage is None:
            self._usage = UsageService()
        return self._usage


# Global singleton container used by application entrypoints.
container = Container()
