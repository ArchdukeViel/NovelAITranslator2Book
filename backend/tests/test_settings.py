"""Tests for AppSettings configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from novelai.config.settings import AppSettings


def test_default_settings() -> None:
    s = AppSettings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.ENV == "development"
    assert s.LOG_LEVEL == "INFO"
    assert s.PROVIDER_DEFAULT == "dummy"
    assert s.PROVIDER_GEMINI_API_KEY is None
    assert s.NVIDIA_API_KEY is None
    assert s.NVIDIA_BASE_URL == "https://integrate.api.nvidia.com/v1"
    assert s.NVIDIA_DEFAULT_MODEL == "google/gemma-4-31b-it"
    assert s.NVIDIA_TIMEOUT_SECONDS == 60.0
    assert s.PROVIDER_GEMINI_DEFAULT_MODEL == "gemini-3.1-flash-lite"
    assert s.PROVIDER_GEMINI_MODEL_FALLBACKS == []
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


def test_gemini_default_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_GEMINI_DEFAULT_MODEL", "gemini-custom-model")

    s = AppSettings(_env_file=None)  # type: ignore[call-arg]

    assert s.PROVIDER_GEMINI_DEFAULT_MODEL == "gemini-custom-model"


def test_nvidia_api_key_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_NVIDIA_API_KEY", "nvidia-key")

    s = AppSettings(_env_file=None)  # type: ignore[call-arg]

    assert s.NVIDIA_API_KEY is not None
    assert s.NVIDIA_API_KEY.get_secret_value() == "nvidia-key"
