# Design: JP-EN Prompt Quality Policy

## Overview

This design turns Japanese-to-English prompt quality into a stable policy and regression surface for the existing translation prompt system.

Prompt correctness hardening is already complete, so this spec should not rewrite the prompt builder or duplicate glossary injection, segmentation, provider routing, cache invalidation, or style preset work. Instead, it defines the JP-EN quality rules that prompts must continue to satisfy, adds review and regression coverage, and establishes prompt policy versioning for future prompt changes.

The goal is to preserve high-quality Japanese-to-English web novel translation behavior across future prompt edits.

## Scope

This spec covers:

* JP-EN prompt review rules.
* Snapshot tests for prompt construction.
* Regression fixtures for glossary, honorifics, ambiguity, dialogue/register, formatting, and JSON metadata.
* Prompt quality checklist for future prompt changes.
* Prompt policy/template versioning.
* Cache identity checks when prompt output changes.

This spec does not introduce a new translation pipeline, new scheduler behavior, new provider routing, new glossary workflow, or new editor QA workflow.

## Architecture

### Affected Files

| File                                                                        | Change type                                                                                   |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Prompt builder module, such as `backend/src/novelai/translation/prompts.py` | Inspect existing JP-EN prompt behavior; add or adjust only missing policy hooks               |
| Translation request builder                                                 | Ensure source/target language and prompt policy identity are available to prompt construction |
| Prompt/parser schema module, if strict JSON mode exists                     | Confirm optional review metadata remains parser-compatible                                    |
| Translation cache helper                                                    | Confirm prompt policy/template identity is included in cache dimensions                       |
| Backend prompt tests                                                        | Add snapshot, fixture, parser, and cache-key regression tests                                 |
| Prompt documentation, if present                                            | Add JP-EN quality checklist and prompt versioning notes                                       |

### Files Not Touched

* Source/crawler adapters.
* Translation scheduler/provider selection.
* Provider API clients.
* Glossary onboarding workflow.
* Glossary review/admin workflow.
* Manual editor glossary QA.
* Public reader routes.
* Storage schemas.

## Policy Positioning

The JP-EN prompt quality policy is a contract for generated prompts, not a separate translation feature.

The prompt builder must continue to produce prompts that satisfy these rules when translating from Japanese to English:

```text
Japanese-to-English web novel quality policy:
- Preserve factual meaning, speaker attribution, and scene order.
- Obey approved glossary terms for names, places, organizations, skills, titles, factions, and recurring terminology.
- Preserve tone, register, narrator voice, and paragraph structure.
- Prefer natural publication-quality English over awkward word-for-word literalness.
- Do not invent facts, gender, relationships, motivations, or speaker identity.
- Preserve deliberate ambiguity. If a referent is unclear, keep wording neutral and report the uncertainty when JSON review metadata is enabled.
```

If equivalent instructions already exist in the hardened prompt builder, tests should assert their presence rather than duplicating the text.

## Activation Rules

The JP-EN policy applies when:

```python
source_language in {"ja", "japanese"} and target_language in {"en", "english"}
```

If source or target language is unknown, the JP-EN policy must not be applied unless an existing explicit override already supports that behavior.

If a feature flag exists, use the existing settings style:

```python
JP_EN_PROMPT_QUALITY_POLICY_ENABLED: bool = True
```

If no feature flag pattern exists, do not add unnecessary config. Prefer stable always-on JP-EN behavior for Japanese-to-English translation.

## Prompt Review Rules

Future prompt changes must preserve the following rules.

### 1. Glossary Compliance

Prompts must instruct the model to:

```text
Glossary compliance:
- Use approved glossary translations exactly for recurring terms and names.
- Do not create alternate translations for approved terms.
- If source context appears to contradict an approved glossary entry, keep the glossary term and report the conflict when JSON review metadata is enabled.
- If a term is absent from the glossary, translate it consistently with prior context and do not over-localize proper nouns.
```

If a dedicated glossary block already exists, do not duplicate the full block. Add only JP-EN-specific conflict/reporting behavior if missing.

### 2. Honorific Policy

Prompts must respect the configured honorific policy.

| Policy     | Required behavior                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------- |
| `preserve` | Preserve romanized honorifics such as `-san`, `-sama`, `-kun`, `-chan`, and `-sensei` consistently |
| `localize` | Convert honorific nuance into natural English address, relationship wording, or tone               |
| `omit`     | Omit honorifics while preserving relationship nuance through tone and wording                      |

The prompt must not mix policies unless the source context clearly requires it.

### 3. Dialogue and Register

Prompts must preserve dialogue quality:

```text
Dialogue and voice:
- Preserve speaker boundaries and dialogue paragraphing.
- Keep character register distinct: polite, rough, childish, formal, archaic, teasing, or intimate speech should not be flattened.
- Preserve narrator voice separately from dialogue voice.
- Translate hesitation, interruption, ellipsis, and emphasis naturally without over-explaining.
- Do not add speaker tags that are not present in the source.
```

### 4. Ambiguous Pronouns and Omitted Subjects

Prompts must prevent unsupported certainty:

```text
Ambiguous pronouns and omitted subjects:
- Use local and carried context to resolve omitted Japanese subjects.
- If the referent remains uncertain, choose neutral English wording rather than inventing certainty.
- Do not invent gender, identity, relationship, motivation, or intent not supported by context.
- Preserve deliberate ambiguity.
- In JSON review metadata, report unresolved ambiguity in uncertainties.
```

### 5. Structure and Formatting

Prompts must preserve chapter structure:

```text
Structure and formatting:
- Keep chapter titles separate from body text when provided separately.
- Preserve paragraph order and scene order.
- Do not merge or split paragraphs unless required for intelligible English and allowed by the output format.
- Preserve author notes, footnotes, endnotes, and translator-style notes as notes.
- Do not introduce Markdown or HTML unless the requested output format requires it.
```

## JSON Review Metadata

If JSON mode is enabled and the parser supports optional fields, prompts may request review metadata:

```json
{
  "title_translation": "Translated title if title input was provided",
  "translated_text": "Translated body text",
  "uncertainties": [
    {
      "source": "short source phrase or location",
      "issue": "ambiguous referent",
      "resolution": "kept neutral wording"
    }
  ],
  "glossary_conflicts": [
    {
      "term": "source term",
      "glossary_translation": "approved translation",
      "issue": "local context may differ"
    }
  ],
  "style_notes": [
    "Bounded note about voice/register choice"
  ]
}
```

Rules:

* These fields must be optional.
* Existing parser behavior must remain compatible when fields are missing.
* Parser tests must cover both presence and absence of optional metadata.
* JSON review metadata must not be required for normal non-JSON translation.
* Review metadata must not leak into public reader text unless an existing review surface intentionally displays it.

## Prompt Length Control

Prompt additions must stay bounded.

Rules:

* Do not repeat glossary entries already injected elsewhere.
* Do not duplicate a full glossary block if one already exists.
* Do not duplicate honorific instructions if the existing honorific block already covers them.
* Prefer short bullet instructions over long prose.
* Keep JP-EN policy content concise.
* Avoid expanding every chunk prompt with redundant text if a shared system/developer prompt section already carries the policy.

## Prompt Versioning

Prompt policy identity must be explicit.

Recommended constant:

```python
JP_EN_PROMPT_POLICY_VERSION = "jp_en_quality_v1"
```

Prompt metadata should include:

```json
{
  "prompt_policy": "jp_en_quality",
  "prompt_policy_version": "jp_en_quality_v1"
}
```

If prompt output changes in a way that can affect translation results, the cache key must include the prompt template or policy version.

This prevents old cached translations from being reused after meaningful prompt-policy changes.

## Cache Identity Rules

Prompt cache identity must include all prompt-shaping dimensions that materially affect output, including existing dimensions such as:

* source language
* target language
* model/provider where already included
* style preset
* consistency mode
* glossary revision or resolved glossary hash
* prompt template version
* JP-EN prompt policy version, when applied

If these dimensions are already covered by existing prompt correctness hardening, this spec only adds regression tests to prevent accidental removal.

## Test Design

Create or extend backend prompt tests.

No tests should call live translation providers.

### Snapshot Tests

Add snapshot coverage for:

* JP-EN non-JSON prompt includes JP-EN quality policy.
* JP-EN JSON prompt includes optional review metadata instructions.
* Non-JP-EN prompt does not include JP-EN-specific policy unless explicitly enabled.
* Honorific `preserve` renders preserve instructions.
* Honorific `localize` renders localization instructions.
* Honorific `omit` renders omission-with-nuance instructions.
* Glossary block and JP-EN policy coexist without duplicated full glossary instructions.
* Prompt metadata includes prompt policy/version identity when JP-EN policy applies.

### Fixture Tests

Use synthetic source snippets and assert prompt instructions, not live model output.

Fixtures:

* glossary/name consistency fixture
* ambiguous pronoun fixture
* omitted subject fixture
* dialogue/register fixture
* chapter title plus body fixture
* footnote or author note fixture
* honorific fixture
* narrator-versus-dialogue voice fixture

### Parser Tests

If JSON review metadata is supported:

* parser accepts `uncertainties`
* parser accepts `glossary_conflicts`
* parser accepts `style_notes`
* parser remains compatible when those fields are absent
* parser rejects malformed required translation fields according to existing rules

### Cache-Key Regression Tests

Add tests that verify:

* JP-EN policy version contributes to cache identity when applied
* changing prompt policy version changes cache identity
* non-JP-EN prompts do not receive JP-EN policy cache dimensions unless explicitly enabled
* glossary revision/hash remains part of cache identity where already required

## Prompt Quality Checklist

Every future JP-EN prompt change must pass this checklist:

* Approved glossary terms remain mandatory.
* Honorific behavior follows configured policy.
* Dialogue speaker boundaries are preserved.
* Character register is not flattened.
* Narrator voice remains distinct from dialogue voice.
* Omitted subjects are resolved only when context supports resolution.
* Ambiguous referents remain neutral when uncertain.
* No gender, relationship, motivation, or speaker identity is invented.
* Chapter title and body remain structurally separate.
* Paragraph and scene order are preserved.
* Author notes, footnotes, and endnotes are preserved as notes.
* JSON review metadata remains optional and parser-compatible.
* Prompt length remains bounded.
* Prompt policy/template versioning is updated when output-shaping instructions change.
* Snapshot tests are updated intentionally, not casually regenerated.

## Migration and Backward Compatibility

* Existing builder callers must continue working.
* Existing non-JP-EN prompts must remain unchanged unless explicitly enabled.
* Existing style presets and consistency modes remain supported.
* Existing glossary injection remains intact.
* Existing glossary-first onboarding and approved-term resolution remain the source of glossary truth.
* JSON parser changes, if needed, must be optional and additive.
* Cache-key updates must prevent stale prompt-policy cache reuse.
* No translation provider behavior is changed.
* No scheduler behavior is changed.
* No public reader behavior is changed.

## Acceptance Criteria

1. JP-EN prompt policy is applied to Japanese-to-English translations.
2. Non-JP-EN prompts are unchanged unless explicitly enabled.
3. Prompt output includes or preserves guidance for glossary compliance, honorifics, dialogue/register, ambiguity, chapter titles, notes, and formatting.
4. JSON mode supports optional uncertainty, glossary conflict, and style note metadata when parser compatibility is available.
5. Prompt policy/template version is included in prompt metadata.
6. Prompt policy/template version contributes to cache identity when prompt output changes.
7. Existing glossary injection and style presets remain compatible.
8. Snapshot, fixture, parser, and cache-key regression tests pass without live provider calls.
9. Future prompt changes have a documented checklist and versioning path.
