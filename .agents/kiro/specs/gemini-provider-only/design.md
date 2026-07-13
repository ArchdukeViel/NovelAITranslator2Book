# Design: Gemini Provider Only

## Overview

Remove the third-party provider and all multi-provider abstractions. Simplify the provider registry to a single `get_provider()` that returns `GeminiProvider`. Clean up files that reference the removed provider.

## Architecture

### Affected Files

| File | Change type | Action |
|---|---|---|
| `backend/src/novelai/providers/nvidia_provider.py` | Delete | Remove entire file |
| `backend/src/novelai/providers/__init__.py` | Modify | Remove removed-provider import and `__all__` entry |
| `backend/src/novelai/providers/registry.py` | Simplify | Replace multi-provider registry with `get_provider()` returning `GeminiProvider` |
| `backend/src/novelai/providers/model_fallbacks.py` | Simplify | Remove removed-provider branch, keep Gemini-only logic |
| `backend/src/novelai/config/settings.py` | Modify | Remove all removed-provider fields and constants |
| `backend/src/novelai/services/admin_service.py` | Modify | Remove removed-provider from provider lists, models, validation |
| `backend/src/novelai/services/preferences_service.py` | Modify | Remove removed-provider model resolution and API key handling |
| `backend/src/novelai/services/novel_orchestration_service.py` | Modify | Simplify `_provider_requires_api_key` |
| `backend/src/novelai/services/orchestration/translation.py` | Modify | Simplify metadata translation sources and messages |
| `backend/tests/test_nvidia_provider.py` | Delete | Remove entire file |

### Files Not Touched

- `providers/gemini_provider.py` — no change
- `providers/dummy_provider.py` — no change (kept for testing)
- `providers/base.py` — no change (interface remains)
- All pipeline stages — no change
- Storage layer — no change
- API routers — no change

## Component Design

### 1. `registry.py` — Before vs After

**Before:**
```python
_PROVIDER_REGISTRY: dict[str, Callable[[], TranslationProvider]] = {}

def register_provider(key, factory): ...
def get_provider(key=None): ...  # looks up registry, falls back to settings.PROVIDER_DEFAULT
def available_providers(): ...
def available_models(key): ...
```

**After:**
```python
from novelai.providers.gemini_provider import GeminiProvider

_provider: GeminiProvider | None = None

def get_provider(key: str | None = None) -> GeminiProvider:
    global _provider
    if _provider is None:
        _provider = GeminiProvider()
    return _provider
```

### 2. `__init__.py` — Simplified

Removed the removed-provider import and `__all__` entry. Simplified to Gemini-only exports.

### 3. `model_fallbacks.py` — Simplified

Removed the removed-provider branch. Now always picks Gemini default model and fallbacks.

### 4. `settings.py` — Fields Removed

Removed all removed-provider-specific fields (API key, base URL, default model, timeout).
`PROVIDER_DEFAULT` changed from `"dummy"` to `"gemini"`.

### 5. `admin_service.py` — Simplified

`API_KEY_PROVIDERS` restricted to `{"gemini"}`. Removed removed-provider display names and model defaults.

### 6. `orchestration/translation.py` — Simplified

`_METADATA_TRANSLATION_PROMPT_SOURCES` restricted to `{"gemini"}`. Error messages updated to not reference the removed provider.

### 7. Backward Compatibility Warning

`get_provider()` logs a warning if a non-Gemini key is requested.

### 8. `preferences_service.py` — Lines to Remove

```python
# REMOVE (removed-provider branch):
if provider_key == "other" and model.startswith("gpt-"):
    return settings.OTHER_DEFAULT_MODEL

# REMOVE (simplify):
if provider_key not in {"gemini", "other"}:  # becomes "gemini"

# REMOVE (removed-provider API key handling):
elif provider_key == "other":
    api_key = settings.OTHER_API_KEY

# REMOVE:
if provider_key == "other":
    settings.OTHER_API_KEY = SecretStr(api_key)

# REMOVE:
if provider_key == "other":
    settings.OTHER_API_KEY = None
```

## Migration and Backward Compatibility

- `DummyProvider` is kept for testing. Development mode can still use the dummy.
- Any code passing a removed-provider key receives a WARNING log and falls back to Gemini.
- Environment variable for the removed provider triggers a WARNING at startup but does not crash.
- The `GeminiProvider` implementation is not changed; it continues to work identically.
- Existing Gemini-specific tests continue to pass.

## Acceptance Criteria

1. The removed provider module is deleted.
2. The removed provider tests are deleted.
3. `backend/src/novelai/config/settings.py` has zero removed-provider fields or constants.
4. `get_provider()` in `registry.py` always returns a `GeminiProvider` instance.
5. `admin_service.py` has `API_KEY_PROVIDERS = {"gemini"}`.
6. All existing tests pass.
7. Setting a removed-provider API key in the environment logs a WARNING at startup.
8. No file in `backend/src/novelai/` contains the removed provider name.
