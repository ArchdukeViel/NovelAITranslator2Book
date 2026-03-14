from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.config.workflow_profiles import (
    WORKFLOW_PROFILE_STEPS,
    normalize_workflow_profile_step,
    normalize_workflow_profiles,
)
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)


class PreferencesService:
    """User preferences persistence (NOT configuration, NOT secrets).

    IMPORTANT DISTINCTION:
    - AppSettings: System/environment configuration (from .env / env vars)
    - PreferencesService: User preferences (persisted to disk, no secrets)
    - Secrets: ALWAYS from environment variables (NEVER persisted)

    This service stores user choices like:
    - Which provider to use (openai vs dummy, etc)
    - Which model to use (gpt-5.4, gpt-5.2, etc)
    - User UI preferences

    It NEVER stores API keys or other secrets.
    """

    PREFS_FILENAME = "preferences.json"
    LLM_ENDPOINT_PROFILES_KEY = "llm_endpoint_profiles"
    LLM_STEP_CONFIGS_KEY = "llm_step_configs"
    GLOSSARY_EXTRACTION_KEY = "glossary_extraction"

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = (storage_dir or settings.DATA_DIR).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.prefs_path = self.storage_dir / self.PREFS_FILENAME
        self._data = self._load()
        self._migrate_legacy_data()

    def _load(self) -> dict[str, Any]:
        if not self.prefs_path.exists():
            return {}
        try:
            return json.loads(self.prefs_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Corrupted preferences file at %s; resetting to defaults.", self.prefs_path)
            return {}

    def _persist(self) -> None:
        atomic_write(
            self.prefs_path,
            json.dumps(self._data, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _default_step_configs() -> dict[str, dict[str, Any]]:
        return {
            step: {
                "endpoint_profile": None,
                "provider": None,
                "model": None,
                "temperature": None,
                "timeout": None,
                "max_retries": None,
                "concurrency": None,
                "kwargs": {},
                "prompt_template": None,
            }
            for step in WORKFLOW_PROFILE_STEPS
        }

    def _migrate_legacy_data(self) -> None:
        """Backfill new LLM config keys from legacy workflow_profiles data."""
        changed = False

        if self.LLM_ENDPOINT_PROFILES_KEY not in self._data or not isinstance(self._data.get(self.LLM_ENDPOINT_PROFILES_KEY), dict):
            self._data[self.LLM_ENDPOINT_PROFILES_KEY] = {}
            changed = True

        current_step_configs = self._data.get(self.LLM_STEP_CONFIGS_KEY)
        merged_step_configs = self._default_step_configs()
        if isinstance(current_step_configs, dict):
            for step, payload in current_step_configs.items():
                normalized_step = normalize_workflow_profile_step(step)
                if normalized_step not in merged_step_configs or not isinstance(payload, dict):
                    continue
                merged_step_configs[normalized_step].update(
                    {
                        "endpoint_profile": payload.get("endpoint_profile"),
                        "provider": payload.get("provider"),
                        "model": payload.get("model"),
                        "temperature": payload.get("temperature"),
                        "timeout": payload.get("timeout"),
                        "max_retries": payload.get("max_retries"),
                        "concurrency": payload.get("concurrency"),
                        "kwargs": payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {},
                        "prompt_template": payload.get("prompt_template"),
                    }
                )

        legacy_profiles = normalize_workflow_profiles(self._data.get("workflow_profiles", {}))
        for step in WORKFLOW_PROFILE_STEPS:
            profile = legacy_profiles[step]
            if merged_step_configs[step].get("provider") is None and profile.get("provider") is not None:
                merged_step_configs[step]["provider"] = profile.get("provider")
                changed = True
            if merged_step_configs[step].get("model") is None and profile.get("model") is not None:
                merged_step_configs[step]["model"] = profile.get("model")
                changed = True

        if self._data.get(self.LLM_STEP_CONFIGS_KEY) != merged_step_configs:
            self._data[self.LLM_STEP_CONFIGS_KEY] = merged_step_configs
            changed = True

        if self.GLOSSARY_EXTRACTION_KEY not in self._data or not isinstance(self._data.get(self.GLOSSARY_EXTRACTION_KEY), dict):
            self._data[self.GLOSSARY_EXTRACTION_KEY] = {
                "mode": "heuristic",
                "prompt_template": None,
                "max_terms": 50,
            }
            changed = True
        else:
            glossary_data = self._data[self.GLOSSARY_EXTRACTION_KEY]
            if "max_terms" not in glossary_data:
                glossary_data["max_terms"] = 50
                changed = True

        if changed:
            self._persist()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a preference value."""
        self._data[key] = value
        self._persist()

    # ============================================================================
    # Strongly-typed preference methods (for IDE support and clarity)
    # ============================================================================

    def get_preferred_provider(self) -> str:
        """Get user's preferred translation provider."""
        return self.get("preferred_provider", "dummy")

    def set_preferred_provider(self, provider_key: str) -> None:
        """Set user's preferred translation provider."""
        self.set("preferred_provider", provider_key)

    def get_preferred_model(self) -> str:
        """Get user's preferred translation model."""
        return self.get("preferred_model", "gpt-5.4")

    def set_preferred_model(self, model: str) -> None:
        """Set user's preferred translation model."""
        self.set("preferred_model", model)

    def get_preferred_source(self) -> str | None:
        """Get user's preferred scraping source."""
        return self.get("preferred_source")

    def set_preferred_source(self, source_key: str) -> None:
        """Set user's preferred scraping source."""
        self.set("preferred_source", source_key)

    # UI preferences
    def get_theme(self) -> str:
        """Get user's preferred UI theme."""
        return self.get("theme", "auto")

    def set_theme(self, theme: str) -> None:
        """Set user's preferred UI theme."""
        self.set("theme", theme)

    def get_language(self) -> str:
        """Get user's preferred UI language."""
        return self.get("language", "en")

    def set_language(self, language: str) -> None:
        """Set user's preferred UI language."""
        self.set("language", language)

    def get_workflow_profiles(self) -> dict[str, dict[str, str | None]]:
        """Return per-step provider/model preferences."""
        normalized_profiles = normalize_workflow_profiles(self.get("workflow_profiles", {}))
        step_configs = self.get_llm_step_configs()
        for step in WORKFLOW_PROFILE_STEPS:
            provider = step_configs[step].get("provider")
            model = step_configs[step].get("model")
            if isinstance(provider, str) and provider.strip():
                normalized_profiles[step]["provider"] = provider.strip()
            if isinstance(model, str) and model.strip():
                normalized_profiles[step]["model"] = model.strip()
        return normalized_profiles

    def get_workflow_profile(self, step: str) -> dict[str, str | None]:
        normalized_step = normalize_workflow_profile_step(step)
        if normalized_step not in WORKFLOW_PROFILE_STEPS:
            raise ValueError(f"Unsupported workflow profile step: {step}")
        return self.get_workflow_profiles()[normalized_step]

    def set_workflow_profile(
        self,
        step: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        normalized_step = normalize_workflow_profile_step(step)
        if normalized_step not in WORKFLOW_PROFILE_STEPS:
            raise ValueError(f"Unsupported workflow profile step: {step}")
        profiles = self.get_workflow_profiles()
        profiles[normalized_step] = {
            "provider": provider.strip() if isinstance(provider, str) and provider.strip() else None,
            "model": model.strip() if isinstance(model, str) and model.strip() else None,
        }
        self.set("workflow_profiles", profiles)
        self.set_llm_step_config(
            normalized_step,
            provider=provider,
            model=model,
        )

    def get_llm_endpoint_profiles(self) -> dict[str, dict[str, Any]]:
        raw = self.get(self.LLM_ENDPOINT_PROFILES_KEY, {})
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, dict[str, Any]] = {}
        for name, payload in raw.items():
            if not isinstance(name, str) or not isinstance(payload, dict):
                continue
            profile_name = name.strip()
            if not profile_name:
                continue
            normalized[profile_name] = {
                "provider": payload.get("provider") if isinstance(payload.get("provider"), str) else None,
                "model": payload.get("model") if isinstance(payload.get("model"), str) else None,
                "temperature": payload.get("temperature") if isinstance(payload.get("temperature"), (int, float)) else None,
                "timeout": payload.get("timeout") if isinstance(payload.get("timeout"), (int, float)) else None,
                "max_retries": payload.get("max_retries") if isinstance(payload.get("max_retries"), int) else None,
                "concurrency": payload.get("concurrency") if isinstance(payload.get("concurrency"), int) else None,
                "kwargs": payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {},
                "api_key_env": payload.get("api_key_env") if isinstance(payload.get("api_key_env"), str) else None,
                "base_url": payload.get("base_url") if isinstance(payload.get("base_url"), str) else None,
                "api_version": payload.get("api_version") if isinstance(payload.get("api_version"), str) else None,
            }
        return normalized

    def set_llm_endpoint_profile(self, name: str, **payload: Any) -> None:
        profile_name = name.strip()
        if not profile_name:
            raise ValueError("Endpoint profile name must not be empty.")
        profiles = self.get_llm_endpoint_profiles()
        profiles[profile_name] = {
            "provider": payload.get("provider") if isinstance(payload.get("provider"), str) and payload.get("provider").strip() else None,
            "model": payload.get("model") if isinstance(payload.get("model"), str) and payload.get("model").strip() else None,
            "temperature": payload.get("temperature") if isinstance(payload.get("temperature"), (int, float)) else None,
            "timeout": payload.get("timeout") if isinstance(payload.get("timeout"), (int, float)) else None,
            "max_retries": payload.get("max_retries") if isinstance(payload.get("max_retries"), int) else None,
            "concurrency": payload.get("concurrency") if isinstance(payload.get("concurrency"), int) else None,
            "kwargs": payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {},
            "api_key_env": payload.get("api_key_env") if isinstance(payload.get("api_key_env"), str) and payload.get("api_key_env").strip() else None,
            "base_url": payload.get("base_url") if isinstance(payload.get("base_url"), str) and payload.get("base_url").strip() else None,
            "api_version": payload.get("api_version") if isinstance(payload.get("api_version"), str) and payload.get("api_version").strip() else None,
        }
        self.set(self.LLM_ENDPOINT_PROFILES_KEY, profiles)

    def remove_llm_endpoint_profile(self, name: str) -> None:
        profiles = self.get_llm_endpoint_profiles()
        profiles.pop(name, None)
        self.set(self.LLM_ENDPOINT_PROFILES_KEY, profiles)

    def get_llm_step_configs(self) -> dict[str, dict[str, Any]]:
        raw = self.get(self.LLM_STEP_CONFIGS_KEY, {})
        merged = self._default_step_configs()
        if isinstance(raw, dict):
            for step, payload in raw.items():
                normalized_step = normalize_workflow_profile_step(step)
                if normalized_step not in merged or not isinstance(payload, dict):
                    continue
                merged[normalized_step].update(
                    {
                        "endpoint_profile": payload.get("endpoint_profile") if isinstance(payload.get("endpoint_profile"), str) else None,
                        "provider": payload.get("provider") if isinstance(payload.get("provider"), str) else None,
                        "model": payload.get("model") if isinstance(payload.get("model"), str) else None,
                        "temperature": payload.get("temperature") if isinstance(payload.get("temperature"), (int, float)) else None,
                        "timeout": payload.get("timeout") if isinstance(payload.get("timeout"), (int, float)) else None,
                        "max_retries": payload.get("max_retries") if isinstance(payload.get("max_retries"), int) else None,
                        "concurrency": payload.get("concurrency") if isinstance(payload.get("concurrency"), int) else None,
                        "kwargs": payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {},
                        "prompt_template": payload.get("prompt_template") if isinstance(payload.get("prompt_template"), str) else None,
                    }
                )
        return merged

    def get_llm_step_config(self, step: str) -> dict[str, Any]:
        normalized_step = normalize_workflow_profile_step(step)
        if normalized_step not in WORKFLOW_PROFILE_STEPS:
            raise ValueError(f"Unsupported workflow profile step: {step}")
        return self.get_llm_step_configs()[normalized_step]

    def set_llm_step_config(self, step: str, **overrides: Any) -> None:
        normalized_step = normalize_workflow_profile_step(step)
        if normalized_step not in WORKFLOW_PROFILE_STEPS:
            raise ValueError(f"Unsupported workflow profile step: {step}")
        step_configs = self.get_llm_step_configs()
        current = dict(step_configs[normalized_step])
        current.update(overrides)
        sanitized = {
            "endpoint_profile": current.get("endpoint_profile") if isinstance(current.get("endpoint_profile"), str) and current.get("endpoint_profile").strip() else None,
            "provider": current.get("provider") if isinstance(current.get("provider"), str) and current.get("provider").strip() else None,
            "model": current.get("model") if isinstance(current.get("model"), str) and current.get("model").strip() else None,
            "temperature": current.get("temperature") if isinstance(current.get("temperature"), (int, float)) else None,
            "timeout": current.get("timeout") if isinstance(current.get("timeout"), (int, float)) else None,
            "max_retries": current.get("max_retries") if isinstance(current.get("max_retries"), int) else None,
            "concurrency": current.get("concurrency") if isinstance(current.get("concurrency"), int) else None,
            "kwargs": current.get("kwargs") if isinstance(current.get("kwargs"), dict) else {},
            "prompt_template": current.get("prompt_template") if isinstance(current.get("prompt_template"), str) and current.get("prompt_template").strip() else None,
        }
        step_configs[normalized_step] = sanitized
        self.set(self.LLM_STEP_CONFIGS_KEY, step_configs)

    def resolve_step_llm_config(
        self,
        step: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_step = normalize_workflow_profile_step(step)
        if normalized_step not in WORKFLOW_PROFILE_STEPS:
            raise ValueError(f"Unsupported workflow profile step: {step}")

        global_step = self.get_llm_step_config(normalized_step)
        novel_profiles = normalize_workflow_profiles(metadata.get("translation_profiles")) if isinstance(metadata, dict) else normalize_workflow_profiles(None)
        endpoint_profiles = self.get_llm_endpoint_profiles()

        resolved = {
            "endpoint_profile": global_step.get("endpoint_profile"),
            "provider": novel_profiles[normalized_step]["provider"] or global_step.get("provider"),
            "model": novel_profiles[normalized_step]["model"] or global_step.get("model"),
            "temperature": global_step.get("temperature"),
            "timeout": global_step.get("timeout"),
            "max_retries": global_step.get("max_retries"),
            "concurrency": global_step.get("concurrency"),
            "kwargs": global_step.get("kwargs") if isinstance(global_step.get("kwargs"), dict) else {},
            "prompt_template": global_step.get("prompt_template"),
        }

        endpoint_name = resolved.get("endpoint_profile")
        if isinstance(endpoint_name, str) and endpoint_name in endpoint_profiles:
            profile = endpoint_profiles[endpoint_name]
            for key in ("provider", "model", "temperature", "timeout", "max_retries", "concurrency"):
                if resolved.get(key) is None and profile.get(key) is not None:
                    resolved[key] = profile.get(key)
            profile_kwargs = profile.get("kwargs") if isinstance(profile.get("kwargs"), dict) else {}
            resolved["kwargs"] = {**profile_kwargs, **resolved["kwargs"]}

        return resolved

    def get_glossary_extraction_mode(self) -> str:
        payload = self.get(self.GLOSSARY_EXTRACTION_KEY, {})
        if not isinstance(payload, dict):
            return "heuristic"
        mode = payload.get("mode")
        if isinstance(mode, str) and mode.strip().lower() in {"heuristic", "llm", "hybrid"}:
            return mode.strip().lower()
        return "heuristic"

    def set_glossary_extraction_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in {"heuristic", "llm", "hybrid"}:
            raise ValueError("Unsupported glossary extraction mode.")
        payload = self.get(self.GLOSSARY_EXTRACTION_KEY, {})
        if not isinstance(payload, dict):
            payload = {}
        payload["mode"] = normalized
        self.set(self.GLOSSARY_EXTRACTION_KEY, payload)

    def get_glossary_extraction_prompt_template(self) -> str | None:
        payload = self.get(self.GLOSSARY_EXTRACTION_KEY, {})
        if not isinstance(payload, dict):
            return None
        prompt_template = payload.get("prompt_template")
        if isinstance(prompt_template, str) and prompt_template.strip():
            return prompt_template
        return None

    def set_glossary_extraction_prompt_template(self, prompt_template: str | None) -> None:
        payload = self.get(self.GLOSSARY_EXTRACTION_KEY, {})
        if not isinstance(payload, dict):
            payload = {}
        payload["prompt_template"] = prompt_template.strip() if isinstance(prompt_template, str) and prompt_template.strip() else None
        self.set(self.GLOSSARY_EXTRACTION_KEY, payload)

    # ============================================================================
    # Backward-compatible aliases (formerly in SettingsService)
    # ============================================================================

    def get_provider_key(self) -> str:
        """Alias for get_preferred_provider (backward compat)."""
        return self.get_preferred_provider()

    def set_provider_key(self, key: str) -> None:
        """Alias for set_preferred_provider (backward compat)."""
        self.set_preferred_provider(key)

    def get_provider_model(self) -> str:
        """Get preferred model with OpenAI validation."""
        model = self.get_preferred_model()
        provider_key = self.get_provider_key()
        if provider_key != "openai":
            return model
        try:
            from novelai.providers.registry import available_models
            supported_models = available_models(provider_key)
        except Exception:
            logger.debug("Could not load available models for provider %s.", provider_key)
            return model
        if model in supported_models:
            return model
        return supported_models[0] if supported_models else model

    def set_provider_model(self, model: str) -> None:
        """Alias for set_preferred_model (backward compat)."""
        self.set_preferred_model(model)

    # ============================================================================
    # Runtime API key management (from environment, never persisted)
    # ============================================================================

    def get_api_key(self, provider_key: str = "openai") -> str | None:
        """Return the runtime API key from environment-backed settings."""
        if provider_key == "gemini":
            api_key = settings.PROVIDER_GEMINI_API_KEY
        else:
            api_key = settings.PROVIDER_OPENAI_API_KEY
        if api_key is None:
            return None
        return api_key.get_secret_value()

    def set_api_key(self, api_key: str, provider_key: str = "openai") -> None:
        """Update the runtime API key without persisting it to disk."""
        if provider_key == "gemini":
            os.environ["PROVIDER_GEMINI_API_KEY"] = api_key
            settings.PROVIDER_GEMINI_API_KEY = SecretStr(api_key)
            return
        os.environ["PROVIDER_OPENAI_API_KEY"] = api_key
        settings.PROVIDER_OPENAI_API_KEY = SecretStr(api_key)

    def clear_api_key(self, provider_key: str = "openai") -> None:
        """Remove the runtime API key from environment-backed settings."""
        if provider_key == "gemini":
            os.environ.pop("PROVIDER_GEMINI_API_KEY", None)
            settings.PROVIDER_GEMINI_API_KEY = None
            return
        os.environ.pop("PROVIDER_OPENAI_API_KEY", None)
        settings.PROVIDER_OPENAI_API_KEY = None

    def get_glossary_extraction_max_terms(self) -> int:
        payload = self.get(self.GLOSSARY_EXTRACTION_KEY, {})
        if not isinstance(payload, dict):
            return 50
        value = payload.get("max_terms")
        if isinstance(value, int) and value > 0:
            return value
        return 50

    def set_glossary_extraction_max_terms(self, max_terms: int) -> None:
        if max_terms < 1:
            raise ValueError("max_terms must be a positive integer.")
        payload = self.get(self.GLOSSARY_EXTRACTION_KEY, {})
        if not isinstance(payload, dict):
            payload = {}
        payload["max_terms"] = max_terms
        self.set(self.GLOSSARY_EXTRACTION_KEY, payload)
