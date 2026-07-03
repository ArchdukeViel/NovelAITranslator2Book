# Requirements: Gemini Provider Only

## Introduction

The codebase previously supported two translation providers. With the architectural decision to standardize on Gemini-only, the third-party provider and all associated multi-provider abstractions were removed.

This spec removes the NVIDIA provider entirely, simplifies the provider layer to treat Gemini as the sole provider, cleans up all NVIDIA references from services and settings, and removes the associated test file.

## Requirements

### REQ-1: Delete NVIDIA Provider Implementation

The NVIDIA provider module must be removed.

- REQ-1.1: Delete `backend/src/novelai/providers/nvidia_provider.py`.
- REQ-1.2: Remove `from novelai.providers.nvidia_provider import NVIDIAProvider` from `backend/src/novelai/providers/__init__.py`.
- REQ-1.3: Remove `NVIDIAProvider` from `__all__` in `backend/src/novelai/providers/__init__.py`.

### REQ-2: Simplify Provider Registry

The provider registry must be simplified for single-provider usage.

- REQ-2.1: Remove `register_provider()`, `available_providers()`, and `available_models()` from `backend/src/novelai/providers/registry.py`. Replace with a simple `get_provider()` that always returns a `GeminiProvider` instance.
- REQ-2.2: The `_PROVIDER_REGISTRY` dictionary and `settings.PROVIDER_DEFAULT` usage must be removed.
- REQ-2.3: `get_provider()` must accept no arguments (or ignore the `key` argument for backward compatibility) and always return `GeminiProvider()`.

### REQ-3: Simplify Model Fallbacks

The model fallback module must be simplified.

- REQ-3.1: Remove the NVIDIA branch from `model_candidates()` in `backend/src/novelai/providers/model_fallbacks.py`.
- REQ-3.2: The `provider_key` parameter must no longer accept `"nvidia"`. Only `"gemini"` or generic handling is needed.
- REQ-3.3: Remove the `supported_models` parameter if it was only used by NVIDIA.

### REQ-4: Clean Up Settings

All NVIDIA configuration must be removed from settings.

- REQ-4.1: Remove from `backend/src/novelai/config/settings.py`:
  - `NVIDIA_DEFAULT_MODEL` constant (line 10)
  - `NVIDIA_DEFAULT_BASE_URL` constant (line 11)
  - `NVIDIA_API_KEY` field (line 64-68)
  - `NVIDIA_BASE_URL` field (line 68)
  - `NVIDIA_DEFAULT_MODEL` field (line 69)
  - `NVIDIA_TIMEOUT_SECONDS` field (line 70)
- REQ-4.2: Remove or update `PROVIDER_DEFAULT` (line 61) from `"dummy"` to `"gemini"` since there is no multi-provider selection.
- REQ-4.3: Remove unused `PROVIDER_GEMINI_MODEL_FALLBACKS` if only one model is in use.

### REQ-5: Clean Up Admin Service

All NVIDIA references in `admin_service.py` must be removed.

- REQ-5.1: Update `API_KEY_PROVIDERS` (line 18) from `{"gemini", "nvidia"}` to `{"gemini"}`.
- REQ-5.2: Remove NVIDIA entries from `DEFAULT_PROVIDER_MODELS` (line 21).
- REQ-5.3: Remove NVIDIA entries from `DEFAULT_PROVIDER_DISPLAY_NAMES` (line 25).
- REQ-5.4: Remove NVIDIA quota hints (lines 42-...).
- REQ-5.5: Update provider validation (line 284) from `"gemini, nvidia"` to `"gemini"`.
- REQ-5.6: Remove the NVIDIA fallback provider entry in the defaults section (lines 836-843).

### REQ-6: Clean Up Other Services

All other NVIDIA references must be removed.

- REQ-6.1: In `services/novel_orchestration_service.py`, update `_provider_requires_api_key` (line 166) from `{"gemini", "nvidia"}` to `{"gemini"}`.
- REQ-6.2: In `services/preferences_service.py`, remove NVIDIA-specific model resolution (lines 456-457), API key get/set (lines 482-483, 498-499, 508-509).
- REQ-6.3: In `services/orchestration/translation.py`, update `_METADATA_TRANSLATION_PROMPT_SOURCES` (line 38) from `{"gemini", "nvidia"}` to `{"gemini"}`. Update the two warning messages (lines 722, 850) from `"Gemini/NVIDIA"` to `"Gemini"`.

### REQ-7: Remove NVIDIA Tests

- REQ-7.1: Delete `backend/tests/test_nvidia_provider.py`.
- REQ-7.2: Remove any NVIDIA-specific test fixtures or parametrize cases in other test files.

### REQ-8: Backward Compatibility

- REQ-8.1: If any environment variable of the form `NVIDIA_API_KEY` exists, log a `WARNING` at startup: `"NVIDIA_API_KEY is set but NVIDIA provider has been removed. Use GEMINI_API_KEY instead."`.
- REQ-8.2: The Gemini provider must be the fallback for any code that previously selected a provider by key. If `provider_key="nvidia"` is passed anywhere, log a `WARNING` and fall back to Gemini.

## Non-Goals

- This spec does not change the Gemini provider implementation itself.
- This spec does not change the translation pipeline stages.
- This spec does not add or change any Gemini API features.
- This spec does not remove the `DummyProvider` (it is kept for testing).
- This spec does not change the frontend.
