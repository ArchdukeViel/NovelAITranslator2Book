# Tasks: JP-EN Prompt Quality Policy

## Task List

- [ ] 1. Preflight Prompt Builder Review
  - [ ] 1.1 Inspect prompt builder module and template constants.
  - [ ] 1.2 Inspect `build_translation_request` and related builder functions.
  - [ ] 1.3 Inspect `TranslateStage` call site and available source/target language values.
  - [ ] 1.4 Inspect honorific policy handling.
  - [ ] 1.5 Inspect glossary block generation and conflict warning behavior.
  - [ ] 1.6 Inspect JSON output prompt schema and parser.
  - [ ] 1.7 Inspect translation cache key generation.
  - [ ] 1.8 Inspect existing prompt tests and snapshots.

- [ ] 2. Add JP-EN Policy Activation
  - [ ] 2.1 Add helper to detect Japanese-to-English translation from source/target language. (REQ-1.3)
  - [ ] 2.2 Add `JP_EN_PROMPT_QUALITY_POLICY_ENABLED` setting or prompt-builder option. (REQ-8.1)
  - [ ] 2.3 Enable policy by default for JP-EN if parser compatibility is confirmed. (REQ-8.2)
  - [ ] 2.4 Provide opt-out behavior. (REQ-8.3)
  - [ ] 2.5 Ensure non-JP-EN prompts do not change unexpectedly. (REQ-1.4)

- [ ] 3. Add Base JP-EN Quality Policy Block
  - [ ] 3.1 Add reusable policy text block. (REQ-1.1)
  - [ ] 3.2 Include meaning preservation priority. (REQ-1.2)
  - [ ] 3.3 Include glossary compliance priority. (REQ-1.2)
  - [ ] 3.4 Include tone/register preservation priority. (REQ-1.2)
  - [ ] 3.5 Include natural English readability priority. (REQ-1.2)
  - [ ] 3.6 Keep the block concise to control prompt length. (REQ-8.5)

- [ ] 4. Strengthen Glossary Compliance Instructions
  - [ ] 4.1 Require approved glossary terms for names, places, organizations, skills, titles, factions, and recurring terms. (REQ-2.1)
  - [ ] 4.2 Instruct model not to invent alternate approved-term translations. (REQ-2.2)
  - [ ] 4.3 Define behavior when glossary conflicts with local context. (REQ-2.3)
  - [ ] 4.4 Add JSON-mode glossary conflict reporting instruction. (REQ-2.4)
  - [ ] 4.5 Preserve proper noun/name policy. (REQ-2.5)
  - [ ] 4.6 Avoid duplicating existing glossary block content. (REQ-8.5)

- [ ] 5. Add Honorific Policy Blocks
  - [ ] 5.1 Ensure configured honorific policy is included. (REQ-3.1)
  - [ ] 5.2 Add preserve-policy instructions. (REQ-3.2)
  - [ ] 5.3 Add localize-policy instructions. (REQ-3.3)
  - [ ] 5.4 Add omit-policy instructions. (REQ-3.4)
  - [ ] 5.5 Add instruction not to mix honorific policies within a chapter. (REQ-3.5)
  - [ ] 5.6 Preserve existing honorific setting names and behavior.

- [ ] 6. Add Dialogue and Register Instructions
  - [ ] 6.1 Preserve speaker boundaries and dialogue paragraphing. (REQ-4.1)
  - [ ] 6.2 Preserve politeness, roughness, age/role cues, and narrator voice. (REQ-4.2)
  - [ ] 6.3 Instruct natural English dialogue without flattening character voices. (REQ-4.3)
  - [ ] 6.4 Preserve hesitation, interruption, ellipsis, and emphasis naturally. (REQ-4.4)
  - [ ] 6.5 Instruct not to add unsupported speaker tags. (REQ-4.5)

- [ ] 7. Add Ambiguity and Pronoun Instructions
  - [ ] 7.1 Instruct use of local and carried context for omitted subjects. (REQ-5.1)
  - [ ] 7.2 Instruct neutral wording when referent remains uncertain. (REQ-5.2)
  - [ ] 7.3 Add JSON-mode uncertainty reporting instruction. (REQ-5.3)
  - [ ] 7.4 Discourage invented gender, identity, relationship, motivation, or intent. (REQ-5.4)
  - [ ] 7.5 Preserve deliberate ambiguity. (REQ-5.5)

- [ ] 8. Add Chapter Structure and Notes Instructions
  - [ ] 8.1 Keep chapter title separate from body when provided separately. (REQ-6.1)
  - [ ] 8.2 Preserve paragraph and scene order. (REQ-6.2)
  - [ ] 8.3 Avoid merging/splitting paragraphs unless allowed. (REQ-6.3)
  - [ ] 8.4 Preserve author notes, footnotes, endnotes, and translator-style notes as notes. (REQ-6.4)
  - [ ] 8.5 Preserve meaningful emphasis and special formatting. (REQ-6.5)
  - [ ] 8.6 Avoid introducing Markdown/HTML unless output mode requires it. (REQ-6.6)

- [ ] 9. Enhance JSON Output Prompt Schema
  - [ ] 9.1 Ensure JSON mode includes `translated_text`. (REQ-7.1)
  - [ ] 9.2 Include `title_translation` when title input exists. (REQ-7.2)
  - [ ] 9.3 Include `uncertainties`. (REQ-7.3)
  - [ ] 9.4 Include `glossary_conflicts`. (REQ-7.4)
  - [ ] 9.5 Include bounded `style_notes` or equivalent. (REQ-7.5)
  - [ ] 9.6 Make new JSON fields optional/backward compatible. (REQ-7.6)
  - [ ] 9.7 Update strict parser/tests before enabling fields by default. (REQ-7.7)

- [ ] 10. Update Prompt Policy Version and Cache Identity
  - [ ] 10.1 Add prompt policy version constant such as `jp_en_quality_v1`. (REQ-10.5)
  - [ ] 10.2 Include policy/template version in prompt metadata.
  - [ ] 10.3 Include policy/template version in translation cache keys if not already present. (REQ-10.5)
  - [ ] 10.4 Ensure existing cache dimensions remain intact.

- [ ] 11. Add Prompt Snapshot Tests
  - [ ] 11.1 Test default JP-EN prompt includes quality policy. (REQ-9.1)
  - [ ] 11.2 Test JP-EN JSON prompt includes schema fields. (REQ-9.2)
  - [ ] 11.3 Test preserve honorific policy prompt. (REQ-9.3)
  - [ ] 11.4 Test localize honorific policy prompt. (REQ-9.3)
  - [ ] 11.5 Test omit honorific policy prompt. (REQ-9.3)
  - [ ] 11.6 Test glossary block and JP-EN policy coexist without duplicated/conflicting instructions. (REQ-9.4)
  - [ ] 11.7 Test non-JP-EN prompt does not include JP-EN policy. (REQ-1.4)

- [ ] 12. Add Golden Fixture Prompt Tests
  - [ ] 12.1 Add synthetic glossary compliance fixture. (REQ-9.5)
  - [ ] 12.2 Add paragraph preservation fixture. (REQ-9.6)
  - [ ] 12.3 Add ambiguous pronoun fixture. (REQ-9.7)
  - [ ] 12.4 Add dialogue/register fixture.
  - [ ] 12.5 Add chapter title plus body fixture.
  - [ ] 12.6 Add footnote/author note fixture.
  - [ ] 12.7 Ensure no test requires live provider calls. (REQ-9.8)

- [ ] 13. Add JSON Parser Compatibility Tests
  - [ ] 13.1 Test parser accepts `uncertainties` when present. (REQ-10.3)
  - [ ] 13.2 Test parser accepts `glossary_conflicts` when present. (REQ-10.3)
  - [ ] 13.3 Test parser accepts `style_notes` when present. (REQ-10.3)
  - [ ] 13.4 Test parser remains compatible when new fields are missing. (REQ-10.3)
  - [ ] 13.5 Test non-JSON output parsing still works. (REQ-10.2)

- [ ] 14. Backward Compatibility Checks
  - [ ] 14.1 Confirm existing prompt builder calls still work. (REQ-10.1)
  - [ ] 14.2 Confirm existing style presets remain compatible. (REQ-1.5, REQ-8.4)
  - [ ] 14.3 Confirm existing consistency modes remain compatible. (REQ-8.4)
  - [ ] 14.4 Confirm existing glossary injection behavior remains intact. (REQ-10.4)
  - [ ] 14.5 Confirm prompt length increase is bounded. (REQ-8.5)

- [ ] 15. Run Verification
  - [ ] 15.1 Run focused prompt builder tests.
  - [ ] 15.2 Run existing translation prompt tests.
  - [ ] 15.3 Run existing JSON parser tests.
  - [ ] 15.4 Run translation cache key tests.
  - [ ] 15.5 Run `ruff check` on changed backend files and tests.
  - [ ] 15.6 Run configured backend type checker if present.
  - [ ] 15.7 Fix test, lint, and type failures caused by this work.

- [ ] 16. Final Acceptance Review
  - [ ] 16.1 Verify JP-EN prompt policy applies to Japanese-to-English translations.
  - [ ] 16.2 Verify non-JP-EN prompts are unchanged unless explicitly enabled.
  - [ ] 16.3 Verify prompt includes guidance for glossary, honorifics, dialogue/register, ambiguity, chapter titles, notes, and formatting.
  - [ ] 16.4 Verify JSON mode supports optional uncertainty and glossary conflict fields when parser compatibility is ready.
  - [ ] 16.5 Verify prompt policy/template version is included in cache identity if prompt output changes.
  - [ ] 16.6 Verify existing glossary injection and style presets remain compatible.
  - [ ] 16.7 Verify snapshot and fixture tests pass without live provider calls.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 JP-EN Quality Policy | 2, 3, 11, 16 |
| REQ-2 Names/Terms/Glossary | 4, 11, 12, 14 |
| REQ-3 Honorific Policy | 5, 11, 14 |
| REQ-4 Dialogue/Register/Voice | 6, 12, 16 |
| REQ-5 Ambiguous Pronouns | 7, 9, 12, 13 |
| REQ-6 Titles/Notes/Formatting | 8, 9, 12 |
| REQ-7 JSON Schema Enhancements | 9, 13, 16 |
| REQ-8 Configurability/Rollout | 2, 3, 14 |
| REQ-9 Prompt Tests | 11, 12, 15 |
| REQ-10 Backward Compatibility | 10, 13, 14, 16 |

## Definition of Done

- [ ] JP-EN policy block exists and is applied only to intended language pair by default.
- [ ] Prompt includes explicit glossary, honorific, dialogue, ambiguity, title, note, and formatting rules.
- [ ] JSON mode supports optional review metadata fields or has a documented parser gating path.
- [ ] Prompt policy version is tracked for cache invalidation.
- [ ] Existing style presets, consistency modes, glossary injection, and non-JP-EN prompts remain compatible.
- [ ] Snapshot and fixture tests pass without live provider calls.

