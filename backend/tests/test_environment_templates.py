"""Contract tests for shared environment templates."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
