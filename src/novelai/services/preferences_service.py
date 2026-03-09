from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import SecretStr

from novelai.config.settings import settings


class PreferencesService:
    """User preferences persistence (NOT configuration, NOT secrets).
    
    IMPORTANT DISTINCTION:
    - AppSettings: System/environment configuration (from .env / env vars)
    - PreferencesService: User preferences (persisted to disk, no secrets)
    - Secrets: ALWAYS from environment variables (NEVER persisted)
    
    This service stores user choices like:
    - Which provider to use (openai vs dummy, etc)
    - Which model to use (gpt-5.4, gpt-5.2, etc)
    - User UI preferences
    
    It NEVER stores API keys or other secrets.
    """

    PREFS_FILENAME = "preferences.json"

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = (storage_dir or settings.DATA_DIR).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.prefs_path = self.storage_dir / self.PREFS_FILENAME
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.prefs_path.exists():
            return {}
        try:
            return json.loads(self.prefs_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _persist(self) -> None:
        self.prefs_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a preference value."""
        self._data[key] = value
        self._persist()

    # ============================================================================
    # Strongly-typed preference methods (for IDE support and clarity)
    # ============================================================================

    def get_preferred_provider(self) -> str:
        """Get user's preferred translation provider."""
        return self.get("preferred_provider", "dummy")

    def set_preferred_provider(self, provider_key: str) -> None:
        """Set user's preferred translation provider."""
        self.set("preferred_provider", provider_key)

    def get_preferred_model(self) -> str:
        """Get user's preferred translation model."""
        return self.get("preferred_model", "gpt-5.4")

    def set_preferred_model(self, model: str) -> None:
        """Set user's preferred translation model."""
        self.set("preferred_model", model)

    def get_preferred_source(self) -> Optional[str]:
        """Get user's preferred scraping source."""
        return self.get("preferred_source")

    def set_preferred_source(self, source_key: str) -> None:
        """Set user's preferred scraping source."""
        self.set("preferred_source", source_key)

    # UI preferences
    def get_theme(self) -> str:
        """Get user's preferred UI theme."""
        return self.get("theme", "auto")

    def set_theme(self, theme: str) -> None:
        """Set user's preferred UI theme."""
        self.set("theme", theme)

    def get_language(self) -> str:
        """Get user's preferred UI language."""
        return self.get("language", "en")

    def set_language(self, language: str) -> None:
        """Set user's preferred UI language."""
        self.set("language", language)

    # ============================================================================
    # Backward-compatible aliases (formerly in SettingsService)
    # ============================================================================

    def get_provider_key(self) -> str:
        """Alias for get_preferred_provider (backward compat)."""
        return self.get_preferred_provider()

    def set_provider_key(self, key: str) -> None:
        """Alias for set_preferred_provider (backward compat)."""
        self.set_preferred_provider(key)

    def get_provider_model(self) -> str:
        """Get preferred model with OpenAI validation."""
        model = self.get_preferred_model()
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
        """Alias for set_preferred_model (backward compat)."""
        self.set_preferred_model(model)

    # ============================================================================
    # Runtime API key management (from environment, never persisted)
    # ============================================================================

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
