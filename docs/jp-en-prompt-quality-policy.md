# JP-EN Prompt Quality Policy

This document defines the Japanese-to-English (JP-EN) prompt quality policy for the Novel AI translation system. It is a contract for generated prompts, not a separate translation feature.

## Scope

The policy applies to prompts generated for Japanese-to-English translation. It does not replace the prompt builder, duplicate glossary injection, rewrite parser behavior, or change translation scheduling/provider routing.

## Activation

The JP-EN policy applies when:

```python
source_language in {"ja", "japanese"} and target_language in {"en", "english"}
```

Unknown source or target languages do not trigger the policy unless an explicit override enables it.

## Policy Identity

- Policy name: `jp_en_quality`
- Policy version: `jp_en_quality_v1`

The policy version is included in `TranslationRequest.prompt_policy_version` and contributes to the cache key. Bump the version when output-shaping instructions change in a way that can affect translation results.

## Core Rules

JP-EN prompts must instruct the model to:

1. **Preserve factual meaning** — do not omit, summarize, censor, soften, or add information.
2. **Obey approved glossary terms** — use approved translations exactly for names, places, organizations, skills, titles, factions, and recurring terminology.
3. **Preserve tone, register, narrator voice, and paragraph structure** — keep the same paragraph breaks as the source.
4. **Prefer natural publication-quality English** — avoid awkward word-for-word literalness.
5. **Do not invent facts** — no fabricated gender, relationships, motivations, or speaker identity.
6. **Preserve deliberate ambiguity** — if a referent is unclear, keep wording neutral and report the uncertainty when JSON review metadata is enabled.

## Review Rules

Future prompt changes must preserve the following rules.

### 1. Glossary Compliance

- Use approved glossary translations exactly for recurring terms and names.
- Do not create alternate translations for approved terms.
- If source context appears to contradict an approved glossary entry, keep the glossary term and report the conflict when JSON review metadata is enabled.
- If a term is absent from the glossary, translate it consistently with prior context and do not over-localize proper nouns.

### 2. Honorific Policy

| Policy     | Required behavior |
| ---------- | ----------------- |
| `retain`   | Preserve romanized honorifics such as `-san`, `-kun`, `-chan`, `-sama`, `-sensei` consistently |
| `translate` | Convert honorific nuance into natural English address, relationship wording, or tone |
| `omit`     | Omit honorifics while preserving relationship nuance through tone and wording |

The prompt must not mix policies unless the source context clearly requires it.

### 3. Dialogue and Register

- Preserve speaker boundaries and dialogue paragraphing.
- Keep character register distinct: polite, rough, childish, formal, archaic, teasing, or intimate speech should not be flattened.
- Preserve narrator voice separately from dialogue voice.
- Translate hesitation, interruption, ellipsis, and emphasis naturally without over-explaining.
- Do not add speaker tags that are not present in the source.

### 4. Ambiguous Pronouns and Omitted Subjects

- Use local and carried context to resolve omitted Japanese subjects.
- If the referent remains uncertain, choose neutral English wording rather than inventing certainty.
- Do not invent gender, identity, relationship, motivation, or intent not supported by context.
- Preserve deliberate ambiguity.
- In JSON review metadata, report unresolved ambiguity in `uncertainties`.

### 5. Structure and Formatting

- Keep chapter titles separate from body text when provided separately.
- Preserve paragraph order and scene order.
- Do not merge or split paragraphs unless required for intelligible English and allowed by the output format.
- Preserve author notes, footnotes, endnotes, and translator-style notes as notes.
- Do not introduce Markdown or HTML unless the requested output format requires it.

## JSON Review Metadata

When JSON mode is enabled, prompts may request optional review metadata:

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

- These fields are optional.
- Existing parser behavior remains compatible when fields are missing.
- Parser tests cover both presence and absence of optional metadata.
- JSON review metadata is not required for normal non-JSON translation.
- Review metadata does not leak into public reader text.

## Prompt Length Control

- Do not repeat glossary entries already injected elsewhere.
- Do not duplicate a full glossary block if one already exists.
- Do not duplicate honorific instructions if the existing honorific block already covers them.
- Prefer short bullet instructions over long prose.
- Keep JP-EN policy content concise.
- Avoid expanding every chunk prompt with redundant text if a shared system/developer prompt section already carries the policy.

## Cache Identity

The cache key includes:

- source language
- target language
- provider key and model
- style preset
- consistency mode
- glossary revision or resolved glossary hash
- prompt template version
- JP-EN prompt policy version (when applied)

Changing the JP-EN policy version changes the cache identity, preventing stale prompt-policy cache reuse.

## Quality Checklist

Every future JP-EN prompt change must pass this checklist:

- [ ] Approved glossary terms remain mandatory.
- [ ] Honorific behavior follows configured policy.
- [ ] Dialogue speaker boundaries are preserved.
- [ ] Character register is not flattened.
- [ ] Narrator voice remains distinct from dialogue voice.
- [ ] Omitted subjects are resolved only when context supports resolution.
- [ ] Ambiguous referents remain neutral when uncertain.
- [ ] No gender, relationship, motivation, or speaker identity is invented.
- [ ] Chapter title and body remain structurally separate.
- [ ] Paragraph and scene order are preserved.
- [ ] Author notes, footnotes, and endnotes are preserved as notes.
- [ ] JSON review metadata remains optional and parser-compatible.
- [ ] Prompt length remains bounded.
- [ ] Prompt policy/template versioning is updated when output-shaping instructions change.
- [ ] Snapshot tests are updated intentionally, not casually regenerated.

## Backward Compatibility

- Existing builder callers continue working.
- Existing non-JP-EN prompts remain unchanged unless explicitly enabled.
- Existing style presets and consistency modes remain supported.
- Existing glossary injection remains intact.
- Existing glossary-first onboarding and approved-term resolution remain the source of glossary truth.
- JSON parser changes, if needed, are optional and additive.
- Cache-key updates prevent stale prompt-policy cache reuse.
- No translation provider behavior is changed.
- No scheduler behavior is changed.
- No public reader behavior is changed.
