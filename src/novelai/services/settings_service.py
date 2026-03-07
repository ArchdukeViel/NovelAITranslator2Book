from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import SecretStr

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
        model = self._prefs.get_preferred_model()
        provider_key = self.get_provider_key()
        if provider_key != "openai":
            return model

        try:
            from novelai.providers.registry import available_models

            supported_models = available_models(provider_key)
        except Exception:
            return model

        if model in supported_models:
            return model
        return supported_models[0] if supported_models else model

    def set_provider_model(self, model: str) -> None:
        self._prefs.set_preferred_model(model)

    def get_api_key(self) -> str | None:
        """Return the runtime API key from environment-backed settings."""
        api_key = settings.PROVIDER_OPENAI_API_KEY
        if api_key is None:
            return None
        return api_key.get_secret_value()

    def set_api_key(self, api_key: str) -> None:
        """Update the runtime API key without persisting it to disk."""
        os.environ["PROVIDER_OPENAI_API_KEY"] = api_key
        settings.PROVIDER_OPENAI_API_KEY = SecretStr(api_key)

    def clear_api_key(self) -> None:
        """Remove the runtime API key from environment-backed settings."""
        os.environ.pop("PROVIDER_OPENAI_API_KEY", None)
        settings.PROVIDER_OPENAI_API_KEY = None

    # NOTE: API keys MUST NEVER be persisted to disk.
    # They must always come from environment variables (PROVIDER_OPENAI_API_KEY, etc.).
    # Use dotenv or .env file for local development, but never commit secrets to git.
    # For production, use OS secret management or secrets vault.
