from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
GEMINI_DEFAULT_MODEL = "gemini-3.1-flash-lite"
GEMINI_FALLBACK_MODEL = "gemma-4-31b-it"


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
        extra="ignore",
    )

    # --- Runtime
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Storage
    # Backend type: "filesystem" (default) or "s3"
    STORAGE_BACKEND: str = Field(
        default="filesystem",
        description="Storage backend type. filesystem (default) or s3.",
    )
    S3_BUCKET: str | None = Field(
        default=None,
        description="S3 bucket name. Required when STORAGE_BACKEND=s3.",
    )
    S3_REGION: str = Field(
        default="us-east-1",
        description="S3 region. Default us-east-1.",
    )
    S3_KEY_PREFIX: str = Field(
        default="",
        description="Optional key prefix (folder) for all S3 objects.",
    )
    S3_ENDPOINT: str | None = Field(
        default=None,
        description="Custom S3 endpoint URL (e.g. MinIO).",
    )
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
    PROVIDER_DEFAULT: str = "gemini"
    PROVIDER_GEMINI_API_KEY: SecretStr | None = None
    PROVIDER_CREDENTIAL_ENCRYPTION_KEY: SecretStr | None = None
    PROVIDER_GEMINI_DEFAULT_MODEL: str = GEMINI_DEFAULT_MODEL
    PROVIDER_GEMINI_MODEL_FALLBACKS: list[str] = Field(
        default_factory=lambda: [GEMINI_FALLBACK_MODEL],
        description=(
            "Gemini-only text model fallback order. Default: Gemma 4 31B as the "
            "fallback/alternative to the primary Gemini 3.1 Flash Lite."
        ),
    )

    # --- Scraping
    SCRAPE_DELAY_SECONDS: float = Field(
        default=1.0,
        description="Minimum delay (seconds) between HTTP requests to source sites.",
    )

    # --- Translation
    TRANSLATION_CONCURRENCY: int = 4
    TRANSLATION_CHAPTER_CONCURRENCY: int = Field(
        default=1,
        ge=1,
        le=32,
        description=(
            "Maximum number of chapters translated in parallel inside a single "
            "orchestrator run. 1 preserves the previous sequential behavior. "
            "Upper bound keeps in-flight chapter work within a single worker process."
        ),
    )
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
    TRANSLATION_DELTA_RETRANSLATION_ENABLED: bool = True
    TRANSLATION_DELTA_REQUIRE_STRUCTURED_PARAGRAPH_MAP: bool = True
    TRANSLATION_DELTA_FORCE_FULL_ON_UNSAFE: bool = True
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
    TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD: float = 0.55

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
    AUTH_EMAIL_DELIVERY_MODE: str = "noop"
    AUTH_PASSWORD_RESET_PATH: str = "/password/reset"
    AUTH_EMAIL_VERIFICATION_PATH: str = "/email/verify"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str = "Dokushodo"
    SMTP_STARTTLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: float = 10.0

    # --- Cache
    TRANSLATION_CACHE_ENABLED: bool = True
    TRANSLATION_CACHE_MAX_ENTRIES: int = 100_000
    TRANSLATION_CACHE_TTL_SECONDS: int = 0
    USAGE_LOG_MAX_ENTRIES: int = 10_000

    # --- Semantic Cache (future feature, disabled by default)
    SEMANTIC_CACHE_ENABLED: bool = False
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for semantic cache candidates.",
    )
    SEMANTIC_CACHE_CONTEXT_GUARD_ENABLED: bool = True
    SEMANTIC_CACHE_EMBEDDING_PROVIDER: str = "gemini"
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = "text-embedding-004"

    # --- LLM QA (future feature, disabled by default)
    LLM_QA_ENABLED: bool = False
    LLM_QA_PROVIDER: str = "gemini"
    LLM_QA_MODEL: str = "gemini-3.1-flash-lite"
    LLM_QA_COST_TRACKING_ENABLED: bool = True

    # --- Public reader availability
    # Controls behavior when a public chapter has no active translation.
    # Allowed values: "hard_404" (default), "chapter_shell", "latest_version".
    # Invalid values are tolerated at load time and resolved by the public router.
    PUBLIC_READER_UNAVAILABLE_POLICY: str = "hard_404"

    # --- Public glossary annotations
    # Enable glossary term annotations in public chapter reader.
    # When enabled, approved glossary terms are matched against translated text
    # and returned as annotations for highlighting/tooltips.
    PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED: bool = False

    # --- Health probes (M2a)
    HEALTH_PROBE_TIMEOUT_MS: int = Field(
        default=1000,
        description="Per-probe timeout in milliseconds. A failed probe must not stop unrelated probes.",
    )
    HEALTH_TOTAL_TIMEOUT_MS: int = Field(
        default=3000,
        description="Total timeout for all probes in a readiness/admin health check.",
    )
    HEALTH_CACHE_TTL_SECONDS: int = Field(
        default=5,
        description="Short-TTL cache for readiness results to reduce probe load.",
    )
    HEALTH_DISK_WARNING_FREE_PERCENT: int = Field(
        default=15,
        description="Free disk percentage below which disk probe reports degraded.",
    )
    HEALTH_DISK_CRITICAL_FREE_PERCENT: int = Field(
        default=5,
        description="Free disk percentage below which disk probe reports unhealthy.",
    )

    # --- Backups (M2c)
    BACKUP_ENABLED: bool = Field(
        default=False,
        description="Enable scheduled local backups. Local backup target first; offsite is a future milestone.",
    )
    BACKUP_SCHEDULE_CRON: str = Field(
        default="0 2 * * *",
        description="Cron expression for scheduled backups (APScheduler format). Default: daily at 02:00.",
    )
    BACKUP_TIMEZONE: str = Field(
        default="UTC",
        description="Timezone for backup schedule evaluation.",
    )
    BACKUP_RETENTION_COUNT: int = Field(
        default=5,
        description="Maximum number of successful backups to retain by count.",
    )
    BACKUP_MIN_SUCCESSFUL_TO_KEEP: int = Field(
        default=3,
        description="Minimum successful backups to preserve regardless of age. Never delete the newest successful backup.",
    )
    BACKUP_MAX_AGE_DAYS: int = Field(
        default=30,
        description="Maximum age in days for successful backups. Older backups are eligible for deletion.",
    )

    # --- Maintenance cleanup (M2c)
    MAINTENANCE_ENABLED: bool = Field(
        default=False,
        description="Enable scheduled maintenance cleanup.",
    )
    MAINTENANCE_SCHEDULE_CRON: str = Field(
        default="0 3 * * *",
        description="Cron expression for scheduled maintenance (APScheduler format). Default: daily at 03:00.",
    )
    MAINTENANCE_TIMEZONE: str = Field(
        default="UTC",
        description="Timezone for maintenance schedule evaluation.",
    )
    MAINTENANCE_DRY_RUN: bool = Field(
        default=False,
        description="When true, maintenance scans eligible items without deleting. Useful for staging verification.",
    )
    MAINTENANCE_ACTIVITY_RETENTION_DAYS: int = Field(
        default=90,
        description="Retention in days for completed successful activity records.",
    )
    MAINTENANCE_FAILED_ACTIVITY_RETENTION_DAYS: int = Field(
        default=180,
        description="Retention in days for failed activity records.",
    )
    MAINTENANCE_FETCH_CACHE_MAX_AGE_HOURS: int = Field(
        default=24,
        description="Maximum age in hours for fetch cache entries. Older entries are eligible for cleanup.",
    )
    MAINTENANCE_PIPELINE_EVENTS_MAX_AGE_DAYS: int = Field(
        default=30,
        description="Maximum age in days for pipeline event records.",
    )
    MAINTENANCE_SCHEDULER_STATE_RETENTION_DAYS: int = Field(
        default=14,
        description="Retention in days for expired scheduler runtime state records.",
    )

    # --- Scheduler runtime state (M2c, DEBT-036)
    SCHEDULER_HEARTBEAT_INTERVAL_SECONDS: int = Field(
        default=30,
        description="Interval at which the scheduler updates its heartbeat.",
    )
    SCHEDULER_STALE_AFTER_SECONDS: int = Field(
        default=120,
        description="Heartbeat age after which the scheduler is considered stale.",
    )
    SCHEDULER_RUNTIME_STATE_TTL_DAYS: int = Field(
        default=14,
        description="TTL in days for expired scheduler runtime state records.",
    )

    # --- File lock (M2c, DEBT-035)
    FILE_LOCK_RETRY_COUNT: int = Field(
        default=10,
        description="Maximum retries for acquiring a multi-process file lock on Windows.",
    )
    FILE_LOCK_RETRY_DELAY_SECONDS: float = Field(
        default=0.1,
        description="Delay between retry attempts when acquiring a file lock.",
    )


settings = AppSettings()
