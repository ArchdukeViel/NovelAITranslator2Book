from __future__ import annotations

from pathlib import Path

from novelai.services.translation_cache import CacheEntry, TranslationCacheService


def _entry(key: str, novel_id: str) -> CacheEntry:
    return CacheEntry(
        key=key,
        source_text="source",
        translated_text="translated",
        source_language="ja",
        target_language="en",
        glossary_hash="glossary",
        provider_key="gemini",
        provider_model="model",
        created_at="2026-08-20T00:00:00+00:00",
        novel_id=novel_id,
    )


def test_translation_cache_uses_index_after_one_time_backfill(tmp_path, monkeypatch) -> None:
    cache = TranslationCacheService(tmp_path / "cache")
    cache.set("a1", _entry("a1", "novel-1"))
    cache.set("b1", _entry("b1", "novel-2"))

    def fail_glob(self: Path, pattern: str):
        raise AssertionError(f"request-path directory scan: {self} {pattern}")

    monkeypatch.setattr(Path, "glob", fail_glob)
    assert cache.get("a1") is not None
    assert cache.invalidate("novel-1") == 1
    stats = cache.stats()
    assert stats["total_entries"] == 1
    assert stats["index_backend"] == "sqlite"
    assert stats["directory_scans"] == 1
    assert cache.get("a1") is None
    assert cache.get("b1") is not None
