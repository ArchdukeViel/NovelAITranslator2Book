# Source-Agnostic Glossary Backend Schema Plan

## 1. Purpose

This phase plans the backend database schema for a source-agnostic per-novel
glossary before migrations or code are implemented.

Glossary ownership must attach to the platform/internal novel identity, not to a
source site, source adapter, source URL, or source novel ID. In the current DB
shape, that means glossary records should primarily reference `novels.id`, while
API layers may still resolve a public/storage slug to the DB novel row.

Source metadata is provenance only. Syosetu `n2056dn`, Kakuyomu
`16817330655991571532`, source URLs, local storage keys, source chapter numbers,
and source snippets can explain where evidence came from, but they should not
own canonical English glossary decisions.

This document is a plan only. It does not add migrations, SQLAlchemy models,
Pydantic schemas, API routes, tests, seed data, provider calls, scraping,
translation, storage mutation, DB mutation, or chapter repair.

## 2. Current Backend Context

Relevant backend concepts from local inspection:

- `Novel` is a DB-backed catalog model in `novels`. It uses integer primary key
  `id`, unique `slug`, title/source metadata, publication fields, counts, and
  timestamp fields. Glossary FK ownership should target `novels.id`, not source
  IDs or slugs.
- `Chapter` is a DB-backed metadata model in `chapters`. It uses integer primary
  key `id`, `novel_id` FK to `novels.id`, `chapter_number`, source URL, storage
  keys, and translation status fields. Glossary occurrence/QA references should
  prefer `chapters.id` when a DB chapter row exists, with optional chapter-number
  or storage-reference fields for local evidence.
- `User` is in `users` with role values `guest`, `user`, and `owner`. Dangerous
  admin routes use `require_role("owner")`. Glossary decisions and audit events
  should store nullable `created_by_user_id`, `updated_by_user_id`, or
  `actor_user_id` FKs to `users.id` where applicable.
- Existing public user data tables such as `library_items`, `reading_progress`,
  `reading_history`, and `reviews` use `users.id`, `novels.id`, and optional
  `chapters.id` FKs. User glossary display overrides should follow this pattern.
- Existing taxonomy models (`genres`, `tags`, `novel_genres`, `novel_tags`) are
  useful comparisons. They separate global labels from per-novel assignments and
  include origin/assignment metadata. Glossary entries should differ by being
  per-novel canonical decisions, not global labels.
- Admin taxonomy routes use owner-only dependencies, CSRF protection, DB session
  dependencies, and thin router logic. Future glossary admin routes should use
  the same route discipline but delegate decision, QA, and repair behavior to
  services.
- Public reader routes are guest-accessible and avoid exposing raw storage
  paths. Public glossary/popover routes must expose only public-safe fields.
- Alembic migrations use `op.create_table`, named PK/FK constraints through
  `op.f(...)`, explicit indexes, nullable timestamps, and reversible
  `downgrade()` blocks. Some migrations seed curated data, but glossary seed
  data should not be inserted in the base schema migration unless a later phase
  explicitly plans it.

Uncertainty:

- The DB `chapters` table has integer IDs and chapter numbers, while stored
  chapter bundles may also use source/storage chapter IDs such as `1.json`.
  Provenance and QA tables should support both DB chapter FKs and source/local
  chapter references.
- Public routes currently resolve novels by slug and storage metadata fallback.
  A later implementation phase must define the exact slug-to-`novels.id`
  resolution helper for glossary APIs.

## 3. Proposed Tables

### `novel_glossary_entries`

The canonical per-novel glossary entry. One row represents a term decision or
candidate for one novel.

Relationships:

- `novel_id` FK to `novels.id`, required.
- Optional `first_seen_chapter_id` / `last_seen_chapter_id` FKs to `chapters.id`.
- Optional `created_by_user_id` / `updated_by_user_id` FKs to `users.id`.
- Parent table for aliases, provenance, decision events, QA findings, and user
  display overrides.

### `novel_glossary_aliases`

Observed, allowed, rejected, banned, deprecated, or source-side variants for one
glossary entry.

Relationships:

- `glossary_entry_id` FK to `novel_glossary_entries.id`, required.
- Usually cascades on glossary entry delete.

### `novel_glossary_source_provenance`

Evidence/provenance rows showing where a candidate or decision came from across
source adapters, local storage, audits, and chapter contexts.

Relationships:

- `glossary_entry_id` FK to `novel_glossary_entries.id`, required.
- Optional `novel_id` FK for direct lookup and denormalized query speed.
- Optional `chapter_id` FK to `chapters.id`.

### `novel_glossary_decision_events`

Audit/history table for owner/admin decisions, automated candidate creation,
QA-driven changes, lock/unlock events, alias changes, merges, and deprecations.

Relationships:

- `glossary_entry_id` FK to `novel_glossary_entries.id`, nullable for bulk or
  failed events if useful.
- `novel_id` FK to `novels.id`, required.
- Optional `actor_user_id` FK to `users.id`.

### `novel_glossary_qa_findings`

Structured QA findings generated by future glossary QA or repair preview logic.
Findings should never directly mutate chapter text.

Relationships:

- `novel_id` FK to `novels.id`, required.
- Optional `chapter_id` FK to `chapters.id`.
- Optional `glossary_entry_id` FK to `novel_glossary_entries.id`.
- Optional `resolved_by_user_id` FK to `users.id`.

### Optional `user_glossary_display_overrides`

Per-user presentation preferences for public reader display. These are private
render-time preferences and must not mutate canonical translated chapter text.

Relationships:

- `user_id` FK to `users.id`, required.
- `novel_id` FK to `novels.id`, required.
- `glossary_entry_id` FK to `novel_glossary_entries.id`, required.

## 4. `novel_glossary_entries`

Proposed fields:

- `id`: integer primary key.
- `novel_id`: required FK to `novels.id`.
- `canonical_term`: source-side term label or neutral concept label. It may be
  source Japanese when reliable, or an internal concept label when source text
  is mojibaked or unavailable.
- `term_type`: enum string, for example `character`, `place`, `organization`,
  `title`, `rank`, `skill`, `magic`, `species`, `item`, `concept`,
  `family_house`, `phrase`, `other`.
- `approved_translation` or `translated_term`: canonical English term to use
  when status/enforcement requires it. Prefer one name; `approved_translation`
  is clearer for translation constraints, while `translated_term` is shorter.
- `status`: enum string such as `candidate`, `recommended`, `approved`,
  `rejected`, `deprecated`.
- `enforcement_level`: enum string such as `none`, `suggest`, `warn`,
  `error`, `blocker`; this lets `APPROVED` and `RECOMMENDED` terms behave
  differently in QA/publishing.
- `owner_locked`: boolean. True when owner/admin says prompt injection and QA
  must treat the canonical term as mandatory.
- `public_visible`: boolean. False for candidates, unresolved terms, admin-only
  notes, or spoilers.
- `public_description`: optional short reader-facing explanation for popovers.
- `admin_notes`: private owner/admin notes. Never expose through public routes.
- `confidence`: optional numeric or string confidence. Numeric is easier to
  sort, but string labels such as `low`, `medium`, `high` are easier for manual
  admin review. Pick one in implementation.
- `replacement_policy`: enum string controlling repair safety, for example
  `never_auto_replace`, `preview_required`, `safe_exact`, `manual_only`.
- `matching_policy`: enum string controlling matching, for example
  `exact_phrase`, `case_insensitive_phrase`, `word_boundary`,
  `source_text_only`, `translated_text_only`, `custom`.
- `first_seen_chapter_id`: nullable FK to `chapters.id`.
- `first_seen_chapter_number`: nullable integer fallback/reference.
- `last_seen_chapter_id`: nullable FK to `chapters.id`.
- `last_seen_chapter_number`: nullable integer fallback/reference.
- `created_by_user_id`: nullable FK to `users.id`.
- `updated_by_user_id`: nullable FK to `users.id`.
- `created_at`: timezone-aware timestamp with server default.
- `updated_at`: timezone-aware timestamp.
- `deprecated_at`: nullable timestamp.

Notes:

- The entry belongs to one novel. `Pocott` in the Kakuyomu novel and another
  `Pocott` in a different novel are separate glossary decisions.
- Do not require `canonical_term` to be globally unique.
- Do not require reliable source Japanese before creating an entry. Kakuyomu
  mojibake evidence shows why an internal concept label must be allowed.

## 5. `novel_glossary_aliases`

Proposed fields:

- `id`: integer primary key.
- `glossary_entry_id`: required FK to `novel_glossary_entries.id`.
- `alias_text`: alias surface text.
- `alias_type`: enum string, for example `allowed`, `rejected`, `banned`,
  `deprecated`, `observed`, `source_variant`.
- `language`: optional language/text-origin code such as `ja`, `en`, `romaji`,
  or `unknown`.
- `text_origin`: optional enum/string such as `source_text`,
  `translated_text`, `manual`, `qa`, `audit`, `provider_output`.
- `applies_to`: enum/string or normalized association value indicating where
  the alias applies: `source_text`, `translated_text`, `prompt`, `qa`,
  `public_display`. If multiple values are needed, prefer either a small
  JSON/list field or a join table in implementation.
- `matching_policy`: nullable override. If null, inherit from entry.
- `case_sensitive`: optional boolean if not captured by `matching_policy`.
- `whole_phrase_only`: optional boolean if not captured by `matching_policy`.
- `notes`: private admin notes.
- `created_at`: timezone-aware timestamp.
- `updated_at`: timezone-aware timestamp.

Examples:

- Kakuyomu `Pocott` entry: alias `Pokot`, type `banned` or `rejected`, applies
  to translated text and QA.
- N2056DN house entry after owner choice: aliases such as `Vancroft` and
  `Vancraft` can be rejected/banned.
- N2056DN `Albert`: alias `Alberto` can be rejected/banned.

## 6. Source Provenance

`novel_glossary_source_provenance` should preserve evidence without making the
source adapter the owner.

Proposed fields:

- `id`: integer primary key.
- `glossary_entry_id`: required FK to `novel_glossary_entries.id`.
- `novel_id`: required FK to `novels.id` for lookup and integrity checks.
- `source_site`: enum/string, for example `syosetu`, `kakuyomu`, `novel18`,
  `generic`, `manual`, `audit_doc`.
- `source_adapter`: optional exact adapter key, for example `syosetu_ncode` or
  `kakuyomu`.
- `source_novel_id`: optional source work ID such as `n2056dn` or
  `16817330655991571532`.
- `source_url`: optional source URL.
- `source_chapter_id`: optional source/storage chapter ID string.
- `source_chapter_number`: optional integer.
- `chapter_id`: nullable FK to `chapters.id`.
- `local_chapter_reference`: optional storage reference such as a chapter
  bundle ID or stable local key. Do not expose raw filesystem paths publicly.
- `raw_source_term`: optional source-language surface form when reliable.
- `observed_translation`: optional observed English surface form.
- `evidence_context_ref`: optional structured reference to a paragraph,
  occurrence, audit section, or offset. Prefer references over storing long
  copyrighted snippets.
- `evidence_snippet`: optional very short snippet only when needed and safe.
  Avoid storing excessive copyrighted text.
- `first_seen_at` / `last_seen_at`: optional timestamps or chapter-linked
  seen-range fields.
- `confidence`: optional numeric or label confidence.
- `evidence_quality`: enum/string such as `clean_source`, `mojibake`,
  `translated_only`, `metadata_only`, `manual_owner_decision`.
- `notes`: private admin notes.
- `created_at`: timezone-aware timestamp.

This supports the Kakuyomu case where local source terms may be mojibaked and
the N2056DN case where audit documents record source terms and drift.

## 7. Decision/Audit History

`novel_glossary_decision_events` should record who changed glossary decisions
and why.

Proposed fields:

- `id`: integer primary key.
- `novel_id`: required FK to `novels.id`.
- `glossary_entry_id`: nullable FK to `novel_glossary_entries.id`.
- `alias_id`: nullable FK to `novel_glossary_aliases.id` if the event targets
  an alias.
- `actor_user_id`: nullable FK to `users.id`.
- `decision_type`: enum string such as `create`, `approve`, `recommend`,
  `reject`, `deprecate`, `merge`, `lock`, `unlock`, `alias_change`,
  `public_visibility_change`, `qa_policy_change`.
- `source_of_decision`: enum/string such as `owner`, `admin`,
  `automated_candidate`, `repair_audit`, `qa`.
- `old_value_json`: nullable JSON/text payload.
- `new_value_json`: nullable JSON/text payload.
- `rationale`: private decision rationale.
- `created_at`: timezone-aware timestamp.

Examples:

- Owner/admin approved Kakuyomu `Pocott` and banned `Pokot`.
- Owner/admin approved `Blessing of the World Tree` because `Protection` was
  ambiguous.
- Later QA may recommend deprecating an alias, but owner/admin should approve
  enforcement before it becomes blocking.

## 8. QA Findings

`novel_glossary_qa_findings` should store structured findings without mutating
chapter content.

Proposed fields:

- `id`: integer primary key.
- `novel_id`: required FK to `novels.id`.
- `chapter_id`: nullable FK to `chapters.id`.
- `chapter_number`: nullable integer fallback/reference.
- `glossary_entry_id`: nullable FK to `novel_glossary_entries.id`.
- `finding_type`: enum string such as `banned_alias`,
  `inconsistent_alias`, `missing_canonical`, `unresolved_term`,
  `source_mismatch`, `replacement_risk`.
- `severity`: enum string such as `info`, `warning`, `error`, `blocker`.
- `matched_text`: matched text in source or translation. Keep short.
- `suggested_text`: optional suggested canonical text.
- `context_reference`: paragraph ID, chapter offset, storage reference, or
  occurrence key. Prefer references over long snippets.
- `context_snippet`: optional short private snippet for review.
- `status`: enum string such as `open`, `accepted`, `dismissed`, `fixed`.
- `reviewer_user_id`: nullable FK to `users.id`.
- `reviewer_notes`: private admin notes.
- `created_at`: timezone-aware timestamp.
- `resolved_at`: nullable timestamp.

Findings should distinguish source-side matching from translated-text matching.
For example, a banned translated alias is different from a source term whose
source-side interpretation is uncertain.

## 9. User Display Overrides

Optional `user_glossary_display_overrides` fields:

- `user_id`: required FK to `users.id`.
- `novel_id`: required FK to `novels.id`.
- `glossary_entry_id`: required FK to `novel_glossary_entries.id`.
- `display_term`: user-selected display term or approved variant.
- `enabled`: boolean.
- `created_at`: timezone-aware timestamp.
- `updated_at`: timezone-aware timestamp.

Recommended constraints:

- Composite primary key or unique constraint on
  `(user_id, novel_id, glossary_entry_id)`.
- The override must be presentation-layer only. It must not mutate canonical
  translation text, repair data, source provenance, or owner/admin decisions.
- Public routes must infer `user_id` from the session, never from a client
  supplied user ID.

## 10. Enums and Validation Rules

Proposed enum values:

- `term_type`: `character`, `family_house`, `place`, `organization`, `title`,
  `rank`, `skill`, `magic`, `species`, `item`, `artifact`, `concept`, `phrase`,
  `other`.
- `entry_status`: `candidate`, `recommended`, `approved`, `rejected`,
  `deprecated`.
- `alias_type`: `allowed`, `rejected`, `banned`, `deprecated`, `observed`,
  `source_variant`.
- `matching_policy`: `exact_phrase`, `case_insensitive_phrase`,
  `word_boundary`, `source_text_only`, `translated_text_only`, `regex_reviewed`,
  `manual_only`, `custom`.
- `replacement_policy`: `never_auto_replace`, `preview_required`,
  `manual_only`, `safe_exact`, `no_replacement`.
- `enforcement_level` / `qa_severity`: `none`, `info`, `warning`, `error`,
  `blocker`.
- `provenance_source`: `syosetu`, `kakuyomu`, `novel18`, `generic`,
  `manual`, `audit_doc`, `qa`, `repair_audit`.
- `decision_event_type`: `create`, `approve`, `recommend`, `reject`,
  `deprecate`, `merge`, `lock`, `unlock`, `alias_change`,
  `public_visibility_change`, `qa_policy_change`.
- `qa_finding_type`: `banned_alias`, `inconsistent_alias`,
  `missing_canonical`, `unresolved_term`, `source_mismatch`,
  `replacement_risk`.
- `qa_finding_status`: `open`, `accepted`, `dismissed`, `fixed`.

Validation rules:

- `approved` entries should require a non-empty `approved_translation` or
  equivalent canonical English field.
- `owner_locked=True` should require `status='approved'` unless an explicit
  admin override is designed.
- Public routes should expose only `public_visible=True` entries and should
  never return `admin_notes`, private rationale, raw filesystem paths, or
  excessive snippets.
- `banned` aliases should not also be `allowed` for the same entry.
- QA enforcement should treat `recommended` terms as warnings by default unless
  owner/admin policy says otherwise.

## 11. Indexes and Constraints

Recommended indexes/constraints:

- `novel_glossary_entries`:
  - FK index on `novel_id`.
  - Composite index on `(novel_id, status)`.
  - Composite index on `(novel_id, term_type)`.
  - Composite index on `(novel_id, public_visible)`.
  - Unique-ish constraint on `(novel_id, canonical_term_normalized)` if a
    normalized column is added. If not, use application-level normalized checks.
  - Do not use global uniqueness across novels. The same surface term may have
    different canonical meanings or translations in different novels.
- `novel_glossary_aliases`:
  - FK index on `glossary_entry_id`.
  - Composite index on `(glossary_entry_id, alias_type)`.
  - Index on normalized alias text for matching/QA.
  - Consider unique constraint on
    `(glossary_entry_id, alias_text_normalized, applies_to)` if normalized
    fields exist.
- `novel_glossary_source_provenance`:
  - Index on `(novel_id, source_site, source_novel_id)`.
  - Index on `(glossary_entry_id, source_site)`.
  - Index on `(chapter_id)` when present.
- `novel_glossary_decision_events`:
  - Index on `(novel_id, created_at)`.
  - Index on `(glossary_entry_id, created_at)`.
  - Index on `(actor_user_id)`.
- `novel_glossary_qa_findings`:
  - Index on `(novel_id, status, severity)`.
  - Index on `(chapter_id, status)`.
  - Index on `(glossary_entry_id, status)`.
  - Index on `(finding_type, severity)`.
- `user_glossary_display_overrides`:
  - Composite primary key or unique constraint on
    `(user_id, novel_id, glossary_entry_id)`.
  - Index on `(novel_id, glossary_entry_id)` if public reader joins need it.

Case-insensitive uniqueness:

- PostgreSQL can support expression indexes such as `lower(canonical_term)` or
  `lower(alias_text)`. Alembic and SQLAlchemy implementation should verify local
  project conventions before using expression indexes.
- If cross-database compatibility matters, store normalized text columns such as
  `canonical_term_normalized` and `alias_text_normalized`.

## 12. Migration Strategy

This is still planning only.

Recommended migration strategy:

- Create tables first with no data mutation.
- Add SQLAlchemy models and imports in a dedicated implementation phase, not in
  this plan.
- Do not seed N2056DN or Kakuyomu glossary entries in the base migration unless
  a later controlled seed phase explicitly chooses that.
- Avoid backfilling from translated chapters in the migration.
- Avoid scraping, provider calls, translation, source fetching, or storage
  mutation.
- Make the migration reversible where possible by dropping glossary tables in
  dependency order.
- Avoid destructive changes to `novels`, `chapters`, `users`, taxonomy tables,
  storage metadata, translated chapters, or provider/request records.
- Keep seed data and repair suggestions outside the schema migration.

## 13. API Implications

Future admin API needs:

- List glossary entries for one novel.
- Create/update an entry.
- Approve/reject/recommend an entry.
- Merge/deprecate entries.
- Manage aliases.
- Lock/unlock entries.
- List provenance/evidence for an entry.
- List QA findings for a novel/chapter.
- Run glossary QA later.
- Preview repair suggestions later.

Future public/user API needs:

- Public glossary for one novel.
- Reader tooltip/popover payload for a chapter or novel.
- User display override create/update/delete.
- User display override list for one novel.

API boundary notes:

- Admin glossary routes should be owner-only and CSRF-protected.
- Public glossary routes must return public-safe fields only.
- User override routes must infer user identity from the session.
- Routers should stay thin and delegate glossary decisions, QA, and repair
  preview logic to service/orchestration layers.

## 14. Prompt Injection Implications

The schema should support prompt builders by:

- Fetching `APPROVED` entries for a novel as strict constraints.
- Fetching `RECOMMENDED` entries as softer constraints or warnings, depending
  owner/admin policy.
- Including rejected/banned aliases when they help prevent known drift, such as
  Kakuyomu `Pokot`, `Guld`, and `Protection of the World Tree`.
- Prioritizing chapter-relevant terms using provenance, first/last seen chapter
  fields, source occurrences, and aliases.
- Excluding unresolved `candidate` entries from strict enforcement.
- Snapshotting selected term IDs, alias IDs, and a `glossary_hash` for
  reproducibility in future translation jobs.
- Preserving the same glossary snapshot if provider fallback is ever explicitly
  enabled later. Fallback must not broaden or narrow glossary constraints
  implicitly.

## 15. Existing Chapter Repair Implications

The schema can store QA findings and suggestions for existing chapters, but it
should not directly rewrite text.

Repair principles:

- Repair should be previewed and audited.
- No naive global find/replace.
- Source text and translated text need separate matching rules.
- Names, ranks, organizations, skills, species, and system phrases need
  different matching and replacement policies.
- N2056DN noble ranks need source-aware matching because `duke`, `marquess`,
  house phrasing, and source terms are not interchangeable.
- Kakuyomu approved aliases such as `Pokot`, `Guld`, and `Protection of the
  World Tree` should be flagged and repaired only after context review.

## 16. Public Reader Popover Implications

Public reader glossary behavior should use:

- `public_visible` to control whether an entry is exposed.
- `public_description` for reader-facing explanation.
- `approved_translation` / canonical display fields for tooltip headings.
- Optional source term/readings only when safe and useful.
- No `admin_notes`, private decision rationale, rejected aliases, raw storage
  paths, or excessive source snippets in public responses.
- No candidate/unresolved terms unless owner/admin explicitly marks them
  public-safe.
- User display overrides layered on top at render time without changing stored
  canonical translated chapter text.

## 17. Open Questions

- Exact implementation names for current backend FK fields should be confirmed
  during migration work, but inspection shows `novels.id`, `chapters.id`, and
  `users.id` are the relevant DB FKs.
- Should glossary QA block publishing for `RECOMMENDED` terms, or only for
  `APPROVED` and `owner_locked` terms?
- Should `magic power` vs `mana` remain a per-novel style decision, or become a
  cross-novel style preference with per-novel overrides?
- Do title/rank renderings need structured subtypes beyond `term_type`, such as
  `rank.noble`, `rank.skill`, `title.formal`, or `title.relationship`?
- Should glossary seed data be manually inserted through admin UI, imported by
  a controlled seed script, or represented as reviewed migration data in a later
  dedicated phase?
- Should occurrence detection be persisted for every chapter or generated on
  demand for QA/public reader display?
- Should aliases support multiple `applies_to` values via JSON/list column or a
  normalized alias-scope table?

## 18. Recommended Next Phase

Recommended next phase:

`GLOSSARY-BACKEND-MIGRATION-1`

The schema plan maps clearly enough to current backend models for migration
planning: `novels.id`, `chapters.id`, and `users.id` are available FK anchors;
current Alembic style supports additive table/index migrations; and admin/public
router patterns are understood. The next phase should still be scoped narrowly
to additive SQLAlchemy models, Alembic migration, and focused migration/model
tests. It should not seed glossary data, run providers, scrape sources, mutate
storage, translate chapters, or repair existing chapter text.
