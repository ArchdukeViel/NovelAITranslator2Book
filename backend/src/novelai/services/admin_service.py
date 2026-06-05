from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.activity.runner import BackgroundActivityRunner
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService

API_KEY_PROVIDERS = {"gemini", "openai"}
DEFAULT_PROVIDER_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5.4",
}
RUNTIME_STATE_DEFINITIONS = {
    "preferences": {
        "label": "Preferences",
        "filename": "preferences.json",
        "description": "Provider/model choices, workflow defaults, UI preferences, and glossary extraction settings.",
        "affects_process": True,
    },
    "translation_cache": {
        "label": "Translation Cache",
        "filename": "translation_cache.json",
        "description": "Cached translation outputs reused by metadata and chapter translation to avoid duplicate model calls.",
        "affects_process": True,
    },
    "usage": {
        "label": "Usage",
        "filename": "usage.json",
        "description": "Token/request usage history used for reporting and cost tracking.",
        "affects_process": False,
    },
}


ADMIN_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Novel AI Admin</title>
  <style>
    :root { color-scheme: light dark; font-family: Inter, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: Canvas; color: CanvasText; }
    header { display: flex; gap: 12px; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid color-mix(in srgb, CanvasText 16%, transparent); }
    main { display: grid; gap: 16px; padding: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    section { border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 8px; padding: 12px; min-width: 0; }
    h1 { font-size: 18px; margin: 0; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    button, input { font: inherit; min-height: 32px; }
    button { border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); background: ButtonFace; color: ButtonText; padding: 0 10px; }
    input { border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); padding: 0 8px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; max-height: 360px; overflow: auto; font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <h1>Novel AI Admin</h1>
    <div class="toolbar">
      <input id="token" type="password" placeholder="API token">
      <button id="save-token">Save</button>
      <button id="refresh">Refresh</button>
    </div>
  </header>
  <main>
    <section>
      <h2>Worker</h2>
      <div class="toolbar">
        <button id="start">Start</button>
        <button id="stop">Stop</button>
        <button id="run-once">Run Once</button>
      </div>
      <pre id="worker-status"></pre>
    </section>
    <section><h2>Activity</h2><pre id="activity"></pre></section>
    <section><h2>Requests</h2><pre id="requests"></pre></section>
    <section><h2>Sources</h2><pre id="sources"></pre></section>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    tokenInput.value = sessionStorage.getItem("novelai.token") || "";
    document.getElementById("save-token").onclick = () => sessionStorage.setItem("novelai.token", tokenInput.value);
    const headers = () => tokenInput.value ? {"Authorization": `Bearer ${tokenInput.value}`} : {};
    async function request(path, options = {}) {
      const response = await fetch(path, {...options, headers: {...headers(), ...(options.headers || {})}});
      if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
      return response.json();
    }
    const pretty = value => JSON.stringify(value, null, 2);
    async function refresh() {
      const [worker, activity, requests, sources] = await Promise.all([
        request("/novels/admin/worker"),
        request("/novels/activity?limit=20"),
        request("/novels/requests?limit=20"),
        request("/novels/activity/source-health"),
      ]);
      document.getElementById("worker-status").textContent = pretty(worker);
      document.getElementById("activity").textContent = pretty(activity.activity);
      document.getElementById("requests").textContent = pretty(requests.requests);
      document.getElementById("sources").textContent = pretty(sources.sources);
    }
    document.getElementById("refresh").onclick = () => refresh().catch(alert);
    document.getElementById("start").onclick = () => request("/novels/admin/worker/start", {method: "POST"}).then(refresh).catch(alert);
    document.getElementById("stop").onclick = () => request("/novels/admin/worker/stop", {method: "POST"}).then(refresh).catch(alert);
    document.getElementById("run-once").onclick = () => request("/novels/admin/worker/run-once", {method: "POST"}).then(refresh).catch(alert);
    refresh().catch(console.error);
  </script>
</body>
</html>
"""


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


class AdminService:
    def __init__(
        self,
        *,
        preferences: PreferencesService,
        translation_cache: TranslationCache,
        usage: UsageService,
        activity_runner: BackgroundActivityRunner,
    ) -> None:
        self.preferences = preferences
        self.translation_cache = translation_cache
        self.usage = usage
        self.activity_runner = activity_runner

    def dashboard_html(self) -> str:
        return ADMIN_DASHBOARD_HTML

    def provider_api_key_status(self, provider: str) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        preferred_provider = self.preferences.get_preferred_provider()
        model = (
            self.preferences.get_preferred_model()
            if preferred_provider == normalized_provider
            else self.resolve_default_model(normalized_provider)
        )
        return {
            "provider": normalized_provider,
            "provider_key": normalized_provider,
            "configured": self.preferences.get_api_key(normalized_provider) is not None,
            "preferred_provider": preferred_provider,
            "preferred_provider_key": preferred_provider,
            "model": model,
            "provider_model": model,
            "fallback_models": model_candidates(normalized_provider, model),
            "validation_status": "unchecked",
            "validation_message": "Connection has not been checked in this server session.",
        }

    def normalize_provider(self, provider: str) -> str:
        normalized = provider.strip().lower()
        if normalized not in API_KEY_PROVIDERS:
            raise ValueError("Provider must be one of: gemini, openai")
        return normalized

    def resolve_default_model(self, provider: str, requested_model: str | None = None) -> str:
        if isinstance(requested_model, str) and requested_model.strip():
            return requested_model.strip()

        try:
            from novelai.providers.registry import available_models

            models = available_models(provider)
        except Exception:
            models = []
        return models[0] if models else DEFAULT_PROVIDER_MODELS[provider]

    def set_provider_globally(self, provider: str, model: str) -> None:
        self.preferences.set_preferred_provider(provider)
        self.preferences.set_preferred_model(model)
        for step in WORKFLOW_PROFILE_STEPS:
            self.preferences.set_llm_step_config(step, provider=provider, model=model)

    def set_provider_api_key(
        self,
        *,
        provider: str,
        api_key: str,
        model: str | None,
        apply_globally: bool,
    ) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        clean_api_key = api_key.strip()
        if not clean_api_key:
            raise ValueError("API key must not be empty")

        resolved_model = self.resolve_default_model(normalized_provider, model)
        self.preferences.set_api_key(clean_api_key, provider_key=normalized_provider)
        if apply_globally:
            self.set_provider_globally(normalized_provider, resolved_model)
        return self.provider_api_key_status(normalized_provider)

    async def validate_provider_api_key(
        self,
        *,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        previous_api_key = self.preferences.get_api_key(normalized_provider)
        temporary_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        resolved_model = self.resolve_default_model(normalized_provider, model)

        if temporary_key is not None:
            self.preferences.set_api_key(temporary_key, provider_key=normalized_provider)

        try:
            if self.preferences.get_api_key(normalized_provider) is None:
                return {
                    **self.provider_api_key_status(normalized_provider),
                    "model": resolved_model,
                    "provider_model": resolved_model,
                    "validation_status": "failed",
                    "validation_message": "No API key is configured for this provider.",
                }

            from novelai.providers.registry import get_provider

            provider_client = get_provider(normalized_provider)
            try:
                supported_models = provider_client.available_models() or []
            except Exception:
                supported_models = []

            last_message = ""
            for candidate_model in model_candidates(normalized_provider, resolved_model, supported_models):
                try:
                    ok, message = await provider_client.validate_connection(model=candidate_model)
                except Exception as exc:
                    ok = False
                    message = str(exc)
                if ok:
                    return {
                        **self.provider_api_key_status(normalized_provider),
                        "model": candidate_model,
                        "provider_model": candidate_model,
                        "fallback_models": model_candidates(normalized_provider, candidate_model, supported_models),
                        "validation_status": "working",
                        "validation_message": message,
                    }
                last_message = f"{candidate_model}: {message}"

            return {
                **self.provider_api_key_status(normalized_provider),
                "model": resolved_model,
                "provider_model": resolved_model,
                "validation_status": "failed",
                "validation_message": last_message or "No Gemini model candidate could be validated.",
            }
        finally:
            if temporary_key is not None:
                if previous_api_key is None:
                    self.preferences.clear_api_key(normalized_provider)
                else:
                    self.preferences.set_api_key(previous_api_key, provider_key=normalized_provider)

    def clear_provider_api_key(self, provider: str) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        self.preferences.clear_api_key(normalized_provider)
        if self.preferences.get_preferred_provider() == normalized_provider:
            self.preferences.set_preferred_provider("dummy")
            self.preferences.set_preferred_model("dummy")
        return self.provider_api_key_status(normalized_provider)

    def list_runtime_state(self) -> dict[str, Any]:
        return {"items": [self.runtime_state_record(key) for key in RUNTIME_STATE_DEFINITIONS]}

    def refresh_runtime_state(self, state_key: str) -> dict[str, Any]:
        key = state_key.strip().lower()
        if key == "preferences":
            self.preferences.reload()
        elif key == "translation_cache":
            self.translation_cache.reload()
        elif key == "usage":
            self.usage.reload()
        else:
            raise KeyError(f"Unknown runtime state file: {state_key}")
        return self.runtime_state_record(key)

    def clear_runtime_state(self, state_key: str) -> dict[str, Any]:
        key = state_key.strip().lower()
        if key == "preferences":
            self.preferences.clear()
        elif key == "translation_cache":
            self.translation_cache.clear()
        elif key == "usage":
            self.usage.clear()
        else:
            raise KeyError(f"Unknown runtime state file: {state_key}")
        return self.runtime_state_record(key)

    def runtime_state_record(self, key: str) -> dict[str, Any]:
        path = self.runtime_state_path(key)
        definition = RUNTIME_STATE_DEFINITIONS[key]
        exists = path.exists()
        stat = path.stat() if exists else None
        return {
            "key": key,
            "label": definition["label"],
            "filename": definition["filename"],
            "path": f"runtime/{definition['filename']}",
            "exists": exists,
            "size_bytes": stat.st_size if stat is not None else 0,
            "updated_at": _iso_from_timestamp(stat.st_mtime) if stat is not None else None,
            "description": definition["description"],
            "affects_process": definition["affects_process"],
        }

    def runtime_state_path(self, key: str) -> Path:
        if key == "preferences":
            return self.preferences.prefs_path
        if key == "translation_cache":
            return self.translation_cache.cache_file
        if key == "usage":
            return self.usage.usage_path
        raise KeyError(f"Unknown runtime state file: {key}")

    def worker_status(self) -> dict[str, Any]:
        return self.activity_runner.status()

    async def start_worker(self) -> dict[str, Any]:
        return await self.activity_runner.start()

    async def stop_worker(self) -> dict[str, Any]:
        return await self.activity_runner.stop()

    async def run_worker_once(self) -> dict[str, Any]:
        activity = await self.activity_runner.run_once()
        return {
            "activity": activity,
            "job": activity,
            "worker": self.activity_runner.status(),
        }
