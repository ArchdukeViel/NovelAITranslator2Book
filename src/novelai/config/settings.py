from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Global configuration for Novel AI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Runtime
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Storage
    # Novel library directory - contains all downloaded novels, translations, and exports
    NOVEL_LIBRARY_DIR: Path = Path("novel_library")
    
    # Legacy alias for backward compatibility
    @property
    def DATA_DIR(self) -> Path:
        """Backward compatibility: DATA_DIR now points to NOVEL_LIBRARY_DIR."""
        return self.NOVEL_LIBRARY_DIR

    # --- Web
    WEB_HOST: str = "127.0.0.1"
    WEB_PORT: int = 8000

    # --- Provider / Model
    PROVIDER_DEFAULT: str = "dummy"
    PROVIDER_OPENAI_API_KEY: SecretStr | None = None

    # --- Translation
    TRANSLATION_CONCURRENCY: int = 4
    COST_PER_TOKEN_USD: float = 0.000002


settings = AppSettings()
