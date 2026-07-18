"""Contract tests for the disposable free-tier hosted preview."""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _render_env_vars() -> dict[str, dict[str, str]]:
    """Parse the small envVars subset used by render.yaml without a YAML dependency."""
    text = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
    env_block = text.split("    envVars:\n", maxsplit=1)[1].split("\n\npreviews:", maxsplit=1)[0]
    entries: dict[str, dict[str, str]] = {}
    for block in re.split(r"(?=      - key: )", env_block):
        key_match = re.search(r"^      - key: (\S+)$", block, re.MULTILINE)
        if key_match is None:
            continue
        entry: dict[str, str] = {}
        for field, value in re.findall(r"^        (\w+): (.+)$", block, re.MULTILINE):
            entry[field] = value.strip("'\"")
        entries[key_match.group(1)] = entry
    return entries


def test_render_blueprint_is_a_single_free_monolith_with_migrations() -> None:
    text = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")

    assert text.count("  - type: web\n") == 1
    assert "    runtime: docker\n" in text
    assert "    plan: free\n" in text
    assert "    healthCheckPath: /health/live\n" in text
    assert "alembic -c alembic.ini upgrade head && exec novelai web" in text
    assert "--port 10000" in text
    assert "previews:\n  generation: none\n" in text


def test_render_blueprint_disables_background_operational_contracts() -> None:
    env = _render_env_vars()

    assert env["ENV"]["value"] == "preview"
    assert env["DEPLOY_MODE"]["value"] == "monolith"
    assert env["WEB_RATE_LIMITER_BACKEND"]["value"] == "memory"
    assert env["SESSION_COOKIE_SECURE"]["value"] == "true"
    assert env["AUTH_EMAIL_DELIVERY_MODE"]["value"] == "noop"
    for key in (
        "JOB_WORKER_ENABLED",
        "BACKUP_ENABLED",
        "BACKUP_S3_ENABLED",
        "DATABASE_BACKUP_ENABLED",
        "DATABASE_RESTORE_VERIFICATION_ENABLED",
        "MAINTENANCE_ENABLED",
        "OPERATOR_ALERT_ENABLED",
    ):
        assert env[key]["value"] == "false"


def test_render_blueprint_requires_external_secrets_without_embedding_values() -> None:
    env = _render_env_vars()

    for key in (
        "DATABASE_URL",
        "S3_ENDPOINT",
        "S3_BUCKET",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "OWNER_BOOTSTRAP_SECRET",
        "PUBLIC_FRONTEND_URL",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REDIRECT_URI",
        "WEB_CORS_ORIGINS",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
    ):
        assert env[key] == {"sync": "false"}

    assert env["SESSION_SECRET_KEY"] == {"generateValue": "true"}
    assert env["PROVIDER_CREDENTIAL_ENCRYPTION_KEY"] == {"generateValue": "true"}


def test_render_blueprint_uses_approved_models_and_non_root_r2_prefix() -> None:
    env = _render_env_vars()

    assert env["PROVIDER_DEFAULT"]["value"] == "gemini"
    assert env["PROVIDER_GEMINI_DEFAULT_MODEL"]["value"] == "gemini-3.1-flash-lite"
    assert json.loads(env["PROVIDER_GEMINI_MODEL_FALLBACKS"]["value"]) == ["gemma-4-31b-it"]
    assert env["S3_KEY_PREFIX"]["value"].strip("/")


def test_vercel_frontend_contract_uses_nextjs_and_backend_rewrite() -> None:
    vercel = json.loads((PROJECT_ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8"))
    next_config = (PROJECT_ROOT / "frontend" / "next.config.mjs").read_text(encoding="utf-8")

    assert vercel["framework"] == "nextjs"
    assert "process.env.BACKEND_API_URL" in next_config
    assert 'source: "/api/:path*"' in next_config


def test_environment_templates_keep_session_cookie_setting_in_the_same_position() -> None:
    templates = [
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "deploy" / ".env.example",
        PROJECT_ROOT / "deploy" / ".env.production.example",
    ]

    key_orders = []
    for path in templates:
        keys = [
            line.split("=", maxsplit=1)[0]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        ]
        key_orders.append(keys)
        assert keys.index("SESSION_COOKIE_SECURE") == keys.index("SESSION_MAX_AGE") + 1

    assert key_orders[0] == key_orders[1] == key_orders[2]
