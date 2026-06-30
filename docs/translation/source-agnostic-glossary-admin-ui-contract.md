# Source-Agnostic Glossary Admin UI Contract

## 1. Purpose

This document defines the owner/admin UI and frontend API-client contract for
managing per-novel glossary records before any frontend implementation begins.
The goal is to keep the UI aligned with the backend contract that already
exists, avoid accidental public or source-specific behavior, and make the next
implementation phases small and testable.

The admin glossary UI manages glossary entries owned by the platform novel
identity, `novel_id`. Source site, source adapter, source URL, and source novel
ID are provenance only. They can explain where evidence came from, but they must
never become glossary ownership.

This document does not implement frontend code, backend routes, API-client
methods, prompt injection, QA scanning, seed insertion, provider calls,
scraping, translation, storage mutation, DB mutation, or chapter repair.

## 2. User Roles and Access

- Access is owner/admin only. The UI must use the existing admin auth boundary
  and must not be reachable from public reader routes.
- Public users and guests cannot access glossary management.
- Unsafe admin API methods must use the existing CSRF behavior through the
  frontend admin API client. The current convention is `X-CSRF-Token` on unsafe
  methods.
- The UI must not expose secrets, provider credentials, raw auth headers,
  cookies, session internals, runtime filesystem paths, or provider request
  payloads.
- Glossary decisions are owner/admin meaningful. The UI should make status,
  lock, deprecate, and alias changes intentional and explainable.

## 3. Admin Entry Points

Recommended entry points:

- Admin novel detail page: add a "Glossary" action or tab for the selected DB
  novel.
- Admin library/list row action: add a compact "Glossary" action for each
  novel row once the admin UI has a stable DB `novel_id`.
- Direct admin route: `/admin/novels/{novel_id}/glossary`.

The frontend route may carry a slug in navigation if that is the existing admin
pattern, but the API client must resolve or receive the backend DB `novel_id`
before calling glossary routes. Do not add public-side glossary management
routes.

## 4. Screen Layout Contract

Main screen: one focused glossary management workspace for one novel.

Required areas:

- Novel identity header: title, slug, DB `novel_id`, source site as metadata,
  publication/translation context if already available.
- Glossary summary counts by status: `candidate`, `recommended`, `approved`,
  `rejected`, `deprecated`, plus owner-locked and public-visible counts.
- Filters/search: text search, status, term type, owner locked, public visible,
  enforcement level, and has banned aliases.
- Entries table: scan-friendly list of glossary entries for the novel.
- Selected entry detail panel or drawer: view/edit one entry without losing
  table context.
- Aliases section: grouped aliases for the selected entry.
- Provenance section: source/evidence rows for the selected entry and optional
  novel-level provenance view.
- Decision history section: event log for the selected entry, with an option to
  view all novel-level events.
- QA findings section: data-access view only, filtered by status/severity/type
  and optionally chapter.
- Unresolved decision checklist: terms marked `candidate`, `recommended`, or
  unresolved by notes/provenance that need owner review before prompt injection
  or repair phases.

## 5. Entry Table Contract

Required columns:

- Canonical term.
- Term type.
- Status.
- Enforcement level / expected QA behavior.
- Owner locked.
- Public visible.
- First/last seen chapter number or reference.
- Alias count.
- Provenance count.
- Updated time.
- Actions.

Table actions should include view/edit, status action, lock/unlock, deprecate,
add alias, add provenance, and view events. Destructive-looking actions should
be styled as review actions, not casual row buttons.

## 6. Entry Detail/Edit Contract

Editable fields:

- `canonical_term`.
- `term_type`.
- `approved_translation` / translated term.
- `status`.
- `enforcement_level`.
- `replacement_policy`.
- `matching_policy`.
- `public_visible`.
- `public_description`.
- `admin_notes`.
- Owner locked controls.

Safety rules:

- No global find/replace button.
- No direct chapter rewrite from this screen.
- No "repair now" command in this phase.
- Repair preview belongs to a later dedicated phase.
- Locking an entry should feel deliberate and should allow a rationale when the
  backend supports one.
- Changing `approved`, `rejected`, `deprecated`, lock, or unlock state should
  refresh decision history after success.

## 7. Alias Management Contract

Alias groups:

- Allowed aliases.
- Observed aliases.
- Rejected/banned aliases.
- Deprecated aliases.
- Source variants.

Alias fields:

- `alias_text`.
- `alias_type`.
- `applies_to`: `source_text`, `translated_text`, `prompt`, `qa`, or
  `public_display`.
- Optional matching policy override.
- Language/text origin when useful.
- Notes.
- Rationale for owner/admin changes where available.

UX rules:

- Banned aliases must have a clear visual warning. They represent known bad
  output or forbidden variants, not preferred alternatives.
- Observed aliases are evidence, not approval.
- Deprecated aliases should remain visible for audit and repair planning.
- Do not implement naive replacement logic from alias rows.

## 8. Source Provenance Contract

Provenance rows should show:

- Source site and source adapter.
- Source novel ID.
- Source URL when safe for admin use.
- Source chapter ID/number and optional DB chapter link.
- Raw source term if reliable.
- Observed translated term.
- Evidence quality, including `mojibake`, uncertain, translated-only, metadata,
  or manual owner decision evidence.
- Local/evidence reference such as audit section, paragraph reference, or stable
  storage key reference, not raw filesystem paths.
- Confidence.
- Created/updated time.

Source provenance is evidence only. The UI must never imply that Syosetu,
Kakuyomu, source URL, source adapter, or source novel ID owns the canonical
glossary entry.

## 9. Decision Events Contract

Decision history should show:

- Event type: `create`, `approve`, `recommend`, `reject`, `deprecate`, `lock`,
  `unlock`, `alias_change`, and future supported event types.
- Actor if available.
- Rationale.
- Timestamp.
- Old/new value payloads in a compact admin-readable form.

No owner/admin meaningful state change should feel silent. After creating,
approving, recommending, rejecting, deprecating, locking, unlocking, or changing
aliases, the UI should refresh the selected entry and its decision history.

## 10. QA Findings Contract

Current phase is data access only:

- List findings for a novel.
- Filter by chapter, status, severity, and type when the API/client supports it.
- Show finding type, severity, status, matched text, suggested text, context
  reference, reviewer notes, and resolved time.
- Update finding status.

Do not add a QA scanner trigger yet. Do not add automatic repair. Do not inspect
or rewrite translated chapter text from this screen. A later QA engine phase may
add run/preview actions after backend support exists.

## 11. Source-Agnostic UX Rules

- The same canonical term may exist in different novels with different
  meanings, translations, aliases, and decisions.
- Source IDs are provenance.
- All operations are scoped under `novel_id`.
- The UI should not imply Syosetu-only behavior.
- Kakuyomu `16817330655991571532` and N2056DN must fit the same UI.
- Source-specific wording belongs in provenance and notes, not in route names,
  component names, or table ownership.

## 12. API Client Contract

Actual function names should follow existing frontend API-client conventions in
`frontend/lib/api.ts`. The expected capabilities are:

- `listGlossaryEntries(novelId, filters?)`.
- `getGlossaryEntry(novelId, entryId)`.
- `createGlossaryEntry(novelId, payload)`.
- `updateGlossaryEntry(novelId, entryId, payload)`.
- `changeGlossaryEntryStatus(novelId, entryId, payload)`.
- `lockGlossaryEntry(novelId, entryId, payload?)`.
- `unlockGlossaryEntry(novelId, entryId, payload?)`.
- `deprecateGlossaryEntry(novelId, entryId, payload?)`.
- `listGlossaryAliases(novelId, entryId)`.
- `addGlossaryAlias(novelId, entryId, payload)`.
- `updateGlossaryAlias(novelId, aliasId, payload)`.
- `deprecateGlossaryAlias(novelId, aliasId, payload?)`.
- `listGlossaryProvenance(novelId)`.
- `listGlossaryEntryProvenance(novelId, entryId)`.
- `addGlossaryProvenance(novelId, entryId, payload)`.
- `listGlossaryDecisionEvents(novelId)`.
- `listGlossaryEntryDecisionEvents(novelId, entryId)`.
- `listGlossaryQaFindings(novelId, filters?)`.
- `createGlossaryQaFinding(novelId, payload)` if manual finding creation is
  included in the first UI pass.
- `updateGlossaryQaFindingStatus(novelId, findingId, payload)`.

Current backend route shape:

- `GET/POST /api/admin/novels/{novel_id}/glossary`.
- `GET/PATCH /api/admin/novels/{novel_id}/glossary/entries/{entry_id}`.
- `POST /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/status`.
- `POST /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/lock`.
- `POST /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/unlock`.
- `POST /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/deprecate`.
- `GET/POST /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/aliases`.
- `PATCH /api/admin/novels/{novel_id}/glossary/aliases/{alias_id}`.
- `POST /api/admin/novels/{novel_id}/glossary/aliases/{alias_id}/deprecate`.
- `GET /api/admin/novels/{novel_id}/glossary/provenance`.
- `GET/POST /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/provenance`.
- `GET /api/admin/novels/{novel_id}/glossary/events`.
- `GET /api/admin/novels/{novel_id}/glossary/entries/{entry_id}/events`.
- `GET/POST /api/admin/novels/{novel_id}/glossary/qa-findings`.
- `PATCH /api/admin/novels/{novel_id}/glossary/qa-findings/{finding_id}/status`.

The API client should use the existing admin request helper so unsafe methods
receive CSRF automatically.

## 13. Validation and Error UX

Expected UI behavior:

- `401`: show signed-out/admin-session-expired state and direct owner to admin
  login flow.
- `403`: show permission denied or CSRF failure. If the detail is an invalid
  CSRF token, refresh CSRF/session state and allow retry after user action.
- `404`: treat as missing novel, missing child resource, or cross-novel
  mismatch. Refresh current list and do not assume the entry/alias/finding still
  belongs to this novel.
- `422`: show field-level validation errors from FastAPI/Pydantic where
  possible.
- Duplicate canonical term within the same novel: show a conflict-like form
  error when the backend reports the DB constraint or validation failure.
- Duplicate allowed alias: show a form-level duplicate warning if backend
  rejects it in a future phase; current UI should still avoid obvious duplicate
  client submissions.
- Backend warnings/uncertainty: render as admin notes, provenance quality,
  confidence, or unresolved-decision callouts rather than as public-facing text.

## 14. Initial Manual Seed Workflow

Owner/admin will manually enter seed decisions from:

- `docs/translation/n2056dn-glossary-seed-decisions.md`.
- `docs/translation/kakuyomu-16817330655991571532-glossary-seed-decisions.md`.

Recommended manual flow:

1. Open the novel's admin glossary route.
2. Create entries for owner-approved or recommended terms only.
3. Use `candidate` or `recommended` for unresolved terms; do not silently mark
   uncertain rows approved.
4. Add rejected/banned aliases such as `Alberto`, `Auri`, `Pokot`, `Guld`, or
   `Protection of the World Tree` only under the correct novel and canonical
   entry.
5. Add provenance rows pointing back to the seed-decision document, source
   novel ID, source adapter, chapter numbers, and evidence quality.
6. Add rationale when changing status or locking terms.
7. Do not seed automatically in this phase.

## 15. Non-Goals

- No public reader popovers yet.
- No user display overrides UI yet.
- No prompt injection yet.
- No glossary QA engine yet.
- No existing chapter repair yet.
- No provider calls.
- No scraping.
- No translation.
- No automatic seed import.
- No global find/replace.

## 16. Implementation Roadmap

Recommended next phases:

1. `GLOSSARY-ADMIN-API-CLIENT-1`.
2. `GLOSSARY-ADMIN-UI-SHELL-1`.
3. `GLOSSARY-ADMIN-ENTRY-CRUD-1`.
4. `GLOSSARY-ADMIN-ALIAS-PROVENANCE-1`.
5. `GLOSSARY-ADMIN-DECISION-QA-VIEW-1`.
6. `GLOSSARY-SEED-MANUAL-ENTRY-1`.
7. `GLOSSARY-PROMPT-INJECTION-1`.
8. `GLOSSARY-QA-ENGINE-1`.
9. `GLOSSARY-PUBLIC-POPOVER-1`.
10. `GLOSSARY-USER-OVERRIDES-1`.

## 17. Open UI/API Questions

- Should the admin route receive DB `novel_id` directly, or should the UI route
  accept slug and resolve to DB ID before loading glossary data?
- Should duplicate alias prevention become a backend constraint or remain
  application-level validation for now?
- Should owner lock require `status=approved` in the UI before submission, or
  should the backend own that policy in a later hardening phase?
- Should QA findings be editable beyond status/reviewer notes, or remain
  append-only except for review status?
- Should manual seed entry support a guided import checklist from the decision
  documents, or stay fully manual for the first UI pass?
