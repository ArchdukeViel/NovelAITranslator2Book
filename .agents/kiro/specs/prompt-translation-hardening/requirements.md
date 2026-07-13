# Requirements: Prompt and Translation Correctness Hardening

## Introduction

The translation pipeline produces adequate output for general web-novel content, but the current prompt layer is not sharp enough for premium Japanese web-novel translation. The system prompt and user prompt templates lack explicit honorific handling, anti-hallucination guardrails, glossary-lock enforcement, and a clear glossary-authority declaration. The glossary block renders all approved terms with the same advisory phrasing, making no distinction between owner-locked mandatory terms and lower-confidence suggestions. The two glossary channels (DB-backed injection service and runtime in-context list) can contradict each other with no conflict resolution. Style presets are only injected into the user prompt and have no footprint in the system prompt. Prompt-version and glossary-hash metadata exist but are not surfaced in a way that operators can use to audit what was injected for a given chapter.

This spec closes those gaps. It does not change the pipeline architecture, storage layout, or provider abstractions. All changes are confined to the prompt layer and the runtime metadata that records what the prompt contained.

## Requirements

### REQ-1: Honorific Policy in Prompt Templates

The system must support a configurable honorific policy that is encoded into the prompt at translation time.

- REQ-1.1: Three policy values must be supported: `retain` (keep Japanese honorific suffix or equivalent in the output), `translate` (render as a culturally appropriate English equivalent), and `omit` (drop honorifics silently).
- REQ-1.2: The honorific policy must be passed to `build_translation_request` and `build_json_translation_request` as an optional parameter. When not supplied, the system must default to `omit`.
- REQ-1.3: The honorific policy block must be included in `{additional_instructions}` in the user prompt when a value other than `None` is provided.
- REQ-1.4: The system prompt must include a general honorific/title awareness statement that references the project-level policy without hardcoding a specific value.
- REQ-1.5: The pipeline stage (`TranslateStage`) must read `context.metadata["honorific_policy"]` and pass it through to the builder.
- REQ-1.6: Adding a new policy value in the future must require only a change to the policy map and templates, not to multiple pipeline files.

### REQ-2: Anti-Hallucination and Faithfulness Rules

The system prompt must explicitly instruct the model against inventing content absent from the source.

- REQ-2.1: The system prompt must include a rule stating that the model must not invent names, subjects, motives, scene details, or any narrative content absent from the source text.
- REQ-2.2: The system prompt must include a rule for subject-omission handling: when Japanese omits a subject and English requires one, the model must resolve from immediate context only; if resolution is ambiguous, choose the least committal natural phrasing rather than inventing an actor.
- REQ-2.3: The system prompt must include a rule stating that if a source term is untranslatable or unknown, the model must preserve the original source-language spelling verbatim rather than guessing or inventing an equivalent.
- REQ-2.4: These rules must appear in both the plain-text system prompt (`MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE`) and the JSON system prompt (`JSON_SYSTEM_PROMPT_TEMPLATE`).
- REQ-2.5: The existing "Do not omit, summarize, censor, soften, or add information" rule must be preserved and strengthened rather than replaced.

### REQ-3: Glossary Lock Semantics

Owner-locked glossary terms must produce a stronger imperative instruction in the rendered glossary block than advisory terms.

- REQ-3.1: The `GlossaryPromptInjectionService._render_block` method must produce a rendered text that separates `owner_locked=True` terms into a distinct sub-section with imperative language (e.g. "LOCKED — always use these translations exactly, do not deviate").
- REQ-3.2: Unlocked approved terms must remain in an advisory sub-section with language such as "Use these approved translations consistently".
- REQ-3.3: If no locked terms exist, the locked sub-section must be omitted entirely (no empty section headers).
- REQ-3.4: If no unlocked terms exist, the advisory sub-section must be omitted entirely.
- REQ-3.5: The block header must include a statement that the glossary is authoritative and supersedes the model's general knowledge when a source term appears in the list.
- REQ-3.6: The `PromptGlossaryBlock` dataclass must expose a `locked_term_count` integer field so callers can distinguish blocks that contain mandatory terms from purely advisory ones.

### REQ-4: Glossary Authority Declaration

The prompt must declare that the project glossary takes precedence over the model's general knowledge.

- REQ-4.1: The user prompt template must include a static instruction stating that when a source term appears in the glossary, the glossary translation is authoritative and must be used regardless of the model's training-time knowledge of that term.
- REQ-4.2: This instruction must appear in both the plain-text user prompt templates and the JSON user prompt template.
- REQ-4.3: The instruction must be positioned before the glossary block in the assembled `{additional_instructions}` string so the model sees the authority declaration before the term list.

### REQ-5: Runtime vs DB Glossary Conflict Resolution

When the DB-backed glossary block and the runtime in-context glossary list contain translations for the same source term, the conflict must be detected and resolved before the prompt is assembled.

- REQ-5.1: `_format_additional_instructions` in `builders.py` must detect when a term present in `prompt_glossary_block` (DB channel) also appears in `glossary_entries` (runtime channel) with a different translation.
- REQ-5.2: On conflict, the DB-backed (`prompt_glossary_block`) translation must win. The conflicting runtime entry must be suppressed from the output.
- REQ-5.3: When a conflict is suppressed, a warning string `"runtime_glossary_conflict_suppressed"` must be added to the `TranslationRequest` metadata or returned alongside the assembled string so the caller can log it.
- REQ-5.4: This deduplication must not alter the order of non-conflicting terms in either channel.

### REQ-6: Style Preset in System Prompt

Style preset genre guidance must be optionally reflected in the system prompt, not only in the user prompt.

- REQ-6.1: A new optional template section `STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES` must be added to `templates.py` containing a short system-level note for each existing style preset (`fantasy`, `romance`, `action`, `comedy`).
- REQ-6.2: `build_system_prompt` and `build_json_system_prompt` must accept an optional `style_preset` parameter and, when supplied, append the corresponding system suffix to the system prompt.
- REQ-6.3: `build_translation_request` and `build_json_translation_request` must pass `style_preset` to both the system prompt builder and the user prompt builder.
- REQ-6.4: Adding a new style preset must require only changes to `templates.py` dictionaries, not to builder or pipeline files.

### REQ-7: Prompt Version and Glossary Hash Audit Metadata

Every translated chapter artifact must record the prompt template version and the glossary hash that was active during translation.

- REQ-7.1: A `PROMPT_TEMPLATE_VERSION` constant must be defined in `templates.py`. It must be incremented (as a string, e.g. `"v2"`) whenever any template string that affects translation output is changed.
- REQ-7.2: `TranslationRequest` must carry a `prompt_template_version` field populated from `PROMPT_TEMPLATE_VERSION`.
- REQ-7.3: `TranslateStage` must write `prompt_template_version` and `glossary_hash` into `context.metadata` per-chunk so they are available to the storage layer when the translated chapter bundle is saved.
- REQ-7.4: `save_translated_chapter` must persist `prompt_template_version` and `glossary_hash` into the translated chapter JSON artifact.
- REQ-7.5: Cache key construction must include `prompt_template_version` so that a version bump automatically invalidates stale cached translations.
- REQ-7.6: The admin chapter detail API response must expose `prompt_template_version` and `glossary_hash` from the translated chapter artifact.

### REQ-8: Workflow Profile Style and Consistency Config

Style preset and consistency mode must be promotable to first-class workflow profile fields.

- REQ-8.1: `WORKFLOW_PROFILE_STEPS` must remain unchanged. Style and consistency config must live under a separate `workflow_defaults` section, not as pipeline steps.
- REQ-8.2: A `workflow_defaults` structure must be added to `workflow_profiles.py` with fields: `style_preset` (string or null), `consistency_mode` (boolean), `honorific_policy` (string or null).
- REQ-8.3: `normalize_workflow_profiles` must accept and validate a `workflow_defaults` key alongside the existing step profiles.
- REQ-8.4: The translate orchestration path must read `workflow_defaults` from the novel's stored profile and use those values as fallbacks when the translation request does not explicitly supply them.
- REQ-8.5: Explicit per-request values must always override profile defaults.

### REQ-9: Template Snapshot and Regression Tests

Changes to prompt templates must be covered by snapshot and regression tests to prevent silent drift.

- REQ-9.1: A new test file `tests/test_prompt_templates.py` must contain snapshot tests that assert the exact rendered output for each template given a fixed set of inputs.
- REQ-9.2: Snapshot tests must cover: plain-text system prompt with and without style preset, JSON system prompt with and without style preset, plain-text user prompt with and without glossary block with and without honorific policy, JSON user prompt equivalents, consistency block inclusion/exclusion, locked vs. unlocked glossary block rendering.
- REQ-9.3: Cache key invalidation tests must assert that changing `prompt_template_version`, `glossary_hash`, `style_preset`, `consistency_mode`, or `honorific_policy` produces a different cache key.
- REQ-9.4: Glossary conflict suppression tests must assert REQ-5 behavior with at least three cases: no conflict, one conflict (DB wins), multiple conflicts (all suppressed).
- REQ-9.5: Honorific policy tests must cover all three policy values and the default (`None`/omit) case.

## Non-Goals

- This spec does not change the provider abstraction, network layer, or any storage schemas beyond the translated chapter artifact fields listed in REQ-7.4.
- This spec does not introduce a new QA stage or modify `TranslationQAStage`.
- This spec does not change how glossary entries are extracted, reviewed, or approved — only how they are rendered into prompts.
- This spec does not add cross-chapter continuity memory (chapter-to-chapter context window injection). That is a separate future feature.
- This spec does not change the public reader API response shape.
