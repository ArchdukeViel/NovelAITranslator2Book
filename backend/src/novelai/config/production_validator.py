"""Production configuration validator.

Validates that production deployments have safe, explicit configuration.
Fatal issues cause startup to fail before serving traffic.
Warnings and info messages are logged but do not block startup.

Never logs or returns secret values, database URLs, raw paths, or credentials.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from novelai.config.settings import AppSettings

DEFAULT_SECRET_VALUES: frozenset[str] = frozenset(
    {
        "changeme-generate-a-real-secret-in-production",
        "changeme",
        "secret",
        "password",
        "test",
        "dev",
        "development",
        "example",
        "placeholder",
        "todo",
        "none",
        "null",
        "",
    }
)

WEAK_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(?:a+|1+|0+|x+|\s*)$", re.IGNORECASE),
    re.compile(r"^test", re.IGNORECASE),
    re.compile(r"^dev", re.IGNORECASE),
    re.compile(r"^example", re.IGNORECASE),
    re.compile(r"^placeholder", re.IGNORECASE),
    re.compile(r"^changeme", re.IGNORECASE),
    re.compile(r"^your[-_]", re.IGNORECASE),
    re.compile(r"^<", re.IGNORECASE),
]


class Severity(StrEnum):
    FATAL = "fatal"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    severity: Severity
    category: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.value}] {self.category}: {self.message}"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def fatals(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.FATAL]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def has_fatal(self) -> bool:
        return any(i.severity == Severity.FATAL for i in self.issues)

    def add(self, severity: Severity, category: str, message: str) -> None:
        self.issues.append(ValidationIssue(severity, category, message))

    def safe_summary(self) -> dict[str, object]:
        """Return a redacted summary safe for logs/admin display."""
        return {
            "fatal_count": len(self.fatals),
            "warning_count": len(self.warnings),
            "categories": sorted({i.category for i in self.issues}),
        }


def _is_weak_secret(value: str | None) -> bool:
    if value is None:
        return True
    v = value.strip()
    if v in DEFAULT_SECRET_VALUES:
        return True
    if len(v) < 16:
        return True
    return any(pat.search(v) for pat in WEAK_SECRET_PATTERNS)


def _is_https_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _is_wildcard_cors(origins: list[str]) -> bool:
    return any(o.strip() == "*" for o in origins)


def _valid_schedule(expression: str, timezone_name: str) -> bool:
    try:
        from croniter import croniter

        croniter(expression, datetime.now(ZoneInfo(timezone_name))).get_next(datetime)
    except (ImportError, KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        return False
    return True


def _secret_value(value: object | None) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if getter else value)


def validate_production_config(settings: AppSettings) -> ValidationResult:
    """Validate configuration for production deployment.

    Returns a ValidationResult with fatal/warning/info issues.
    Fatal issues must cause startup to fail.
    """
    result = ValidationResult()

    # --- ENV mode
    if settings.ENV != "production":
        result.add(Severity.FATAL, "env", "ENV must be 'production' for production deployment.")
        return result

    is_reader = settings.SERVICE_ROLE == "reader"

    # --- Required secrets (admin only — reader has no session/auth)
    if not is_reader and _is_weak_secret(settings.SESSION_SECRET_KEY):
        result.add(
            Severity.FATAL,
            "session",
            "SESSION_SECRET_KEY is missing, default, or too weak for production.",
        )

    if not is_reader and (
        not settings.OWNER_BOOTSTRAP_SECRET
        or settings.OWNER_BOOTSTRAP_SECRET.strip() == ""
    ):
        result.add(
            Severity.FATAL,
            "owner",
            "OWNER_BOOTSTRAP_SECRET is required for production owner bootstrap.",
        )
    elif not is_reader and _is_weak_secret(settings.OWNER_BOOTSTRAP_SECRET):
        result.add(
            Severity.FATAL,
            "owner",
            "OWNER_BOOTSTRAP_SECRET is default or too weak for production.",
        )

    # --- Public frontend URL (admin only — reader doesn't issue redirects)
    if not is_reader and not settings.PUBLIC_FRONTEND_URL:
        result.add(
            Severity.FATAL,
            "public_url",
            "PUBLIC_FRONTEND_URL is required in production.",
        )
    elif not is_reader and not _is_https_url(settings.PUBLIC_FRONTEND_URL):
        result.add(
            Severity.FATAL,
            "public_url",
            "PUBLIC_FRONTEND_URL must use HTTPS in production.",
        )

    # --- CORS
    if not settings.WEB_CORS_ORIGINS:
        result.add(
            Severity.WARNING,
            "cors",
            "WEB_CORS_ORIGINS is empty; production should set explicit allowed origins.",
        )
    elif _is_wildcard_cors(settings.WEB_CORS_ORIGINS):
        result.add(
            Severity.FATAL,
            "cors",
            "WEB_CORS_ORIGINS must not use '*' in production with credentials.",
        )
    else:
        for origin in settings.WEB_CORS_ORIGINS:
            if not _is_https_url(origin) and origin.strip() != "http://localhost:3000":
                parsed = urlparse(origin)
                if parsed.scheme != "http" or not parsed.netloc:
                    result.add(
                        Severity.WARNING,
                        "cors",
                        "WEB_CORS_ORIGINS contains a non-HTTPS origin (review needed).",
                    )

    # --- Rate limiter backend (admin only — reader doesn't use rate limiting)
    if not is_reader and settings.WEB_RATE_LIMITER_BACKEND == "memory":
        result.add(
            Severity.FATAL,
            "rate_limiter",
            "WEB_RATE_LIMITER_BACKEND must be 'redis' in production for multi-instance safety.",
        )
    elif not is_reader and settings.WEB_RATE_LIMITER_BACKEND == "redis" and not settings.REDIS_URL:
        result.add(
            Severity.FATAL,
            "rate_limiter",
            "REDIS_URL is required when WEB_RATE_LIMITER_BACKEND=redis.",
        )

    # --- Managed PostgreSQL
    if not settings.DATABASE_URL:
        result.add(Severity.FATAL, "database", "DATABASE_URL is required in production.")
    if settings.DB_SSL_MODE not in {"require", "verify-ca", "verify-full"}:
        result.add(Severity.FATAL, "database", "DB_SSL_MODE must require TLS in production.")
    if settings.DB_CONNECTION_MODE != "transaction":
        per_process_limit = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
        combined_limit = per_process_limit * 2
        if combined_limit > settings.DB_CONNECTION_BUDGET:
            result.add(
                Severity.FATAL,
                "database",
                "Combined admin and reader pools exceed DB_CONNECTION_BUDGET.",
            )

    # --- Storage backend
    if settings.STORAGE_BACKEND == "s3":
        if not settings.S3_BUCKET:
            result.add(
                Severity.FATAL,
                "storage",
                "S3_BUCKET is required when STORAGE_BACKEND=s3.",
            )
        # R2 and other S3-compatible targets without IAM require explicit credentials
        if settings.S3_ENDPOINT and not (
            settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY
        ):
            result.add(
                Severity.FATAL,
                "storage",
                "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required when S3_ENDPOINT is set (e.g. Cloudflare R2).",
            )
    elif settings.STORAGE_BACKEND not in ("filesystem", "s3"):
        result.add(
            Severity.FATAL,
            "storage",
            "Unknown STORAGE_BACKEND value.",
        )

    # --- Trusted proxy
    if not settings.TRUSTED_PROXY_CIDRS:
        result.add(
            Severity.INFO,
            "proxy",
            "TRUSTED_PROXY_CIDRS is empty; forwarded headers will be ignored.",
        )

    # --- Allowed hosts
    if not settings.ALLOWED_HOSTS:
        result.add(
            Severity.WARNING,
            "hosts",
            "ALLOWED_HOSTS is empty; host header validation is disabled.",
        )

    # --- CSRF
    if not settings.CSRF_TRUSTED_ORIGINS and settings.WEB_CORS_ORIGINS:
        result.add(
            Severity.WARNING,
            "csrf",
            "CSRF_TRUSTED_ORIGINS is empty; consider setting it to match WEB_CORS_ORIGINS.",
        )

    # --- Backup
    if not settings.BACKUP_ENABLED:
        result.add(
            Severity.WARNING,
            "backup",
            "BACKUP_ENABLED is false; production should have backups enabled or a documented exception.",
        )
    elif settings.STORAGE_BACKEND == "s3":
        if not settings.BACKUP_S3_ENABLED:
            result.add(
                Severity.FATAL,
                "backup",
                "BACKUP_S3_ENABLED must be true when production storage uses S3.",
            )
        if not settings.BACKUP_S3_BUCKET:
            result.add(
                Severity.FATAL,
                "backup",
                "BACKUP_S3_BUCKET is required when S3 offsite backups are enabled.",
            )
        elif settings.BACKUP_S3_BUCKET == settings.S3_BUCKET:
            result.add(
                Severity.FATAL,
                "backup",
                "BACKUP_S3_BUCKET must be different from the production S3_BUCKET.",
            )
        if not settings.BACKUP_S3_PREFIX.strip().strip("/"):
            result.add(
                Severity.FATAL,
                "backup",
                "BACKUP_S3_PREFIX must be a non-root prefix.",
            )
        if not settings.BACKUP_S3_ENDPOINT_URL:
            result.add(
                Severity.FATAL,
                "backup",
                "BACKUP_S3_ENDPOINT_URL is required for S3-compatible offsite backups.",
            )
        if not settings.BACKUP_S3_ACCESS_KEY_ID or not settings.BACKUP_S3_SECRET_ACCESS_KEY:
            result.add(
                Severity.FATAL,
                "backup",
                "BACKUP_S3_ACCESS_KEY_ID and BACKUP_S3_SECRET_ACCESS_KEY are required for offsite backups.",
            )
        if not settings.SNAPSHOT_SOURCE_S3_ACCESS_KEY_ID or not settings.SNAPSHOT_SOURCE_S3_SECRET_ACCESS_KEY:
            result.add(
                Severity.FATAL,
                "backup",
                "Dedicated read-only snapshot-source credentials are required for S3 backups.",
            )
        source_access_key = _secret_value(settings.SNAPSHOT_SOURCE_S3_ACCESS_KEY_ID)
        target_access_key = _secret_value(settings.BACKUP_S3_ACCESS_KEY_ID)
        application_access_key = _secret_value(settings.S3_ACCESS_KEY_ID)
        if source_access_key and source_access_key in {target_access_key, application_access_key}:
            result.add(
                Severity.FATAL,
                "backup",
                "Snapshot-source credentials must differ from application and backup-target credentials.",
            )
        if not _valid_schedule(settings.BACKUP_SCHEDULE_CRON, settings.BACKUP_TIMEZONE):
            result.add(Severity.FATAL, "backup", "BACKUP_SCHEDULE_CRON or BACKUP_TIMEZONE is invalid.")

    if settings.DATABASE_BACKUP_ENABLED:
        if not settings.BACKUP_S3_ENABLED:
            result.add(Severity.FATAL, "database_backup", "Database backups require the independent S3 target.")
        if not settings.DATABASE_BACKUP_S3_PREFIX.strip().strip("/"):
            result.add(Severity.FATAL, "database_backup", "DATABASE_BACKUP_S3_PREFIX must not be root.")
        if settings.DATABASE_BACKUP_S3_PREFIX.strip("/") == settings.BACKUP_S3_PREFIX.strip("/"):
            result.add(Severity.FATAL, "database_backup", "Database and object snapshots require separate prefixes.")
        encryption_key = _secret_value(settings.DATABASE_BACKUP_ENCRYPTION_KEY)
        if not encryption_key or len(encryption_key) < 32:
            result.add(Severity.FATAL, "database_backup", "A strong database-backup encryption key is required.")
        if not _valid_schedule(settings.DATABASE_BACKUP_SCHEDULE_CRON, settings.DATABASE_BACKUP_TIMEZONE):
            result.add(
                Severity.FATAL,
                "database_backup",
                "DATABASE_BACKUP_SCHEDULE_CRON or DATABASE_BACKUP_TIMEZONE is invalid.",
            )

    if settings.DATABASE_RESTORE_VERIFICATION_ENABLED:
        target_url = _secret_value(settings.DATABASE_RESTORE_TARGET_URL)
        if not settings.DATABASE_BACKUP_ENABLED:
            result.add(Severity.FATAL, "database_restore", "Restore verification requires database backups.")
        if not target_url or "restore" not in target_url.lower():
            result.add(
                Severity.FATAL,
                "database_restore",
                "DATABASE_RESTORE_TARGET_URL must identify a dedicated restore-verification database.",
            )
        if target_url and target_url == settings.DATABASE_URL:
            result.add(Severity.FATAL, "database_restore", "Restore verification must never target production.")
        if (
            target_url
            and settings.DATABASE_RESTORE_SSL_MODE == "disable"
            and urlparse(target_url).hostname != "restore-db"
        ):
            result.add(
                Severity.FATAL,
                "database_restore",
                "Restore TLS may be disabled only for the internal Compose restore-db host.",
            )
        if not _valid_schedule(
            settings.DATABASE_RESTORE_VERIFICATION_SCHEDULE_CRON,
            settings.DATABASE_RESTORE_VERIFICATION_TIMEZONE,
        ):
            result.add(Severity.FATAL, "database_restore", "Restore verification cron or timezone is invalid.")

    if settings.OPERATOR_ALERT_ENABLED:
        if not settings.OPERATOR_ALERT_EMAIL:
            result.add(Severity.FATAL, "alerts", "OPERATOR_ALERT_EMAIL is required when alerts are enabled.")
        if settings.AUTH_EMAIL_DELIVERY_MODE != "smtp" or not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            result.add(Severity.FATAL, "alerts", "Operator alerts require working SMTP configuration.")

    # --- HSTS
    if settings.HSTS_MAX_AGE_SECONDS > 0 and not _is_https_url(settings.PUBLIC_FRONTEND_URL):
        result.add(
            Severity.WARNING,
            "hsts",
            "HSTS is enabled but PUBLIC_FRONTEND_URL is not HTTPS; HSTS may break HTTP access.",
        )

    return result


def assert_production_config(settings: AppSettings) -> None:
    """Validate production config and raise RuntimeError on fatal issues.

    Called at startup when ENV=production.
    """
    result = validate_production_config(settings)
    if result.has_fatal:
        messages = [str(i) for i in result.fatals]
        raise RuntimeError(
            "Production configuration validation failed with fatal issues:\n"
            + "\n".join(messages)
        )
