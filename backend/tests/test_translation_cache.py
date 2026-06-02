"""Tests for the TranslationCache service."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from novelai.services.translation_cache import TranslationCache

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
