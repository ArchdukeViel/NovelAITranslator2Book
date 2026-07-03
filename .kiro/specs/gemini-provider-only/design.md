# Design: Gemini Provider Only

## Overview

Remove the NVIDIA provider and all multi-provider abstractions. Simplify the provider registry to a single `get_provider()` that returns `GeminiProvider`. Clean up 8 files that reference NVIDIA.

## Architecture

### Affected Files

| File | Change type | Action |
|---|---|---|
| `backend/src/novelai/providers/nvidia_provider.py` | Delete | Remove entire file |
| `backend/src/novelai/providers/__init__.py` | Modify | Remove NVIDIA import and `__all__` entry |
| `backend/src/novelai/providers/registry.py` | Simplify | Replace multi-provider registry with `get_provider()` returning `GeminiProvider` |
| `backend/src/novelai/providers/model_fallbacks.py` | Simplify | Remove NVIDIA branch, keep Gemini-only logic |
| `backend/src/novelai/config/settings.py` | Modify | Remove all NVIDIA_* fields and constants |
| `backend/src/novelai/services/admin_service.py` | Modify | Remove NVIDIA from provider lists, models, validation |
| `backend/src/novelai/services/preferences_service.py` | Modify | Remove NVIDIA model resolution and API key handling |
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

### 2. `__init__.py` — Before vs After

**Before:**
```python
from novelai.providers.gemini_provider import GeminiProvider
from novelai.providers.nvidia_provider import NVIDIAProvider
from novelai.providers.registry import (
    available_models, available_providers, get_provider, register_provider,
)
__all__ = [..., "GeminiProvider", "NVIDIAProvider", "available_models", "available_providers", ...]
```

**After:**
```python
from novelai.providers.gemini_provider import GeminiProvider
from novelai.providers.registry import get_provider

__all__ = [
    "ProviderFactory",
    "TranslationProvider",
    "GeminiProvider",
    "get_provider",
]
```

### 3. `model_fallbacks.py` — Before vs After

**Before:**
```python
if provider_key == "gemini":
    _add_unique(candidates, settings.PROVIDER_GEMINI_DEFAULT_MODEL)
    for model in settings.PROVIDER_GEMINI_MODEL_FALLBACKS:
        _add_unique(candidates, model)
elif provider_key == "nvidia":
    _add_unique(candidates, settings.NVIDIA_DEFAULT_MODEL)
    for model in supported:
        _add_unique(candidates, model)
```

**After:**
```python
_add_unique(candidates, settings.PROVIDER_GEMINI_DEFAULT_MODEL)
for model in settings.PROVIDER_GEMINI_MODEL_FALLBACKS:
    _add_unique(candidates, model)
```

### 4. `settings.py` — Fields to Remove

```python
# REMOVE:
NVIDIA_DEFAULT_MODEL = "google/gemma-4-31b-it"
NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_API_KEY: SecretStr | None = ...
NVIDIA_BASE_URL: str = NVIDIA_DEFAULT_BASE_URL
NVIDIA_DEFAULT_MODEL: str = NVIDIA_DEFAULT_MODEL
NVIDIA_TIMEOUT_SECONDS: float = 60.0

# UPDATE:
PROVIDER_DEFAULT: str = "gemini"  # was "dummy"
```

### 5. `admin_service.py` — Before vs After

**Before:**
```python
API_KEY_PROVIDERS = {"gemini", "nvidia"}
DEFAULT_PROVIDER_MODELS = {
    "nvidia": "google/gemma-4-31b-it",
}
DEFAULT_PROVIDER_DISPLAY_NAMES = {
    "nvidia": "NVIDIA",
}
...
raise ValueError("Provider must be one of: gemini, nvidia")
```

**After:**
```python
API_KEY_PROVIDERS = {"gemini"}
DEFAULT_PROVIDER_MODELS = {}
DEFAULT_PROVIDER_DISPLAY_NAMES = {}
...
raise ValueError("Provider must be: gemini")
```

### 6. `orchestration/translation.py` — Before vs After

**Before:**
```python
_METADATA_TRANSLATION_PROMPT_SOURCES = {"gemini", "nvidia"}
...
"Metadata translation skipped because no active Gemini/NVIDIA provider is configured."
```

**After:**
```python
_METADATA_TRANSLATION_PROMPT_SOURCES = {"gemini"}
...
"Metadata translation skipped because no active Gemini provider is configured."
```

### 7. Backward Compatibility Warning at Startup

In `providers/registry.py` `get_provider()`:

```python
import os
import logging

logger = logging.getLogger(__name__)

def get_provider(key: str | None = None) -> GeminiProvider:
    global _provider
    if key and key != "gemini":
        logger.warning(
            "Provider key '%s' requested but only Gemini is available. Falling back to Gemini.", key
        )
    if os.environ.get("NVIDIA_API_KEY"):
        logger.warning(
            "NVIDIA_API_KEY is set but NVIDIA provider has been removed. Use GEMINI_API_KEY instead."
        )
    if _provider is None:
        _provider = GeminiProvider()
    return _provider
```

### 8. `preferences_service.py` — Lines to Remove

```python
# REMOVE (line 456-457):
if provider_key == "nvidia" and model.startswith("gpt-"):
    return settings.NVIDIA_DEFAULT_MODEL

# REMOVE (line 458, simplify):
if provider_key not in {"gemini", "nvidia"}:  # becomes "gemini"

# REMOVE (lines 482-483):
elif provider_key == "nvidia":
    api_key = settings.NVIDIA_API_KEY

# REMOVE (lines 498-499):
if provider_key == "nvidia":
    settings.NVIDIA_API_KEY = SecretStr(api_key)

# REMOVE (lines 508-509):
if provider_key == "nvidia":
    settings.NVIDIA_API_KEY = None
```

## Migration and Backward Compatibility

- `DummyProvider` is kept for testing. Development mode can still use the dummy.
- Any code passing `provider_key="nvidia"` receives a WARNING log and falls back to Gemini.
- Environment variable `NVIDIA_API_KEY` triggers a WARNING at startup but does not crash.
- The `GeminiProvider` implementation is not changed; it continues to work identically.
- Existing Gemini-specific tests continue to pass.

## Acceptance Criteria

1. `backend/src/novelai/providers/nvidia_provider.py` is deleted.
2. `backend/tests/test_nvidia_provider.py` is deleted.
3. `backend/src/novelai/config/settings.py` has zero `NVIDIA_*` fields or constants.
4. `get_provider()` in `registry.py` always returns a `GeminiProvider` instance.
5. `admin_service.py` has `API_KEY_PROVIDERS = {"gemini"}`.
6. All existing tests pass (`pytest backend/tests/ --tb=short -q -m "not nvidia"`).
7. Setting `NVIDIA_API_KEY` in the environment logs a WARNING at startup.
8. No file in `backend/src/novelai/` contains the string `"nvidia"` (case-insensitive).
