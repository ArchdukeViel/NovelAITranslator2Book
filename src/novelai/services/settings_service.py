from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from novelai.config.settings import settings


class SettingsService:
    """Persistence for runtime settings (provider, model, API keys, etc.)."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = (storage_dir or settings.DATA_DIR).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.storage_dir / "settings.json"
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _persist(self) -> None:
        self.settings_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._persist()

    def get_provider_key(self) -> str:
        return self.get("provider_key", settings.PROVIDER_DEFAULT)

    def set_provider_key(self, key: str) -> None:
        self.set("provider_key", key)

    def get_provider_model(self) -> str:
        return self.get("provider_model", "gpt-4o-mini")

    def set_provider_model(self, model: str) -> None:
        self.set("provider_model", model)

    def get_api_key(self) -> Optional[str]:
        return self.get("provider_api_key")

    def set_api_key(self, api_key: str) -> None:
        self.set("provider_api_key", api_key)
