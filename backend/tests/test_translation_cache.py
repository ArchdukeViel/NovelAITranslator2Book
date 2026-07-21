"""Tests for the TranslationCache service."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.services.translation_cache import TranslationCache, build_translation_cache_key

_TMP = Path(__file__).resolve().parent / ".tmp" / "cache"


@pytest.fixture()
def cache_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestTranslationCache:
    def test_get_returns_none_on_miss(self, cache_dir: Path) -> None:
        cache = TranslationCache(base_dir=cache_dir)
        assert cache.get("hello", "openai", "gpt-4") is None

    def test_set_and_get(self, cache_dir: Path) -> None:
        cache = TranslationCache(base_dir=cache_dir)
        cache.set("hello", "openai", "gpt-4", "こんにちは")
        assert cache.get("hello", "openai", "gpt-4") == "こんにちは"

    def test_different_model_is_separate_key(self, cache_dir: Path) -> None:
        cache = TranslationCache(base_dir=cache_dir)
        cache.set("hello", "openai", "gpt-4", "A")
        cache.set("hello", "openai", "gpt-5", "B")
        assert cache.get("hello", "openai", "gpt-4") == "A"
        assert cache.get("hello", "openai", "gpt-5") == "B"

    def test_persists_across_instances(self, cache_dir: Path) -> None:
        c1 = TranslationCache(base_dir=cache_dir)
        c1.set("text", "prov", "m", "result")
        c2 = TranslationCache(base_dir=cache_dir)
        assert c2.get("text", "prov", "m") == "result"

    def test_corrupted_cache_file_resets(self, cache_dir: Path) -> None:
        cache_file = cache_dir / "translation_cache.json"
        cache_file.write_text("NOT JSON", encoding="utf-8")
        cache = TranslationCache(base_dir=cache_dir)
        assert cache.get("any", "p", "m") is None

    def test_ignores_legacy_provider_model_text_key(self, cache_dir: Path) -> None:
        legacy_payload = "openai:gpt-4:hello"
        legacy_key = hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest()
        cache_file = cache_dir / "translation_cache.json"
        cache_file.write_text(f'{{"{legacy_key}": "legacy translation"}}', encoding="utf-8")

        cache = TranslationCache(base_dir=cache_dir)

        assert cache.get("hello", "openai", "gpt-4") is None

    def test_exact_key_changes_when_prompt_affecting_metadata_changes(self) -> None:
        base = {
            "source_text": "本文",
            "source_language": "Japanese",
            "target_language": "English",
            "provider_key": "gemini",
            "provider_model": "gemini-2.5-flash-lite",
            "prompt_version": "translation-v1",
            "glossary_hash": "glossary-a",
            "style_preset": "balanced",
            "json_output": False,
            "consistency_mode": False,
        }
        baseline = build_translation_cache_key(**base)

        for field, value in (
            ("provider_model", "gemini-3.1-flash-lite"),
            ("prompt_version", "translation-v2"),
            ("glossary_hash", "glossary-b"),
            ("style_preset", "literary"),
            ("json_output", True),
            ("consistency_mode", True),
        ):
            changed = {**base, field: value}
            assert build_translation_cache_key(**changed) != baseline

    def test_set_and_get_by_exact_key(self, cache_dir: Path) -> None:
        cache = TranslationCache(base_dir=cache_dir)
        key = cache.build_key(
            source_text="本文",
            source_language="Japanese",
            target_language="English",
            provider_key="openai",
            provider_model="gpt-5.4",
            prompt_version="translation-v1",
            glossary_hash="glossary-a",
            style_preset="balanced",
            json_output=True,
            consistency_mode=True,
        )
        cache.set_by_key(key, "Translated text.")
        assert cache.get_by_key(key) == "Translated text."
