# Saved Novel Glossary Inventory

## 1. Purpose

This inventory exists to keep the planned glossary implementation from becoming
Syosetu-specific. The glossary architecture must account for every saved
translated novel before database, schema, backend service, or reader work begins.

Both the Syosetu `n2056dn` novel and the saved Kakuyomu novel are already present
in local storage with translated chapters. Glossary ownership should therefore be
attached to platform novel identity, with source metadata treated as provenance,
not as the glossary owner.

This document is read-only planning. It does not decide canonical term spellings,
change schema, modify translations, scrape sources, call providers, or mutate
storage or database content.

## 2. Current Saved Novel Inventory

Inventory source: local file-backed storage metadata under
`storage/novel_library/novel/*/metadata.json` and translated chapter bundles
under each novel's `chapters/` directory.

| Internal/platform novel identity | Public slug / storage slug | Source adapter / site | Source novel ID or URL | Source title | Translated chapter count | Public availability status | Known glossary risk | Notes / uncertainty |
|---|---|---|---|---|---:|---|---|---|
| `n2056dn` | `my-father-is-a-hero-my-mother-is-a-spirit-and-i-am-a-reincarnator` | `syosetu_ncode` / Syosetu | `n2056dn`; `https://ncode.syosetu.com/n2056dn/` | Original Japanese title exists in metadata; translated title is `My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator.` | 7 | Audit says chapters 1-7 are translated and public; chapter 8 is unavailable. Metadata status is `completed`. | High. Known term drift is documented in `docs/translation/n2056dn-term-consistency-audit.md`. | Metadata contains 148 chapter entries. Public slug is stored as `storage_slug`; no separate `public_slug` field was populated in metadata. |
| `16817330655991571532` | `that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale` | `kakuyomu` / Kakuyomu | `16817330655991571532`; `https://kakuyomu.jp/works/16817330655991571532` | Original Japanese title exists in metadata; translated title is `That Time I Was Reincarnated as a World Tree [Comic Vol. 1 Now On Sale]` | 5 | Five translated chapter bundles are present locally. Metadata status is `ongoing`. Public DB publication flag was not confirmed from local file metadata. | Unknown. No term consistency audit exists yet. | Metadata contains 88 chapter entries. The current translated count remains 5. A Kakuyomu seed audit is needed before broad glossary rollout is considered complete. |

The inventory intentionally treats source URLs and source novel IDs as
provenance. They are useful for discovery and audit context, but they should not
be the primary key for glossary ownership.

## 3. Glossary Ownership Mapping

For each saved novel:

- Platform/internal novel record owns the glossary. Conceptually this is the
  platform novel identity, such as `novel_id` / DB `novels.slug` / storage
  metadata `novel_id`, depending on the final backend contract.
- Source metadata is provenance. `source_key`, `source_novel_id`, `source_url`,
  adapter-specific fields, and source titles explain where terms came from but
  should not own canonical glossary records.
- Translated chapters consume the glossary. Prompt injection, post-translation
  QA, and future repair workflows should read a glossary snapshot for the target
  platform novel before touching chapter text.
- The public reader is a display surface. Public popovers and user overrides
  should render approved glossary information for the platform novel without
  changing canonical stored translations.

For `n2056dn`, the glossary owner should be the platform novel identity
`n2056dn`, even though the visible slug is title-based and the provenance source
is Syosetu.

For the Kakuyomu work, the glossary owner should be the platform novel identity
`16817330655991571532`, even though the visible slug is title-based and the
provenance source is Kakuyomu.

## 4. Source-Agnostic Risk Review

Current structures that could tempt a source-specific glossary implementation:

- Source folder and storage slug names are title-based under
  `storage/novel_library/novel/`. They are convenient public/display paths, but
  title slugs can change and should not become glossary ownership.
- Source IDs are prominent. Syosetu uses `n2056dn`; Kakuyomu uses a long numeric
  work ID. A glossary model keyed directly by these source IDs would not handle
  mirrors, imports, merged records, or future adapter changes cleanly.
- Source adapter metadata differs. `source_key` is `syosetu_ncode` for the
  Syosetu novel and `kakuyomu` for the Kakuyomu novel. Future adapters may expose
  ruby, readings, source blocks, and source URLs differently.
- Public slug assumptions are risky. The public router can derive a slug from
  `storage_slug` or translated title, while DB-backed public catalog entries may
  use DB `Novel.slug`. Glossary APIs should avoid making public slug the only
  owner identity.
- Translated chapter storage layout is per novel folder and chapter bundle. This
  is a consumer layout for translation and reader output, not the correct place
  to encode source-specific glossary ownership.

No fixes are made in this phase. These are planning risks only.

## 5. N2056DN Glossary Risk Snapshot

The `n2056dn` audit found material term drift in translated chapters 1-7:

- Vancleift / Vancroft / Vancraft
- Albert / Alberto
- Origin / Ori / Auri
- Spirit Realm / Spirit World
- Duke / Ducal House / Marquisate / marquess
- Kingdom Knights / Order of Knights
- Ellen / Eren

These require owner/admin canonical decisions before future translation,
glossary seed data, prompt injection constraints, QA gating, or existing chapter
repair.

No canonical spellings are decided in this inventory phase.

## 6. Kakuyomu Glossary Risk Placeholder

The saved Kakuyomu novel is present locally with five translated chapter bundles.
No term drift audit was found or performed in this phase.

Do not invent Kakuyomu term problems from title or source metadata alone. The
Kakuyomu work needs its own seed audit before broad glossary implementation is
considered complete. That audit should inspect the saved source and translated
chapters, identify recurring names/terms, and recommend owner/admin decisions in
the same source-agnostic shape as the `n2056dn` audit.

## 7. Recommended Next Phases

1. `GLOSSARY-N2056DN-SEED-DECISIONS-1`
2. `GLOSSARY-KAKUYOMU-SEED-AUDIT-1`
3. `GLOSSARY-BACKEND-SCHEMA-PLAN-1`
4. `GLOSSARY-BACKEND-MIGRATION-1`
5. `GLOSSARY-ADMIN-CRUD-1`
6. `GLOSSARY-PROMPT-INJECTION-1`
7. `GLOSSARY-QA-1`
8. `GLOSSARY-EXISTING-CHAPTER-REPAIR-AUDIT-1`
9. `GLOSSARY-PUBLIC-POPOVER-1`
10. `GLOSSARY-USER-OVERRIDES-1`

Seed decisions and audits should come before schema/migration implementation so
the data model is shaped by both Syosetu and Kakuyomu saved novels, not only by
the pilot Syosetu case.

## 8. Explicit Non-Decisions

- No canonical term spellings are decided in this phase.
- No schema is implemented.
- No source-specific glossary ownership is accepted.
- No existing translations are modified.
- No backend API, frontend UI, migration, test, storage, or DB change is made.
