"""Translation cache — key builders, simple cache, and sharded cache service.

This module consolidates the former ``services/translation_cache.py`` (simple
single-file cache) and ``services/cache/translation_cache.py`` (sharded
file-per-entry cache with TTL) into a single module.

- ``build_translation_cache_key()`` — exact key from prompt- and model-affecting inputs
- ``make_cache_key()`` — simpler key for segment-level caching
- ``TranslationCache`` — simple on-disk JSON cache (key -> translation text)
- ``TranslationCacheService`` — sharded file-per-entry cache with TTL and metadata
- ``CacheEntry`` — Pydantic model for cache entries
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from novelai.config.settings import settings
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------


def build_translation_cache_key(
    *,
    source_text: str,
    source_language: str | None = None,
    target_language: str | None = None,
    provider_key: str,
    provider_model: str | None,
    prompt_version: str | None = None,
    glossary_hash: str | None = None,
    style_preset: str | None = None,
    json_output: bool = False,
    consistency_mode: bool = False,
    chapter_memory_hash: str | None = None,
    novel_memory_hash: str | None = None,
    selected_glossary_hash: str | None = None,
    system_prompt_hash: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    structured_output_schema_version: str | None = None,
    prompt_template_version: str | None = None,
    honorific_policy: str | None = None,
) -> str:
    """Build an exact translation cache key from prompt- and model-affecting inputs."""
    payload: dict[str, Any] = {
        "source_text_hash": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "source_language": source_language,
        "target_language": target_language,
        "provider_key": provider_key,
        "provider_model": provider_model,
        "prompt_version": prompt_version,
        "glossary_hash": glossary_hash,
        "style_preset": style_preset,
        "json_output": json_output,
        "consistency_mode": consistency_mode,
        "chapter_memory_hash": chapter_memory_hash,
        "novel_memory_hash": novel_memory_hash,
        "selected_glossary_hash": selected_glossary_hash,
        "system_prompt_hash": system_prompt_hash,
        "temperature": temperature,
        "top_p": top_p,
        "structured_output_schema_version": structured_output_schema_version,
        "prompt_template_version": prompt_template_version,
        "honorific_policy": honorific_policy,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def make_cache_key(
    source_text: str,
    source_language: str,
    target_language: str,
    glossary_hash: str,
    provider_key: str = "",
    provider_model: str = "",
    prompt_version: str = "",
) -> str:
    """Generate a deterministic SHA-256 cache key for a segment.

    Includes all translation-affecting parameters so different providers,
    models, prompt versions, or glossary hashes produce distinct keys.
    """
    raw = f"{source_text}|{source_language}|{target_language}|{glossary_hash}|{provider_key}|{provider_model}|{prompt_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CacheEntry model
# ---------------------------------------------------------------------------


class CacheEntry(BaseModel):
    key: str
    source_text: str
    translated_text: str
    source_language: str | None = None
    target_language: str | None = None
    glossary_hash: str
    provider_key: str
    provider_model: str
    created_at: str  # ISO timestamp
    ttl_seconds: int = 0
    novel_id: str | None = None


# ---------------------------------------------------------------------------
# TranslationCache — simple single-file JSON cache
# ---------------------------------------------------------------------------


class TranslationCache:
    """Simple on-disk cache for translated chunks.

    This cache is keyed by a hash of the input text + provider+model, so repeated
    translations of the same text will reuse previous results.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.base_dir / "translation_cache.json"
        self._data: dict[str, str] = self._load_cache()

    def _load_cache(self) -> dict[str, str]:
        if not self.cache_file.exists():
            return {}
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Corrupted cache file at %s; resetting to empty.", self.cache_file)
            return {}

    def _persist(self) -> None:
        atomic_write(self.cache_file, json.dumps(self._data, ensure_ascii=False, indent=2))

    def reload(self) -> None:
        """Reload cached translations from disk."""
        self._data = self._load_cache()

    def clear(self) -> None:
        """Remove all cached translations."""
        self._data = {}
        self._persist()

    @staticmethod
    def _hash_key(text: str, provider: str, model: str | None) -> str:
        return build_translation_cache_key(
            source_text=text,
            provider_key=provider,
            provider_model=model,
        )

    @staticmethod
    def _legacy_hash_key(text: str, provider: str, model: str | None) -> str:
        payload = f"{provider}:{model}:{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def build_key(**kwargs: Any) -> str:
        return build_translation_cache_key(**kwargs)

    def get_by_key(self, key: str) -> str | None:
        return self._data.get(key)

    def set_by_key(self, key: str, translation: str) -> None:
        self._data[key] = translation
        self._evict_if_needed()
        self._persist()

    def get(self, text: str, provider: str, model: str | None) -> str | None:
        key = self._hash_key(text, provider, model)
        return self._data.get(key) or self._data.get(self._legacy_hash_key(text, provider, model))

    def set(self, text: str, provider: str, model: str | None, translation: str) -> None:
        key = self._hash_key(text, provider, model)
        self._data[key] = translation
        self._evict_if_needed()
        self._persist()

    def _evict_if_needed(self) -> None:
        """Remove oldest entries when cache exceeds the configured maximum."""
        max_entries = settings.TRANSLATION_CACHE_MAX_ENTRIES
        if len(self._data) <= max_entries:
            return
        excess = len(self._data) - max_entries
        keys_to_remove = list(self._data.keys())[:excess]
        for key in keys_to_remove:
            del self._data[key]
        logger.info("Evicted %d entries from translation cache (max %d).", excess, max_entries)


# ---------------------------------------------------------------------------
# TranslationCacheService — sharded file-per-entry cache with TTL
# ---------------------------------------------------------------------------


class TranslationCacheService:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = (cache_dir or settings.NOVEL_LIBRARY_DIR / "translation_cache").resolve()
        self.hits = 0
        self.misses = 0

    def _shard_path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def _parse_timestamp(self, ts: str) -> datetime:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    def get(self, key: str) -> CacheEntry | None:
        if not settings.TRANSLATION_CACHE_ENABLED:
            return None
        path = self._shard_path(key)
        if not path.exists():
            self.misses += 1
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            entry = CacheEntry(**data)
            ttl = entry.ttl_seconds if entry.ttl_seconds > 0 else settings.TRANSLATION_CACHE_TTL_SECONDS
            if ttl > 0:
                created_dt = self._parse_timestamp(entry.created_at)
                age = (datetime.now(UTC) - created_dt).total_seconds()
                if age > ttl:
                    path.unlink(missing_ok=True)
                    self.misses += 1
                    return None
            self.hits += 1
            return entry
        except Exception as exc:
            logger.warning("Failed to read cache entry %s: %s", key, exc)
            self.misses += 1
            return None

    def set(self, key: str, entry: CacheEntry) -> None:
        if not settings.TRANSLATION_CACHE_ENABLED:
            return
        path = self._shard_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write(path, json.dumps(entry.model_dump(), ensure_ascii=False))
            self._evict_if_needed()
        except Exception as exc:
            logger.warning("Failed to write cache entry %s: %s", key, exc)

    def invalidate(self, novel_id: str) -> int:
        """Best-effort invalidation of all cache entries for a given novel_id."""
        if not settings.TRANSLATION_CACHE_ENABLED:
            return 0
        count = 0
        try:
            if not self.cache_dir.exists():
                return 0
            for path in self.cache_dir.glob("**/*.json"):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("novel_id") == novel_id:
                        path.unlink(missing_ok=True)
                        count += 1
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Cache invalidation failed for novel %s: %s", novel_id, exc)
        return count

    def stats(self) -> dict[str, Any]:
        total_entries = 0
        total_size = 0
        try:
            if self.cache_dir.exists():
                for path in self.cache_dir.glob("**/*.json"):
                    if path.is_file():
                        total_entries += 1
                        total_size += path.stat().st_size
        except Exception:
            pass
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size": total_size,
        }

    def _evict_if_needed(self) -> None:
        max_entries = settings.TRANSLATION_CACHE_MAX_ENTRIES
        try:
            if not self.cache_dir.exists():
                return
            files = []
            for path in self.cache_dir.glob("**/*.json"):
                if path.is_file():
                    files.append(path)
            if len(files) <= max_entries:
                return
            # Sort by modification time (oldest first)
            files.sort(key=lambda p: p.stat().st_mtime)
            excess = len(files) - max_entries
            for path in files[:excess]:
                path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Eviction failed: %s", exc)
