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

import contextlib
import hashlib
import json
import logging
import sqlite3
import time
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
    *,
    provider_key: str,
    provider_model: str,
    prompt_version: str,
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
    chunk_id: str | None = None
    # Provenance fields (accepted-output-only contract): pending entries
    # carry the exact attempt, run, and output identity so a flush can never
    # cache an output from a rejected attempt.
    attempt_number: int | None = None
    translation_run_id: str | None = None
    output_hash: str | None = None
    # Acceptance provenance: stamped at flush time by CacheFlushStage so a
    # cached entry records when and under which QA result it was accepted.
    accepted_at: str | None = None
    qa_status: str | None = None


# ---------------------------------------------------------------------------
# TranslationCache — simple single-file JSON cache
# ---------------------------------------------------------------------------


class TranslationCache:
    """Simple on-disk cache for translated chunks.

    This cache is keyed by a hash of the input text + provider+model, so repeated
    translations of the same text will reuse previous results.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.NOVEL_LIBRARY_DIR).resolve()
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
    def _hash_key(
        source_text: str,
        provider_key: str,
        provider_model: str | None,
    ) -> str:
        return build_translation_cache_key(
            source_text=source_text,
            provider_key=provider_key,
            provider_model=provider_model,
        )

    @staticmethod
    def build_key(**kwargs: Any) -> str:
        return build_translation_cache_key(**kwargs)

    def get_by_key(self, key: str) -> str | None:
        return self._data.get(key)

    def set_by_key(self, key: str, translation: str) -> None:
        self._data[key] = translation
        self._evict_if_needed()
        self._persist()

    def get(
        self,
        source_text: str,
        provider_key: str,
        provider_model: str | None,
    ) -> str | None:
        key = self._hash_key(source_text, provider_key, provider_model)
        return self._data.get(key)

    def set(
        self,
        source_text: str,
        provider_key: str,
        provider_model: str | None,
        translated_text: str,
    ) -> None:
        key = self._hash_key(source_text, provider_key, provider_model)
        self._data[key] = translated_text
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
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.cache_dir / "translation_cache_index.sqlite3"
        self.hits = 0
        self.misses = 0
        self.index_scans = 0
        self.index_maintenance_ms = 0.0
        self._ensure_index()

    def _connect_index(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.index_path, timeout=10.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _ensure_index(self) -> None:
        started = time.perf_counter()
        with self._connect_index() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    novel_id TEXT,
                    created_at TEXT,
                    last_accessed_at REAL NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS ix_cache_entries_novel_id
                    ON cache_entries (novel_id);
                CREATE INDEX IF NOT EXISTS ix_cache_entries_last_accessed
                    ON cache_entries (last_accessed_at);
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            initialized = connection.execute(
                "SELECT value FROM cache_metadata WHERE key = 'directory_backfill_complete'"
            ).fetchone()
            if initialized is None:
                self.index_scans += 1
                for path in self.cache_dir.glob("**/*.json"):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        entry = CacheEntry(**data)
                    except Exception:
                        continue
                    now = time.time()
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO cache_entries
                            (cache_key, path, novel_id, created_at, last_accessed_at, size_bytes)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry.key,
                            str(path),
                            entry.novel_id,
                            entry.created_at,
                            path.stat().st_mtime if path.exists() else now,
                            path.stat().st_size if path.exists() else 0,
                        ),
                    )
                connection.execute(
                    "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('directory_backfill_complete', '1')"
                )
        self.index_maintenance_ms += (time.perf_counter() - started) * 1000

    def _index_entry(self, key: str, path: Path, entry: CacheEntry, *, accessed_at: float | None = None) -> None:
        timestamp = accessed_at if accessed_at is not None else time.time()
        with self._connect_index() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries
                    (cache_key, path, novel_id, created_at, last_accessed_at, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    path = excluded.path,
                    novel_id = excluded.novel_id,
                    created_at = excluded.created_at,
                    last_accessed_at = excluded.last_accessed_at,
                    size_bytes = excluded.size_bytes
                """,
                (key, str(path), entry.novel_id, entry.created_at, timestamp, path.stat().st_size),
            )

    def _remove_index_entry(self, key: str) -> None:
        with self._connect_index() as connection:
            connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))

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
                    self._remove_index_entry(key)
                    self.misses += 1
                    return None
            with contextlib.suppress(Exception), self._connect_index() as connection:
                connection.execute(
                    "UPDATE cache_entries SET last_accessed_at = ?, size_bytes = ? WHERE cache_key = ?",
                    (time.time(), path.stat().st_size, key),
                )
            self.hits += 1
            return entry
        except Exception as exc:
            logger.warning("Failed to read cache entry %s: %s", key, exc)
            with contextlib.suppress(Exception):
                self._remove_index_entry(key)
            self.misses += 1
            return None

    def set(self, key: str, entry: CacheEntry) -> None:
        if not settings.TRANSLATION_CACHE_ENABLED:
            return
        path = self._shard_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write(path, json.dumps(entry.model_dump(), ensure_ascii=False))
            self._index_entry(key, path, entry)
            self._evict_if_needed()
        except Exception as exc:
            logger.warning("Failed to write cache entry %s: %s", key, exc)

    def invalidate(self, novel_id: str) -> int:
        """Best-effort invalidation of all cache entries for a given novel_id."""
        if not settings.TRANSLATION_CACHE_ENABLED:
            return 0
        count = 0
        try:
            with self._connect_index() as connection:
                rows = connection.execute(
                    "SELECT cache_key, path FROM cache_entries WHERE novel_id = ?", (novel_id,)
                ).fetchall()
                for key, raw_path in rows:
                    Path(str(raw_path)).unlink(missing_ok=True)
                    connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
                    count += 1
        except Exception as exc:
            logger.warning("Cache invalidation failed for novel %s: %s", novel_id, exc)
        return count

    def stats(self) -> dict[str, Any]:
        total_entries = 0
        total_size = 0
        try:
            with self._connect_index() as connection:
                total_entries, total_size = connection.execute(
                    "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM cache_entries"
                ).fetchone()
        except Exception:
            pass
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size": total_size,
            "index_backend": "sqlite",
            "directory_scans": self.index_scans,
            "maintenance_ms": round(self.index_maintenance_ms, 3),
        }

    def _evict_if_needed(self) -> None:
        max_entries = settings.TRANSLATION_CACHE_MAX_ENTRIES
        try:
            started = time.perf_counter()
            with self._connect_index() as connection:
                total = int(connection.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0])
                if total <= max_entries:
                    return
                excess = total - max_entries
                rows = connection.execute(
                    "SELECT cache_key, path FROM cache_entries ORDER BY last_accessed_at ASC LIMIT ?",
                    (excess,),
                ).fetchall()
                for key, raw_path in rows:
                    Path(str(raw_path)).unlink(missing_ok=True)
                    connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
            self.index_maintenance_ms += (time.perf_counter() - started) * 1000
        except Exception as exc:
            logger.warning("Eviction failed: %s", exc)
