from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from novelai.activity.runner import BackgroundActivityRunner
from novelai.api.routers.dependencies import (
    get_activity_runner,
    get_preferences,
    get_translation_cache,
    get_usage,
    verify_api_key,
)
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService

router = APIRouter()

_API_KEY_PROVIDERS = {"gemini", "openai"}
_DEFAULT_PROVIDER_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5.4",
}
_RUNTIME_STATE_DEFINITIONS = {
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


class ProviderApiKeyRequest(BaseModel):
    provider: str = "gemini"
    provider_key: str | None = None
    api_key: str
    model: str | None = None
    provider_model: str | None = None
    apply_globally: bool = True
    validate_connection: bool = True


class ProviderApiKeyValidationRequest(BaseModel):
    provider: str = "gemini"
    provider_key: str | None = None
    api_key: str | None = None
    model: str | None = None
    provider_model: str | None = None


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def _runtime_state_path(
    key: str,
    preferences: PreferencesService,
    cache: TranslationCache,
    usage: UsageService,
) -> Path:
    if key == "preferences":
        return preferences.prefs_path
    if key == "translation_cache":
        return cache.cache_file
    if key == "usage":
        return usage.usage_path
    raise HTTPException(status_code=404, detail=f"Unknown runtime state file: {key}")


def _runtime_state_record(key: str, path: Path) -> dict[str, Any]:
    definition = _RUNTIME_STATE_DEFINITIONS[key]
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


def _runtime_state_records(
    preferences: PreferencesService,
    cache: TranslationCache,
    usage: UsageService,
) -> list[dict[str, Any]]:
    return [
        _runtime_state_record(key, _runtime_state_path(key, preferences, cache, usage))
        for key in _RUNTIME_STATE_DEFINITIONS
    ]


def _normalize_api_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in _API_KEY_PROVIDERS:
        raise HTTPException(status_code=400, detail="Provider must be one of: gemini, openai")
    return normalized


def _resolve_default_model(provider: str, requested_model: str | None = None) -> str:
    if isinstance(requested_model, str) and requested_model.strip():
        return requested_model.strip()

    try:
        from novelai.providers.registry import available_models

        models = available_models(provider)
    except Exception:
        models = []
    return models[0] if models else _DEFAULT_PROVIDER_MODELS[provider]


def _provider_api_key_status(preferences: PreferencesService, provider: str) -> dict[str, Any]:
    preferred_provider = preferences.get_preferred_provider()
    model = preferences.get_preferred_model() if preferred_provider == provider else _resolve_default_model(provider)
    return {
        "provider": provider,
        "provider_key": provider,
        "configured": preferences.get_api_key(provider) is not None,
        "preferred_provider": preferred_provider,
        "preferred_provider_key": preferred_provider,
        "model": model,
        "provider_model": model,
        "fallback_models": model_candidates(provider, model),
        "validation_status": "unchecked",
        "validation_message": "Connection has not been checked in this server session.",
    }


def _apply_provider_globally(preferences: PreferencesService, provider: str, model: str) -> None:
    preferences.set_preferred_provider(provider)
    preferences.set_preferred_model(model)
    for step in WORKFLOW_PROFILE_STEPS:
        preferences.set_llm_step_config(step, provider=provider, model=model)


async def _validate_provider_api_key(
    preferences: PreferencesService,
    *,
    provider: str,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    previous_api_key = preferences.get_api_key(provider)
    temporary_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
    resolved_model = _resolve_default_model(provider, model)

    if temporary_key is not None:
        preferences.set_api_key(temporary_key, provider_key=provider)

    try:
        if preferences.get_api_key(provider) is None:
            return {
                **_provider_api_key_status(preferences, provider),
                "model": resolved_model,
                "provider_model": resolved_model,
                "validation_status": "failed",
                "validation_message": "No API key is configured for this provider.",
            }

        from novelai.providers.registry import get_provider

        provider_client = get_provider(provider)
        try:
            supported_models = provider_client.available_models() or []
        except Exception:
            supported_models = []

        last_message = ""
        for candidate_model in model_candidates(provider, resolved_model, supported_models):
            try:
                ok, message = await provider_client.validate_connection(model=candidate_model)
            except Exception as exc:
                ok = False
                message = str(exc)
            if ok:
                return {
                    **_provider_api_key_status(preferences, provider),
                    "model": candidate_model,
                    "provider_model": candidate_model,
                    "fallback_models": model_candidates(provider, candidate_model, supported_models),
                    "validation_status": "working",
                    "validation_message": message,
                }
            last_message = f"{candidate_model}: {message}"

        return {
            **_provider_api_key_status(preferences, provider),
            "model": resolved_model,
            "provider_model": resolved_model,
            "validation_status": "failed",
            "validation_message": last_message or "No Gemini model candidate could be validated.",
        }
    finally:
        if temporary_key is not None:
            if previous_api_key is None:
                preferences.clear_api_key(provider)
            else:
                preferences.set_api_key(previous_api_key, provider_key=provider)

_ADMIN_HTML = """<!doctype html>
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


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(_auth: None = Depends(verify_api_key)) -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML)


@router.get("/admin/provider-api-key/{provider}")
async def get_provider_api_key_status(
    provider: str,
    preferences: PreferencesService = Depends(get_preferences),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    normalized_provider = _normalize_api_provider(provider)
    return _provider_api_key_status(preferences, normalized_provider)


@router.post("/admin/provider-api-key")
async def set_provider_api_key(
    body: ProviderApiKeyRequest,
    preferences: PreferencesService = Depends(get_preferences),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    provider = _normalize_api_provider(body.provider_key or body.provider)
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key must not be empty")

    model = _resolve_default_model(provider, body.provider_model or body.model)
    preferences.set_api_key(api_key, provider_key=provider)
    if body.apply_globally:
        _apply_provider_globally(preferences, provider, model)

    if body.validate_connection:
        return await _validate_provider_api_key(preferences, provider=provider, model=model)
    return _provider_api_key_status(preferences, provider)


@router.post("/admin/provider-api-key/validate")
async def validate_provider_api_key(
    body: ProviderApiKeyValidationRequest,
    preferences: PreferencesService = Depends(get_preferences),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    provider = _normalize_api_provider(body.provider_key or body.provider)
    return await _validate_provider_api_key(
        preferences,
        provider=provider,
        api_key=body.api_key,
        model=body.provider_model or body.model,
    )


@router.delete("/admin/provider-api-key/{provider}")
async def clear_provider_api_key(
    provider: str,
    preferences: PreferencesService = Depends(get_preferences),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    normalized_provider = _normalize_api_provider(provider)
    preferences.clear_api_key(normalized_provider)
    if preferences.get_preferred_provider() == normalized_provider:
        preferences.set_preferred_provider("dummy")
        preferences.set_preferred_model("dummy")
    return _provider_api_key_status(preferences, normalized_provider)


@router.get("/admin/runtime-state")
async def list_runtime_state(
    preferences: PreferencesService = Depends(get_preferences),
    cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return {"items": _runtime_state_records(preferences, cache, usage)}


@router.post("/admin/runtime-state/{state_key}/refresh")
async def refresh_runtime_state(
    state_key: str,
    preferences: PreferencesService = Depends(get_preferences),
    cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    key = state_key.strip().lower()
    if key == "preferences":
        preferences.reload()
    elif key == "translation_cache":
        cache.reload()
    elif key == "usage":
        usage.reload()
    else:
        raise HTTPException(status_code=404, detail=f"Unknown runtime state file: {state_key}")
    return _runtime_state_record(key, _runtime_state_path(key, preferences, cache, usage))


@router.delete("/admin/runtime-state/{state_key}")
async def clear_runtime_state(
    state_key: str,
    preferences: PreferencesService = Depends(get_preferences),
    cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    key = state_key.strip().lower()
    if key == "preferences":
        preferences.clear()
    elif key == "translation_cache":
        cache.clear()
    elif key == "usage":
        usage.clear()
    else:
        raise HTTPException(status_code=404, detail=f"Unknown runtime state file: {state_key}")
    return _runtime_state_record(key, _runtime_state_path(key, preferences, cache, usage))


@router.get("/admin/worker")
async def get_worker_status(
    runner: BackgroundActivityRunner = Depends(get_activity_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return runner.status()


@router.post("/admin/worker/start")
async def start_worker(
    runner: BackgroundActivityRunner = Depends(get_activity_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await runner.start()


@router.post("/admin/worker/stop")
async def stop_worker(
    runner: BackgroundActivityRunner = Depends(get_activity_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await runner.stop()


@router.post("/admin/worker/run-once")
async def run_worker_once(
    runner: BackgroundActivityRunner = Depends(get_activity_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    activity = await runner.run_once()
    return {
        "activity": activity,
        "job": activity,
        "worker": runner.status(),
    }
