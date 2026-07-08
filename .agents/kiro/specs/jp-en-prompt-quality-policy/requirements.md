# Requirements: JP-EN Prompt Quality Policy

## Introduction

The translation pipeline already has a capable prompt architecture: style presets, consistency modes, honorific policy, context overlap, glossary injection, approved-term resolution, and JSON output mode are already part of the system.

Prompt correctness hardening is already complete, so this spec must not replace the prompt builder or duplicate existing glossary, parser, cache, or translation pipeline work. Instead, this spec defines Japanese-to-English prompt quality as a stable policy and regression surface.

The goal is to ensure future prompt changes continue producing Japanese-to-English web novel prompts that are readable, glossary-compliant, structurally faithful, ambiguity-aware, and reviewable.

## Requirements

### REQ-1: Define JP-EN Prompt Quality Policy

The project must maintain a dedicated Japanese-to-English web novel prompt quality policy.

* REQ-1.1: The policy must apply to Japanese-to-English translation prompts.
* REQ-1.2: The policy must prioritize factual meaning preservation, glossary compliance, tone/register preservation, narrator voice, paragraph structure, and natural English readability.
* REQ-1.3: The policy must not replace existing style presets, consistency modes, segmentation, glossary injection, or provider routing.
* REQ-1.4: The policy must not duplicate existing prompt blocks when equivalent instructions already exist.
* REQ-1.5: Existing non-JP-EN prompts must remain unchanged unless an explicit existing override enables JP-EN policy behavior.
* REQ-1.6: The policy must be documented as a prompt contract that future prompt changes must preserve.

### REQ-2: Activation Rules

JP-EN policy activation must be explicit and predictable.

* REQ-2.1: The policy must apply when `source_language` is Japanese and `target_language` is English.
* REQ-2.2: Japanese source language aliases must include at least `ja` and `japanese`.
* REQ-2.3: English target language aliases must include at least `en` and `english`.
* REQ-2.4: If source or target language is unknown, the JP-EN policy must not apply unless an explicit existing override requests it.
* REQ-2.5: If a prompt feature-flag pattern already exists, the JP-EN policy may use that pattern.
* REQ-2.6: If no feature-flag pattern exists, do not add unnecessary configuration solely for this policy.
* REQ-2.7: Existing builder callers must remain compatible.

### REQ-3: Glossary and Approved-Term Compliance

JP-EN prompts must preserve glossary-first behavior.

* REQ-3.1: Prompts must require approved glossary terms for names, places, organizations, factions, skills, titles, abilities, and recurring terminology.
* REQ-3.2: Prompts must instruct the model not to invent alternate translations for approved glossary terms.
* REQ-3.3: Prompts must preserve approved-term casing, spelling, and formatting when the glossary defines them.
* REQ-3.4: If local context appears to conflict with an approved glossary entry, the prompt must prefer the approved glossary term.
* REQ-3.5: If JSON review metadata is enabled, the prompt should instruct the model to report glossary conflicts in `glossary_conflicts`.
* REQ-3.6: Terms absent from the glossary should be translated consistently with context.
* REQ-3.7: Proper nouns must not be over-localized unless the glossary or configured style preset requires it.
* REQ-3.8: This spec must not change glossary onboarding, glossary approval, or glossary injection logic.

### REQ-4: Honorific and Address Policy

JP-EN prompts must preserve the configured honorific policy.

* REQ-4.1: Prompts must include or preserve the configured honorific policy.
* REQ-4.2: If policy is `preserve`, prompts must instruct consistent romanized honorific usage such as `-san`, `-sama`, `-kun`, `-chan`, and `-sensei`.
* REQ-4.3: If policy is `localize`, prompts must instruct the model to express honorific nuance through natural English address, relationship wording, or tone.
* REQ-4.4: If policy is `omit`, prompts must instruct the model to omit honorifics while preserving relationship nuance through tone and wording.
* REQ-4.5: Prompts must discourage mixing honorific policies within the same chapter unless source context clearly requires it.
* REQ-4.6: Existing honorific prompt behavior must remain compatible.

### REQ-5: Dialogue, Register, and Voice

JP-EN prompts must protect character voice and dialogue quality.

* REQ-5.1: Prompts must instruct the model to preserve speaker boundaries.
* REQ-5.2: Prompts must preserve dialogue paragraphing.
* REQ-5.3: Prompts must preserve character register, including politeness level, roughness, formality, childishness, teasing tone, intimacy, archaic speech, or role-based speech.
* REQ-5.4: Prompts must preserve narrator voice separately from dialogue voice.
* REQ-5.5: Prompts must translate dialogue into natural English without flattening distinct voices.
* REQ-5.6: Prompts must preserve hesitation, interruption, ellipsis, and emphasis naturally.
* REQ-5.7: Prompts must discourage adding speaker tags, explanations, or emotional interpretation that is not present in the source.

### REQ-6: Ambiguous Pronouns and Omitted Subjects

JP-EN prompts must handle Japanese ambiguity conservatively.

* REQ-6.1: Prompts must instruct the model to use local and carried context to resolve omitted subjects and ambiguous pronouns.
* REQ-6.2: When the referent remains uncertain, prompts must instruct neutral English wording rather than invented certainty.
* REQ-6.3: Prompts must discourage inventing gender, identity, relationship, speaker attribution, motivation, or intent.
* REQ-6.4: Prompts must preserve deliberate ambiguity when the source appears intentionally ambiguous.
* REQ-6.5: If JSON review metadata is enabled, prompts should instruct the model to report unresolved ambiguity in `uncertainties`.
* REQ-6.6: Ambiguity handling must not require live model evaluation tests.

### REQ-7: Chapter Structure, Notes, and Formatting

JP-EN prompts must preserve web novel structure.

* REQ-7.1: Prompts must keep chapter title translation separate from body translation when title input is provided separately.
* REQ-7.2: Prompts must preserve paragraph order.
* REQ-7.3: Prompts must preserve scene order.
* REQ-7.4: Prompts must discourage merging or splitting paragraphs unless required for intelligible English and allowed by the existing output format.
* REQ-7.5: Prompts must preserve author notes, translator-style notes, footnotes, and endnotes as notes when present.
* REQ-7.6: Prompts must preserve semantically meaningful emphasis markers or special formatting.
* REQ-7.7: Prompts must not introduce Markdown or HTML unless the requested output format requires it.
* REQ-7.8: Existing formatting/output-mode behavior must remain compatible.

### REQ-8: JSON Review Metadata Compatibility

JSON mode should support optional review metadata without breaking existing parsing.

* REQ-8.1: JSON mode must continue supporting the required translated text field used by the current parser.
* REQ-8.2: JSON mode should support `title_translation` when title input is provided.
* REQ-8.3: JSON mode should support optional `uncertainties`.
* REQ-8.4: JSON mode should support optional `glossary_conflicts`.
* REQ-8.5: JSON mode should support optional `style_notes` or an equivalent bounded review-notes field.
* REQ-8.6: New review metadata fields must be optional.
* REQ-8.7: Parser behavior must remain compatible when optional review metadata fields are absent.
* REQ-8.8: If the current parser is strict, parser tests must be updated before enabling new optional fields by default.
* REQ-8.9: Review metadata must not leak into public reader text unless an existing review surface explicitly displays it.

### REQ-9: Prompt Length Control

JP-EN prompt quality instructions must remain bounded.

* REQ-9.1: Prompt additions must be concise.
* REQ-9.2: Prompt blocks must not repeat glossary entries already injected elsewhere.
* REQ-9.3: Prompt blocks must not duplicate a full glossary section if one already exists.
* REQ-9.4: Prompt blocks must not duplicate honorific instructions if existing honorific policy instructions already cover them.
* REQ-9.5: The prompt builder should prefer short policy bullets over long prose.
* REQ-9.6: The policy must not substantially increase every chunk prompt when an existing shared system/developer section can carry the instruction.
* REQ-9.7: Snapshot tests must make prompt growth visible.

### REQ-10: Prompt Versioning and Cache Identity

Prompt policy identity must be explicit and cache-safe.

* REQ-10.1: The JP-EN prompt policy must have a stable policy/template version.
* REQ-10.2: Recommended version value: `jp_en_quality_v1`.
* REQ-10.3: Prompt metadata should include prompt policy identity when the JP-EN policy applies.
* REQ-10.4: If prompt output changes in a way that can affect translation results, cache identity must include the prompt template or policy version.
* REQ-10.5: Cache identity must continue including existing prompt-shaping dimensions such as style preset, consistency mode, glossary revision or glossary hash, source language, and target language where already required.
* REQ-10.6: Changing the JP-EN prompt policy version must change cache identity for JP-EN prompts.
* REQ-10.7: Non-JP-EN prompts must not receive JP-EN cache dimensions unless explicitly enabled.

### REQ-11: Prompt Snapshot Tests

Prompt behavior must be protected by snapshot tests.

* REQ-11.1: Add or update snapshot tests for the default JP-EN non-JSON prompt.
* REQ-11.2: Add or update snapshot tests for the JP-EN JSON prompt.
* REQ-11.3: Add or update snapshot tests proving non-JP-EN prompts do not include JP-EN-specific policy by default.
* REQ-11.4: Add or update snapshot tests for honorific policy `preserve`.
* REQ-11.5: Add or update snapshot tests for honorific policy `localize`.
* REQ-11.6: Add or update snapshot tests for honorific policy `omit`.
* REQ-11.7: Add or update snapshot tests proving glossary instructions and JP-EN policy coexist without duplicated full glossary blocks.
* REQ-11.8: Add or update snapshot tests proving prompt metadata includes policy/version identity when the JP-EN policy applies.
* REQ-11.9: Snapshot updates must be intentional and reviewed, not casually regenerated.

### REQ-12: Golden Fixture Prompt Tests

Prompt quality must be covered by focused prompt-only fixtures.

* REQ-12.1: Add a glossary/name consistency fixture.
* REQ-12.2: Add an ambiguous pronoun fixture.
* REQ-12.3: Add an omitted subject fixture.
* REQ-12.4: Add a dialogue/register fixture.
* REQ-12.5: Add a narrator-versus-dialogue voice fixture.
* REQ-12.6: Add a chapter title plus body fixture.
* REQ-12.7: Add an author note, footnote, or endnote fixture.
* REQ-12.8: Add an honorific fixture.
* REQ-12.9: Fixture tests must assert prompt instructions and generated request shape.
* REQ-12.10: Fixture tests must not call live translation providers.

### REQ-13: Parser Regression Tests

JSON parser compatibility must be tested when review metadata is supported.

* REQ-13.1: Parser tests must accept JSON responses with `uncertainties`.
* REQ-13.2: Parser tests must accept JSON responses with `glossary_conflicts`.
* REQ-13.3: Parser tests must accept JSON responses with `style_notes`.
* REQ-13.4: Parser tests must accept JSON responses where optional review fields are missing.
* REQ-13.5: Parser tests must continue enforcing required translation fields according to current parser rules.
* REQ-13.6: Parser tests must not require live provider calls.

### REQ-14: Cache-Key Regression Tests

Prompt cache behavior must be protected by tests.

* REQ-14.1: Add a regression test proving JP-EN policy version contributes to cache identity when applied.
* REQ-14.2: Add a regression test proving changing the JP-EN policy version changes cache identity.
* REQ-14.3: Add a regression test proving non-JP-EN prompts do not receive JP-EN policy cache dimensions by default.
* REQ-14.4: Add a regression test proving existing glossary revision or glossary hash cache dimensions remain intact.
* REQ-14.5: Add a regression test proving style preset and consistency mode cache dimensions remain intact where already required.

### REQ-15: Prompt Quality Checklist

Future JP-EN prompt changes must be reviewed against a documented checklist.

* REQ-15.1: The checklist must require approved glossary terms to remain mandatory.
* REQ-15.2: The checklist must require honorific behavior to follow configured policy.
* REQ-15.3: The checklist must require speaker boundaries and dialogue paragraphing to be preserved.
* REQ-15.4: The checklist must require character register and narrator voice to remain distinct.
* REQ-15.5: The checklist must require ambiguous referents to remain neutral when uncertain.
* REQ-15.6: The checklist must prohibit invented gender, relationship, motivation, speaker identity, or unsupported facts.
* REQ-15.7: The checklist must require chapter titles and body text to remain structurally separate.
* REQ-15.8: The checklist must require paragraph order and scene order to be preserved.
* REQ-15.9: The checklist must require author notes, footnotes, and endnotes to be preserved as notes.
* REQ-15.10: The checklist must require JSON review metadata to remain optional and parser-compatible.
* REQ-15.11: The checklist must require prompt policy/template version updates when output-shaping instructions change.

### REQ-16: Backward Compatibility

Existing translation behavior must remain compatible.

* REQ-16.1: Existing prompt builder calls must continue working.
* REQ-16.2: Existing non-JSON parsing must continue working.
* REQ-16.3: Existing JSON parsing must continue working or be updated with backward-compatible optional fields.
* REQ-16.4: Existing glossary injection must remain intact.
* REQ-16.5: Existing glossary-first onboarding and approved-term resolution must remain the source of glossary truth.
* REQ-16.6: Existing style presets must remain compatible.
* REQ-16.7: Existing consistency modes must remain compatible.
* REQ-16.8: Existing translation scheduler behavior must not change.
* REQ-16.9: Existing provider routing behavior must not change.
* REQ-16.10: Public reader rendering must not change.

## Non-Goals

* This spec does not replace the translation model provider.
* This spec does not implement a new segmentation algorithm.
* This spec does not change provider routing.
* This spec does not change translation scheduler behavior.
* This spec does not change glossary onboarding or glossary review workflows.
* This spec does not enforce glossary terms in manual editing; that belongs to `glossary-aware-editor-qa`.
* This spec does not require live LLM evaluation tests.
* This spec does not change public reader rendering.
* This spec does not add a new translation storage format.
* This spec does not duplicate prompt correctness hardening already completed.
