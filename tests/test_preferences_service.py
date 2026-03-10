"""Tests for the PreferencesService."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

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
