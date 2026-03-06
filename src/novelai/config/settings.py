from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Global configuration for Novel AI."""

    # --- Runtime
    ENV: str = Field("development", description="Application environment.")
    LOG_LEVEL: str = Field("INFO", description="Logging level (DEBUG/INFO/WARN/ERROR)")

    # --- Storage
    DATA_DIR: Path = Field(Path("data"), description="Base directory for stored novels and artifacts.")

    # --- Web
    WEB_HOST: str = Field("127.0.0.1", description="Host for the web server.")
    WEB_PORT: int = Field(8000, description="Port for the web server.")

    # --- Provider / Model
    PROVIDER_DEFAULT: str = Field("dummy", description="Default translation provider key.")
    PROVIDER_OPENAI_API_KEY: Optional[SecretStr] = Field(None, description="OpenAI API key.")

    # --- Translation
    TRANSLATION_CONCURRENCY: int = Field(4, description="Max concurrent translation requests.")
    COST_PER_TOKEN_USD: float = Field(
        0.000002,
        description="Estimated cost per token in USD (used for diagnostics only).",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = AppSettings()
