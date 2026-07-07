# Design: JP-EN Prompt Quality Policy

## Overview

This design adds a dedicated Japanese-to-English web novel prompt policy to the existing translation prompt builder. The policy strengthens instructions around glossary compliance, honorifics, dialogue/register, omitted subjects, chapter structure, and JSON-mode review metadata.

The design is additive. It keeps the existing translation pipeline, segmentation, glossary injection, provider routing, and style presets.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| Prompt builder module, such as `backend/src/novelai/translation/prompts.py` | Add JP-EN policy block and integrate into prompt construction |
| Translation request builder | Pass source/target language and policy options into prompt builder |
| JSON output parser/schema, if strict | Accept optional review metadata fields |
| Translation cache helper | Include prompt policy/template identity if not already included |
| Backend tests for prompts | Add snapshot and fixture tests |

### Files Not Touched

- Source/crawler adapters.
- Translation scheduler/provider selection.
- Glossary review workflow.
- Manual editor glossary QA.
- Public reader routes.

## Prompt Policy Structure

Add a reusable prompt section:

```text
Japanese-to-English web novel quality policy:
- Preserve factual meaning, speaker attribution, and scene order.
- Obey approved glossary terms for names, places, organizations, skills, titles, factions, and recurring terminology.
- Preserve tone, register, narrator voice, and paragraph structure.
- Prefer natural publication-quality English over awkward word-for-word literalness.
- Do not invent facts, gender, relationships, motivations, or speaker identity.
- Preserve deliberate ambiguity. If a referent is unclear, keep wording neutral and report the uncertainty in JSON mode.
```

This block should be inserted after general translation role/system instructions and before chunk-specific text. It should not duplicate existing glossary or honorific blocks. If existing builder already includes a concept, the JP-EN block should reference it briefly and let the specialized block carry details.

## Activation Rules

Enable the policy when:

```python
source_language in {"ja", "japanese"} and target_language in {"en", "english"}
```

Optional config:

```python
JP_EN_PROMPT_QUALITY_POLICY_ENABLED: bool = True
```

If the project already has prompt feature flags, use the existing settings style.

If source/target language is unknown, do not apply the JP-EN policy unless explicitly requested.

## Prompt Builder API

If the builder already receives language/config values, extend internally. If not, add optional parameters:

```python
def build_translation_request(
    *,
    source_language: str | None = None,
    target_language: str | None = None,
    honorific_policy: str | None = None,
    style_preset: str | None = None,
    consistency_mode: str | None = None,
    glossary_entries: Sequence[GlossaryEntry] | None = None,
    prompt_glossary_block: str | None = None,
    json_output: bool = False,
    enable_jp_en_quality_policy: bool | None = None,
    ...
) -> TranslationPromptRequest:
    ...
```

Existing callers should not break because new parameters are optional.

## Policy Blocks

### Glossary Compliance Block

Add or strengthen:

```text
Glossary compliance:
- Use approved glossary translations exactly for recurring terms and names.
- Do not create alternate translations for approved terms.
- If the source context appears to contradict a glossary entry, keep the glossary term and report the conflict in the glossary_conflicts field when JSON output is enabled.
- If a term is absent from the glossary, translate it consistently with prior context and do not over-localize proper nouns.
```

If a separate glossary block already exists, avoid duplicating the full block. Add only JP-EN-specific conflict behavior.

### Honorific Policy Block

Generate based on existing configured honorific policy:

| Policy | Prompt behavior |
|---|---|
| `preserve` | Preserve romanized honorifics like `-san`, `-sama`, `-kun`, `-chan`, `-sensei` consistently |
| `localize` | Convert honorific nuance into natural English address or relationship wording |
| `omit` | Omit honorifics but preserve relationship nuance through tone and wording |

The block should say not to mix policies unless source context requires it.

### Dialogue and Register Block

```text
Dialogue and voice:
- Preserve speaker boundaries and dialogue paragraphing.
- Keep character register distinct: polite, rough, childish, formal, archaic, teasing, or intimate speech should not be flattened.
- Preserve narrator voice separately from dialogue voice.
- Translate hesitation, interruption, ellipsis, and emphasis naturally without over-explaining.
- Do not add speaker tags that are not present in the source.
```

### Ambiguity Block

```text
Ambiguous pronouns and omitted subjects:
- Use local and carried context to resolve omitted Japanese subjects.
- If the referent remains uncertain, choose neutral English wording rather than inventing certainty.
- Do not invent gender, identity, relationship, motivation, or intent not supported by context.
- Preserve deliberate ambiguity.
- In JSON output, report unresolved ambiguity in uncertainties.
```

### Structure and Notes Block

```text
Structure and formatting:
- Keep chapter titles separate from body text when provided separately.
- Preserve paragraph order and scene order.
- Do not merge or split paragraphs unless required for intelligible English and allowed by the output format.
- Preserve author notes, footnotes, endnotes, and translator-style notes as notes.
- Do not introduce Markdown or HTML unless the requested output format requires it.
```

## JSON Output Schema

If JSON mode is enabled and parser compatibility allows optional fields, ask for:

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

If current parser is strict, introduce these fields as optional and update parser tests before enabling them by default.

## Prompt Length Control

Prompt length must be bounded:

- Keep policy blocks concise.
- Do not repeat glossary entries already present in glossary block.
- Do not repeat honorific instructions if existing honorific block already covers them.
- Add one JP-EN policy section plus small specialized additions.
- Prefer short bullet instructions over long prose.

## Cache Key Impact

Because prompt output changes, translation cache identity must include prompt template or policy version if it does not already.

Recommended:

```python
JP_EN_PROMPT_POLICY_VERSION = "jp_en_quality_v1"
```

Include it in prompt metadata and cache key dimensions. This prevents old cached translations from being reused after prompt policy changes.

## Test Design

Create or extend prompt tests.

### Snapshot Tests

- default JP-EN non-JSON prompt includes policy block,
- JP-EN JSON prompt includes schema fields,
- non-JP-EN prompt does not include JP-EN policy,
- honorific `preserve` policy renders preserve instructions,
- honorific `localize` policy renders localize instructions,
- honorific `omit` policy renders omit instructions,
- glossary block and JP-EN policy coexist without duplicated full glossary instructions.

### Fixture Tests

Use synthetic source snippets and assert prompt instructions, not live LLM output:

- name/glossary compliance fixture,
- ambiguous pronoun fixture,
- dialogue/register fixture,
- chapter title plus body fixture,
- footnote/author note fixture.

### Parser Tests

If JSON fields are added:

- parser accepts `uncertainties`,
- parser accepts `glossary_conflicts`,
- parser accepts `style_notes`,
- parser remains compatible when fields are missing.

No tests should call live translation providers.

## Migration and Backward Compatibility

- Existing builder callers keep working because new parameters are optional.
- Existing non-JP-EN prompts do not change.
- Existing style presets and consistency modes remain supported.
- Existing glossary injection remains intact.
- JSON parser changes are optional/additive.
- Cache key updates prevent stale prompt-policy cache reuse.

## Acceptance Criteria

1. JP-EN prompt policy is applied to Japanese-to-English translations.
2. Non-JP-EN prompts are unchanged unless explicitly enabled.
3. Prompt includes explicit guidance for glossary compliance, honorifics, dialogue/register, ambiguity, chapter titles, notes, and formatting.
4. JSON mode supports optional uncertainty and glossary conflict fields when parser compatibility is ready.
5. Prompt policy/template version is included in cache identity if prompt output changes.
6. Existing glossary injection and style presets remain compatible.
7. Snapshot and fixture tests pass without live provider calls.

