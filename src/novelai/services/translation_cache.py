from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from novelai.config.settings import settings

logger = logging.getLogger(__name__)


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
        self.cache_file.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _hash_key(text: str, provider: str, model: str | None) -> str:
        payload = f"{provider}:{model}:{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, text: str, provider: str, model: str | None) -> str | None:
        key = self._hash_key(text, provider, model)
        return self._data.get(key)

    def set(self, text: str, provider: str, model: str | None, translation: str) -> None:
        key = self._hash_key(text, provider, model)
        self._data[key] = translation
        self._persist()
