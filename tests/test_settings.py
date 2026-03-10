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
    assert s.TRANSLATION_CONCURRENCY == 4
    assert s.COST_PER_TOKEN_USD > 0
    assert s.SCRAPE_DELAY_SECONDS == 1.0
    assert s.TRANSLATION_TARGET_LANGUAGE == "English"


def test_data_dir_alias() -> None:
    s = AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        NOVEL_LIBRARY_DIR=Path("/tmp/test_lib"),
    )
    assert Path("/tmp/test_lib") == s.DATA_DIR


def test_web_defaults() -> None:
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.WEB_HOST == "127.0.0.1"
    assert s.WEB_PORT == 8000
