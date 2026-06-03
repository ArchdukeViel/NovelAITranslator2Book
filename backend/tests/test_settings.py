"""Tests for AppSettings configuration."""

from __future__ import annotations

from pathlib import Path

from novelai.config.settings import AppSettings


def test_default_settings() -> None:
    s = AppSettings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.ENV == "development"
    assert s.LOG_LEVEL == "INFO"
    assert s.PROVIDER_DEFAULT == "dummy"
    assert s.PROVIDER_OPENAI_API_KEY is None
    assert s.PROVIDER_GEMINI_API_KEY is None
    assert s.TRANSLATION_CONCURRENCY == 4
    assert s.COST_PER_TOKEN_USD > 0
    assert s.SCRAPE_DELAY_SECONDS == 1.0
    assert s.TRANSLATION_TARGET_LANGUAGE == "English"
    assert s.DATA_DIR.is_absolute() or bool(s.DATA_DIR.anchor)


def test_data_dir_alias() -> None:
    s = AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        NOVEL_LIBRARY_DIR=Path("/tmp/test_lib"),
    )
    assert Path("/tmp/test_lib") == s.DATA_DIR


def test_relative_data_dir_resolves_from_project_root() -> None:
    s = AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        NOVEL_LIBRARY_DIR=Path("storage/novel_library"),
    )
    assert s.DATA_DIR.is_absolute()
    assert s.DATA_DIR.parts[-2:] == ("storage", "novel_library")


def test_web_defaults() -> None:
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.WEB_HOST == "127.0.0.1"
    assert s.WEB_PORT == 8000
