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
