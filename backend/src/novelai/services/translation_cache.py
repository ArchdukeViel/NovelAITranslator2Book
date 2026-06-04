from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from novelai.config.settings import settings
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)


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
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
