"""Tests for the PreferencesService."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from novelai.config.settings import settings
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.runtime.container import Container
from novelai.services.preferences_service import PreferencesService

_TMP = Path(__file__).resolve().parent / ".tmp" / "prefs"


@pytest.fixture()
def prefs_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestPreferencesService:
    def test_container_exposes_only_canonical_preferences_service(self, prefs_dir: Path) -> None:
        preferences = PreferencesService(storage_dir=prefs_dir)
        container = Container(_preferences=preferences)

        assert container.preferences is preferences
        assert not hasattr(container, "settings")

    def test_container_exposes_only_canonical_activity_services(self) -> None:
        assert isinstance(Container.activity_log, property)
        assert isinstance(Container.activity_worker, property)
        assert isinstance(Container.activity_runner, property)
        assert not hasattr(Container, "jobs")
        assert not hasattr(Container, "job_worker")
        assert not hasattr(Container, "job_runner")

    def test_get_returns_default_on_missing_key(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get("missing", "default_val") == "default_val"

    def test_set_and_get(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set("colour", "blue")
        assert svc.get("colour") == "blue"

    def test_persists_across_instances(self, prefs_dir: Path) -> None:
        s1 = PreferencesService(storage_dir=prefs_dir)
        s1.set("lang", "ja")
        s2 = PreferencesService(storage_dir=prefs_dir)
        assert s2.get("lang") == "ja"

    def test_corrupted_file_resets(self, prefs_dir: Path) -> None:
        (prefs_dir / "preferences.json").write_text("{bad", encoding="utf-8")
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get("anything") is None

    def test_preferred_provider_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_preferred_provider() == "dummy"

    def test_set_preferred_provider(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_preferred_provider("gemini")
        assert svc.get_preferred_provider() == "gemini"

    def test_preferred_model_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_preferred_model() == settings.PROVIDER_GEMINI_DEFAULT_MODEL

    def test_theme_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_theme() == "auto"

    def test_language_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_language() == "en"

    def test_llm_step_configs_include_current_phase_keys(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        profiles = svc.get_llm_step_configs()
        assert set(WORKFLOW_PROFILE_STEPS).issubset(set(profiles.keys()))

    def test_llm_step_config_rejects_removed_step_alias(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        with pytest.raises(ValueError, match="Unsupported workflow profile step"):
            svc.set_llm_step_config(
                "term_translation",
                provider="gemini",
                model="gemini-3.1-flash-lite",
            )

    def test_llm_step_config_persists_current_configuration(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_llm_step_config("glossary_translation", provider="gemini", model="gemini-3.1-flash-lite")

        reloaded = PreferencesService(storage_dir=prefs_dir)
        step_config = reloaded.get_llm_step_config("glossary_translation")
        assert step_config["provider"] == "gemini"
        assert step_config["model"] == "gemini-3.1-flash-lite"

    def test_provider_specific_runtime_api_key_methods(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_api_key("gemini-key", provider_key="gemini")
        assert svc.get_api_key("gemini") == "gemini-key"
        svc.clear_api_key(provider_key="gemini")
        assert svc.get_api_key("gemini") is None
        svc.set_api_key("other-key", provider_key="gemini")
        assert svc.get_api_key("gemini") == "other-key"
        svc.clear_api_key(provider_key="gemini")
        assert svc.get_api_key("gemini") is None

    def test_replaces_unsupported_gemini_model_with_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_preferred_provider("gemini")
        svc.set_preferred_model("unsupported-model")

        assert svc.get_provider_model() == "gemini-3.1-flash-lite"
