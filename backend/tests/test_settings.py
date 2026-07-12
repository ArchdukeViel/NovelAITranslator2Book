"""Tests for AppSettings configuration."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ORM models are registered by the session-scoped autouse fixture in conftest.py.
from novelai.config.settings import AppSettings, settings
from novelai.db.base import Base
from novelai.services.preferences_service import PreferencesService
from novelai.services.provider_credentials import ProviderCredentialService, hydrate_active_provider_credentials


def test_default_settings() -> None:
    s = AppSettings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.ENV == "development"
    assert s.LOG_LEVEL == "INFO"
    assert s.PROVIDER_DEFAULT == "gemini"
    assert s.PROVIDER_GEMINI_API_KEY is None
    assert s.PROVIDER_GEMINI_DEFAULT_MODEL == "gemini-3.1-flash-lite"
    assert s.PROVIDER_GEMINI_MODEL_FALLBACKS == ["gemma-4-31b-it"]
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





@pytest.fixture()
def sqlite_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_provider_credential_hydration_loads_active_encrypted_key(monkeypatch, sqlite_session, tmp_path, caplog) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("bootstrap-test-encryption-key"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", None)
    preferences = PreferencesService(tmp_path / "prefs")
    credential_service = ProviderCredentialService(sqlite_session)
    credential_service.upsert_credential(
        provider="gemini",
        api_key="AIza-bootstrap-secret",
        label="Primary Gemini",
        model="gemini-3.1-flash-lite",
        is_active=True,
        notes=None,
    )

    caplog.set_level("INFO")
    diagnostics = hydrate_active_provider_credentials(db=sqlite_session, preferences=preferences)

    assert preferences.get_api_key("gemini") == "AIza-bootstrap-secret"
    assert diagnostics == [
        {
            "provider": "gemini",
            "credential_id": "gemini",
            "db_id": 1,
            "label": "Primary Gemini",
            "hydrated": True,
            "reason": "active",
        }
    ]
    assert "AIza-bootstrap-secret" not in caplog.text


def test_provider_credential_hydration_skips_disabled_and_invalid(monkeypatch, sqlite_session, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("bootstrap-test-encryption-key"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", None)
    preferences = PreferencesService(tmp_path / "prefs")
    credential_service = ProviderCredentialService(sqlite_session)
    credential_service.upsert_credential(
        provider="gemini",
        api_key="AIza-disabled-secret",
        label="Disabled Gemini",
        model="gemini-3.1-flash-lite",
        is_active=False,
        notes=None,
    )

    diagnostics = hydrate_active_provider_credentials(db=sqlite_session, preferences=preferences)

    assert preferences.get_api_key("gemini") is None
    assert diagnostics == [
        {"provider": "gemini", "credential_id": "gemini", "db_id": 1, "label": "Disabled Gemini", "hydrated": False, "reason": "disabled"},
    ]


def test_provider_credential_hydration_missing_key_fails_safely(monkeypatch, sqlite_session, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("bootstrap-test-encryption-key"))
    credential_service = ProviderCredentialService(sqlite_session)
    credential_service.upsert_credential(
        provider="gemini",
        api_key="AIza-needs-key",
        label="Primary Gemini",
        model="gemini-3.1-flash-lite",
        is_active=True,
        notes=None,
    )
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", None)
    preferences = PreferencesService(tmp_path / "prefs")

    diagnostics = hydrate_active_provider_credentials(
        db=sqlite_session,
        preferences=preferences,
        require_encryption_key=False,
    )

    assert diagnostics[0]["reason"] == "encryption_key_missing"
    assert diagnostics[0]["hydrated"] is False
    assert preferences.get_api_key("gemini") is None

    with pytest.raises(ValueError, match="PROVIDER_CREDENTIAL_ENCRYPTION_KEY"):
        hydrate_active_provider_credentials(
            db=sqlite_session,
            preferences=preferences,
            require_encryption_key=True,
        )


def test_provider_credential_hydration_leaves_env_key_when_no_db_credential(monkeypatch, sqlite_session, tmp_path) -> None:
    monkeypatch.setattr(settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", SecretStr("bootstrap-test-encryption-key"))
    monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", SecretStr("env-gemini-key"))
    preferences = PreferencesService(tmp_path / "prefs")

    diagnostics = hydrate_active_provider_credentials(db=sqlite_session, preferences=preferences)

    assert diagnostics == []
    assert preferences.get_api_key("gemini") == "env-gemini-key"


def test_runtime_bootstrap_calls_provider_credential_hydration(monkeypatch) -> None:
    bootstrap_module = importlib.import_module("novelai.runtime.bootstrap")

    calls = []
    monkeypatch.setattr(bootstrap_module, "_BOOTSTRAPPED", False)
    monkeypatch.setattr(bootstrap_module, "bootstrap_providers", lambda: None)
    monkeypatch.setattr(bootstrap_module, "bootstrap_sources", lambda: None)
    monkeypatch.setattr(bootstrap_module, "bootstrap_input_adapters", lambda: None)
    monkeypatch.setattr(bootstrap_module, "bootstrap_exporters", lambda: None)
    monkeypatch.setattr(bootstrap_module, "bootstrap_provider_credentials", lambda: calls.append("hydrated") or [])

    bootstrap_module.bootstrap()

    assert calls == ["hydrated"]


def test_rq_worker_startup_uses_shared_bootstrap(monkeypatch) -> None:
    from novelai.worker import tasks

    bootstrap_module = importlib.import_module("novelai.runtime.bootstrap")
    container_module = importlib.import_module("novelai.runtime.container")
    calls = []
    runner = SimpleNamespace(worker=object())
    monkeypatch.setattr(bootstrap_module, "bootstrap", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(container_module, "container", SimpleNamespace(activity_runner=runner, job_runner=None))

    assert tasks._get_worker_service() is runner
    assert calls == ["bootstrap"]
