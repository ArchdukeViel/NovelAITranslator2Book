# Requirements: JP-EN Prompt Quality Policy

## Introduction

The translation pipeline already has a capable prompt architecture: it supports style presets, consistency modes, honorific policy, context overlap, glossary entries, and JSON output mode. The deep research reports identify a quality gap specific to Japanese-to-English web novel translation: the current prompt contract is not explicit enough about ambiguous pronouns, dialogue/register, names and honorifics, chapter title handling, notes/footnotes, glossary conflict behavior, and uncertainty reporting.

This spec improves Japanese-to-English prompt policy without replacing the translation pipeline. The goal is to make generated translations more consistent, readable, glossary-compliant, and reviewable through prompt-builder changes and tests.

## Requirements

### REQ-1: Add JP-EN Translation Quality Policy

The prompt builder must include a dedicated Japanese-to-English web novel quality policy.

- REQ-1.1: Add a reusable JP-EN policy block to the prompt builder.
- REQ-1.2: The policy must prioritize meaning preservation, glossary compliance, tone/register preservation, and natural English readability.
- REQ-1.3: The policy must be applied only when source language is Japanese and target language is English, unless explicitly configured otherwise.
- REQ-1.4: Existing non-JP-EN translation prompts must not change unexpectedly.
- REQ-1.5: Existing style presets must remain compatible.

### REQ-2: Names, Terms, and Glossary Compliance

The prompt must strengthen terminology consistency.

- REQ-2.1: Prompt instructions must require approved glossary terms for names, places, organizations, skills, titles, factions, and recurring technical terms.
- REQ-2.2: Prompt instructions must tell the model not to invent alternate translations for approved glossary terms.
- REQ-2.3: Prompt instructions must define behavior when glossary terms conflict with local context.
- REQ-2.4: In JSON mode, the model must report glossary conflicts in a structured field when supported.
- REQ-2.5: The prompt must preserve untranslated proper nouns according to glossary or existing name policy.
- REQ-2.6: The prompt must avoid over-localizing names and culturally specific terms unless the glossary or style preset requires it.

### REQ-3: Honorific and Address Policy

The prompt must make honorific handling explicit.

- REQ-3.1: The prompt must include the configured honorific policy.
- REQ-3.2: If honorifics are preserved, the prompt must instruct consistent romanized honorific usage.
- REQ-3.3: If honorifics are localized, the prompt must instruct meaning-preserving English equivalents where natural.
- REQ-3.4: If honorifics are omitted, the prompt must preserve relationship nuance through tone and wording where possible.
- REQ-3.5: The prompt must avoid mixing honorific policies within the same chapter unless source context requires it.

### REQ-4: Dialogue, Register, and Voice

The prompt must improve character voice and dialogue consistency.

- REQ-4.1: The prompt must preserve speaker boundaries and dialogue paragraphing.
- REQ-4.2: The prompt must preserve character register, politeness level, roughness, age/role cues, and narrator voice.
- REQ-4.3: The prompt must translate dialogue into natural English without flattening distinct voices.
- REQ-4.4: The prompt must preserve emotional beats such as hesitation, interruption, ellipsis, and emphasis without excessive literalism.
- REQ-4.5: The prompt must avoid adding speaker tags or explanations not present in the source.

### REQ-5: Ambiguous Pronouns and Implied Subjects

The prompt must handle Japanese ambiguity conservatively.

- REQ-5.1: The prompt must instruct the model to use context to resolve omitted subjects and ambiguous pronouns.
- REQ-5.2: If referent remains uncertain, the prompt must instruct neutral wording rather than invented certainty.
- REQ-5.3: In JSON mode, uncertainty must be reported in a structured `uncertainties` field when supported.
- REQ-5.4: The prompt must discourage inventing gender, identity, relationship, or intent not supported by local or carried context.
- REQ-5.5: The prompt must preserve deliberate ambiguity when the source text is intentionally ambiguous.

### REQ-6: Chapter Titles, Notes, and Formatting

The prompt must handle web novel structure explicitly.

- REQ-6.1: The prompt must keep chapter title translation separate from body translation when title input is available separately.
- REQ-6.2: The prompt must preserve paragraph order and scene order.
- REQ-6.3: The prompt must not merge or split paragraphs unless required for intelligible English and allowed by existing formatting policy.
- REQ-6.4: The prompt must preserve author notes, translator notes, footnotes, or endnotes as notes when present in source blocks.
- REQ-6.5: The prompt must preserve emphasis markers and special formatting when semantically meaningful.
- REQ-6.6: The prompt must not introduce markdown or HTML formatting unless the output mode requires it.

### REQ-7: JSON Output Schema Enhancements

When JSON output mode is used, prompt schema should support reviewable quality metadata.

- REQ-7.1: JSON prompt mode should include `translated_text`.
- REQ-7.2: JSON prompt mode should include `title_translation` when title input is present.
- REQ-7.3: JSON prompt mode should include `uncertainties`.
- REQ-7.4: JSON prompt mode should include `glossary_conflicts`.
- REQ-7.5: JSON prompt mode should include `style_notes` or equivalent bounded quality notes when supported.
- REQ-7.6: New JSON fields must be optional/backward compatible if downstream parsers cannot consume them yet.
- REQ-7.7: If downstream parsing currently expects a strict schema, update parser/tests before enabling new fields by default.

### REQ-8: Configurability and Rollout

The new prompt policy must be safely configurable.

- REQ-8.1: Add a setting or prompt-builder option to enable the JP-EN quality policy.
- REQ-8.2: The default should be enabled for Japanese-to-English web novel translation if tests confirm parser compatibility.
- REQ-8.3: Provide an opt-out setting if prompt length or provider behavior regresses.
- REQ-8.4: The policy must be compatible with existing style presets and consistency modes.
- REQ-8.5: Prompt length increase must be bounded and should not duplicate existing instruction blocks unnecessarily.

### REQ-9: Prompt Snapshot and Golden Fixture Tests

Prompt changes must be covered by tests.

- REQ-9.1: Add prompt snapshot tests for default JP-EN prompt.
- REQ-9.2: Add prompt snapshot tests for JSON mode.
- REQ-9.3: Add prompt snapshot tests for each supported honorific policy.
- REQ-9.4: Add prompt snapshot tests proving glossary block and JP-EN policy coexist without duplicated/conflicting instructions.
- REQ-9.5: Add golden fixture tests for glossary compliance.
- REQ-9.6: Add golden fixture tests for paragraph preservation.
- REQ-9.7: Add golden fixture tests for ambiguous pronoun uncertainty behavior where model calls are mocked or prompt-only assertions are used.
- REQ-9.8: Tests must not require live provider calls.

### REQ-10: Backward Compatibility

Existing translation pipeline behavior must remain compatible.

- REQ-10.1: Existing prompt builder calls must continue to work.
- REQ-10.2: Existing non-JSON output parsing must continue to work.
- REQ-10.3: Existing JSON output parsing must continue to work or be updated with backward-compatible optional fields.
- REQ-10.4: Existing glossary injection behavior must remain intact.
- REQ-10.5: Existing translation cache keys must include prompt template/policy identity if prompt output changes.

## Non-Goals

- This spec does not replace the translation model provider.
- This spec does not implement a new segmentation algorithm.
- This spec does not change glossary review workflows.
- This spec does not enforce glossary terms in manual editing; that belongs to `glossary-aware-editor-qa`.
- This spec does not require live LLM evaluation tests.
- This spec does not change public reader rendering.

