"""Contract tests for the disposable free-tier hosted Vercel preview."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_vercel_frontend_contract_uses_nextjs_and_backend_rewrite() -> None:
    vercel = json.loads((PROJECT_ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8"))
    next_config = (PROJECT_ROOT / "frontend" / "next.config.mjs").read_text(encoding="utf-8")

    assert vercel["framework"] == "nextjs"
    assert "process.env.BACKEND_API_URL" in next_config
    assert 'source: "/api/:path*"' in next_config


def test_vercel_services_contract_routes_frontend_and_monolith_backend() -> None:
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["services"]["frontend"] == {"root": "frontend/", "framework": "nextjs"}
    backend = config["services"]["backend"]
    assert backend["root"] == "."
    assert backend["framework"] == "fastapi"
    assert backend["entrypoint"] == "vercel_app:app"
    assert backend["functions"]["vercel_app.py"]["maxDuration"] == 300
    assert (
        backend["installCommand"]
        == "pip install uv && uv pip install --system --locked --requirement requirements.lock"
    )

    routes = {rewrite["source"]: rewrite["destination"]["service"] for rewrite in config["rewrites"]}
    assert routes["/api/(.*)"] == "backend"
    assert routes["/health/(.*)"] == "backend"
    assert routes["/metrics"] == "backend"
    assert routes["/(.*)"] == "frontend"


def test_vercel_backend_entrypoint_exports_monolith_app() -> None:
    source = (PROJECT_ROOT / "vercel_app.py").read_text(encoding="utf-8")

    assert "from novelai.api.app import app" in source


def test_vercel_upload_excludes_local_and_non_runtime_trees() -> None:
    ignored = set((PROJECT_ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines())

    assert {".tmp/", ".codegraph/", "backend/tests/", "frontend/node_modules/", "graphify-out/"} <= ignored


def test_architecture_records_vercel_runtime_boundaries() -> None:
    architecture = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")

    assert "NOVEL_LIBRARY_DIR=/tmp/novelai-preview" in architecture
    assert "ALLOWED_HOSTS=*.vercel.app" in architecture
    assert "comma-separated environment format, not JSON array text" in architecture


def test_environment_templates_keep_session_cookie_setting_in_the_same_position() -> None:
    templates = [
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "deploy" / ".env.example",
        PROJECT_ROOT / "deploy" / ".env.production.example",
    ]

    key_orders = []
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert "docs/CONFIGURATION.md" in text
        assert "docs/environment.md" not in text
        keys = [
            line.split("=", maxsplit=1)[0]
            for line in text.splitlines()
            if line and not line.startswith("#") and "=" in line
        ]
        key_orders.append(keys)
        assert keys.index("SESSION_COOKIE_SECURE") == keys.index("SESSION_MAX_AGE") + 1

    assert key_orders[0] == key_orders[1] == key_orders[2]


def test_markdown_and_env_reference_links_exist() -> None:
    """Verify that doc link references in .env.example templates exist on disk."""
    import re

    doc_link_pattern = re.compile(r"docs/[A-Za-z0-9_\-]+\.md")
    templates = [
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "deploy" / ".env.example",
        PROJECT_ROOT / "deploy" / ".env.production.example",
    ]

    for path in templates:
        text = path.read_text(encoding="utf-8")
        matches = doc_link_pattern.findall(text)
        assert matches, f"No doc link references found in {path}"
        for ref in matches:
            target = PROJECT_ROOT / ref
            assert target.exists(), f"Broken doc link reference '{ref}' in {path}"
