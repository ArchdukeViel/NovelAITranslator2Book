from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from novelai.config.settings import settings


class SettingsService:
    """Persistent user preferences for translation workflow.
    
    DEPRECATED: Use PreferencesService instead.
    This class is kept for backwards compatibility but now delegates to PreferencesService.
    
    NOTE: API keys MUST NEVER be stored here.
    They must ALWAYS come from environment variables only.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        # For backwards compatibility, keep the same interface
        self.storage_dir = (storage_dir or settings.DATA_DIR).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Import here to avoid circular imports
        from novelai.services.preferences_service import PreferencesService
        self._prefs = PreferencesService(storage_dir=storage_dir or settings.DATA_DIR)

    def get(self, key: str, default: Any = None) -> Any:
        return self._prefs.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._prefs.set(key, value)

    def get_provider_key(self) -> str:
        return self._prefs.get_preferred_provider()

    def set_provider_key(self, key: str) -> None:
        self._prefs.set_preferred_provider(key)

    def get_provider_model(self) -> str:
        return self._prefs.get_preferred_model()

    def set_provider_model(self, model: str) -> None:
        self._prefs.set_preferred_model(model)

    # NOTE: API keys MUST NEVER be persisted to disk.
    # They must always come from environment variables (PROVIDER_OPENAI_API_KEY, etc.).
    # Use dotenv or .env file for local development, but never commit secrets to git.
    # For production, use OS secret management or secrets vault.
