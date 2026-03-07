from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
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
    # Main runtime library: metadata, chapters, exports, preferences, logs.
    NOVEL_LIBRARY_DIR: Path = Field(
        default=Path("novel_library"),
        validation_alias=AliasChoices("NOVEL_LIBRARY_DIR", "DATA_DIR"),
    )

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
    TRANSLATION_TARGET_LANGUAGE: str = "English"


settings = AppSettings()
