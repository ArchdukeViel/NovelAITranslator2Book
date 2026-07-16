from typing import Any

import pytest

from novelai.config.production_validator import (
    assert_production_config,
    validate_production_config,
)
from novelai.config.settings import AppSettings


def _make_prod_settings(**overrides: Any) -> AppSettings:
    """Create AppSettings with production defaults, then override."""
    defaults: dict[str, Any] = dict(
        ENV="production",
        SESSION_SECRET_KEY="a-strong-secret-that-is-32-chars-long!",
        OWNER_BOOTSTRAP_SECRET="another-strong-secret-32-chars-long!!",
        PUBLIC_FRONTEND_URL="https://example.com",
        WEB_CORS_ORIGINS=["https://example.com"],
        WEB_RATE_LIMITER_BACKEND="redis",
        REDIS_URL="redis://localhost:6379/0",
        BACKUP_ENABLED=True,
        ALLOWED_HOSTS=["example.com"],
        CSRF_TRUSTED_ORIGINS=["https://example.com"],
        TRUSTED_PROXY_CIDRS=["10.0.0.0/8"],
        HSTS_MAX_AGE_SECONDS=0,
        STORAGE_BACKEND="filesystem",
        DATABASE_URL="postgresql+psycopg://example.invalid/postgres",
        DB_SSL_MODE="require",
    )
    defaults.update(overrides)
    return AppSettings(**defaults)


class TestProductionConfigValidator:
    def test_valid_config_passes(self):
        result = validate_production_config(_make_prod_settings())
        assert not result.has_fatal, f"Expected no fatals, got: {[str(i) for i in result.fatals]}"

    def test_database_tls_is_required(self):
        result = validate_production_config(_make_prod_settings(DB_SSL_MODE="prefer"))
        assert any(i.category == "database" for i in result.fatals)

    def test_non_production_env_fatal(self):
        result = validate_production_config(_make_prod_settings(ENV="development"))
        assert result.has_fatal
        assert any("ENV" in i.message for i in result.fatals)

    def test_weak_session_secret_fatal(self):
        result = validate_production_config(
            _make_prod_settings(SESSION_SECRET_KEY="changeme-generate-a-real-secret-in-production")
        )
        assert result.has_fatal
        assert any("SESSION_SECRET_KEY" in i.message for i in result.fatals)

    def test_short_session_secret_fatal(self):
        result = validate_production_config(
            _make_prod_settings(SESSION_SECRET_KEY="short")
        )
        assert result.has_fatal
        assert any("SESSION_SECRET_KEY" in i.message for i in result.fatals)

    def test_missing_owner_bootstrap_fatal(self):
        result = validate_production_config(
            _make_prod_settings(OWNER_BOOTSTRAP_SECRET="")
        )
        assert result.has_fatal
        assert any("OWNER_BOOTSTRAP_SECRET" in i.message for i in result.fatals)

    def test_weak_owner_bootstrap_fatal(self):
        result = validate_production_config(
            _make_prod_settings(OWNER_BOOTSTRAP_SECRET="placeholder")
        )
        assert result.has_fatal
        assert any("OWNER_BOOTSTRAP_SECRET" in i.message for i in result.fatals)

    def test_missing_public_url_fatal(self):
        result = validate_production_config(
            _make_prod_settings(PUBLIC_FRONTEND_URL=None)
        )
        assert result.has_fatal
        assert any("PUBLIC_FRONTEND_URL" in i.message for i in result.fatals)

    def test_non_https_public_url_fatal(self):
        result = validate_production_config(
            _make_prod_settings(PUBLIC_FRONTEND_URL="http://example.com")
        )
        assert result.has_fatal
        assert any("HTTPS" in i.message for i in result.fatals)

    def test_wildcard_cors_fatal(self):
        result = validate_production_config(
            _make_prod_settings(WEB_CORS_ORIGINS=["*"])
        )
        assert result.has_fatal
        assert any("'*'" in i.message or "wildcard" in i.message.lower() for i in result.fatals)

    def test_memory_rate_limiter_fatal(self):
        result = validate_production_config(
            _make_prod_settings(WEB_RATE_LIMITER_BACKEND="memory")
        )
        assert result.has_fatal
        assert any("redis" in i.message.lower() for i in result.fatals)

    def test_redis_limiter_no_url_fatal(self):
        result = validate_production_config(
            _make_prod_settings(WEB_RATE_LIMITER_BACKEND="redis", REDIS_URL=None)
        )
        assert result.has_fatal
        assert any("REDIS_URL" in i.message for i in result.fatals)

    def test_missing_s3_bucket_fatal(self):
        result = validate_production_config(
            _make_prod_settings(STORAGE_BACKEND="s3", S3_BUCKET=None)
        )
        assert result.has_fatal
        assert any("S3_BUCKET" in i.message for i in result.fatals)

    def test_unknown_storage_backend_fatal(self):
        result = validate_production_config(
            _make_prod_settings(STORAGE_BACKEND="invalid")
        )
        assert result.has_fatal
        assert any("STORAGE_BACKEND" in i.message.upper() or "Unknown" in i.message for i in result.fatals)

    def test_s3_production_requires_independent_backup_target(self):
        result = validate_production_config(
            _make_prod_settings(
                STORAGE_BACKEND="s3",
                S3_BUCKET="production",
                S3_ENDPOINT="https://example.invalid",
                S3_ACCESS_KEY_ID="source-key",
                S3_SECRET_ACCESS_KEY="source-secret",
                BACKUP_S3_ENABLED=True,
                BACKUP_S3_BUCKET="production",
                BACKUP_S3_ENDPOINT_URL="https://example.invalid",
                BACKUP_S3_ACCESS_KEY_ID="backup-key",
                BACKUP_S3_SECRET_ACCESS_KEY="backup-secret",
                SNAPSHOT_SOURCE_S3_ACCESS_KEY_ID="snapshot-read-key",
                SNAPSHOT_SOURCE_S3_SECRET_ACCESS_KEY="snapshot-read-secret",
            )
        )
        assert any("must be different" in issue.message for issue in result.fatals)

    def test_s3_production_requires_backup_credentials(self):
        result = validate_production_config(
            _make_prod_settings(
                STORAGE_BACKEND="s3",
                S3_BUCKET="production",
                S3_ENDPOINT="https://example.invalid",
                S3_ACCESS_KEY_ID="source-key",
                S3_SECRET_ACCESS_KEY="source-secret",
                BACKUP_S3_ENABLED=True,
                BACKUP_S3_BUCKET="backup",
                BACKUP_S3_ENDPOINT_URL="https://example.invalid",
                BACKUP_S3_ACCESS_KEY_ID=None,
                BACKUP_S3_SECRET_ACCESS_KEY=None,
            )
        )
        assert any("BACKUP_S3_ACCESS_KEY_ID" in issue.message for issue in result.fatals)

    def test_valid_s3_production_backup_configuration_passes(self):
        result = validate_production_config(
            _make_prod_settings(
                STORAGE_BACKEND="s3",
                S3_BUCKET="production",
                S3_ENDPOINT="https://example.invalid",
                S3_ACCESS_KEY_ID="source-key",
                S3_SECRET_ACCESS_KEY="source-secret",
                BACKUP_S3_ENABLED=True,
                BACKUP_S3_BUCKET="backup",
                BACKUP_S3_PREFIX="snapshots",
                BACKUP_S3_ENDPOINT_URL="https://example.invalid",
                BACKUP_S3_ACCESS_KEY_ID="backup-key",
                BACKUP_S3_SECRET_ACCESS_KEY="backup-secret",
                SNAPSHOT_SOURCE_S3_ACCESS_KEY_ID="snapshot-read-key",
                SNAPSHOT_SOURCE_S3_SECRET_ACCESS_KEY="snapshot-read-secret",
            )
        )
        assert not result.has_fatal

    def test_restore_verification_rejects_production_target(self):
        result = validate_production_config(
            _make_prod_settings(
                DATABASE_BACKUP_ENABLED=True,
                DATABASE_BACKUP_ENCRYPTION_KEY="x" * 64,
                DATABASE_RESTORE_VERIFICATION_ENABLED=True,
                DATABASE_RESTORE_TARGET_URL="postgresql+psycopg://user:password@db/production",
            )
        )
        assert any(issue.category == "database_restore" for issue in result.fatals)

    def test_warnings_present_with_valid_config(self):
        """Even valid config should have some informational items."""
        result = validate_production_config(
            _make_prod_settings(
                TRUSTED_PROXY_CIDRS=[],
                ALLOWED_HOSTS=[],
                BACKUP_ENABLED=False,
            )
        )
        # Should not have fatals but should have warnings
        assert not result.has_fatal
        warnings = result.warnings
        assert any("ALLOWED_HOSTS" in i.message for i in warnings)
        assert any("backup" in i.message.lower() for i in warnings)

    def test_assert_raises_on_fatal(self):
        with pytest.raises(RuntimeError, match="Production configuration validation failed"):
            assert_production_config(_make_prod_settings(ENV="development"))

    def test_assert_passes_with_valid(self):
        # Should not raise
        assert_production_config(_make_prod_settings())

    def test_safe_summary_redacted(self):
        result = validate_production_config(_make_prod_settings(ENV="development"))
        summary = result.safe_summary()
        assert isinstance(summary, dict)
        fatal_count = summary.get("fatal_count", 0)
        assert isinstance(fatal_count, int) and fatal_count > 0
        assert "categories" in summary
        # Should not contain any secret-like values
        summary_str = str(summary)
        assert "changeme" not in summary_str

    def test_empty_cors_warning(self):
        result = validate_production_config(
            _make_prod_settings(WEB_CORS_ORIGINS=[])
        )
        assert any("WEB_CORS_ORIGINS" in i.message for i in result.issues)
