# pyright: strict
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Kept as a compatibility name for older configuration imports. It is not a
# second candidate: the production contract uses one exact Gemini model.
GEMINI_FALLBACK_MODEL = GEMINI_DEFAULT_MODEL


def _default_runtime_dir() -> Path:
    return PROJECT_ROOT / "storage" / "runtime"


def _resolve_project_path(path: Path) -> Path:
    if path.is_absolute() or path.anchor:
        return path
    return PROJECT_ROOT / path


def _empty_string_to_empty_list(v: Any) -> Any:
    """Normalize empty string to empty list for list-typed settings.

    With NoDecode annotation, pydantic-settings passes the raw env string
    instead of attempting JSON parsing. Empty string is normalized to [].
    Comma-separated values are split into a list.
    """
    if v == "" or v is None:
        return []
    if isinstance(v, str):
        # Handle comma-separated values like "a,b,c"
        return [item.strip() for item in v.split(",") if item.strip()]
    return v


class AppSettings(BaseSettings):
    """Global configuration for Novel AI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Service role (admin or reader)
    SERVICE_ROLE: str = Field(
        default="admin",
        description="Service role: 'admin' (port 8000) or 'reader' (port 8001). Reader skips session/owner validation.",
    )

    # --- Runtime
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- R2 content storage and disposable runtime
    R2_BUCKET: str = Field(
        default="dokushodo",
        description="Canonical Cloudflare R2 application bucket.",
    )
    R2_REGION: str = Field(
        default="auto",
        description="Cloudflare R2 signing region.",
    )
    R2_ENDPOINT: str | None = Field(
        default=None,
        description="Cloudflare R2 account endpoint.",
    )
    R2_ACCESS_KEY_ID: SecretStr | None = Field(default=None)
    R2_SECRET_ACCESS_KEY: SecretStr | None = Field(default=None)
    R2_STORAGE_LIMIT_GB: float = Field(
        default=9.5,
        description="R2 application bucket soft limit in GB.",
    )
    R2_BACKUP_BUCKET: str = Field(
        default="dokushodo-backup",
        description="Independent Cloudflare R2 recovery bucket.",
    )
    R2_BACKUP_ENDPOINT: str | None = Field(default=None)
    R2_BACKUP_ACCESS_KEY_ID: SecretStr | None = Field(default=None)
    R2_BACKUP_SECRET_ACCESS_KEY: SecretStr | None = Field(default=None)
    R2_SOURCE_ACCESS_KEY_ID: SecretStr | None = Field(default=None)
    R2_SOURCE_SECRET_ACCESS_KEY: SecretStr | None = Field(default=None)
    RUNTIME_DIR: Path = Field(default_factory=_default_runtime_dir)

    @field_validator("RUNTIME_DIR", mode="after")
    @classmethod
    def _resolve_runtime_dir(cls, value: Path) -> Path:
        return _resolve_project_path(value)

    # --- Web
    WEB_HOST: str = "127.0.0.1"
    WEB_PORT: int = 8000
    WEB_CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=list)
    WEB_REQUEST_TIMEOUT_SECONDS: int = 600
    WEB_RATE_LIMITER_BACKEND: str = "memory"
    DEBUG_ERRORS: bool = Field(
        default=False,
        description="Include internal error traces in HTTP 500 error responses (development only).",
    )
    JOB_WORKER_ENABLED: bool = False
    JOB_WORKER_POLL_SECONDS: float = 2.0
    ACTIVITY_HISTORY_MAX_ENTRIES: int = Field(
        default=10_000,
        ge=100,
        le=1_000_000,
        description="Maximum activity history returned by bounded operator/list queries.",
    )
    ACTIVITY_METADATA_MAX_BYTES: int = Field(
        default=256_000,
        ge=4_096,
        le=4_000_000,
        description="Maximum serialized progress/result metadata stored on one activity.",
    )
    ACTIVITY_RETRY_HISTORY_MAX_ENTRIES: int = Field(
        default=100,
        ge=1,
        le=10_000,
        description="Maximum retry snapshots retained inside one activity metadata record.",
    )

    # --- Outbound fetch hardening (bounded redirects, streaming size limits)
    HTTP_MAX_REDIRECTS: int = Field(default=5, ge=1, le=20)
    HTTP_RETRY_AFTER_MAX_SECONDS: int = Field(default=120, ge=1, le=3600)
    HTTP_API_RESPONSE_MAX_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024)
    HTTP_HTML_RESPONSE_MAX_BYTES: int = Field(default=20 * 1024 * 1024, ge=1024)
    HTTP_ASSET_RESPONSE_MAX_BYTES: int = Field(default=50 * 1024 * 1024, ge=1024)

    # --- Production hardening (DEBT-055)
    TRUSTED_PROXY_CIDRS: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="CIDR ranges of trusted reverse proxies. Forwarded headers are honored only from these.",
    )
    ALLOWED_HOSTS: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Allowed Host header values. Empty list disables host validation (development only).",
    )
    CSRF_TRUSTED_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Origins trusted for CSRF. Should match WEB_CORS_ORIGINS in production.",
    )
    SECURITY_HEADERS_ENABLED: bool = Field(
        default=True,
        description="Emit baseline security headers (X-Content-Type-Options, Referrer-Policy, X-Frame-Options).",
    )
    HSTS_MAX_AGE_SECONDS: int = Field(
        default=0,
        description="HSTS max-age. Set >0 only for HTTPS production domains. 0 disables HSTS.",
    )

    # --- Request body enforcement (ASGI middleware)
    WEB_MAX_AUTH_BODY_BYTES: int = Field(
        default=65_536,
        ge=1_024,
        le=1_048_576,
        description="Max request body bytes for /api/auth/* endpoints.",
    )
    WEB_MAX_JSON_BODY_BYTES: int = Field(
        default=1_048_576,
        ge=4_096,
        le=33_554_432,
        description="Max request body bytes for general /api/* mutation endpoints.",
    )
    WEB_MAX_DOCUMENT_BODY_BYTES: int = Field(
        default=33_554_432,
        ge=65_536,
        le=268_435_456,
        description="Reserved max body bytes for future document upload (32 MiB). No current upload route.",
    )

    @field_validator(
        "WEB_CORS_ORIGINS",
        "TRUSTED_PROXY_CIDRS",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
        mode="before",
    )
    @classmethod
    def _normalize_empty_list_env(cls, v: Any) -> Any:
        return _empty_string_to_empty_list(v)

    # --- Provider / Model
    PROVIDER_DEFAULT: str = "gemini"
    PROVIDER_GEMINI_API_KEY: SecretStr | None = None
    PROVIDER_CREDENTIAL_ENCRYPTION_KEY: SecretStr | None = None
    PROVIDER_GEMINI_DEFAULT_MODEL: str = GEMINI_DEFAULT_MODEL
    PROVIDER_GEMINI_MODEL_FALLBACKS: list[str] = Field(
        default_factory=list,
        description="Deprecated compatibility setting. Gemini model fallback is disabled.",
    )

    @field_validator("PROVIDER_GEMINI_DEFAULT_MODEL", mode="before")
    @classmethod
    def _enforce_gemini_model_contract(cls, value: Any) -> str:
        """Reject explicit model drift instead of silently selecting another model."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return GEMINI_DEFAULT_MODEL
        if str(value).strip() != GEMINI_DEFAULT_MODEL:
            raise ValueError(
                f"PROVIDER_GEMINI_DEFAULT_MODEL must be {GEMINI_DEFAULT_MODEL}; model fallback is disabled."
            )
        return GEMINI_DEFAULT_MODEL

    @field_validator("PROVIDER_GEMINI_MODEL_FALLBACKS", mode="before")
    @classmethod
    def _disable_gemini_model_fallbacks(cls, value: Any) -> list[str]:
        """Reject configured alternatives while retaining the legacy field."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return []
        if isinstance(value, (list, tuple, set)) and not value:
            return []
        raise ValueError("PROVIDER_GEMINI_MODEL_FALLBACKS must be empty; model fallback is disabled.")

    # --- Public contributor credentials
    CONTRIBUTOR_CREDENTIALS_ENABLED: bool = Field(
        default=True,
        description="Enable authenticated contributor credential intake and contributor-backed translation jobs.",
    )
    CONTRIBUTOR_CONSENT_VERSION: str = Field(
        default="2026-08-19",
        description="Consent text version accepted when a user registers a contributor credential.",
    )
    CONTRIBUTOR_MAX_ACTIVE_PER_USER: int = Field(default=1, ge=1, le=1)
    CONTRIBUTOR_RPM_LIMIT: int = Field(default=15, ge=1)
    CONTRIBUTOR_TPM_LIMIT: int = Field(default=250_000, ge=1)
    CONTRIBUTOR_RPD_LIMIT: int = Field(default=500, ge=1)
    CONTRIBUTOR_USAGE_RETENTION_DAYS: int = Field(default=365, ge=1)

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
    TRANSLATION_PROVIDER_DEADLINE_SECONDS: int = Field(
        default=600,
        ge=1,
        le=86_400,
        description="Maximum provider/retry time for one translation chunk before failing fast.",
    )
    TRANSLATION_PROVIDER_RETRY_BACKOFF_BASE_SECONDS: float = Field(default=1.0, ge=0.0, le=60.0)
    TRANSLATION_PROVIDER_RETRY_BACKOFF_MAX_SECONDS: float = Field(default=30.0, ge=0.0, le=300.0)
    TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE: int = 25
    TRANSLATION_GLOSSARY_BATCH_SIZE: int = Field(default=25, ge=1, le=100)
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
    TRANSLATION_MODEL_POLICY: list[dict[str, Any]] = Field(  # pyright: ignore[reportUnknownVariableType]
        default_factory=list,
        description=(
            "Editable scheduler model policy. Items may define provider_key, provider_model, "
            "priority_order, quality_priority_order, rpm_limit, and rpd_limit."
        ),
    )
    COST_PER_TOKEN_USD: float = 0.000002
    TRANSLATION_TARGET_LANGUAGE: str = "English"
    TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD: float = 0.55
    GEMINI_RPM_LIMIT: int = Field(default=15, ge=1)
    GEMINI_TPM_LIMIT: int = Field(default=250_000, ge=1)
    GEMINI_RPD_LIMIT: int = Field(default=500, ge=1)
    GEMINI_CONCURRENCY_LIMIT: int = Field(
        default=4,
        ge=1,
        le=256,
        description="Global in-flight Gemini request limit shared by all processes using the owner key.",
    )
    CONTRIBUTOR_CONCURRENCY_LIMIT: int = Field(
        default=2,
        ge=1,
        le=256,
        description="Global in-flight request limit per contributor credential.",
    )
    PROVIDER_RESERVATION_TTL_SECONDS: int = Field(
        default=900,
        ge=60,
        le=86_400,
        description="Maximum age of a provider admission reservation before it stops counting as in-flight.",
    )
    GEMINI_ESTIMATED_OUTPUT_TOKENS: int = Field(default=1024, ge=1)

    # --- Database
    DATABASE_URL: str | None = None
    MIGRATION_DATABASE_URL: str | None = None
    DATABASE_BACKUP_URL: SecretStr | None = None
    DB_CONNECTION_MODE: Literal["direct", "session", "transaction"] = "direct"
    DB_POOL_SIZE: int = Field(default=5, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0)
    DB_POOL_PROCESS_COUNT: int = Field(
        default=3,
        ge=1,
        description=(
            "Number of long-lived processes/replicas that can own a configured "
            "database pool in the deployment topology."
        ),
    )
    DB_CONNECTION_RESERVE: int = Field(
        default=2,
        ge=0,
        description=(
            "Connections reserved for migration, readiness, and emergency "
            "operator access outside long-lived application pool ceilings."
        ),
    )
    DB_CONNECTION_BUDGET: int = Field(default=20, ge=1)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=0)
    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=10, ge=1)
    DB_SSL_MODE: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=120_000, ge=1)
    DB_LOCK_TIMEOUT_MS: int = Field(default=10_000, ge=1)
    DB_IDLE_IN_TRANSACTION_TIMEOUT_MS: int = Field(default=60_000, ge=1)

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
    # Development-only override. Staging and production are always secure even
    # if an old environment file still contains SESSION_COOKIE_SECURE=false.
    SESSION_COOKIE_SECURE: bool | None = None
    # Google OAuth for public user login. Missing values disable OAuth endpoints
    # without breaking app startup.
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_OAUTH_REDIRECT_URI: str | None = None
    PUBLIC_FRONTEND_URL: str | None = "http://127.0.0.1:3000"
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
    PUBLIC_RANKING_CACHE_ENABLED: bool = True
    PUBLIC_RANKING_CACHE_TTL_SECONDS: int = Field(default=60, ge=1, le=300)
    PUBLIC_RANKING_CACHE_MAX_ENTRIES: int = Field(default=64, ge=1, le=1024)
    PUBLIC_PROJECTION_CACHE_ENABLED: bool = True
    PUBLIC_PROJECTION_CACHE_TTL_SECONDS: int = Field(default=30, ge=1, le=300)
    PUBLIC_PROJECTION_CACHE_MAX_ENTRIES: int = Field(default=256, ge=1, le=2048)
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

    # --- LLM QA (DEBT-053): default-off; activates LLM-based translation grading.
    # When enabled and a translation provider is available, the QA stage also
    # asks the configured provider to grade each chunk that passes the
    # deterministic checks. Chunks below LLM_QA_MIN_SCORE are disposed of
    # according to LLM_QA_POLICY:
    #   advisory      - (default) deterministic QA stays green; a warning is
    #                   recorded and no retry marker is produced.
    #   blocking_retry- chunk status becomes needs_retry (bounded by
    #                   LLM_QA_MAX_RETRY_ATTEMPTS); once exhausted the chunk
    #                   moves to needs_review.
    #   review        - chunk status becomes needs_review immediately.
    # A retry marker is always backed by a real chunk status; a chunk is never
    # left "translated" while claiming a retry state.
    LLM_QA_ENABLED: bool = False
    LLM_QA_PROVIDER: str = "gemini"
    LLM_QA_MODEL: str = GEMINI_DEFAULT_MODEL
    LLM_QA_COST_TRACKING_ENABLED: bool = True
    LLM_QA_MIN_SCORE: float = 0.75
    LLM_QA_MAX_RETRY_ATTEMPTS: int = 1
    LLM_QA_POLICY: str = "advisory"
    LLM_QA_SAMPLE_RATE: float = Field(default=0.10, ge=0.0, le=1.0)
    LLM_QA_RISK_SCORE_THRESHOLD: float = Field(default=0.90, ge=0.0, le=1.0)
    LLM_QA_MAX_CONTEXT_CHARS: int = Field(default=6000, ge=500)

    @field_validator("LLM_QA_POLICY", mode="after")
    @classmethod
    def _validate_llm_qa_policy(cls, v: str) -> str:
        valid = {"advisory", "blocking_retry", "review"}
        if v not in valid:
            raise ValueError(f"Invalid LLM_QA_POLICY '{v}'. Allowed values: {sorted(valid)}")
        return v

    # --- Public reader availability
    # Controls behavior when a public chapter has no active translation.
    # Allowed values: "hard_404" (default), "chapter_shell", "latest_version".
    # Invalid values are tolerated at load time and resolved by the public router.
    PUBLIC_READER_UNAVAILABLE_POLICY: str = "hard_404"

    # --- Public glossary annotations
    # Enable glossary term annotations in public chapter reader.
    # When enabled, approved glossary terms are matched against translated text
    # and returned as annotations for highlighting/tooltips.
    PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED: bool = True

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
        ge=0,
        le=300,
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
        description="Enable scheduled R2 backups to the independent recovery bucket.",
    )
    BACKUP_SCHEDULE_CRON: str = Field(
        default="0 2 * * *",
        description="Intended backup schedule. The lightweight scheduler currently runs once per UTC day.",
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
    BACKUP_SAFETY_GRACE_DAYS: int = Field(
        default=7,
        ge=0,
        description="Minimum age for unreferenced R2 backup objects before collection.",
    )
    R2_BACKUP_ENABLED: bool = Field(
        default=False,
        description="Copy scheduled backups to the independent R2 recovery bucket.",
    )
    R2_BACKUP_PREFIX: str = Field(default="snapshots")
    SCHEDULED_JOB_LEASE_SECONDS: int = Field(default=900, ge=60)

    # --- Logical database recovery
    DATABASE_BACKUP_ENABLED: bool = False
    DATABASE_BACKUP_SCHEDULE_CRON: str = "0 1 * * *"
    DATABASE_BACKUP_TIMEZONE: str = "UTC"
    DATABASE_BACKUP_PREFIX: str = "database"
    DATABASE_BACKUP_RETENTION_DAYS: int = Field(default=30, ge=1)
    DATABASE_BACKUP_MIN_SUCCESSFUL_TO_KEEP: int = Field(default=3, ge=1)
    DATABASE_BACKUP_ENCRYPTION_KEY: SecretStr | None = None
    PG_DUMP_PATH: str = "pg_dump"
    DATABASE_RESTORE_VERIFICATION_ENABLED: bool = False
    DATABASE_RESTORE_VERIFICATION_SCHEDULE_CRON: str = "0 3 1 * *"
    DATABASE_RESTORE_VERIFICATION_TIMEZONE: str = "UTC"
    DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS: int = Field(
        default=32,
        ge=1,
        description="Maximum age in days for a successful database restore verification. Exceeding this makes the probe unhealthy.",
    )
    DATABASE_RESTORE_TARGET_URL: SecretStr | None = None
    DATABASE_RESTORE_SSL_MODE: Literal["disable", "require", "verify-ca", "verify-full"] = "require"
    PG_RESTORE_PATH: str = "pg_restore"

    # --- Operator alerts
    OPERATOR_ALERT_ENABLED: bool = False
    OPERATOR_ALERT_EMAIL: str | None = None
    OPERATOR_ALERT_FAILURE_THRESHOLD: int = Field(default=3, ge=1)
    OPERATOR_ALERT_COOLDOWN_SECONDS: int = Field(default=3600, ge=60)
    OPERATOR_ALERT_STALE_BACKUP_HOURS: int = Field(default=36, ge=1)

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
    NOTIFICATION_RETENTION_DAYS: int = Field(
        default=90,
        ge=1,
        description="Retention in days for archived notifications.",
    )
    NOTIFICATION_RETENTION_BATCH_SIZE: int = Field(
        default=500,
        ge=1,
        le=1_000,
        description="Maximum archived notifications deleted per maintenance run.",
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

    # --- SMTP / notification (DEBT-075, DEBT-043)
    # pyright seems to think SMTP_PORT (etc.) are redefined from stdlib
    # typeshed stubs.  The pydantic-settings fields are annotations, not
    # redefinitions — they define environment-variable bindings.
    SMTP_HOST: str | None = Field(  # type: ignore[reportConstantRedefinition]
        default=None,
        description="SMTP server hostname. When set, SmtpNotificationBackend is used instead of the noop logger.",
    )
    SMTP_PORT: int = Field(  # type: ignore[reportConstantRedefinition]
        default=587,
        description="SMTP server port. Default 587 (STARTTLS).",
    )
    SMTP_USERNAME: str | None = Field(  # type: ignore[reportConstantRedefinition]
        default=None,
        description="SMTP username for authentication.",
    )
    SMTP_PASSWORD: SecretStr | None = Field(  # type: ignore[reportConstantRedefinition]
        default=None,
        description="SMTP password for authentication.",
    )
    SMTP_FROM_ADDRESS: str = Field(
        default="noreply@novelai.app",
        description="From: address for outgoing notification emails.",
    )

    # --- Analytics baseline (DEBT-009)
    ANALYTICS_ENABLED: bool = Field(
        default=False,
        description="Enable analytics event recording. When disabled, ingest endpoint returns 503 and server-side recording is skipped.",
    )
    ANALYTICS_PUBLIC_INGESTION_ENABLED: bool = Field(
        default=False,
        description="Enable public analytics ingestion. Requires ANALYTICS_ENABLED.",
    )
    ANALYTICS_STORE_RAW_QUERY: bool = Field(
        default=False,
        description="Store raw search queries. Disabled by default for privacy.",
    )
    ANALYTICS_STORE_IP: bool = Field(
        default=False,
        description="Store client IP addresses. Disabled by default; analytics schema has no IP field.",
    )
    ANALYTICS_RETENTION_DAYS: int = Field(
        default=365,
        ge=1,
        description="Retention in days for analytics events. Events older than this are eligible for cleanup.",
    )
    ANALYTICS_RETENTION_BATCH_SIZE: int = Field(
        default=1_000,
        ge=1,
        le=10_000,
        description="Maximum analytics event rows deleted per retention transaction.",
    )
    ANALYTICS_INGEST_MAX_BATCH: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum public analytics events accepted per request.",
    )
    ANALYTICS_INGEST_MAX_BODY_BYTES: int = Field(
        default=32_768,
        ge=1_024,
        le=262_144,
        description="Maximum public analytics ingestion request body size.",
    )
    ANALYTICS_ASYNC_QUEUE_SIZE: int = Field(
        default=1_000,
        ge=1,
        le=10_000,
        description="Bounded process-local queue capacity for asynchronous analytics writes.",
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


def session_cookie_secure() -> bool:
    """Return the fail-closed session-cookie transport policy."""

    if settings.ENV.strip().lower() in {"staging", "production"}:
        return True
    return settings.SESSION_COOKIE_SECURE is True
