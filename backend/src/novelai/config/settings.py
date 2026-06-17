from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _default_novel_library_dir() -> Path:
    return PROJECT_ROOT / "storage" / "novel_library"


def _resolve_project_path(path: Path) -> Path:
    if path.is_absolute() or path.anchor:
        return path
    return PROJECT_ROOT / path


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
        default_factory=_default_novel_library_dir,
        validation_alias=AliasChoices("NOVEL_LIBRARY_DIR", "DATA_DIR"),
    )

    # Legacy alias for backward compatibility
    @property
    def DATA_DIR(self) -> Path:
        """Backward compatibility: DATA_DIR now points to NOVEL_LIBRARY_DIR."""
        return _resolve_project_path(self.NOVEL_LIBRARY_DIR)

    # --- Web
    WEB_HOST: str = "127.0.0.1"
    WEB_PORT: int = 8000
    WEB_API_KEY: SecretStr | None = None
    WEB_CORS_ORIGINS: list[str] = Field(default_factory=list)
    WEB_REQUEST_TIMEOUT_SECONDS: int = 600
    WEB_RATE_LIMITER_BACKEND: str = "memory"
    JOB_WORKER_ENABLED: bool = False
    JOB_WORKER_POLL_SECONDS: float = 2.0

    # --- Provider / Model
    PROVIDER_DEFAULT: str = "dummy"
    PROVIDER_OPENAI_API_KEY: SecretStr | None = None
    PROVIDER_GEMINI_API_KEY: SecretStr | None = None
    PROVIDER_GEMINI_MODEL_FALLBACKS: list[str] = Field(
        default_factory=lambda: [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
            "gemini-3-flash-preview",
            "gemini-3-pro-preview",
            "gemini-3.1-flash-preview",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-flash-latest",
            "gemini-pro-latest",
        ],
        description=(
            "Gemini text model fallback order. Override with a JSON list if Google AI Studio "
            "enables newer series such as Gemini 3.1 for your account."
        ),
    )

    # --- Scraping
    SCRAPE_DELAY_SECONDS: float = Field(
        default=1.0,
        description="Minimum delay (seconds) between HTTP requests to source sites.",
    )

    # --- Translation
    TRANSLATION_CONCURRENCY: int = 4
    TRANSLATION_TARGET_CHARS_PER_CHUNK: int = 4500
    TRANSLATION_HARD_MAX_CHARS_PER_CHUNK: int = 7000
    TRANSLATION_CHUNK_OVERLAP_PARAGRAPHS: int = 1
    TRANSLATION_ALLOW_MULTI_CHAPTER_BUNDLES: bool = True
    TRANSLATION_MAX_CHAPTERS_PER_BUNDLE: int = 3
    TRANSLATION_MAX_ATTEMPTS_PER_CHUNK: int = 3
    TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE: int = 25
    TRANSLATION_ADAPTIVE_CHUNKING_ENABLED: bool = True
    TRANSLATION_ADAPTIVE_SOFT_TARGET_CHARS: int = 5800
    TRANSLATION_ADAPTIVE_HARD_MAX_CHARS: int = 7000
    TRANSLATION_CONDITIONAL_OVERLAP_ENABLED: bool = True
    TRANSLATION_DEFAULT_OVERLAP_PARAGRAPHS: int = 0
    TRANSLATION_UNSAFE_BOUNDARY_OVERLAP_PARAGRAPHS: int = 1
    TRANSLATION_BOUNDARY_CONTEXT_CHARS: int = 160
    TRANSLATION_DELTA_WINDOW_PADDING_PARAGRAPHS: int = 1
    TRANSLATION_SCHEDULER_POLICY: str = "volume_first"
    TRANSLATION_MODEL_POLICY: list[dict[str, object]] = Field(
        default_factory=list,
        description=(
            "Editable scheduler model policy. Items may define provider_key, provider_model, "
            "priority_order, quality_priority_order, rpm_limit, and rpd_limit."
        ),
    )
    COST_PER_TOKEN_USD: float = 0.000002
    TRANSLATION_TARGET_LANGUAGE: str = "English"

    # --- Database
    DATABASE_URL: str | None = None

    # --- Redis (Phase 3 workers)
    REDIS_URL: str | None = None

    # --- Auth / Session (Phase 4)
    # Secret key for signing HTTP-only session cookies.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    SESSION_SECRET_KEY: str = "changeme-generate-a-real-secret-in-production"
    # Bootstrap secret for the owner to log in before Google OAuth is available.
    # Set to a strong random value in .env; never commit the real value.
    OWNER_BOOTSTRAP_SECRET: str | None = None
    # Session cookie max age in seconds (default: 8 hours).
    SESSION_MAX_AGE: int = 28_800
    # Google OAuth for public user login. Missing values disable OAuth endpoints
    # without breaking app startup.
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_OAUTH_REDIRECT_URI: str | None = None
    PUBLIC_FRONTEND_URL: str = "http://127.0.0.1:3000"

    # --- Cache
    TRANSLATION_CACHE_MAX_ENTRIES: int = 50_000
    USAGE_LOG_MAX_ENTRIES: int = 10_000


settings = AppSettings()
