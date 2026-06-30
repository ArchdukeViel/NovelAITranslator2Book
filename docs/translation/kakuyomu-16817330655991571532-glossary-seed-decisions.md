# Kakuyomu 16817330655991571532 Glossary Seed Decisions

## 1. Purpose

This is the initial seed decision sheet for Kakuyomu novel
`16817330655991571532`. It turns the audited chapter 1-5 terminology findings
into practical owner/admin review items that can later become approved
per-novel glossary entries.

This document does not implement the glossary system. It does not create schema,
migrations, backend services, admin UI, prompt injection, QA checks, repair
logic, provider calls, scraping, translation, storage mutation, or DB mutation.

These decisions are intended to become approved per-novel glossary entries after
owner/admin review. Uncertain terms remain owner/admin decisions and must not be
silently invented, forced, or treated as approved.

## 2. Novel Identity

| Field | Value |
|---|---|
| Source | Kakuyomu |
| Source novel ID | `16817330655991571532` |
| Platform novel identity | `16817330655991571532` |
| Public slug | `that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale` |
| Source URL | `https://kakuyomu.jp/works/16817330655991571532` |
| Source title from local metadata | `è»¢ç”Ÿã—ãŸã‚‰ä¸–ç•Œæ¨¹ã ã£ãŸä»¶ã€ã‚³ãƒŸã‚«ãƒ©ã‚¤ã‚º1å·»ç™ºå£²ä¸­ã€‘` |
| Translated title from local metadata | `That Time I Was Reincarnated as a World Tree [Comic Vol. 1 Now On Sale]` |
| Current audited translated chapter range | Chapters 1-5 |
| Metadata status | `ongoing` |
| Public DB publication flag | Not confirmed in the audit |
| Source-term evidence note | Japanese source-term evidence may be limited by mojibake in local files/docs |

## 3. Decision Status Legend

| Status | Meaning |
|---|---|
| `APPROVED` | Owner/admin has explicitly accepted this canonical form. No terms are marked approved in this phase unless already explicit. |
| `RECOMMENDED` | Available audit evidence supports this as the safest seed candidate, but owner/admin can still override before implementation. |
| `NEEDS_OWNER_DECISION` | Current evidence is insufficient or the term affects story/worldbuilding enough that owner/admin must decide. |
| `REJECTED_ALIAS` | Alias should be treated as banned for a specific canonical term once that term is approved or recommended. |
| `DEPRECATED` | Older rendering should be phased out but may need context-aware repair rather than automatic replacement. |

## 4. Conservative Decision Rules

- If one spelling is clearly dominant and evidence-backed, mark it
  `RECOMMENDED`.
- If the audit clearly identifies one form as wrong, mark it `REJECTED_ALIAS` or
  `DEPRECATED`.
- If the term cannot be confidently decided from available evidence, mark it
  `NEEDS_OWNER_DECISION`.
- Do not invent source Japanese terms from mojibaked text.
- Do not pretend skill names or character names are solved if the audit evidence
  is weak.
- Do not use source adapter identity as glossary ownership.
- Do not treat this document as permission to rewrite existing chapters.

## 5. Canonical Seed Glossary Table

| Concept / Japanese source term if reliable locally | Term type | Canonical English | Allowed aliases | Rejected/banned aliases | Status | Reason | Evidence / observed drift | Notes for prompt injection |
|---|---|---|---|---|---|---|---|---|
| Core title concept; source term is mojibaked locally but audit associates it with `World Tree` | `concept` / `place` / `identity` | `World Tree` | None initially | None initially | `RECOMMENDED` | The translated title and chapter 4 consistently use `World Tree`; it is central enough to protect even without broad drift. | `World Tree` appears repeatedly in chapter 4; title uses `World Tree`. Chapter 3 has `World Sapling`, likely contextual. | Enforce `World Tree` for the core title/world concept. Do not force generic lower-case `sapling` contexts to become `World Tree`. |
| Village/place name; source term is mojibaked locally, audit records the same apparent source for both variants | `place` | `Pocott` | `Pocott Village` | `Pokot`; `Pokot Village` | `APPROVED` | Owner/admin chose `Pocott` as canon and rejected `Pokot`. | `Pocott` / `Pocott Village` appears in chapter 3; `Pokot` / `Pokot Village` appears in chapters 4-5. | Enforce `Pocott`; flag `Pokot`. |
| Alto Gilbert / Alto; source terms are mojibaked locally | `character` | `Alto Gilbert`; short form `Alto` | `Alto` for short references | None initially | `RECOMMENDED` | Recurring character name is consistent in chapters 3-4 and safe to seed as a protection term. | `Alto` appears repeatedly in chapters 3-4; `Alto Gilbert` appears in chapter 3. | Use full name for introductions/formal references; allow `Alto` for normal narration/dialogue. |
| Beatrice; source term is mojibaked locally | `character` | `Beatrice` | None initially | None initially | `RECOMMENDED` | Name is consistent in available evidence and likely recurring. | `Beatrice` appears in chapters 3-4 without visible drift. | Include only when relevant to chapter context; no banned aliases yet. |
| Jill; source term is mojibaked locally | `character` | `Jill` | None initially | None initially | `RECOMMENDED` | Name is consistent in available evidence and important in chapter 4. | `Jill` appears repeatedly in chapter 4 without visible drift. | Include for chapters where Jill appears; no banned aliases yet. |
| Gurd / Guld; source term is mojibaked locally | `character` | `Gurd` | None initially | `Guld` | `APPROVED` | Owner/admin chose `Gurd` as canon and rejected `Guld`. | `Guld Pocott` / `Guld` appears in chapter 3; `Gurd` appears in chapter 4 as mayor of the village. | Enforce `Gurd`; flag `Guld`. |
| Bilg; source term is mojibaked locally | `character` | `Bilg` | None initially | None initially | `NEEDS_OWNER_DECISION` | Evidence is internally consistent but limited to chapter 4, and relation to `Gurd` should be confirmed. | `Bilg` appears repeatedly in chapter 4. | Do not enforce as locked yet; candidate for seed after owner confirmation. |
| World Tree skill name; source term is mojibaked locally but audit notes likely `World Tree` plus protection/blessing context | `skill` / `magic_system` | `Blessing of the World Tree` | `Blessing of the World Tree (UR)` when rank notation is present | `Protection of the World Tree`; `Protection of the World Tree (UR)` | `APPROVED` | Owner/admin chose `Blessing of the World Tree` because it is clearer as a fantasy skill/status effect, while `Protection of the World Tree` is ambiguous. If reliable Japanese source evidence later proves a strict protection/guardian sense, this can be revisited. | `Protection of the World Tree (UR)` appears in chapter 3; `Blessing of the World Tree (UR)` appears in chapter 4. | Enforce `Blessing of the World Tree`; flag `Protection of the World Tree`. |
| Slime / Slime King; source term is mojibaked locally | `species` / `rank` | `Slime King` for the rank/species phrase; `slime` for generic species | `slime` for generic lower-case species references | `King Slime` should be treated as a warning alias once owner accepts `Slime King` | `RECOMMENDED` | `Slime King` is stable in chapter 4 and is a high-risk fantasy species/rank term. | `Slime King` appears repeatedly in chapter 4; `slime` appears generically in chapters 3-4. | Enforce `Slime King` for the named rank/species phrase; do not force every generic `slime` into title case. |
| White Wolves; exact source compound not reliable locally | `species` | `White Wolves` | Singular `White Wolf` only if grammar requires it | None initially | `NEEDS_OWNER_DECISION` | The term is consistent in chapter 5 but exact source compound and whether it is a formal species name need confirmation. | `White Wolves` appears in chapter 5. | Treat as a warning candidate until owner confirms whether it should be locked. |
| Status Open | `magic_system` / `phrase` | `Status Open` | None initially | None initially | `RECOMMENDED` | Repeated command/system phrase is stable and suitable for prompt protection. | `Status Open` appears in chapter 3. | Enforce exact phrase when used as the system command. |
| Rank notation | `rank` / `magic_system` | `UR`; `N-rank`; contextual `N` | None initially | None initially | `RECOMMENDED` | Rank notation appears stable and should remain compact. | `UR` appears in chapters 3-4; `N-rank` appears in chapter 3. | Preserve rank notation; QA must avoid treating single-letter `N` as a general glossary hit. |
| Woodcutter (N) | `skill` | `Woodcutter (N)` | None initially | None initially | `RECOMMENDED` | Specific skill name is stable in chapter 3 and low-risk to preserve as observed. | `Woodcutter (N)` appears in chapter 3. | Include only where this skill appears; no banned aliases yet. |
| Sword Saint | `skill` / `title` | `Sword Saint` | None initially | None initially | `RECOMMENDED` | High-fantasy skill/title phrase is stable in available evidence and likely easy to drift later. | `Sword Saint` appears in chapter 3. | Preserve phrase casing. |
| magic power | `magic_system` | `magic power` | None initially | `mana` should be a warning alias unless owner changes style | `RECOMMENDED` | Chapters 4-5 consistently use `magic power`; per-novel glossary should own this style choice. | `magic power` appears in chapters 4-5. | Use `magic power` for this novel unless owner later chooses `mana`. |
| Fuuka; exact source term not confirmed in audit summary | `character` | Needs owner confirmation: likely `Fuuka` if recurring | None until owner confirmation | None initially | `NEEDS_OWNER_DECISION` | Chapter 1 has repeated `Fuuka`, but the first five chapters do not provide enough evidence to judge recurrence or drift. | `Fuuka` appears in chapter 1. | Do not enforce until owner confirms recurrence/importance. |

## 6. Initial Recommended Decisions

Approved owner/admin decisions:

- Use `Pocott`; reject `Pokot`.
- Use `Gurd`; reject `Guld`.
- Use `Blessing of the World Tree`; reject `Protection of the World Tree`.

Recommended seed entries, subject to later owner/admin override:

- Use `World Tree` for the core title/world concept.
- Use `Alto Gilbert` for the full character name and `Alto` for short
  references.
- Use `Beatrice`.
- Use `Jill`.
- Use `Slime King` for the named species/rank phrase; keep generic `slime`
  lower-case where appropriate.
- Use `Status Open` for the system command phrase.
- Preserve rank notation such as `UR` and `N-rank`.
- Use `Woodcutter (N)` and `Sword Saint` for the observed skill/title phrases.
- Use `magic power` as the per-novel style unless the owner later chooses
  `mana`.

Not yet decided:

- Whether `Bilg`, `White Wolves`, and `Fuuka` should be locked in the initial
  seed set.

## 7. Prompt Injection Seed

Compact draft for future translation prompts. This block includes only
`RECOMMENDED` terms. It excludes unresolved terms as enforceable constraints.

```text
Kakuyomu 16817330655991571532 glossary constraints:
- Core concept/title term => World Tree. Use for the central world/tree concept; do not force generic sapling contexts.
- Village/place name => Pocott. Do not use Pokot.
- Alto Gilbert => Alto Gilbert. Use Alto for short references.
- Beatrice => Beatrice.
- Jill => Jill.
- Gurd => Gurd. Do not use Guld.
- Blessing of the World Tree => Blessing of the World Tree. Do not use Protection of the World Tree.
- Slime King => Slime King for the named species/rank phrase. Do not use King Slime unless owner changes this later.
- Status Open => Status Open for the system command phrase.
- Rank notation => preserve UR and N-rank formatting.
- Woodcutter (N) => Woodcutter (N).
- Sword Saint => Sword Saint.
- magic power => magic power. Do not switch to mana unless owner changes the style.

Unresolved, do not enforce yet:
- Bilg, White Wolves, and Fuuka need owner confirmation before locking.
```

## 8. QA Rules Seed

Future Kakuyomu glossary QA should:

- Flag banned aliases only after owner/admin approves the canonical term, such
  as `Pokot`, `Guld`, `Protection of the World Tree`, `King Slime` if `Slime
  King` is accepted, or `mana` if `magic power` remains the per-novel style.
- Flag inconsistent place names, especially use of banned `Pokot` where
  `Pocott` is expected.
- Flag inconsistent character names, especially use of banned `Guld` where
  `Gurd` is expected.
- Flag inconsistent skill/system names, especially use of banned `Protection of
  the World Tree` where `Blessing of the World Tree` is expected.
- Flag inconsistent species/rank/system terms such as `Slime King`, `White
  Wolves`, `Status Open`, `UR`, `N-rank`, `Woodcutter (N)`, `Sword Saint`, and
  `magic power`.
- Treat locked owner-approved violations as hard errors after approval.
- Treat unresolved terms, limited source evidence, and likely false positives as
  warnings until owner/admin decisions and source-aware matching exist.

## 9. Existing Chapter Repair Notes

Existing chapters 1-5 should not be globally find/replaced.

Any repair pass must be previewed and audited. Character names, place names,
skill names, species/rank terms, and system phrases require context-aware
replacement. Rejected aliases such as `Pokot`, `Guld`, and `Protection of the
World Tree` should be repaired only with context review, not with a blind global
replacement.

Repair should happen only after glossary backend/QA support or a dedicated
controlled manual repair phase. A repair phase should preserve paragraph
markers, reader layout, active translation version behavior, and public chapter
contracts.

## 10. Human Decisions Still Needed

- Confirm whether `Bilg` is the intended spelling and whether it should be
  locked.
- Confirm whether `White Wolves` is a formal species/group term and whether
  singular `White Wolf` should be an allowed grammar variant.
- Confirm whether `Fuuka` is recurring/important enough for the initial seed
  set.
- Confirm whether `magic power` should remain the per-novel style or whether
  later translations should use `mana`.
- Decide whether glossary QA should block publishing immediately for
  `RECOMMENDED` terms or only after owner/admin marks terms `APPROVED`.

## 11. Source-Agnostic Design Notes

This Kakuyomu seed decision sheet supports the same future glossary system as
N2056DN:

- Glossary owner should be the platform/internal novel identity
  `16817330655991571532`.
- Kakuyomu source novel ID, source URL, source title, and source adapter should
  be provenance, not glossary ownership.
- Approved terms should later support prompt injection, glossary QA, admin
  review, existing chapter repair review, and public reader popovers.
- The source adapter may expose raw text, source URLs, ruby/readings, and
  candidate terms, but it should not own canonical English terms.
- Schema/API names should remain source-agnostic and should not create a
  Kakuyomu-only glossary path.

## 12. Recommended Next Phase

Recommended next phase:

`GLOSSARY-BACKEND-SCHEMA-PLAN-1`

Backend schema planning is now safe because both Syosetu/N2056DN and Kakuyomu
have architecture, audit, and seed-decision evidence. The schema plan should
still distinguish `APPROVED` owner/admin decisions from merely `RECOMMENDED`
terms, unresolved terms, observed aliases, and rejected/banned aliases.

Schema planning should use this sheet to understand required data shapes:
approved terms, recommended terms, unresolved terms, aliases, warnings,
rejected/banned aliases, source provenance, owner approval states, and prompt/QA
behavior.
