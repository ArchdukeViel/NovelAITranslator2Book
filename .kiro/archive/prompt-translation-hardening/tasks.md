# Tasks: Prompt and Translation Correctness Hardening

## Task List

- [x] 1. Add `PROMPT_TEMPLATE_VERSION` constant and template content changes
  - [x] 1.1 Add `PROMPT_TEMPLATE_VERSION = "v2"` constant to `backend/src/novelai/prompts/templates.py`
  - [x] 1.2 Add anti-hallucination and subject-omission rules to `MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE` (REQ-2.1, REQ-2.2, REQ-2.3)
  - [x] 1.3 Add glossary-authority rule to `MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE` (REQ-4.1)
  - [x] 1.4 Add honorific/title awareness statement to `MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE` (REQ-1.4)
  - [x] 1.5 Apply equivalent additions to `JSON_SYSTEM_PROMPT_TEMPLATE` (REQ-2.4)
  - [x] 1.6 Add `HONORIFIC_POLICY_BLOCKS` dict for `retain`, `translate`, `omit` values (REQ-1.1)
  - [x] 1.7 Add `STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES` dict for existing four presets (REQ-6.1)
  - [x] 1.8 Add glossary-authority instruction line to `DEFAULT_USER_PROMPT_TEMPLATE`, `STRONG_CONSISTENCY_USER_PROMPT_TEMPLATE`, and `JSON_USER_PROMPT_TEMPLATE` (REQ-4.1, REQ-4.2)

- [x] 2. Update `TranslationRequest` model with new fields
  - [x] 2.1 Add `honorific_policy: str | None = None` to `TranslationRequest` in `backend/src/novelai/prompts/models.py` (REQ-1.2)
  - [x] 2.2 Add `prompt_template_version: str = ""` to `TranslationRequest` (REQ-7.2)
  - [x] 2.3 Add `runtime_glossary_conflict_warnings: tuple[str, ...] = ()` to `TranslationRequest` (REQ-5.3)

- [x] 3. Update builders with honorific policy, style system suffix, and conflict resolution
  - [x] 3.1 Add `style_preset` parameter to `build_system_prompt` and `build_json_system_prompt`; append `STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES` entry when supplied (REQ-6.2)
  - [x] 3.2 Add `honorific_policy` parameter to `_format_additional_instructions`; append `HONORIFIC_POLICY_BLOCKS` entry when supplied (REQ-1.3)
  - [x] 3.3 Implement runtime vs. DB glossary conflict detection and suppression in `_format_additional_instructions`; change return type to `tuple[str, list[str]]` (REQ-5.1, REQ-5.2, REQ-5.3)
  - [x] 3.4 Update all callers of `_format_additional_instructions` in `builders.py` to unpack the new tuple return (REQ-5.3)
  - [x] 3.5 Add `honorific_policy` parameter to `build_user_prompt`, `build_json_user_prompt`, `build_translation_request`, `build_json_translation_request` (REQ-1.2)
  - [x] 3.6 Pass `style_preset` to system prompt builders from `build_translation_request` and `build_json_translation_request` (REQ-6.3)
  - [x] 3.7 Populate `TranslationRequest.prompt_template_version` from `PROMPT_TEMPLATE_VERSION` in `build_translation_request` (REQ-7.2)
  - [x] 3.8 Populate `TranslationRequest.honorific_policy` and `TranslationRequest.runtime_glossary_conflict_warnings` in `build_translation_request` (REQ-1.2, REQ-5.3)

- [x] 4. Update `GlossaryPromptInjectionService` for locked vs. advisory sub-sections
  - [x] 4.1 Add `locked_term_count: int = 0` field to `PromptGlossaryBlock` dataclass (REQ-3.6)
  - [x] 4.2 Rewrite `_render_text` to produce a "LOCKED" sub-section for `owner_locked=True` terms and an "APPROVED" sub-section for the rest (REQ-3.1, REQ-3.2)
  - [x] 4.3 Omit sub-section headers when that sub-section has no terms (REQ-3.3, REQ-3.4)
  - [x] 4.4 Add glossary-authority statement to the block header (REQ-3.5)
  - [x] 4.5 Set `locked_term_count` on the returned `PromptGlossaryBlock` (REQ-3.6)

- [x] 5. Update `TranslateStage` to thread honorific policy and write audit metadata
  - [x] 5.1 Read `context.metadata["honorific_policy"]` in `_build_prompt_request` and pass to `build_translation_request` (REQ-1.5)
  - [x] 5.2 Import `PROMPT_TEMPLATE_VERSION` from `templates` in `translate.py`
  - [x] 5.3 Write `prompt_template_version` to `context.metadata` in `worker()` after building the request (REQ-7.3)
  - [x] 5.4 Include `prompt_template_version` in `_record_prompt_glossary_metadata` per-chunk record (REQ-7.3)

- [x] 6. Persist prompt version and glossary hash to translated chapter artifact
  - [x] 6.1 Update `save_translated_chapter` in `backend/src/novelai/storage/translations.py` to write `prompt_template_version` and `glossary_hash` fields into the artifact JSON (REQ-7.4)
  - [x] 6.2 Ensure these fields default to empty string when not provided (backward-compatible write)

- [x] 7. Include `prompt_template_version` in cache key
  - [x] 7.1 Locate cache key construction in `TranslationCache` or equivalent
  - [x] 7.2 Add `prompt_template_version` as a required cache key component (REQ-7.5)
  - [x] 7.3 Add `honorific_policy` as a cache key component

- [x] 8. Add `workflow_defaults` to `workflow_profiles.py`
  - [x] 8.1 Add `default_workflow_defaults()` function returning `{style_preset: None, consistency_mode: False, honorific_policy: None}` (REQ-8.2)
  - [x] 8.2 Add `normalize_workflow_defaults()` function with validation against `STYLE_PRESET_TEMPLATES` and `HONORIFIC_POLICY_BLOCKS` (REQ-8.3)
  - [x] 8.3 Update `normalize_workflow_profiles` to return `{"steps": ..., "defaults": ...}` structure (REQ-8.3)
  - [x] 8.4 Update translate orchestration to read `workflow_defaults` and apply as `context.metadata` fallbacks (REQ-8.4, REQ-8.5)

- [x] 9. Expose prompt version and glossary hash in admin chapter detail API
  - [x] 9.1 Read `prompt_template_version` and `glossary_hash` from translated chapter artifact in admin library route (REQ-7.6)
  - [x] 9.2 Include them in the admin chapter detail response; return `null` when absent (legacy artifacts) (REQ-7.6)

- [x] 10. Write snapshot and regression tests
  - [x] 10.1 Create `backend/tests/test_prompt_templates.py` with snapshot tests for all template/builder combinations (REQ-9.1, REQ-9.2)
  - [x] 10.2 Add conflict suppression tests: no conflict, single conflict DB wins, multiple conflicts all suppressed (REQ-9.4)
  - [x] 10.3 Add honorific policy tests for all three values and `None` default (REQ-9.5)
  - [x] 10.4 Add locked vs. advisory glossary rendering tests including `locked_term_count` assertion (REQ-9.2)
  - [x] 10.5 Add cache key invalidation tests for `prompt_template_version`, `honorific_policy`, and existing fields (REQ-9.3)
  - [x] 10.6 Run `pytest backend/tests/test_prompt_templates.py --tb=short -q` and confirm all pass
  - [x] 10.7 Run `ruff check backend/src/novelai/prompts/ backend/src/novelai/services/glossary_prompt_injection.py backend/src/novelai/translation/pipeline/stages/translate.py` and fix any issues
  - [x] 10.8 Run `pyright backend/src/novelai/prompts/ backend/src/novelai/services/glossary_prompt_injection.py` and fix any type errors
