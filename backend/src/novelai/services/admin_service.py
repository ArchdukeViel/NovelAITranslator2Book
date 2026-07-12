from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from novelai.activity.runner import BackgroundActivityRunner
from novelai.config.settings import settings
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.export_manifest_service import (
    compute_export_freshness,
    latest_export,
    list_manifests,
)
from novelai.services.preferences_service import PreferencesService
from novelai.services.provider_credentials import ProviderCredentialService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService

API_KEY_PROVIDERS = {"gemini"}
DEFAULT_PROVIDER_MODELS = {
    "gemini": "gemini-3.1-flash-lite",
}
PROVIDER_LABELS = {
    "gemini": "Gemini",
}
DEFAULT_QUOTA_HINTS = {
    ("gemini", "gemini-3.1-flash-lite"): {
        "rpm_limit": 15,
        "tpm_limit": 250_000,
        "rpd_limit": 500,
        "cooldown_seconds": 90,
        "daily_reset": None,
    },
}
ALLOWED_FALLBACK_FAILURE_REASONS = {
    "rate_limit",
    "quota_exceeded",
    "model_unavailable",
    "provider_timeout",
    "transient_provider_error",
}
DISALLOWED_FALLBACK_FAILURE_REASONS = {
    "qa_failure",
    "safety_refusal",
    "paragraph_missing",
    "deterministic_validation_failure",
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
    "runtime_chunks": {
        "label": "Translation Chunks",
        "filename": "translation_chunks.json",
        "description": "Translation chunk records saved during pipeline execution.",
        "affects_process": True,
    },
    "runtime_chunk_attempts": {
        "label": "Chunk Attempts",
        "filename": "chunk_attempt_records.json",
        "description": "Per-attempt records for each translation chunk.",
        "affects_process": True,
    },
    "runtime_bundles": {
        "label": "Translation Bundles",
        "filename": "translation_bundles.json",
        "description": "Translation bundle records for chapter-level grouping.",
        "affects_process": True,
    },
    "runtime_outputs": {
        "label": "Translation Outputs",
        "filename": "translation_outputs.json",
        "description": "Translation output records from completed pipeline runs.",
        "affects_process": True,
    },
    "backup_manifest": {
        "label": "Backup Manifest",
        "filename": "manifest.json",
        "description": "Manifest of all backups stored on disk.",
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


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _optional_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _secret_last4(secret: str) -> str:
    return secret[-4:] if len(secret) >= 4 else secret


def _secret_fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


class AdminService:
    def __init__(
        self,
        *,
        preferences: PreferencesService,
        translation_cache: TranslationCache,
        usage: UsageService,
        activity_runner: BackgroundActivityRunner,
        storage: Any | None = None,
        db_session: Session | None = None,
    ) -> None:
        self.preferences = preferences
        self.translation_cache = translation_cache
        self.usage = usage
        self.activity_runner = activity_runner
        self.storage = storage
        self.db_session = db_session

    def dashboard_html(self) -> str:
        return ADMIN_DASHBOARD_HTML

    def provider_api_key_status(self, provider: str) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        credential = self._credential_metadata(normalized_provider)
        preferred_provider = self.preferences.get_preferred_provider()
        model = (
            self.preferences.get_preferred_model()
            if preferred_provider == normalized_provider
            else self.resolve_default_model(normalized_provider)
        )
        return {
            "provider_key": normalized_provider,
            "configured": self._provider_configured(normalized_provider),
            "preferred_provider_key": preferred_provider,
            "provider_model": model,
            "fallback_models": model_candidates(normalized_provider, model),
            "label": credential.get("label") or PROVIDER_LABELS.get(normalized_provider, normalized_provider),
            "is_active": credential.get("is_active", self.preferences.get_api_key(normalized_provider) is not None),
            "last4": credential.get("last4"),
            "fingerprint": credential.get("fingerprint"),
            "created_at": credential.get("created_at"),
            "updated_at": credential.get("updated_at"),
            "last_validated_at": credential.get("last_validated_at"),
            "validation_status": credential.get("validation_status") or "unchecked",
            "validation_message": credential.get("validation_message")
            or "Connection has not been checked in this server session.",
        }

    def normalize_provider(self, provider: str) -> str:
        normalized = provider.strip().lower()
        if normalized not in API_KEY_PROVIDERS:
            raise ValueError("Provider must be: gemini")
        return normalized

    def resolve_default_model(self, provider: str, requested_model: str | None = None) -> str:
        normalized_provider = self.normalize_provider(provider)
        if isinstance(requested_model, str) and requested_model.strip():
            candidate = requested_model.strip()
            self.validate_provider_model(normalized_provider, candidate)
            return candidate

        try:
            from novelai.providers.registry import available_models

            models = available_models(normalized_provider)
        except Exception:
            models = []
        return models[0] if models else DEFAULT_PROVIDER_MODELS[normalized_provider]

    def validate_provider_model(self, provider: str, model: str) -> None:
        normalized_provider = self.normalize_provider(provider)
        try:
            from novelai.providers.registry import available_models

            models = available_models(normalized_provider)
        except Exception:
            models = []
        if models and model not in models:
            raise ValueError(f"Model {model!r} is not available for provider {normalized_provider!r}.")

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
        self._upsert_credential_metadata(
            normalized_provider,
            label=PROVIDER_LABELS.get(normalized_provider, normalized_provider),
            model=resolved_model,
            is_active=True,
            api_key=clean_api_key,
            validation_status="unchecked",
            validation_message="Connection has not been checked in this server session.",
        )
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
        credential_service = self._credential_service()
        credential = credential_service.get_by_provider(normalized_provider) if credential_service is not None else None
        if temporary_key is None and credential is not None and credential_service is not None:
            temporary_key = credential_service.decrypt_api_key(credential)
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
                    now = _utc_now_iso()
                    if credential is not None and credential_service is not None:
                        credential_service.update_metadata(
                            credential,
                            model=candidate_model,
                            validation_status="working",
                            validation_message=message,
                            last_validated_at=datetime.now(UTC),
                        )
                    self._upsert_credential_metadata(
                        normalized_provider,
                        model=candidate_model,
                        is_active=True,
                        validation_status="working",
                        validation_message=message,
                        last_validated_at=now,
                    )
                    return {
                        **self.provider_api_key_status(normalized_provider),
                        "model": candidate_model,
                        "provider_model": candidate_model,
                        "fallback_models": model_candidates(normalized_provider, candidate_model, supported_models),
                        "validation_status": "working",
                        "validation_message": message,
                    }
                last_message = f"{candidate_model}: {message}"

            if credential is not None and credential_service is not None:
                credential_service.update_metadata(
                    credential,
                    validation_status="failed",
                    validation_message=last_message or "No provider model candidate could be validated.",
                    last_validated_at=datetime.now(UTC),
                )
            return {
                **self.provider_api_key_status(normalized_provider),
                "model": resolved_model,
                "provider_model": resolved_model,
                "validation_status": "failed",
                "validation_message": last_message or "No provider model candidate could be validated.",
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
        self._upsert_credential_metadata(normalized_provider, is_active=False, validation_status="unchecked")
        if self.preferences.get_preferred_provider() == normalized_provider:
            self.preferences.set_preferred_provider("dummy")
            self.preferences.set_preferred_model("dummy")
        return self.provider_api_key_status(normalized_provider)

    def provider_inventory(self) -> dict[str, Any]:
        return {
            "providers": [
                {
                    "provider": provider,
                    "label": PROVIDER_LABELS.get(provider, provider),
                    "configured": self._provider_configured(provider),
                    "default_model": self.resolve_default_model(provider),
                    "models": [item for item in self.provider_models()["models"] if item["provider"] == provider],
                }
                for provider in sorted(API_KEY_PROVIDERS)
            ],
            "credentials": self.list_provider_credentials()["credentials"],
            "fallback_policy": self.get_provider_fallback_policy(),
        }

    def provider_models(self) -> dict[str, Any]:
        models: list[dict[str, Any]] = []
        for provider in sorted(API_KEY_PROVIDERS):
            try:
                from novelai.providers.registry import available_models

                provider_models = available_models(provider)
            except Exception:
                provider_models = []
            if not provider_models:
                provider_models = [DEFAULT_PROVIDER_MODELS[provider]]
            for model in provider_models:
                quota = DEFAULT_QUOTA_HINTS.get((provider, model), {})
                models.append(
                    {
                        "provider": provider,
                        "model": model,
                        "provider_model": model,
                        "selectable": True,
                        "is_default": model == self.resolve_default_model(provider),
                        "quota": {
                            "rpm_limit": quota.get("rpm_limit"),
                            "tpm_limit": quota.get("tpm_limit"),
                            "rpd_limit": quota.get("rpd_limit"),
                            "cooldown_seconds": quota.get("cooldown_seconds"),
                            "daily_reset": quota.get("daily_reset"),
                        },
                    }
                )
        return {"models": models}

    def list_provider_credentials(self) -> dict[str, Any]:
        credential_service = self._credential_service()
        if credential_service is not None:
            seen = set()
            rows = []
            for credential in credential_service.list_credentials():
                seen.add(credential.provider)
                rows.append(ProviderCredentialService.safe_response(credential))
            for provider in sorted(API_KEY_PROVIDERS - seen):
                rows.append(self._safe_credential_response(provider))
            return {"credentials": rows}
        return {"credentials": [self._safe_credential_response(provider) for provider in sorted(API_KEY_PROVIDERS)]}

    def create_provider_credential(
        self,
        *,
        provider: str,
        api_key: str,
        label: str | None = None,
        model: str | None = None,
        is_active: bool = True,
        notes: str | None = None,
        apply_globally: bool = False,
    ) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        clean_api_key = api_key.strip()
        if not clean_api_key:
            raise ValueError("API key must not be empty")
        resolved_model = self.resolve_default_model(normalized_provider, model)
        credential_service = self._require_credential_service()
        credential = credential_service.upsert_credential(
            provider=normalized_provider,
            api_key=clean_api_key,
            label=label or PROVIDER_LABELS.get(normalized_provider, normalized_provider),
            model=resolved_model,
            is_active=is_active,
            notes=notes,
        )
        self.preferences.set_api_key(clean_api_key, provider_key=normalized_provider)
        self._upsert_credential_metadata(
            normalized_provider,
            label=credential.label,
            model=resolved_model,
            is_active=is_active,
            notes=notes,
            api_key=clean_api_key,
            validation_status="unchecked",
            validation_message="Connection has not been checked in this server session.",
        )
        if apply_globally:
            self.set_provider_globally(normalized_provider, resolved_model)
            policy = self.get_provider_fallback_policy()
            policy["default_provider"] = normalized_provider
            policy["default_model"] = resolved_model
            policy["default_credential_id"] = normalized_provider
            self.set_provider_fallback_policy(policy)
        return ProviderCredentialService.safe_response(credential)

    def update_provider_credential(
        self,
        credential_id: str,
        *,
        label: str | None = None,
        model: str | None = None,
        is_active: bool | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        provider = self.normalize_provider(credential_id)
        resolved_model = self.resolve_default_model(provider, model) if model is not None else None
        credential_service = self._require_credential_service()
        credential = credential_service.get_by_id_or_provider(provider)
        if credential is None:
            raise KeyError(f"Provider credential not found: {credential_id}")
        credential_service.update_metadata(
            credential,
            label=label,
            model=resolved_model,
            is_active=is_active,
            notes=notes,
        )
        self._upsert_credential_metadata(
            provider,
            label=label,
            model=resolved_model,
            is_active=is_active,
            notes=notes,
        )
        return ProviderCredentialService.safe_response(credential)

    def delete_provider_credential(self, credential_id: str) -> dict[str, Any]:
        provider = self.normalize_provider(credential_id)
        credential_service = self._require_credential_service()
        credential = credential_service.get_by_id_or_provider(provider)
        if credential is None:
            raise KeyError(f"Provider credential not found: {credential_id}")
        credential_service.update_metadata(credential, is_active=False, validation_status="unchecked")
        self.preferences.clear_api_key(provider)
        self._upsert_credential_metadata(provider, is_active=False, validation_status="unchecked")
        return ProviderCredentialService.safe_response(credential)

    def get_provider_fallback_policy(self) -> dict[str, Any]:
        state = self.preferences.get_provider_management()
        raw_policy = state.get("fallback_policy") if isinstance(state.get("fallback_policy"), dict) else {}
        policy = self._default_fallback_policy()
        if isinstance(raw_policy, dict):
            policy.update({key: value for key, value in raw_policy.items() if key != "candidates"})
            if isinstance(raw_policy.get("candidates"), list):
                policy["candidates"] = [
                    self._normalize_policy_candidate(item, index)
                    for index, item in enumerate(raw_policy["candidates"])
                    if isinstance(item, dict)
                ]
        policy["candidates"] = sorted(policy["candidates"], key=lambda item: int(item.get("priority_order", 0) or 0))
        policy["fallback_on_qa_failure"] = bool(policy.get("fallback_on_qa_failure", False))
        policy["disallowed_failure_reasons"] = sorted(DISALLOWED_FALLBACK_FAILURE_REASONS)
        return policy

    def set_provider_fallback_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(policy, dict):
            raise ValueError("Fallback policy must be an object.")
        normalized = self.get_provider_fallback_policy()
        for key in ("default_provider", "default_model", "default_credential_id", "allow_cross_provider_fallback", "allow_run_overrides", "fallback_on_qa_failure"):
            if key in policy:
                normalized[key] = policy[key]
        default_provider = self.normalize_provider(str(normalized.get("default_provider") or "gemini"))
        default_model = str(normalized.get("default_model") or self.resolve_default_model(default_provider))
        self.validate_provider_model(default_provider, default_model)
        normalized["default_provider"] = default_provider
        normalized["default_model"] = default_model
        normalized["default_credential_id"] = self.normalize_provider(str(normalized.get("default_credential_id") or default_provider))
        if "candidates" in policy:
            if not isinstance(policy["candidates"], list):
                raise ValueError("Fallback policy candidates must be a list.")
            normalized["candidates"] = [
                self._normalize_policy_candidate(item, index)
                for index, item in enumerate(policy["candidates"])
                if isinstance(item, dict)
            ]
        if not normalized["candidates"]:
            normalized["candidates"] = self._default_fallback_policy()["candidates"]
        state = self.preferences.get_provider_management()
        state["fallback_policy"] = normalized
        self.preferences.set_provider_management(state)
        return self.get_provider_fallback_policy()

    def scheduler_policy_models(
        self,
        *,
        provider_key: str,
        model: str,
        allow_cross_provider_fallback: bool,
    ) -> list[dict[str, Any]]:
        policy = self.get_provider_fallback_policy()
        candidates = []
        for item in policy.get("candidates", []):
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            provider = self.normalize_provider(str(item.get("provider") or item.get("provider_key") or provider_key))
            credential_id = self.normalize_provider(str(item.get("credential_id") or provider))
            credential = self._credential_metadata(credential_id)
            if credential.get("is_active") is False:
                continue
            if self.preferences.get_api_key(credential_id) is None:
                continue
            if not allow_cross_provider_fallback and provider != provider_key:
                continue
            candidate_model = str(item.get("model") or item.get("provider_model") or model)
            self.validate_provider_model(provider, candidate_model)
            candidates.append(
                {
                    "provider_key": provider,
                    "provider_model": candidate_model,
                    "priority_order": int(item.get("priority_order", len(candidates)) or len(candidates)),
                    "rpm_limit": item.get("rpm_limit"),
                    "rpd_limit": item.get("rpd_limit"),
                }
            )
        if candidates:
            return candidates
        return [{"provider_key": provider_key, "provider_model": model, "priority_order": 0}]

    def _provider_management_state(self) -> dict[str, Any]:
        state = self.preferences.get_provider_management()
        credentials = state.get("credentials")
        if not isinstance(credentials, dict):
            state["credentials"] = {}
        return state

    def _save_provider_management_state(self, state: dict[str, Any]) -> None:
        self.preferences.set_provider_management(state)

    def _credential_metadata(self, provider: str) -> dict[str, Any]:
        credential_service = self._credential_service()
        if credential_service is not None:
            credential = credential_service.get_by_provider(provider)
            if credential is not None:
                return {
                    "id": credential.provider,
                    "provider": credential.provider,
                    "label": credential.label,
                    "is_active": credential.is_active,
                    "last4": credential.last4,
                    "fingerprint": credential.key_fingerprint,
                    "model": credential.model,
                    "validation_status": credential.validation_status,
                    "validation_message": credential.validation_message,
                    "created_at": credential.created_at.isoformat().replace("+00:00", "Z") if credential.created_at else None,
                    "updated_at": credential.updated_at.isoformat().replace("+00:00", "Z") if credential.updated_at else None,
                    "last_validated_at": credential.last_validated_at.isoformat().replace("+00:00", "Z")
                    if credential.last_validated_at
                    else None,
                    "notes": credential.notes,
                }
        state = self._provider_management_state()
        credentials = state.get("credentials", {})
        metadata = credentials.get(provider) if isinstance(credentials, dict) else None
        if not isinstance(metadata, dict):
            return {}
        return dict(metadata)

    def _upsert_credential_metadata(
        self,
        provider: str,
        *,
        label: str | None = None,
        model: str | None = None,
        is_active: bool | None = None,
        notes: str | None = None,
        api_key: str | None = None,
        validation_status: str | None = None,
        validation_message: str | None = None,
        last_validated_at: str | None = None,
    ) -> None:
        state = self._provider_management_state()
        credentials = state.setdefault("credentials", {})
        current = credentials.get(provider) if isinstance(credentials.get(provider), dict) else {}
        now = _utc_now_iso()
        record = dict(current)
        record.setdefault("id", provider)
        record.setdefault("provider", provider)
        record.setdefault("created_at", now)
        record["updated_at"] = now
        if label is not None:
            record["label"] = label.strip() if label.strip() else PROVIDER_LABELS.get(provider, provider)
        if model is not None:
            record["model"] = model
        if is_active is not None:
            record["is_active"] = bool(is_active)
        if notes is not None:
            record["notes"] = notes
        if api_key is not None:
            record["last4"] = _secret_last4(api_key)
            record["fingerprint"] = _secret_fingerprint(api_key)
        if validation_status is not None:
            record["validation_status"] = validation_status
        if validation_message is not None:
            record["validation_message"] = validation_message
        if last_validated_at is not None:
            record["last_validated_at"] = last_validated_at
        credentials[provider] = record
        self._save_provider_management_state(state)

    def _safe_credential_response(self, provider: str) -> dict[str, Any]:
        normalized_provider = self.normalize_provider(provider)
        credential_service = self._credential_service()
        if credential_service is not None:
            credential = credential_service.get_by_provider(normalized_provider)
            if credential is not None:
                return ProviderCredentialService.safe_response(credential)
        metadata = self._credential_metadata(normalized_provider)
        configured = self._provider_configured(normalized_provider)
        model = metadata.get("model") if isinstance(metadata.get("model"), str) else self.resolve_default_model(normalized_provider)
        return {
            "id": normalized_provider,
            "provider": normalized_provider,
            "label": metadata.get("label") or PROVIDER_LABELS.get(normalized_provider, normalized_provider),
            "is_active": bool(metadata.get("is_active", configured)),
            "configured": configured,
            "last4": metadata.get("last4"),
            "fingerprint": metadata.get("fingerprint"),
            "model": model,
            "provider_model": model,
            "validation_status": metadata.get("validation_status") or "unchecked",
            "validation_message": metadata.get("validation_message"),
            "last_validated_at": metadata.get("last_validated_at"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "notes": metadata.get("notes"),
        }

    def _credential_service(self) -> ProviderCredentialService | None:
        return ProviderCredentialService(self.db_session) if self.db_session is not None else None

    def _require_credential_service(self) -> ProviderCredentialService:
        service = self._credential_service()
        if service is None:
            raise ValueError("Database is required for provider credential management.")
        return service

    def _provider_configured(self, provider: str) -> bool:
        credential_service = self._credential_service()
        if credential_service is not None and credential_service.get_by_provider(provider) is not None:
            return True
        return self.preferences.get_api_key(provider) is not None

    def _default_fallback_policy(self) -> dict[str, Any]:
        provider = self.preferences.get_preferred_provider()
        if provider not in API_KEY_PROVIDERS:
            provider = "gemini"
        model = self.preferences.get_provider_model() if provider in API_KEY_PROVIDERS else settings.PROVIDER_GEMINI_DEFAULT_MODEL
        if provider == "gemini" and model == "google/gemma-4-31b-it":
            model = settings.PROVIDER_GEMINI_DEFAULT_MODEL
        primary_quota = DEFAULT_QUOTA_HINTS.get((provider, model), {})
        return {
            "default_provider": provider,
            "default_model": model,
            "default_credential_id": provider,
            "allow_cross_provider_fallback": False,
            "allow_run_overrides": True,
            "fallback_on_qa_failure": False,
            "allowed_failure_reasons": sorted(ALLOWED_FALLBACK_FAILURE_REASONS),
            "disallowed_failure_reasons": sorted(DISALLOWED_FALLBACK_FAILURE_REASONS),
            "candidates": [
                {
                    "priority_order": 0,
                    "provider_key": provider,
                    "provider_model": model,
                    "credential_id": provider,
                    "enabled": True,
                    "allowed_failure_reasons": sorted(ALLOWED_FALLBACK_FAILURE_REASONS),
                    "rpm_limit": primary_quota.get("rpm_limit"),
                    "tpm_limit": primary_quota.get("tpm_limit"),
                    "rpd_limit": primary_quota.get("rpd_limit"),
                    "cooldown_seconds": primary_quota.get("cooldown_seconds"),
                    "daily_reset": primary_quota.get("daily_reset"),
                },
            ],
        }

    def _normalize_policy_candidate(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        provider = self.normalize_provider(str(item.get("provider") or item.get("provider_key") or "gemini"))
        model = str(item.get("model") or item.get("provider_model") or self.resolve_default_model(provider))
        self.validate_provider_model(provider, model)
        credential_id = self.normalize_provider(str(item.get("credential_id") or provider))
        raw_reasons = item.get("allowed_failure_reasons")
        if isinstance(raw_reasons, list):
            reasons = {str(value).strip() for value in raw_reasons if isinstance(value, str) and value.strip()}
            invalid_reasons = sorted(reasons - ALLOWED_FALLBACK_FAILURE_REASONS)
            if invalid_reasons:
                raise ValueError(f"Unsupported fallback failure reasons: {', '.join(invalid_reasons)}")
            allowed_reasons = sorted(reasons)
        else:
            allowed_reasons = sorted(ALLOWED_FALLBACK_FAILURE_REASONS)
        quota = DEFAULT_QUOTA_HINTS.get((provider, model), {})
        return {
            "priority_order": _optional_nonnegative_int(item.get("priority_order")) if _optional_nonnegative_int(item.get("priority_order")) is not None else index,
            "provider_key": provider,
            "provider_model": model,
            "credential_id": credential_id,
            "enabled": item.get("enabled", True) is not False,
            "allowed_failure_reasons": allowed_reasons,
            "rpm_limit": _optional_positive_int(item.get("rpm_limit")) or quota.get("rpm_limit"),
            "tpm_limit": _optional_positive_int(item.get("tpm_limit")) or quota.get("tpm_limit"),
            "rpd_limit": _optional_positive_int(item.get("rpd_limit")) or quota.get("rpd_limit"),
            "cooldown_seconds": _optional_positive_int(item.get("cooldown_seconds")) or quota.get("cooldown_seconds"),
            "daily_reset": _clean_text(item.get("daily_reset")) or quota.get("daily_reset"),
            "manual_usage_snapshot": item.get("manual_usage_snapshot") if isinstance(item.get("manual_usage_snapshot"), dict) else None,
        }

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
        elif key in ("runtime_chunks", "runtime_chunk_attempts", "runtime_bundles", "runtime_outputs", "backup_manifest"):
            pass  # File-backed — no in-memory state to reload.
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
        elif key in ("runtime_chunks", "runtime_chunk_attempts", "runtime_bundles", "runtime_outputs", "backup_manifest"):
            path = self.runtime_state_path(key)
            if path.exists():
                path.unlink()
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
        if self.storage is None:
            return self._legacy_runtime_state_path(key)
        if key == "runtime_chunks":
            return self.storage.runtime_path("translation", "chunks.json")
        if key == "runtime_chunk_attempts":
            return self.storage.runtime_path("translation", "chunk_attempts.json")
        if key == "runtime_bundles":
            return self.storage.runtime_path("translation", "bundles.json")
        if key == "runtime_outputs":
            return self.storage.runtime_path("translation", "outputs.json")
        if key == "backup_manifest":
            return self.storage.backups_path("manifest.json")
        raise KeyError(f"Unknown runtime state file: {key}")

    def _legacy_runtime_state_path(self, key: str) -> Path:
        """Fallback when storage is not injected — resolves via settings.DATA_DIR."""
        if key == "runtime_chunks":
            return settings.DATA_DIR / "runtime" / "translation" / "chunks.json"
        if key == "runtime_chunk_attempts":
            return settings.DATA_DIR / "runtime" / "translation" / "chunk_attempts.json"
        if key == "runtime_bundles":
            return settings.DATA_DIR / "runtime" / "translation" / "bundles.json"
        if key == "runtime_outputs":
            return settings.DATA_DIR / "runtime" / "translation" / "outputs.json"
        if key == "backup_manifest":
            return settings.DATA_DIR / "backups" / "manifest.json"
        raise KeyError(f"Unknown runtime state file: {key}")

    def scheduler_health(self) -> dict[str, Any]:
        policy = self.get_provider_fallback_policy()
        configs = self.scheduler_policy_models(
            provider_key=str(policy.get("default_provider", "gemini")),
            model=str(policy.get("default_model", "")),
            allow_cross_provider_fallback=bool(policy.get("allow_cross_provider_fallback", False)),
        )
        health: list[dict[str, Any]] = []
        for item in configs:
            pk = str(item.get("provider_key") or "")
            pm = str(item.get("provider_model") or "")
            credential = self._credential_metadata(pk)
            configured = (
                credential.get("is_active") is not False
                and self.preferences.get_api_key(pk) is not None
            )
            health.append({
                "provider_key": pk,
                "provider_model": pm,
                "priority_order": item.get("priority_order", 0),
                "configured": configured,
                "credential_active": credential.get("is_active") if credential else None,
                "rpm_limit": item.get("rpm_limit"),
                "rpd_limit": item.get("rpd_limit"),
            })

        # Load persisted scheduler runtime state from most recent job
        runtime_state = self._load_latest_scheduler_state()
        if runtime_state:
            for model in health:
                key = (model["provider_key"], model["provider_model"])
                if key in runtime_state:
                    state = runtime_state[key]
                    model["status"] = state.get("status", "available")
                    model["requests_this_minute"] = state.get("requests_this_minute", 0)
                    model["requests_today"] = state.get("requests_today", 0)
                    model["cooldown_until"] = state.get("cooldown_until")
                    model["exhausted_until"] = state.get("exhausted_until")
                    model["failed_at"] = state.get("failed_at")
                    model["last_error_code"] = state.get("last_error_code")
                    model["last_error_message"] = state.get("last_error_message")

        default_provider = str(policy.get("default_provider", "gemini"))
        default_model = str(policy.get("default_model", ""))
        return {
            "policy": {
                "default_provider": default_provider,
                "default_model": default_model,
                "allow_cross_provider_fallback": bool(policy.get("allow_cross_provider_fallback", False)),
                "fallback_on_qa_failure": bool(policy.get("fallback_on_qa_failure", False)),
            },
            "models": health,
        }

    def _load_latest_scheduler_state(self) -> dict[tuple[str, str], dict[str, Any]] | None:
        """Load the most recent scheduler runtime state from storage."""
        if self.storage is None:
            return None
        try:
            all_states = self.storage.load_all_scheduler_states()
            if not all_states:
                return None
            # Find the most recently updated state
            latest = max(all_states.values(), key=lambda s: s.get("updated_at", ""))
            model_states = latest.get("model_states", [])
            result = {}
            for state in model_states:
                if isinstance(state, dict):
                    pk = state.get("provider_key")
                    pm = state.get("provider_model")
                    if pk and pm:
                        result[(pk, pm)] = state
            return result if result else None
        except Exception:
            return None

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

    def list_novel_exports(self, novel_id: str) -> dict[str, Any]:
        if self.storage is None:
            raise ValueError("storage is not configured")
        meta = self.storage.load_metadata(novel_id)
        if meta is None:
            raise KeyError("Novel not found")
        manifests = list_manifests(self.storage, novel_id)
        for m in manifests:
            m["freshness"] = compute_export_freshness(
                self.storage, novel_id, m,
                current_glossary_revision=meta.get("glossary_revision"),
                current_novel_updated_at=meta.get("updated_at"),
            )
        return {"novel_id": novel_id, "manifests": manifests}

    def latest_novel_export(self, novel_id: str, export_format: str) -> dict[str, Any]:
        if self.storage is None:
            raise ValueError("storage is not configured")
        meta = self.storage.load_metadata(novel_id)
        if meta is None:
            raise KeyError("Novel not found")
        latest = latest_export(self.storage, novel_id, export_format)
        if latest is None:
            raise KeyError("No export found for format")
        return latest
