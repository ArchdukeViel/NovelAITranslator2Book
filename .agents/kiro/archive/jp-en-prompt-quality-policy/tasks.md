# Tasks: JP-EN Prompt Quality Policy

## Overview

Maintain Japanese-to-English prompt quality as a policy and regression surface for the existing translation prompt system.

Prompt correctness hardening is already complete, so this work must not replace the prompt builder, duplicate glossary injection, rewrite parser behavior unnecessarily, or change translation scheduling/provider routing. The main implementation is verification: confirm the existing prompt system satisfies the JP-EN quality contract, add missing lightweight hooks only where needed, and protect behavior with snapshot, fixture, parser, cache-key, and checklist tests.

Scope boundaries:

* Do not replace the translation pipeline.
* Do not change provider routing.
* Do not change scheduler behavior.
* Do not change glossary onboarding or glossary review workflows.
* Do not change public reader rendering.
* Do not require live LLM/provider calls.
* Do not duplicate prompt correctness hardening already completed.

## Task List

* [x] 1. Preflight Prompt System Review

  * [x] 1.1 Inspect the prompt builder module and template constants.
  * [x] 1.2 Inspect `build_translation_request` and related prompt construction functions.
  * [x] 1.3 Inspect the translation stage call site and confirm available `source_language` and `target_language` values.
  * [x] 1.4 Inspect honorific policy handling.
  * [x] 1.5 Inspect style preset and consistency mode handling.
  * [x] 1.6 Inspect glossary block generation and approved-term injection.
  * [x] 1.7 Inspect JSON output prompt schema and parser behavior.
  * [x] 1.8 Inspect translation cache-key generation.
  * [x] 1.9 Inspect existing prompt tests, snapshots, fixtures, and parser tests.
  * [x] 1.10 Record which JP-EN quality requirements are already satisfied by completed prompt correctness hardening.

* [x] 2. Define JP-EN Policy Contract

  * [x] 2.1 Create or update the JP-EN prompt quality policy documentation.
  * [x] 2.2 Document that the policy applies to Japanese-to-English translation prompts.
  * [x] 2.3 Document that the policy preserves factual meaning, glossary compliance, tone/register, narrator voice, paragraph structure, and natural English readability.
  * [x] 2.4 Document that the policy does not replace style presets, consistency modes, segmentation, glossary injection, or provider routing.
  * [x] 2.5 Document that equivalent existing prompt instructions should be reused instead of duplicated.
  * [x] 2.6 Document that non-JP-EN prompts must remain unchanged unless an explicit existing override enables JP-EN behavior.

* [x] 3. Verify JP-EN Activation Rules

  * [x] 3.1 Confirm JP-EN policy behavior applies when source language is Japanese and target language is English.
  * [x] 3.2 Confirm Japanese aliases include at least `ja` and `japanese`.
  * [x] 3.3 Confirm English aliases include at least `en` and `english`.
  * [x] 3.4 Confirm unknown source or target language does not accidentally trigger JP-EN policy.
  * [x] 3.5 Confirm existing builder callers remain compatible.
  * [x] 3.6 If a feature flag already exists, verify it follows existing settings style.
  * [x] 3.7 Do not add a new feature flag unless the project already uses prompt feature flags or there is a confirmed regression need.

* [x] 4. Verify Glossary and Approved-Term Behavior

  * [x] 4.1 Confirm prompts require approved glossary terms for names, places, organizations, factions, skills, titles, abilities, and recurring terminology.
  * [x] 4.2 Confirm prompts instruct the model not to invent alternate translations for approved glossary terms.
  * [x] 4.3 Confirm approved-term casing, spelling, and formatting are preserved when defined by the glossary.
  * [x] 4.4 Confirm local context conflicts prefer the approved glossary term.
  * [x] 4.5 Confirm JSON review metadata can report glossary conflicts when enabled.
  * [x] 4.6 Confirm non-glossary terms are instructed to be translated consistently with context.
  * [x] 4.7 Confirm proper nouns are not over-localized unless glossary/style policy requires it.
  * [x] 4.8 Add only minimal prompt text if a required glossary behavior is missing.
  * [x] 4.9 Do not duplicate the existing glossary block.

* [x] 5. Verify Honorific Policy Behavior

  * [x] 5.1 Confirm the configured honorific policy appears in prompt construction.
  * [x] 5.2 Confirm `preserve` instructs consistent romanized honorific usage such as `-san`, `-sama`, `-kun`, `-chan`, and `-sensei`.
  * [x] 5.3 Confirm `localize` instructs natural English address, relationship wording, or tone.
  * [x] 5.4 Confirm `omit` instructs omission while preserving relationship nuance.
  * [x] 5.5 Confirm prompts discourage mixing honorific policies within one chapter unless source context requires it.
  * [x] 5.6 Preserve existing honorific setting names and behavior.
  * [x] 5.7 Add only minimal prompt text if a required honorific behavior is missing.

* [x] 6. Verify Dialogue, Register, and Voice Instructions

  * [x] 6.1 Confirm prompts preserve speaker boundaries.
  * [x] 6.2 Confirm prompts preserve dialogue paragraphing.
  * [x] 6.3 Confirm prompts preserve character register, politeness, roughness, formality, childishness, teasing tone, intimacy, archaic speech, and role-based speech.
  * [x] 6.4 Confirm prompts preserve narrator voice separately from dialogue voice.
  * [x] 6.5 Confirm prompts instruct natural English dialogue without flattening distinct voices.
  * [x] 6.6 Confirm prompts preserve hesitation, interruption, ellipsis, and emphasis naturally.
  * [x] 6.7 Confirm prompts discourage unsupported speaker tags, explanations, or emotional interpretation.
  * [x] 6.8 Add only minimal prompt text if a required voice/register behavior is missing.

* [x] 7. Verify Ambiguity and Omitted Subject Handling

  * [x] 7.1 Confirm prompts instruct use of local and carried context for omitted Japanese subjects.
  * [x] 7.2 Confirm prompts instruct neutral English wording when referents remain uncertain.
  * [x] 7.3 Confirm prompts discourage invented gender, identity, relationship, speaker attribution, motivation, or intent.
  * [x] 7.4 Confirm prompts preserve deliberate ambiguity.
  * [x] 7.5 Confirm JSON review metadata can report unresolved ambiguity in `uncertainties` when enabled.
  * [x] 7.6 Add only minimal prompt text if a required ambiguity behavior is missing.

* [x] 8. Verify Chapter Structure, Notes, and Formatting

  * [x] 8.1 Confirm prompts keep chapter title translation separate from body translation when title input is separate.
  * [x] 8.2 Confirm prompts preserve paragraph order.
  * [x] 8.3 Confirm prompts preserve scene order.
  * [x] 8.4 Confirm prompts discourage merging or splitting paragraphs unless required and allowed by output format.
  * [x] 8.5 Confirm prompts preserve author notes, translator-style notes, footnotes, and endnotes as notes.
  * [x] 8.6 Confirm prompts preserve semantically meaningful emphasis markers or special formatting.
  * [x] 8.7 Confirm prompts do not introduce Markdown or HTML unless requested by output format.
  * [x] 8.8 Add only minimal prompt text if a required formatting behavior is missing.

* [x] 9. Verify JSON Review Metadata Compatibility

  * [x] 9.1 Confirm JSON mode still supports the required translated text field used by the current parser.
  * [x] 9.2 Confirm JSON mode supports `title_translation` when title input exists, if already supported.
  * [x] 9.3 Confirm optional `uncertainties` are parser-compatible when present.
  * [x] 9.4 Confirm optional `glossary_conflicts` are parser-compatible when present.
  * [x] 9.5 Confirm optional `style_notes` or equivalent bounded review notes are parser-compatible when present.
  * [x] 9.6 Confirm parser behavior remains compatible when optional review metadata fields are absent.
  * [x] 9.7 If parser is strict, update parser/tests before enabling optional fields by default.
  * [x] 9.8 Confirm review metadata does not leak into public reader text.

* [x] 10. Verify Prompt Length Control

  * [x] 10.1 Measure or snapshot prompt size before and after any prompt text changes.
  * [x] 10.2 Confirm JP-EN policy text is concise.
  * [x] 10.3 Confirm glossary entries are not repeated outside the existing glossary injection block.
  * [x] 10.4 Confirm full glossary instructions are not duplicated.
  * [x] 10.5 Confirm honorific instructions are not duplicated.
  * [x] 10.6 Prefer short policy bullets over long prose.
  * [x] 10.7 Prefer shared system/developer prompt sections over repeating long text in every chunk prompt.

* [x] 11. Verify Prompt Versioning and Cache Identity

  * [x] 11.1 Confirm JP-EN prompt policy/template version exists or add a stable version constant such as `jp_en_quality_v1`.
  * [x] 11.2 Confirm prompt metadata includes policy identity when JP-EN policy applies.
  * [x] 11.3 Confirm cache identity includes prompt template or policy version when prompt output changes.
  * [x] 11.4 Confirm cache identity still includes source language and target language where required.
  * [x] 11.5 Confirm cache identity still includes style preset where required.
  * [x] 11.6 Confirm cache identity still includes consistency mode where required.
  * [x] 11.7 Confirm cache identity still includes glossary revision or resolved glossary hash where required.
  * [x] 11.8 Confirm changing JP-EN policy version changes JP-EN cache identity.
  * [x] 11.9 Confirm non-JP-EN prompts do not receive JP-EN cache dimensions by default.

* [x] 12. Add Prompt Snapshot Tests

  * [x] 12.1 Add or update snapshot test for default JP-EN non-JSON prompt.
  * [x] 12.2 Add or update snapshot test for JP-EN JSON prompt.
  * [x] 12.3 Add or update snapshot test proving non-JP-EN prompts do not include JP-EN-specific policy by default.
  * [x] 12.4 Add or update snapshot test for honorific policy `preserve`.
  * [x] 12.5 Add or update snapshot test for honorific policy `localize`.
  * [x] 12.6 Add or update snapshot test for honorific policy `omit`.
  * [x] 12.7 Add or update snapshot test proving glossary instructions and JP-EN policy coexist without duplicated full glossary blocks.
  * [x] 12.8 Add or update snapshot test proving prompt metadata includes policy/version identity when JP-EN policy applies.
  * [x] 12.9 Review snapshot diffs manually before accepting updates.

* [x] 13. Add Golden Fixture Prompt Tests

  * [x] 13.1 Add glossary/name consistency fixture.
  * [x] 13.2 Add ambiguous pronoun fixture.
  * [x] 13.3 Add omitted subject fixture.
  * [x] 13.4 Add dialogue/register fixture.
  * [x] 13.5 Add narrator-versus-dialogue voice fixture.
  * [x] 13.6 Add chapter title plus body fixture.
  * [x] 13.7 Add author note, footnote, or endnote fixture.
  * [x] 13.8 Add honorific fixture.
  * [x] 13.9 Assert prompt instructions and generated request shape.
  * [x] 13.10 Do not call live translation providers.

* [x] 14. Add Parser Regression Tests

  * [x] 14.1 Test parser accepts JSON responses with `uncertainties`.
  * [x] 14.2 Test parser accepts JSON responses with `glossary_conflicts`.
  * [x] 14.3 Test parser accepts JSON responses with `style_notes` or equivalent bounded review notes.
  * [x] 14.4 Test parser accepts JSON responses where optional review fields are absent.
  * [x] 14.5 Test parser continues enforcing required translation fields according to current parser rules.
  * [x] 14.6 Test non-JSON parsing still works.
  * [x] 14.7 Do not call live translation providers.

* [x] 15. Add Cache-Key Regression Tests

  * [x] 15.1 Test JP-EN policy version contributes to cache identity when applied.
  * [x] 15.2 Test changing JP-EN policy version changes cache identity.
  * [x] 15.3 Test non-JP-EN prompts do not receive JP-EN policy cache dimensions by default.
  * [x] 15.4 Test glossary revision or glossary hash remains part of cache identity where required.
  * [x] 15.5 Test style preset remains part of cache identity where required.
  * [x] 15.6 Test consistency mode remains part of cache identity where required.

* [x] 16. Add Prompt Quality Checklist

  * [x] 16.1 Add a JP-EN prompt quality checklist to prompt documentation or test docs.
  * [x] 16.2 Checklist must require approved glossary terms to remain mandatory.
  * [x] 16.3 Checklist must require honorific behavior to follow configured policy.
  * [x] 16.4 Checklist must require speaker boundaries and dialogue paragraphing to be preserved.
  * [x] 16.5 Checklist must require character register and narrator voice to remain distinct.
  * [x] 16.6 Checklist must require ambiguous referents to remain neutral when uncertain.
  * [x] 16.7 Checklist must prohibit invented gender, relationship, motivation, speaker identity, and unsupported facts.
  * [x] 16.8 Checklist must require chapter title and body text to remain structurally separate.
  * [x] 16.9 Checklist must require paragraph order and scene order to be preserved.
  * [x] 16.10 Checklist must require author notes, footnotes, and endnotes to be preserved as notes.
  * [x] 16.11 Checklist must require JSON review metadata to remain optional and parser-compatible.
  * [x] 16.12 Checklist must require prompt policy/template version updates when output-shaping instructions change.

* [x] 17. Backward Compatibility Checks

  * [x] 17.1 Confirm existing prompt builder calls continue working.
  * [x] 17.2 Confirm existing non-JSON parsing continues working.
  * [x] 17.3 Confirm existing JSON parsing continues working or only changes through backward-compatible optional fields.
  * [x] 17.4 Confirm glossary injection remains intact.
  * [x] 17.5 Confirm glossary-first onboarding remains unchanged.
  * [x] 17.6 Confirm approved-term resolution remains the source of glossary truth.
  * [x] 17.7 Confirm style presets remain compatible.
  * [x] 17.8 Confirm consistency modes remain compatible.
  * [x] 17.9 Confirm translation scheduler behavior is unchanged.
  * [x] 17.10 Confirm provider routing behavior is unchanged.
  * [x] 17.11 Confirm public reader rendering is unchanged.

* [x] 18. Run Verification

  * [x] 18.1 Run focused prompt builder tests.
  * [x] 18.2 Run prompt snapshot tests.
  * [x] 18.3 Run golden fixture prompt tests.
  * [x] 18.4 Run JSON parser tests.
  * [x] 18.5 Run translation cache-key tests.
  * [x] 18.6 Run existing translation prompt tests.
  * [x] 18.7 Run `ruff check` on changed backend source and test files.
  * [x] 18.8 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  * [x] 18.9 Fix test, lint, and type failures caused by this work.

* [x] 19. Final Acceptance Review

  * [x] 19.1 Verify JP-EN prompt policy applies to Japanese-to-English translations.
  * [x] 19.2 Verify non-JP-EN prompts are unchanged unless explicitly enabled.
  * [x] 19.3 Verify prompt output includes or preserves guidance for glossary compliance.
  * [x] 19.4 Verify prompt output includes or preserves guidance for honorifics.
  * [x] 19.5 Verify prompt output includes or preserves guidance for dialogue/register.
  * [x] 19.6 Verify prompt output includes or preserves guidance for ambiguity and omitted subjects.
  * [x] 19.7 Verify prompt output includes or preserves guidance for chapter titles, notes, and formatting.
  * [x] 19.8 Verify JSON mode supports optional review metadata when parser compatibility is available.
  * [x] 19.9 Verify prompt policy/template version is included in prompt metadata.
  * [x] 19.10 Verify prompt policy/template version contributes to cache identity when prompt output changes.
  * [x] 19.11 Verify existing glossary injection, style presets, and consistency modes remain compatible.
  * [x] 19.12 Verify snapshot, fixture, parser, and cache-key regression tests pass without live provider calls.

## Requirement Coverage Matrix

| Requirement                                    | Covered By Tasks      |
| ---------------------------------------------- | --------------------- |
| REQ-1 Define JP-EN Prompt Quality Policy       | 1, 2, 12, 16, 19      |
| REQ-2 Activation Rules                         | 3, 12, 17, 19         |
| REQ-3 Glossary and Approved-Term Compliance    | 4, 12, 13, 16, 17, 19 |
| REQ-4 Honorific and Address Policy             | 5, 12, 13, 16, 17, 19 |
| REQ-5 Dialogue, Register, and Voice            | 6, 13, 16, 19         |
| REQ-6 Ambiguous Pronouns and Omitted Subjects  | 7, 13, 14, 16, 19     |
| REQ-7 Chapter Structure, Notes, and Formatting | 8, 13, 16, 19         |
| REQ-8 JSON Review Metadata Compatibility       | 9, 14, 17, 19         |
| REQ-9 Prompt Length Control                    | 10, 12, 17            |
| REQ-10 Prompt Versioning and Cache Identity    | 11, 15, 19            |
| REQ-11 Prompt Snapshot Tests                   | 12, 18                |
| REQ-12 Golden Fixture Prompt Tests             | 13, 18                |
| REQ-13 Parser Regression Tests                 | 14, 18                |
| REQ-14 Cache-Key Regression Tests              | 15, 18                |
| REQ-15 Prompt Quality Checklist                | 16                    |
| REQ-16 Backward Compatibility                  | 17, 18, 19            |

## Definition of Done

* [x] JP-EN prompt quality policy is documented as a stable prompt contract.
* [x] Existing prompt builder behavior is audited against the policy.
* [x] Missing JP-EN prompt instructions are added only where necessary.
* [x] JP-EN policy applies only to intended Japanese-to-English prompts by default.
* [x] Non-JP-EN prompts remain unchanged unless explicitly enabled.
* [x] Glossary, honorific, dialogue/register, ambiguity, title, note, and formatting rules are protected by tests.
* [x] JSON review metadata remains optional and parser-compatible.
* [x] Prompt policy/template versioning is explicit.
* [x] Cache identity changes when JP-EN prompt policy output changes.
* [x] Existing style presets, consistency modes, glossary injection, provider routing, and scheduler behavior remain compatible.
* [x] Snapshot, fixture, parser, and cache-key tests pass without live provider calls.
* [x] Relevant linting and type checks pass.
