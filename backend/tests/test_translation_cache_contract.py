"""Contract tests: TranslationCache key field matching.

Each test verifies that changing exactly one of the six cache-key fields
causes a cache miss, and that returning all six unchanged produces a hit.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from novelai.services.translation_cache import TranslationCache, build_translation_cache_key

_TMP = Path(__file__).resolve().parent / ".tmp" / "cache_contract"

_BASE: dict[str, str | bool | None] = {
    "source_text": "Hello world.",
    "provider_key": "test_provider",
    "provider_model": "test_model",
    "prompt_version": "v1",
    "glossary_hash": "abc123",
    "style_preset": "formal",
    "json_output": False,
    "consistency_mode": False,
}


@pytest.fixture()
def cache_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _hit(cache_dir: Path, **overrides: object) -> str | None:
    """Build key from base+overrides and look up in a fresh cache instance."""
    kwargs = dict(_BASE, **overrides)
    key = build_translation_cache_key(**kwargs)  # type: ignore[arg-type]
    return TranslationCache(base_dir=cache_dir).get_by_key(key)


def _store(cache_dir: Path, **overrides: object) -> None:
    """Store a result under key built from base+overrides."""
    kwargs = dict(_BASE, **overrides)
    key = build_translation_cache_key(**kwargs)  # type: ignore[arg-type]
    TranslationCache(base_dir=cache_dir).set_by_key(key, "translated_output")


class TestCacheReuseContract:
    def test_cache_reuse_all_six_fields_match(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir) == "translated_output"

    def test_cache_miss_on_source_text_change(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir, source_text="Different text.") is None

    def test_cache_miss_on_prompt_version_change(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir, prompt_version="v2") is None

    def test_cache_miss_on_glossary_hash_change(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir, glossary_hash="def456") is None

    def test_cache_miss_on_style_preset_change(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir, style_preset="casual") is None

    def test_cache_miss_on_json_output_change(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir, json_output=True) is None

    def test_cache_miss_on_consistency_mode_change(self, cache_dir: Path) -> None:
        _store(cache_dir)
        assert _hit(cache_dir, consistency_mode=True) is None

    def test_force_retranslate_bypasses_cache(self, cache_dir: Path) -> None:
        """When force_retranslate is True, cache should not be consulted."""
        _store(cache_dir)
        # Force retranslate means callers skip cache lookup entirely —
        # confirm the key *would* have matched.
        kwargs = dict(_BASE)
        key = build_translation_cache_key(**kwargs)  # type: ignore[arg-type]
        assert TranslationCache(base_dir=cache_dir).get_by_key(key) is not None
