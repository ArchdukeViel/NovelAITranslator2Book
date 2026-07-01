# Kakuyomu 16817330655991571532 Term Consistency Audit

## 1. Purpose

This audit identifies glossary candidates and visible terminology drift for the
saved Kakuyomu novel `16817330655991571532`.

This phase does not implement the glossary system and does not decide final
canonical terms unless an issue is obvious and evidence-backed. Terms with
uncertain source readings, later-story risk, or insufficient evidence are marked
for owner/admin review instead of being silently canonized.

The audit protects the source-agnostic glossary architecture from becoming
Syosetu-only. The same future per-novel glossary system must support this
Kakuyomu novel and Syosetu N2056DN.

## 2. Novel Identity

| Field | Value |
|---|---|
| Source | Kakuyomu |
| Source novel ID | `16817330655991571532` |
| Platform novel identity | `16817330655991571532` |
| Public slug / storage slug | `that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale` |
| Source URL | `https://kakuyomu.jp/works/16817330655991571532` |
| Source title from local metadata | `転生したら世界樹だった件【コミカライズ1巻発売中】` |
| Translated title from local metadata | `That Time I Was Reincarnated as a World Tree [Comic Vol. 1 Now On Sale]` |
| Current translated chapter count | 5 |
| Local metadata chapter entries | 88 |
| Metadata status | `ongoing` |
| Public DB publication flag | Unconfirmed from local file metadata in this phase |

## 3. Local Evidence Inspected

Read-only local evidence inspected:

- `docs/translation/source-agnostic-glossary-architecture.md`
- `docs/translation/saved-novel-glossary-inventory.md`
- `docs/translation/n2056dn-glossary-seed-decisions.md`
- `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/metadata.json`
- `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/chapters/1.json`
- `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/chapters/2.json`
- `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/chapters/3.json`
- `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/chapters/4.json`
- `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/chapters/5.json`
- Folder listing for
  `storage/novel_library/novel/that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale/`

Local folder structure includes `chapters/`, `checkpoints/`, `metadata_backups/`,
`state/`, and `metadata.json`. The chapter folder contains additional numbered
chapter bundles, but this audit intentionally inspected metadata and only the
five chapter bundles in scope for the current translated-count audit: chapters
1-5. Source text is present inside those same chapter bundles for chapters 1-5
and was inspected only for glossary provenance.

No `.env`, credentials, DB content, provider requests, external sites, or
runtime mutation were inspected or touched.

## 4. Candidate Glossary Terms

| Surface term / observed English | Japanese source term if locally available | Term type | Chapters observed | Consistency status | Suggested canonical direction | Notes |
|---|---|---|---|---|---|---|
| `World Tree` | `世界樹` | place / concept / species-like identity | 3, 4 | consistent, high risk | Keep `World Tree` unless owner prefers title-specific style | Core title-derived concept. Local translated text uses `World Tree` repeatedly in chapter 4. |
| `World Sapling` | `世界樹` / young-tree context also includes `若木` | concept / growth stage | 3 | uncertain | Needs owner/admin review | Chapter 3 uses `World Sapling`, while chapter 4 strongly uses `World Tree`. It may be contextual, not drift. |
| `sapling` | `若木` | growth stage / generic term | 2, 3, 4, 5 | consistent enough | Keep generic `sapling` for non-title contexts | Frequent lower-case generic usage; should not be over-glossarized unless QA false positives are avoidable. |
| `Pocott Village` / `Pocott` | `ポコット` | place | 3 | possible drift | Needs owner/admin review; likely choose one village spelling | Chapter 3 uses `Pocott`; later chapters use `Pokot`. This is the clearest observed drift. |
| `Pokot Village` / `Pokot` | `ポコット` | place | 4, 5 | possible drift | Needs owner/admin review; likely choose one village spelling | Same apparent source place as `Pocott`, but rendered differently in chapters 4-5. |
| `Alto Gilbert` / `Alto` | `アルト`; `ギルバート` | person | 3, 4 | consistent | Keep `Alto Gilbert` / `Alto` | Recurring character. No visible drift in translated chapters 3-4. |
| `Guld Pocott` / `Guld` | `グルド`; likely paired with `ポコット` | person | 3 | possible drift / source check needed | Needs owner/admin review | Chapter 3 uses `Guld`. Chapter 4 mentions `Gurd`, which may be the same person/family line or a related name. |
| `Gurd` | `グルド` appears locally in raw-source term scan | person | 4 | possible drift | Needs source check | Chapter 4 says `Gurd, the mayor of Pokot Village`; this may be a drift from `Guld` or a distinct older relative. Do not decide without context. |
| `Bilg` | `ビルグ` | person | 4 | consistent in available evidence | Needs owner/admin review if recurring | Appears as the son of `Gurd` in chapter 4. Could become important if later chapters use the family. |
| `Beatrice` | `ベアトリス` | person | 3, 4 | consistent | Keep `Beatrice` if owner accepts | Low current drift; recurring character relation to Alto/Jill. |
| `Jill` | `ジル` | person | 4 | consistent | Keep `Jill` if owner accepts | Important chapter 4 character and likely future recurring name. |
| `Slime` / `slime` | `スライム` | species | 3, 4 | consistent | Keep `slime`; protect `Slime King` as species/rank term | Common species term. Usually lower-case except formal species/rank phrase. |
| `Slime King` | `スライムキング` | species / rank | 4 | consistent, high risk | Keep `Slime King` if owner accepts | Evolution/species rank term; likely glossary-protect to avoid `King Slime` drift. |
| `White Wolves` | Source term not confirmed beyond local wolf term `狼` | species | 5 | consistent, source check needed | Needs source check | Could be a named evolved species. The raw scan confirms wolf-related source terms but exact compound should be verified before canon. |
| `skill` / `Skill` | `スキル` | magic_system | 3, 4 | consistent enough | Keep `skill`; protect specific skill names | System term appears around coming-of-age ceremony, ranks, and status. |
| `Protection of the World Tree (UR)` | Source contains `世界樹` and skill context; exact full source phrase needs source check | skill name | 3 | possible drift | Needs owner/admin review | Chapter 3 names Alto's skill `Protection of the World Tree (UR)`. |
| `Blessing of the World Tree (UR)` | `世界樹の加護` found locally in source scan | skill name | 4 | possible drift | Likely prefer `Blessing of the World Tree`, but needs review | Chapter 4 uses `Blessing of the World Tree`; this likely refers to the same skill as chapter 3's `Protection of the World Tree`. |
| `Status Open` | `ステータス` | magic_system / phrase | 3 | consistent | Keep if owner accepts | Repeated command/system phrase in chapter 3. |
| `UR`, `N-rank`, `N` | Source rank notation locally present through translated text; source phrase needs later schema-independent handling | rank / magic_system | 3, 4 | consistent enough | Keep rank notation as-is for now | Rank notation is compact and visible. QA should avoid treating single-letter ranks as general words. |
| `Woodcutter (N)` | `きこり` | skill name | 3 | consistent | Needs owner/admin review if recurring | Specific skill name. Low drift so far. |
| `Sword Saint` | `剣聖` | skill name / title | 3 | consistent | Needs owner/admin review if recurring | Specific skill/title phrase. High fantasy term that could drift later. |
| `magic power` | `魔力` | magic_system | 4, 5 | consistent | Keep `magic power` unless style guide prefers `mana` | Recurs around monster nutrients/fertilizer. Could conflict with other novels' `mana` style, so per-novel glossary should own it. |
| `Fuuka` | Source term not confirmed in this audit summary | person | 1 | uncertain | Needs owner/admin review if recurring | Chapter 1 translated text has recurring `Fuuka`; not enough evidence in the first five chapters to judge drift. |

## 5. Drift Findings

Observed drift across the five translated chapters:

- Place name drift: `Pocott` / `Pocott Village` in chapter 3 versus
  `Pokot` / `Pokot Village` in chapters 4-5. This is the strongest
  evidence-backed inconsistency and should get owner/admin review.
- Skill name drift: chapter 3 uses `Protection of the World Tree (UR)`, while
  chapter 4 uses `Blessing of the World Tree (UR)`. Local source scanning found
  `世界樹の加護`, which makes `Blessing of the World Tree` likely, but this should
  be confirmed before seed decisions.
- Possible person-name drift: `Guld` in chapter 3 and `Gurd` in chapter 4 may be
  a spelling drift, family relation, or separate character. Chapter 4 also
  introduces `Bilg`. This needs source/context review before deciding.

No clear drift was found for `Alto`, `Alto Gilbert`, `Beatrice`, `Jill`,
`World Tree`, `Slime King`, `White Wolves`, `Status Open`, `UR`, `N-rank`,
`Woodcutter`, `Sword Saint`, or `magic power` within chapters 1-5.

Do not invent additional drift beyond these observed items.

## 6. High-Risk Terms

Terms that should probably be glossary-protected even where currently
consistent:

- `World Tree`: title-derived central concept and likely identity/place/species
  term.
- `Pocott` / `Pokot`: visible place-name drift already exists.
- `Alto Gilbert`, `Beatrice`, `Jill`, `Guld` / `Gurd`, and `Bilg`: character and
  family names are likely to recur and are easy for providers to respell.
- `Blessing of the World Tree` / `Protection of the World Tree`: likely same or
  related skill name; high risk because it combines title terminology and system
  terminology.
- `Slime King` and `White Wolves`: evolved species/rank terms that can drift
  into alternate fantasy renderings.
- `Status Open`, `UR`, `N-rank`, `Woodcutter`, `Sword Saint`, and `magic power`:
  magic/system terms and rank notation should stay stable.

## 7. Source-Agnostic Notes

This Kakuyomu audit should feed the same future per-novel glossary system as
N2056DN:

- Glossary owner should be the platform/internal novel identity
  `16817330655991571532`.
- Kakuyomu source novel ID and source URL should be provenance, not the glossary
  owner.
- Approved terms should later support prompt injection, glossary QA, admin
  review, existing chapter repair review, and public reader popovers.
- The Kakuyomu source adapter may expose raw text, source URLs, and source term
  candidates, but it should not own canonical English terms.
- Future schema/API names should remain source-agnostic and should not create a
  Kakuyomu-only glossary path.

## 8. Comparison With N2056DN

N2056DN already has severe known drift across names, noble ranks, organization
names, and spirit-realm terminology. That audit needs canonical owner/admin seed
decisions before more translation.

This Kakuyomu novel has a different risk shape. The first five translated
chapters show less broad drift, but they include early visible inconsistencies in
place spelling and likely skill-name rendering. The glossary model must support
both cases: heavy drift repair for N2056DN and lighter but still important
terminology protection for Kakuyomu.

The same architecture must cover Syosetu, Kakuyomu, generic imports, and future
source adapters without source-specific ownership.

## 9. Recommended Seed Decisions Needed

Owner/admin review checklist:

- Choose canonical village spelling: `Pocott` vs `Pokot`.
- Decide whether `Protection of the World Tree (UR)` and
  `Blessing of the World Tree (UR)` are the same skill, and choose the canonical
  English if so.
- Determine whether `Guld` and `Gurd` are drift or distinct characters.
- Confirm whether `Bilg` is the intended spelling for the chapter 4 character.
- Confirm whether `World Tree` should be locked as the title-derived core term.
- Confirm whether `Slime King`, `White Wolves`, `Status Open`, `UR`, `N-rank`,
  `Woodcutter`, `Sword Saint`, and `magic power` should be protected in the
  initial Kakuyomu seed set.
- Decide whether `magic power` should remain the per-novel style, or whether
  this novel should use `mana` in later translations.

There is enough evidence for a small Kakuyomu seed decision phase, mainly
because of `Pocott` / `Pokot` and `Protection of the World Tree` / `Blessing of
the World Tree`.

## 10. Recommended Next Phase

Recommended next phase:

`GLOSSARY-KAKUYOMU-SEED-DECISIONS-1`

Prefer caution. The Kakuyomu audit found enough candidate terms needing
owner/admin decisions that schema planning should wait until these source-
agnostic seed requirements are reviewed.
