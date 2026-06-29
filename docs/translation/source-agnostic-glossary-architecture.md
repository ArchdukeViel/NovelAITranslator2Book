# Source-Agnostic Novel Glossary Architecture

## 1. Summary

The glossary system defines novel-specific terminology contracts for translation,
review, publication, and reader display. Its job is to keep character names,
houses, places, organizations, titles, ranks, magic terms, and setting concepts
stable across all chapters of a novel.

Glossary ownership is per novel, not per source site. A glossary belongs to a
`novel_id` and must continue to apply if the novel is imported from Syosetu,
Kakuyomu, Novel18, a generic import, a mirror, or a future source adapter.

Source-specific logic is limited to discovery and extraction. Adapters may expose
raw source text, ruby/furigana, readings, source metadata, and candidate terms,
but canonical glossary storage, approval, prompt injection, QA, public reader
display, and user overrides remain source-agnostic.

This document is a contract proposal only. It does not add migrations, runtime
code, backend APIs, frontend UI, scraping, provider calls, or chapter repairs.

## 2. Scope

In scope:

- Canonical owner/admin glossary per `novel_id`.
- Translation prompt glossary injection for source-to-English translation jobs.
- Glossary consistency QA after translation and before publication decisions.
- Public reader glossary popovers for approved canonical terms.
- User-specific display overrides that apply only at render time.
- Future term discovery from raw source text, ruby/furigana, readings, and other
  adapter-provided candidate metadata.

The glossary system should support the pilot inconsistency audit in
`docs/translation/n2056dn-term-consistency-audit.md`, including drift such as
Vancleift / Vancroft / Vancraft, Albert / Alberto, Origin / Ori / Auri, Spirit
Realm / Spirit World, noble-title vocabulary, Kingdom Knights / Order of Knights,
and Ellen / Eren.

## 3. Non-goals

Out of scope:

- Rewriting user preferences into canonical translated chapter storage.
- Blind global find/replace across existing chapter text.
- Syosetu-only naming, routes, tables, services, or glossary assumptions.
- Replacing human owner approval for important canonical glossary decisions.
- Translating chapters in this phase.
- Calling Gemini, NVIDIA, Gemma, or any other provider in this phase.
- Scraping source sites or mutating translated chapter storage.
- Adding Alembic migrations, backend APIs, or frontend reader UI in this phase.

## 4. Data Model Proposal

These entities are proposed for a later migration phase. Field names should be
validated against the current SQLAlchemy model conventions before implementation.

### NovelGlossaryTerm

Canonical owner-approved term for one novel.

Proposed fields:

- `id`: primary key.
- `novel_id`: required foreign key or canonical novel identifier.
- `source_term`: source-language surface form.
- `source_reading`: optional reading, ruby, furigana, romaji, or adapter-derived
  pronunciation note.
- `source_language`: language code or label, for example `ja`.
- `category`: controlled category.
- `canonical_translation`: approved canonical English display/translation.
- `short_definition`: concise reader-facing explanation.
- `notes`: owner/admin notes for translation and review.
- `confidence`: manual or computed confidence level.
- `locked`: when true, translation prompt injection and QA treat the canonical
  translation as mandatory.
- `created_by_user_id`: owner/admin user that created the term, nullable for
  imports or seed data.
- `updated_by_user_id`: latest owner/admin user that changed the term.
- `created_at`: creation timestamp.
- `updated_at`: update timestamp.

Suggested categories:

- `character`
- `family_house`
- `place`
- `organization`
- `title`
- `rank`
- `skill`
- `magic`
- `species`
- `artifact`
- `concept`
- `other`

### NovelGlossaryAlias

Observed, accepted, disallowed, or source-side variant for a canonical term.

Proposed fields:

- `id`: primary key.
- `glossary_term_id`: required link to `NovelGlossaryTerm`.
- `alias_text`: variant text.
- `alias_type`: one of `observed_translation`, `disallowed_translation`,
  `accepted_variant`, or `source_variant`.
- `case_sensitive`: whether matching should preserve case sensitivity.
- `whole_phrase_only`: whether matching requires phrase boundaries.
- `notes`: owner/admin notes explaining use or risk.
- `created_at`: creation timestamp.
- `updated_at`: update timestamp.

Alias examples for the pilot novel include observed translations such as
`Vancleift`, `Vancroft`, and `Vancraft`; disallowed translations once the owner
chooses a canonical house name; and structured source variants for formal house
or family references.

### NovelGlossaryOccurrence

Detected source or translated occurrence used for review, QA, and repair
planning. This table may be named `DetectedGlossaryOccurrence` if implementation
keeps candidate discovery separate from approved glossary records.

Proposed fields:

- `id`: primary key.
- `novel_id`: required novel scope.
- `glossary_term_id`: optional link once a candidate is matched to a term.
- `chapter_id`: chapter where the occurrence was found.
- `paragraph_id`: optional paragraph reference when available.
- `chunk_id`: optional translation chunk reference when available.
- `surface_text`: exact matched text.
- `source_context`: short source-side context snippet.
- `translated_context`: short translated context snippet.
- `detected_translation`: observed English rendering when available.
- `detection_source`: `source_text`, `translated_text`, `qa`, `manual`, or
  adapter-specific discovery label.
- `confidence`: detection confidence.
- `created_at`: detection timestamp.

### UserGlossaryOverride

Per-user display preference for a term in one novel.

Proposed fields:

- `id`: primary key.
- `user_id`: required public user account.
- `novel_id`: required novel scope.
- `glossary_term_id`: required canonical glossary term.
- `preferred_translation`: selected approved display variant.
- `custom_translation`: optional private custom display string.
- `enabled`: whether this override is active.
- `created_at`: creation timestamp.
- `updated_at`: update timestamp.

The uniqueness rule should prevent more than one active preference row for the
same `(user_id, novel_id, glossary_term_id)` tuple.

### GlossaryDecisionAudit

Optional owner/admin history table for decisions and reversions.

Proposed fields:

- `id`: primary key.
- `novel_id`: required novel scope.
- `glossary_term_id`: optional term link.
- `actor_user_id`: owner/admin user that made the change.
- `action`: `created`, `updated`, `locked`, `unlocked`, `alias_added`,
  `alias_marked_disallowed`, `override_promoted`, or similar.
- `before`: structured previous value.
- `after`: structured new value.
- `reason`: short owner/admin reason.
- `created_at`: audit timestamp.

## 5. Source-Agnostic Boundaries

Syosetu, Kakuyomu, Novel18, generic imports, and future adapters may expose raw
text, ruby/furigana, readings, chapter structures, and source metadata
differently. They may also produce source term candidates with different levels
of confidence.

Once a term is extracted or proposed, all canonical behavior is source-agnostic:

- Storage is scoped by `novel_id`, not by `source_key` or source URL.
- Prompt injection consumes approved `NovelGlossaryTerm` records and relevant
  aliases without caring which adapter found them.
- Glossary QA checks translated text against the same canonical terms for every
  source.
- Public reader popovers render approved terms through public glossary reads.
- User overrides are saved by account and novel, never by source site.

Future source adapters should only need to provide raw text, optional readings,
and candidate terms. They should not require custom glossary tables, source-bound
glossary APIs, or separate reader behavior.

## 6. Translation Pipeline Integration

Glossary injection should happen during prompt construction, before provider
calls, and should be preserved across provider fallback. Existing architecture
already treats `glossary_hash` as part of translation metadata, so future
implementation should continue snapshotting glossary inputs for reproducibility.

Proposed behavior:

- Build a compact glossary block per chapter or chunk.
- Select only terms relevant to the source text when prompt budget is tight.
- Prioritize locked terms, recently observed terms, high-confidence terms, and
  terms whose `source_term` or source aliases appear in the current chapter.
- Include source term, reading, canonical English, category, and concise notes
  when useful.
- Include disallowed variants selectively when they prevent known drift, such as
  preventing `Vancroft` or `Vancraft` after a canonical house name is approved.
- Avoid flooding the prompt with every alias for every term.
- Treat locked terms as mandatory constraints.
- Ensure provider fallback uses the same glossary snapshot and constraints, not
  a newly broadened or narrowed glossary.
- Record enough metadata to identify the glossary snapshot used for a translation
  job, including a stable hash and selected term IDs.

Example prompt fields for one term:

```text
Source: <source_term>
Reading: <source_reading>
Category: family_house
Use: House Vanclyft
Avoid: Vancroft; Vancraft
Notes: Use family/house phrasing by context.
Locked: yes
```

The exact formatting belongs in prompt-builder implementation, not in API
routers or React components.

## 7. Glossary QA

Glossary QA should run after provider output and before publication decisions.
It should produce structured findings rather than directly rewriting chapter
text.

Checks:

- Canonical locked term appears where expected from source occurrences.
- Disallowed alias is not used in translated output.
- Inconsistent variants are detected across a chapter, batch, or novel.
- Accepted variants are permitted only when their alias rules allow them.
- Category-specific rules are applied where useful, for example noble ranks and
  formal house names.
- False positives are avoided through phrase-level matching, boundaries, and
  context windows.

Severity proposal:

- `blocker`: locked term violation that changes identity, rank, or core setting
  meaning; should fail publishing until reviewed or repaired.
- `warning`: likely inconsistency or unapproved alias; owner can publish with
  acknowledgment.
- `info`: observed variant, candidate occurrence, or context note that does not
  block publishing.

Publishing should fail only for configured `blocker` findings. Early phases may
warn only until the owner approves canonical names and the QA false-positive rate
is understood.

## 8. Existing Chapter Repair Strategy

Chapters 1-7 of Syosetu `n2056dn` should eventually be repaired through an
approved glossary, not by naive global replacement.

Repair strategy:

- Wait for owner approval of canonical names and title decisions from the audit.
- Use approved glossary terms and disallowed aliases as repair constraints.
- Inspect source and translated context before changing a passage.
- Prefer targeted chapter repair or glossary-aware postprocess over raw
  find/replace.
- Preserve paragraph IDs, marker protocol, chapter structure, and reader layout.
- Verify repairs with glossary QA and regular translation QA before publishing.

Examples requiring context include noble ranks where `duke`, `marquess`, and
house terminology depend on the exact source term, and names where the owner may
choose between source fidelity and existing public text.

## 9. Public Reader Glossary Popover

Public reader glossary behavior should be reader-facing and lightweight.

Proposed UI behavior:

- Highlight the first occurrence of approved glossary terms subtly.
- Make highlighted terms clickable or tappable.
- Show a floating popover near the term, with mobile-safe placement.
- Display source term, reading, canonical translation, category, short
  definition, and approved notes.
- Show observed variants when helpful and safe for readers.
- Offer a user preference selector for signed-in users.
- Allow signed-out users to view canonical glossary information but not save
  overrides.
- Avoid visual noise by limiting repeated highlights after the first occurrence
  or offering a reader preference for highlight intensity.

Reader UI should consume public API data and render-time display helpers. It
should not own glossary approval, scheduler, provider, storage, or authorization
policy.

## 10. User Overrides

User overrides are private reader display preferences.

Rules:

- User preferences apply at render time only.
- Canonical stored translated chapter text remains unchanged.
- Per-user choices are saved by account, using backend session identity.
- Overrides apply only to the same `novel_id`.
- Signed-out users cannot save overrides.
- Custom display should be allowed only where replacement is safe.
- Overrides should avoid grammar-breaking replacements.
- Owner-approved variants should be easier and safer than arbitrary custom text.

Render-time application should prefer structured term spans or precomputed
occurrence metadata over broad text replacement. If a term has possessive,
plural, title-case, or phrase-dependent forms, the override should either use
explicit alias rules or be disabled for unsafe contexts.

User overrides must not become authorization shortcuts. The backend must infer
the user from the session, not from client-provided user IDs.

## 11. Matching and Replacement Safety

Glossary matching should be conservative.

Rules:

- No blind common-word replacement.
- Prefer phrase-level matching over isolated short-token matching.
- Use word-boundary and punctuation handling for Latin text.
- Handle Japanese/source terms separately from English translated text.
- Possessive and plural forms require explicit handling.
- Case sensitivity should be configurable per alias.
- Common terms and ambiguous titles require category and context checks.
- Structured aliases should cover forms such as `House Vancroft`,
  `House Vancroft's`, and `Vancroft family`.
- Replacement must preserve paragraph IDs and marker protocol.

QA may flag suspicious matches without mutating content. Any repair stage should
operate on approved occurrences and keep a reviewable diff.

## 12. Admin Workflow

Owner/admin glossary workflow:

- Detect or import candidate terms for a novel.
- Review candidate terms with source and translated context.
- Approve canonical terms and categories.
- Add source readings, short definitions, notes, and aliases.
- Lock important terms that must be enforced in prompts and QA.
- Mark variants as accepted, observed, source variants, or disallowed.
- Run glossary QA before publishing more chapters.
- Review QA findings and either repair, approve with warning, or defer.
- Audit important decisions so later repairs can explain why a term changed.

The admin route layer should remain thin in future implementation. Review,
approval, QA, and repair planning should live in service/orchestration layers.

## 13. API Surface Proposal

No APIs are implemented in this phase. Proposed future routes and types are
listed to guide later scoped work.

Admin routes:

- `GET /api/admin/novels/{novel_id}/glossary`
- `POST /api/admin/novels/{novel_id}/glossary`
- `PATCH /api/admin/novels/{novel_id}/glossary/{term_id}`
- `DELETE /api/admin/novels/{novel_id}/glossary/{term_id}`
- `POST /api/admin/novels/{novel_id}/glossary/{term_id}/aliases`
- `PATCH /api/admin/novels/{novel_id}/glossary/aliases/{alias_id}`
- `POST /api/admin/novels/{novel_id}/glossary/qa`
- `GET /api/admin/novels/{novel_id}/glossary/occurrences`

Public routes:

- `GET /api/public/novels/{novel_id}/glossary`
- `GET /api/public/novels/{novel_id}/chapters/{chapter_id}/glossary`

User override routes:

- `GET /api/user/glossary-overrides?novel_id={novel_id}`
- `POST /api/user/glossary-overrides`
- `PATCH /api/user/glossary-overrides/{override_id}`
- `DELETE /api/user/glossary-overrides/{override_id}`

Translation/job contract additions:

- Translation job accepts or resolves a glossary snapshot for the target
  `novel_id`.
- Job metadata includes selected term IDs, alias IDs where relevant,
  `glossary_hash`, and glossary snapshot timestamp.
- Provider fallback preserves the same glossary snapshot.

Types should use canonical names such as `novel_id`, `chapter_id`,
`paragraph_id`, `chunk_id`, `provider_key`, `provider_model`, `activity_id`,
`job_id`, and `request_id`.

## 14. Phase Roadmap

Proposed phases after this architecture:

1. `NOVEL-GLOSSARY-DATA-MODEL-1`: add database models, migrations, repository
   boundaries, and tests for novel-scoped glossary terms, aliases, occurrences,
   and optional audit history.
2. `NOVEL-GLOSSARY-SEED-N2056DN-1`: seed approved or pending glossary records
   from the `n2056dn` audit after owner decisions.
3. `TRANSLATION-GLOSSARY-INJECTION-1`: integrate approved glossary snapshots
   into prompt construction and provider fallback.
4. `TRANSLATION-GLOSSARY-QA-1`: add structured glossary QA findings and publish
   gating policy.
5. `ADMIN-GLOSSARY-MANAGEMENT-1`: add owner/admin review and management APIs and
   UI.
6. `PUBLIC-READER-GLOSSARY-POPOVER-1`: add public read APIs, reader term spans,
   and glossary popovers.
7. `USER-GLOSSARY-OVERRIDES-1`: add per-user override storage and render-time
   display behavior.
8. `EXISTING-CHAPTER-GLOSSARY-REPAIR-1`: repair chapters 1-7 with approved
   terms, context review, and QA.
9. Resume Syosetu translation with glossary constraints enabled for chapter 8
   and later.

Each phase should preserve the backend/frontend contract discipline from
`docs/architecture/architecture.md` and avoid mixing database, translation,
admin UI, and public reader work unless explicitly scoped together.

## 15. Open Decisions

Owner approval needed:

- Canonical names from the `n2056dn` audit, especially the house name, Albert
  vs Alberto, Ellen vs Eren, Ori vs Auri, spirit realm/polity naming, noble
  title style, and Order of Knights naming.
- Whether public readers can submit glossary suggestions.
- Whether user overrides are private only or can be promoted into owner
  suggestions.
- How aggressive public reader highlighting should be.
- Whether glossary QA failures should block publishing immediately or begin as
  warnings until confidence improves.
- Whether arbitrary custom user override text is allowed, or only owner-approved
  variants are selectable.
- Whether occurrence detection should be persisted for every chapter or generated
  on demand for public reader display.
