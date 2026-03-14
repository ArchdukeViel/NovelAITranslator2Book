"""Tests for the PreferencesService."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.services.preferences_service import PreferencesService

_TMP = Path(__file__).resolve().parent / ".tmp" / "prefs"


@pytest.fixture()
def prefs_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestPreferencesService:
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
        svc.set_preferred_provider("openai")
        assert svc.get_preferred_provider() == "openai"

    def test_preferred_model_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_preferred_model() == "gpt-5.4"

    def test_theme_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_theme() == "auto"

    def test_language_default(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        assert svc.get_language() == "en"

    def test_workflow_profiles_include_new_phase_keys(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        profiles = svc.get_workflow_profiles()
        assert set(WORKFLOW_PROFILE_STEPS).issubset(set(profiles.keys()))

    def test_workflow_profile_accepts_legacy_step_alias(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_workflow_profile("term_translation", provider="openai", model="gpt-5.4")
        profile = svc.get_workflow_profile("glossary_translation")
        assert profile["provider"] == "openai"
        assert profile["model"] == "gpt-5.4"

    def test_llm_step_config_migrates_from_workflow_profile(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_workflow_profile("glossary_translation", provider="openai", model="gpt-5.4")

        reloaded = PreferencesService(storage_dir=prefs_dir)
        step_config = reloaded.get_llm_step_config("glossary_translation")
        assert step_config["provider"] == "openai"
        assert step_config["model"] == "gpt-5.4"

    def test_provider_specific_runtime_api_key_methods(self, prefs_dir: Path) -> None:
        svc = PreferencesService(storage_dir=prefs_dir)
        svc.set_api_key("gemini-key", provider_key="gemini")
        assert svc.get_api_key("gemini") == "gemini-key"
        svc.clear_api_key(provider_key="gemini")
        assert svc.get_api_key("gemini") is None
