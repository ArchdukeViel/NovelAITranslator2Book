# Tasks: Gemini Provider Only

## Task List

- [x] 1. Delete NVIDIA provider files
  - [x] 1.1 Delete `backend/src/novelai/providers/nvidia_provider.py` (REQ-1.1)
  - [x] 1.2 Delete `backend/tests/test_nvidia_provider.py` (REQ-7.1)

- [x] 2. Simplify provider registry
  - [x] 2.1 Rewrite `backend/src/novelai/providers/registry.py` to single-provider `get_provider()` returning `GeminiProvider` (REQ-2.1, REQ-2.2, REQ-2.3)
  - [x] 2.2 Add backward compatibility warnings for `nvidia` key and `NVIDIA_API_KEY` env var (REQ-8.1, REQ-8.2)

- [x] 3. Clean up `providers/__init__.py`
  - [x] 3.1 Remove `NVIDIAProvider` import (REQ-1.2)
  - [x] 3.2 Remove `NVIDIAProvider` from `__all__` (REQ-1.3)
  - [x] 3.3 Remove `available_models`, `available_providers`, `register_provider` imports

- [x] 4. Simplify model fallbacks
  - [x] 4.1 Remove NVIDIA branch from `model_candidates()` in `model_fallbacks.py` (REQ-3.1, REQ-3.2)
  - [x] 4.2 Remove unused `supported_models` parameter if no longer needed (REQ-3.3)

- [x] 5. Clean up settings
  - [x] 5.1 Remove `NVIDIA_DEFAULT_MODEL` and `NVIDIA_DEFAULT_BASE_URL` constants (REQ-4.1)
  - [x] 5.2 Remove `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_DEFAULT_MODEL`, `NVIDIA_TIMEOUT_SECONDS` fields (REQ-4.1)
  - [x] 5.3 Update `PROVIDER_DEFAULT` to `"gemini"` (REQ-4.2)

- [x] 6. Clean up `admin_service.py`
  - [x] 6.1 Update `API_KEY_PROVIDERS` to `{"gemini"}` (REQ-5.1)
  - [x] 6.2 Remove NVIDIA from `DEFAULT_PROVIDER_MODELS` (REQ-5.2)
  - [x] 6.3 Remove NVIDIA from `DEFAULT_PROVIDER_DISPLAY_NAMES` (REQ-5.3)
  - [x] 6.4 Remove NVIDIA quota hints (REQ-5.4)
  - [x] 6.5 Update provider validation error message (REQ-5.5)
  - [x] 6.6 Remove NVIDIA fallback provider defaults (REQ-5.6)

- [x] 7. Clean up other services
  - [x] 7.1 Update `_provider_requires_api_key` in `novel_orchestration_service.py` (REQ-6.1)
  - [x] 7.2 Remove NVIDIA model resolution and API key handling in `preferences_service.py` (REQ-6.2)
  - [x] 7.3 Update `_METADATA_TRANSLATION_PROMPT_SOURCES` and warning messages in `translation.py` (REQ-6.3)

- [x] 8. Remove NVIDIA test references
  - [x] 8.1 Update test fixtures that reference NVIDIA models or API keys (REQ-7.2)
  - [x] 8.2 Remove any NVIDIA parametrize cases from integration tests (REQ-7.2)

- [x] 9. Verify
  - [x] 9.1 Run `rg -i nvidia backend/src/novelai/` and confirm zero results (REQ acceptance criteria 8)
  - [x] 9.2 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 9.3 Run `ruff check backend/src/novelai/` and fix issues
  - [x] 9.4 Run `pyright` and fix type errors
