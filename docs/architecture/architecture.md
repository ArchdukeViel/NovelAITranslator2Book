# NovelAI Architecture

## 0. Document Status

Status: canonical project architecture.

Last reviewed: 2026-06-09.

This is the single active architecture reasoning file for NovelAI. It is the source of truth for future Codex prompts, implementation decisions, project boundaries, refactor rules, and architecture audits.

Historical architecture notes may be archived under `docs/archive/architecture/`, but active architecture decisions should be reflected here. Do not reintroduce scattered prompt packs, pasted scratch files, generated reports, or project tree exports into `docs/architecture/`.

Current mode:

```text
single-owner / controlled-admin with public platform features
Postgres-backed metadata (14 tables), file-backed chapter content
Redis/RQ background workers for crawl and translation jobs
guest/user/owner authentication (backend-enforced)
public reader + user library/progress/ratings/requests
scheduler-enabled for admin-owned provider/model routing
baseline owner/admin security hardened
not multi-admin-team
```

Authorized target mode (see Section 18, Deployable v1 Target Mode):

```text
deployable single-owner public platform (v1)
guest / user / owner roles, backend-enforced
Postgres-backed users, sessions, ownership, and saved data
file/object-backed chapter content, assets, and exports
public reader + user library/progress/ratings/requests
public contribution credentials NOT in v1 (later gated phase, Section 12)
```

This document records the current runtime AND an authorized transition target. A
capability does not exist until later code and tests prove it. The v1 target
authorizes public auth, the guest/user/owner role model, database support for
users/ownership/saved data, and an object storage boundary — sequenced behind
the platform expansion plan. It does NOT authorize public contribution
credentials (later gated phase), batch mode, billing, organizations, or
multi-admin teams.

## 1. Product Boundary

NovelAI is a web-based Japanese novel ingestion, translation, editing, library, and export system.

The product has four conceptual surfaces:

1. Owner/admin surface: crawl/import sources, manage requests, manage jobs, translate chapters, edit output, configure providers, inspect activity/scheduler state, and export.
2. Public reader surface: browse published translated novels and read published chapters.
3. Registered user surface (authorized for v1): public users sign up, log in, save novels to a library, track reading progress, rate/review, and request novels/chapters. See Section 20.
4. Contribution surface (later gated phase): registered users optionally contribute Gemini/OpenAI provider quota for approved public-library jobs. Gated behind Section 12; not part of v1.
5. Backend runtime: source ingestion, input import, translation pipeline, storage, usage/cost tracking, activity logging, scheduler state, security controls, and export generation.

Current core mode is a single-owner / controlled-admin translation system. It includes owner/admin operations, public reading, source ingestion, translation, storage, jobs/activity, provider settings, scheduler, exports, and baseline security protections.

Core mode does not require multi-admin teams, billing, organizations, distributed workers, database migration, batch translation, or public contribution credentials.

Public contribution mode is an explicit later phase. It is not a settings-page enhancement and it is not current core. It would add registered users, request approval, user-contributed Gemini credentials, encrypted credential storage, usage limits, contribution consent, credential audit records, and strict authorization boundaries.

## 2. Current Implementation Status

Implemented:

- Smart segmentation with deterministic paragraph and chunk IDs.
- Typed `Paragraph` and `TranslationChunk` contracts.
- Provider error classification through `ProviderError` / `ProviderErrorCode`.
- API error-envelope mapping for known provider/domain failures.
- Pipeline, job, stage, and chunk traceability.
- Deterministic `TranslationQAStage` before final save.
- Storage/cache contracts for runtime traceability, translation chunks, chunk outputs, temporary bundles, provider request records, scheduler state, fetch cache, and exact translation cache keys.
- Central FetchService foundation with shared HTTP client, URL safety validation, per-domain throttle, and fetch cache hooks.
- Source quality gates and Generic source confidence scoring.
- Offline source parser fixture tests.
- API/frontend error and progress contract cleanup.
- Admin frontend shared primitives and scheduler-aware activity display.
- Multi-model scheduler backend for admin-owned provider/model selection, cooldown/quota state, pause/resume status, model-state progress reporting, and chunk-attempt provider/model traceability.
- Baseline owner/admin security hardening: path traversal protection, runtime storage isolation, secret redaction, structured errors, SSRF checks, and ignore policy.
- PostgreSQL 16 database with SQLAlchemy 2.x ORM and Alembic migrations (14 tables: novels, chapters, users, crawl_jobs, translation_jobs, provider_requests, reading_progress, reading_history, library_items, reviews, novel_requests, audit_logs, system_settings, alembic_version).
- Redis 7 + RQ background workers for crawl and translation jobs.
- HTTP-only session authentication with guest/user/owner role model and `require_role()` FastAPI dependency.
- Object-level authorization on user-owned endpoints (library, progress, reviews, requests).
- Public catalog router with search, filter, pagination for published novels.
- User data router: library items, reading progress, reading history, reviews, novel requests.

Explicitly not implemented:

- Public contribution credentials (later gated phase, Section 12).
- Encrypted user credential storage.
- Credential revocation/deletion/audit lifecycle.
- Per-credential usage limits.
- Public contribution consent flow.
- Batch mode.
- Billing, organizations, or multi-admin teams.
- Backend package flattening from `backend/src/novelai` to another layout.
- Object storage boundary (S3/R2/B2) for deployed content/assets/exports.
- Data migration script from file-backed storage to Postgres.

## 3. Non-Goals and Blocked Phases

The following are authorized for the v1 target and have been implemented
(see Section 2 for details):

- Public user authentication and guest/user/owner role model (Section 19).
- Database support for users, sessions, ownership, and saved data (Section 21).
- Public reader/user features: library, reading progress, ratings, requests (Section 20).

Still pending for v1:

- Object storage boundary for deployed content/assets/exports (Section 22).
- Owner dashboard hardening (audit log wiring, user management UI).
- Data migration script from file-backed storage to Postgres.

Still blocked / gated (do NOT implement, even during platform expansion):

- Public contribution credentials (later gated phase, Section 12).
- Public credential UI.
- Credential pooling or marketplace behavior.
- Batch mode.
- Billing, organizations, or multi-admin teams.
- Broad folder migrations or package flattening.

Public contribution credentials remain gated behind Section 12. Whether or not
auth and a database exist, do not fake user ownership with browser localStorage
IDs, request-provided user names, unsigned cookies, or frontend-only flags;
ownership is established only by the backend session/authorization layer
(Section 19).

## 4. Backend Architecture

Repository ownership:

```text
backend/src/novelai/
  activity/          Background activity queue, runner, worker, progress, events
  api/               FastAPI app, routers, dependencies, error handlers, schemas
  config/            Settings and workflow profiles
  core/              Shared domain errors and primitive types
  export/            Exporter interfaces and concrete output formats
  glossary/          Glossary and term memory logic
  infrastructure/    External plumbing such as HTTP fetching, throttle, cache
  inputs/            Non-web input adapters
  prompts/           Prompt builders, prompt models, templates, response parsing
  providers/         LLM provider interfaces and implementations
  runtime/           Dependency container, bootstrap, CLI runtime
  services/          Application use cases and orchestration
  shared/            Cross-domain protocols, pipeline contracts, typed helpers
  sources/           Web source parsers/adapters and source registry
  storage/           File-backed persistence boundary and schema readers/writers
  translation/       Translation stages, QA, scheduler, post-processing
  utils/             Tiny pure utilities only
```

Layer rules:

- API routers stay thin.
- Use-case orchestration belongs in `backend/src/novelai/services/*` or `backend/src/novelai/services/orchestration/*`.
- Long-running work belongs in `activity/`, job runtime, and storage-backed progress records.
- Source-specific selectors and parsing belong in `sources/*`.
- HTTP fetching, throttling, retry, URL safety, and fetch cache belong in `infrastructure/http/*` or the documented equivalent.
- Provider-specific API details belong in `providers/*`.
- Prompt construction belongs in `prompts/*`.
- Persistence belongs behind `storage/*`.
- Frontend calls backend only through `frontend/lib/api.ts`.

Dependency direction:

```text
api -> services -> domain modules -> storage/providers/sources/export
translation -> prompts -> providers
scheduler -> providers through provider registry
frontend -> backend API only
```

Forbidden direction:

```text
storage -> api
providers -> api
providers -> storage
sources -> services
frontend -> storage files
translation stages -> FastAPI request objects
source parsers -> ad hoc HTTP clients
React -> scheduler/provider/storage/QA policy
```

Routers may validate request payloads, apply the current admin token dependency, call services, and return typed models. Routers must not scrape websites, build prompts, translate text, write storage files directly, parse provider-specific errors, or expose raw secrets.

The runtime container is the composition root for shared services. Do not create hidden singleton-like runtime state in random modules.

## 5. Translation Pipeline Architecture

Canonical flow:

```text
chapter-based storage
-> paragraph IDs
-> temporary chunks/bundles
-> prompt construction
-> scheduler/provider translation
-> structured output or safe plain-text fallback
-> deterministic QA
-> post-process
-> save final translated output per chapter
```

Core contracts:

```text
Paragraph
  paragraph_id
  chapter_id
  text
  char_count

TranslationChunk
  chunk_id
  novel_id
  chapter_ids
  paragraph_ids
  source_text
  char_count
  previous_context
  paragraph_refs
```

Rules:

- `SmartSegmentStage` owns segmentation.
- Paragraph IDs are deterministic within a chapter, such as `p0001`.
- Chunk IDs are deterministic, such as `c0001`.
- Every translated unit must preserve `novel_id`, `chapter_id`, `paragraph_id`, and `chunk_id` where the current pipeline supports it.
- Paragraph and chapter order must remain stable.
- Scene breaks, image placeholders, and explicit internal markers must not lose position.
- Long chapters must not become hundreds of provider calls.
- The system must not send a whole novel as one giant provider request.
- The system must not translate every paragraph as its own provider request.
- Temporary bundles are translation preparation artifacts, not canonical storage.
- Canonical translated output remains chapter-based unless the architecture explicitly changes later.
- Multi-chapter bundles must preserve explicit chapter boundaries and be splittable without fragile text guessing.
- Failed chunks and QA failures must be traceable.

Prompt construction belongs in `prompts/*`. Translation stages may assemble typed prompt inputs, but they should not scatter long prompt strings across the pipeline.

Provider errors are normalized through `ProviderError` / `ProviderErrorCode`. Known provider errors must not collapse into anonymous generic 500 responses.

`TranslationQAStage` must run after provider output and before final save. Failed QA output must not be saved as clean final translated text. QA checks include empty output, source-identical output, suspicious length ratios, placeholders, image markers, scene breaks, provider refusal/error text, probable summary/truncation, and paragraph/chapter mapping integrity where structured data exists.

Exact translation cache keys must include prompt-affecting and model-affecting metadata, including `source_text_hash`, source/target language, `provider_key`, `provider_model`, `prompt_version`, glossary hash, style preset, JSON/structured-output mode, consistency mode, and other prompt-affecting fields when present.

## 6. Multi-Model Scheduler Architecture

Status: implemented for admin-owned provider/model routing.

The scheduler belongs in the translation/service/job layer, not in providers and not in React.

Scheduler responsibilities:

- Select `provider_key` and `provider_model`.
- Track per-model RPM/RPD state.
- Track `requests_this_minute` and `requests_today` where available.
- Respect `cooldown_until` and `exhausted_until`.
- Distinguish RPM cooldown from daily quota exhaustion.
- Pause jobs when every eligible model is cooling down or exhausted.
- Expose `paused_reason`, `resume_after`, and `model_states` through activity/job progress.
- Record provider/model per chunk attempt.
- Preserve successful chunk progress.
- Avoid random round-robin quality drift.

Supported scheduler policy values:

```text
volume_first
quality_first
```

Model statuses:

```text
available
cooling_down
daily_exhausted
disabled
failed
```

The scheduler must not:

- Bypass prompt construction.
- Bypass glossary handling.
- Bypass exact cache-key rules.
- Bypass provider request recording.
- Bypass chunk status tracking.
- Bypass QA before final save.
- Leak provider credentials or provider request headers.
- Randomly rotate models when consistency matters.
- Retranslate successful chunks after pause/resume unless explicitly forced.

Current debt remains around scheduler runtime persistence and resume hardening. Provider request and chunk output storage hooks exist, but every runtime path must continue to be audited so successful and failed attempts are consistently inspectable after interruptions.

## 7. Source Ingestion Architecture

Target ingestion model:

```text
SourceRegistry
-> SourceAdapter.detect / normalize
-> FetchService
   - shared HTTP client
   - SSRF-safe URL validation
   - per-domain throttle
   - retry/backoff
   - fetch cache / conditional request hooks
-> Source parser
   - metadata
   - chapter list
   - chapter payload
   - images/assets
-> SourceQualityGate
-> StorageService
```

Rules:

- Source registry is the only source lookup mechanism.
- Source-specific selectors stay in `sources/*`.
- Source adapters do not write storage files directly.
- Source adapters do not call translation providers.
- Generic source is fallback and must carry confidence/warnings.
- Adult source age gates and blocked pages must be classified before translation.
- Source tests use offline fixtures; they must not require live websites.

Implemented:

- Central FetchService foundation.
- Shared HTTP client factory.
- Per-domain throttle.
- Fetch cache hooks.
- URL safety / SSRF protection.
- Source quality gates.
- Generic confidence scoring.
- Offline fixtures for Syosetu/Novel18, Kakuyomu, and Generic.

Known migration debt:

- Syosetu/Novel18 is integrated with FetchService.
- Kakuyomu still needs full migration to FetchService if legacy direct HTTP behavior remains.
- Generic still needs full migration to FetchService if legacy direct HTTP behavior remains.
- Fixture coverage is representative, not exhaustive against live-site drift.

## 8. Storage and Runtime Data Architecture

Storage is file-backed. Runtime storage lives under `storage/novel_library` by default and should remain untracked unless intentionally sanitized as a fixture or example.

Storage path knowledge belongs only in `backend/src/novelai/storage/*`.

Canonical storage remains chapter-based:

```text
chapter raw snapshot
parsed chapter
final translated chapter
translation versions / edits
chapter state
```

Translation preparation may use temporary chunks and bundles, but those are runtime/cache/retry artifacts. They are not canonical chapter output and may be deleted after successful final save if retention policy allows it.

Runtime records include or may include:

- Novel metadata and chapter bundles.
- Raw scraped chapter snapshots.
- Parsed chapter data.
- Final translated chapter output.
- Translation cache.
- Usage data.
- Activity log and queue.
- Pipeline events.
- Chunk states.
- Translation chunks.
- Chunk outputs.
- Temporary bundle records.
- Provider request records.
- Scheduler state.
- Fetch cache entries.
- Export artifacts.

Storage rules:

- Raw scraped chapter files should not be silently deleted after translation.
- Parsed chapter files should not be silently deleted after translation.
- Final translated output is saved per chapter.
- Temporary bundle deletion must not break final translated chapters.
- Provider request records must not store API keys, authorization headers, cookies, raw secrets, or raw tracebacks.
- Runtime files are private unless explicitly published through safe storage readers and API/export services.
- Frontend must never receive raw filesystem paths.

`docs/reference/DATA_OUTPUT_STRUCTURE.md` documents local runtime storage policy and output shapes. Runtime subfolders such as `storage/novel_library/`, `storage/output/`, `storage/input/`, and `storage/logs/` should stay ignored/untracked unless explicitly documented as examples.

## 9. API and Frontend Contract Architecture

Canonical names:

```text
source_key
source_novel_id
source_url
novel_id
chapter_id
paragraph_id
chunk_id
bundle_id
provider_key
provider_model
activity_id
job_id
request_id
credential_id
requesting_user_id
credential_owner_user_id
prompt_version
glossary_hash
```

Compatibility aliases tolerated for existing storage/API/frontend compatibility:

```text
id
source
provider
model
slug
```

Aliases are debt. Keep them only when existing callers, route params, or persisted storage need them. New backend/frontend/storage contracts should prefer canonical names.

Known API errors should return a structured envelope:

```json
{
  "code": "PROVIDER_ERROR",
  "message": "Human-readable summary",
  "explanation": "What this usually means",
  "details": {},
  "trace_id": "optional"
}
```

Public/frontend-facing errors must not include raw tracebacks, API keys, authorization headers, cookies, provider request headers, provider secrets, or unsafe filesystem internals.

Progress payloads should remain backward compatible while supporting:

```text
status
current_stage
current_label
completed
total
errors
warnings
paused_reason
resume_after
model_states
```

Frontend API calls go through `frontend/lib/api.ts`. Adding new API fields without updating frontend types is contract drift.

## 10. Frontend Architecture

Frontend ownership:

```text
frontend/app/               Next.js App Router pages and route groups
frontend/components/        Reusable UI, admin, and public components
frontend/lib/               API client, shared types, client utilities, store
frontend/server/            Frontend server environment handling
```

Current admin routes live under `frontend/app/(admin)/admin/*`.

Current frontend contract layer:

- `frontend/lib/api.ts` is the only browser/backend API client.
- `frontend/lib/api-types.ts` owns shared frontend API types when present.
- `frontend/lib/novel-input.ts` owns source detection and novel ID derivation helpers.
- `frontend/lib/format.ts` owns display formatting helpers.
- `frontend/lib/admin-errors.ts` owns admin-facing error formatting.

Admin pages render workflows and call typed API functions. They must not read runtime storage directly, call providers, implement scheduler policy, implement translation QA, build prompts, or own credential policy.

React displays scheduler state, QA state, provider state, storage-backed job state, and credential metadata returned by the backend. React does not decide those policies.

Shared admin primitives include error banners, empty states, loading rows, progress bars, scheduler badges/panels, dialogs, sortable headers, and related presentational components.

No public contribution credential UI exists. Do not add it until the Section 12 gated phase opens.

## 11. Security Architecture

Protected data classification:

Critical:

- Provider API keys.
- Admin/session tokens.
- Encryption keys.
- `.env` and deployment secret files.
- Backups and archives containing runtime state.

High:

- Raw scraped chapters.
- Parsed chapters.
- Translation chunks and temporary bundles.
- Provider request/response records.
- Unpublished translations.
- Job events and logs.

Medium:

- Published translated chapters.
- Public metadata.
- Public assets.

Baseline owner/admin protections implemented:

- Path traversal protection for storage-backed identifiers.
- Runtime storage isolation; `storage/novel_library` is private runtime data.
- API/log secret redaction for API keys, bearer tokens, cookies, authorization headers, provider headers, passwords, and common secret fields.
- Structured error envelopes.
- Unknown 500s do not expose tracebacks by default.
- FetchService SSRF protection for integrated source adapters.
- Git ignore policy for runtime storage, secrets, logs, backups, and generated artifacts.

URL safety rejects private/internal targets, non-http schemes, embedded URL credentials, localhost names, metadata hostnames, loopback addresses, private ranges, link-local ranges, reserved ranges, multicast ranges, and unspecified addresses.

Security rules:

- Do not serve `storage/novel_library` directly as static files.
- Do not accept raw filesystem paths from frontend/API clients.
- Do not expose raw provider credentials after creation.
- Do not log raw API keys, authorization headers, cookies, provider request headers, or raw secrets.
- Do not return raw tracebacks by default.
- Do not store contributed credentials until encrypted credential storage and ownership boundaries exist.

Security still missing for public contribution mode:

- Registered public users.
- `owner_admin` role separation.
- Object-level authorization.
- Encrypted contributed credential storage.
- Credential lifecycle audit logs.
- Contribution consent and limits.
- Scheduler enforcement of contributed credential scope.
- Separate public-user and admin credential management UIs.

## 12. Public Contribution Credentials — Later Gated Phase

Verdict: Later gated phase (NOT in v1, NOT blocked indefinitely).

This reclassifies the former "Not Ready / blocked" stance. Public API
contribution (registered users donating Gemini/OpenAI provider quota for
approved public-library jobs) is an explicitly planned future phase that opens
only after its gate conditions below are met and tested. It is out of scope for
the deployable v1 target (Section 18). The v1 auth + database + ownership work
(Sections 19/21) is a prerequisite, not the gate itself.

This phase must not open until ALL of the following exist and are tested. These
warnings are preserved and non-negotiable:

- Encrypted contributed-credential storage (encryption at rest; raw keys never
  returned, logged, or exposed after creation).
- Explicit contribution consent capture per credential.
- Credential revocation/deletion lifecycle.
- Per-credential usage limits and scheduler enforcement of contributed
  credential scope (contributed keys usable only for approved public-library jobs).
- Security audit records for credential create/use/revoke/delete.
- Strict object-level authorization (user A cannot access user B's credentials,
  requests, jobs, activities, novels, or exports).
- Per-user ownership of each contributed credential.
- Credential validation before activation (verify the key works before it becomes usable).
- A usage ledger recording every contributed-credential request.
- Provider isolation so a contributed credential is used only for its own provider and scope.
- Abuse and rate-limit controls on contributed-credential usage.
- Owner disable controls to globally suspend contribution or disable a specific credential.

Gate prerequisites (build order):

1. Real authentication/account boundary (Section 19).
2. Backend role/permission boundary (guest/user/owner).
3. Object-level authorization for credentials, requests, jobs, activities, novels, and exports.
4. Request approval semantics tied to authenticated requester/reviewer identities.
5. Encrypted credential storage.
6. Credential revoke/delete lifecycle.
7. Security audit logging.
8. Contribution consent capture.
9. Usage limits and scheduler scope enforcement.
10. Tests proving user A cannot access user B's objects and raw keys are never returned after creation.

Do not fake users with localStorage, request-provided user IDs, unsigned
cookies, or frontend-only flags.

## 13. Implementation History Summary

Prompts 1-10 completed the core reliability pass:

- Prompt 1: Smart segmentation, typed paragraph/chunk contracts, deterministic IDs, chunk packing, and source markers.
- Prompt 2: Provider error classification and API error mapping for Gemini/OpenAI.
- Prompt 3: Pipeline context, stage events, chunk state, scheduler state foundations, and failed-stage traceability.
- Prompt 4: Deterministic translation QA before final save.
- Prompt 5: Central FetchService foundation and Syosetu/Novel18 integration.
- Prompt 6: Source quality gates and Generic confidence scoring.
- Prompt 7: Offline parser fixture tests.
- Prompt 8: Storage/cache contracts, provider request records, fetch cache, scheduler state, and exact translation cache keys.
- Prompt 9: API/frontend contract and error envelope cleanup.
- Prompt 10: Final core integration audit and small cleanup.

Prompt 11 scheduler readiness was established after the core reliability pass. The backend now includes scheduler behavior for admin-owned provider/model routing and the admin UI displays scheduler state.

Prompt 12 public contribution credentials are reclassified from blocked to a later gated phase (Section 12); not in v1.

Prompt 13A baseline owner/admin security hardening is implemented. Full contribution-mode security remains future work because it depends on real auth, roles, object-level authorization, encrypted credential storage, and audit/consent boundaries.

## 14. Current Debt Register

P0 - correctness/security risk:

- Public contribution credentials are a later gated phase (Section 12); do not implement them before encrypted storage, consent, revocation, usage limits, audit records, and strict authorization exist. v1 auth/DB/ownership (Sections 19/21) is a prerequisite, not the gate.
- Runtime provider request records and chunk output records must remain complete for scheduler-managed paths so failures and resumptions are inspectable.
- Successful chunk reuse after pause/resume needs continued hardening so completed chunks are not retranslated unless explicitly forced.
- Private runtime storage must stay isolated from frontend/static serving.

P1 - maintainability/reliability risk:

- Temporary bundle lifecycle needs continued hardening around retry, debug retention, and cleanup.
- Kakuyomu FetchService migration remains if legacy direct HTTP behavior still exists.
- Generic FetchService migration remains if legacy direct HTTP behavior still exists.
- `operations.py` remains thicker than ideal and should be thinned through service extraction.
- `admin.py` remains thicker than ideal and should be thinned through service extraction.
- Legacy aliases (`id`, `source`, `provider`, `model`) remain for compatibility and need a planned migration.
- Storage backward compatibility needs continued discipline for older runtime records.
- Source parser fixtures are representative, not exhaustive against live-site drift.

P2 - cleanup/cosmetic:

- Frontend lint is not configured non-interactively; `next lint` can prompt for setup.
- Backend package flattening is deferred and should only happen as a dedicated mechanical migration.
- Remaining architecture-doc encoding artifacts should be fixed if encountered in archived historical docs, but active architecture reasoning should stay here.
- More examples for provider request records, chunk outputs, and bundle lifecycle may help future maintainers.

## 15. Future Roadmap

Recommended order:

1. Scheduler runtime persistence and resume hardening.
2. Migrate remaining source adapters to FetchService.
3. Thin routers by moving remaining orchestration into services.
4. Optional backend package flattening as a dedicated mechanical migration, not mixed with scheduler/frontend/security work.
5. Build the v1 public platform: database foundation (Section 21), auth/session boundary (Section 19), public reader + user features (Section 20), object storage boundary (Section 22).
6. Open the contribution-credentials gated phase only after Section 12's encryption/consent/revocation/usage-limit/audit/authorization conditions are met and tested.

Do not add new source sites before FetchService, source quality gates, and parser fixtures are stable.

Do not add batch mode before synchronous translation, scheduler, provider errors, storage contracts, and QA are reliable.

Do not add database support just to avoid designing storage contracts. Database migration is a product/scale decision, not a shortcut.

## 16. Agent Prompting Rules

Use this header in future agent prompts (Codex, Hermes, Cline, etc.):

```text
You are working inside the NovelAI project. Follow docs/architecture/architecture.md as the highest project-level design authority.

Non-negotiable rules:
- Keep API routers thin.
- Put use-case logic in services/orchestration.
- Put source parsing only in source adapters/parsers.
- Put HTTP fetching, throttling, and fetch cache in infrastructure/http or the documented equivalent.
- Put persistence only behind storage services.
- Put prompt construction only in prompts.
- Put provider-specific API logic only in providers.
- Put scheduler policy in translation/service/job layer, not providers or React.
- Put credential encryption/decryption behind credential service/storage boundary when credential storage exists.
- Frontend must call backend only through frontend/lib/api.ts.
- Preserve canonical names: source_key, novel_id, source_novel_id, chapter_id, paragraph_id, chunk_id, bundle_id, provider_key, provider_model, credential_id, requesting_user_id, credential_owner_user_id, activity_id/job_id, request_id.
- Add/update tests for every changed contract.
- Do not add new source sites before FetchService, source quality gates, and parser fixtures are stable.
- Do not add batch translation before SmartSegmentStage, provider errors, scheduler, storage contracts, and translation QA are stable.
- Do not implement public contribution credentials unless authenticated users, owner_admin authorization, object-level authorization, encrypted credential storage, request approval, audit logging, usage limits, and consent exist or are explicitly introduced.
- Public contributed credentials may only be used for approved public-library jobs.
- Raw API keys must never be returned, logged, or exposed through admin/public frontend after creation.
- Storage runtime data must not be served directly.
- Before editing, identify which architectural boundary owns the change.
```

When asked for a review, prioritize architecture violations, bugs, behavioral regressions, missing tests, and contract drift.

When asked for cleanup, avoid package flattening, broad migrations, and unrelated refactors unless the prompt explicitly asks for them.

## 17. Validation Commands

Backend:

```powershell
pytest backend/tests -q
pyright
```

Frontend:

```powershell
cd frontend
npm run typecheck
npm run build
cd ..
```

Docs and git hygiene:

```powershell
git status --short
git diff --stat
git diff --check
rg "old architecture companion doc names" docs -g "*.md"
```

Run lint only if configured non-interactively. If lint prompts for ESLint setup, skip it and report that lint is not configured non-interactively.

## 18. Deployable v1 Target Mode

Status: authorized target. Sequenced behind the platform expansion plan
(`.hermes/plans/`), built phase-by-phase, not all at once.

v1 is a deployable single-owner public platform: a public reader plus
registered-user features (library, reading progress, ratings, requests), backed
by a database for users/sessions/ownership/saved data and an object storage
boundary for deployed content/assets/exports. The single owner is the only
admin.

In scope for v1:

- Guest / user / owner role model, backend-enforced (Section 19).
- Public reader over a database-backed catalog (Section 20).
- User accounts with login and saved data (Sections 19, 21).
- Object storage boundary for content/assets/exports at deploy scale (Section 22).
- Owner-only operational controls (existing admin surface, hardened).

Out of scope for v1:

- Public contribution credentials (later gated phase, Section 12).
- Batch mode, billing, organizations, multi-admin teams.

v1 must not be deployed publicly until the owner boundary (Section 19) is
backend-enforced and tested, and rate limiting protects provider-backed actions.
Public users must never be able to trigger paid translation jobs directly.

## 19. Authentication and Session Architecture

Status: authorized for v1. Build after the database foundation (Section 21) is
stable; do not implement auth before the schema and API boundary are clear.

Single owner-admin rule:

- Exactly one owner. The owner is the only admin. There is no separate admin
  team, no admin-invitation flow, and no staff/team permissions in v1.
- The owner is seeded via secure backend bootstrap (env/CLI), never via a public
  signup path.

Role model (backend-enforced):

```text
guest  - unauthenticated; read public catalog/chapters and search only
user   - authenticated; library, reading progress, reading history,
         ratings/reviews, requests, profile
owner  - authenticated; all dangerous operations (crawl, translate, providers,
         usage, logs, edit/delete, settings, user management)
```

Enforcement rules:

- Authorization is enforced in the backend API, not by hiding frontend routes.
  Frontend route protection alone is fake security.
- Every dangerous router requires an owner-role dependency and rejects
  non-owner calls with 401/403 — never 200.
- Object-level authorization: a user may only read/write their own saved data
  (library, progress, reviews, requests). Tests must prove user A cannot access
  user B's objects.
- Ownership is established only by the backend session/authorization layer, never
  by client-supplied IDs, localStorage, unsigned cookies, or frontend flags.

Session strategy (pinned decision for v1):

- v1 authentication uses secure, HTTP-only, same-site session cookies with
  server-side session state. This is the decided default for v1.
- JWT is NOT the v1 default. JWT may be reconsidered later only if mobile or
  external API-client requirements appear; if adopted then, handle token
  rotation and revocation carefully.

Google OAuth first decision:

- Google OAuth is the first/primary intended login method for public users.
  Design the user/auth schema for OAuth identities from the start
  (`auth_provider`, provider subject ID). Email/password may be added later but
  is not required for v1.
- OAuth is still implemented after the database foundation and API boundary are
  stable — it is a login method, not the foundation.

## 20. Public Reader and Registered-User Features

Status: authorized for v1. See the permission matrix in the expansion plan.

Guest (unauthenticated):

- Browse public catalog, read published chapters, search/filter
  (title/author/tag/status/language/recent/popular).

User (authenticated):

- Save novels to a personal library.
- Track reading progress per novel/chapter.
- View reading history.
- Rate and review novels.
- Request novels/chapters (rate-limited). Requests are requests only — they never
  auto-trigger paid translation. The owner approves and runs jobs.
- Manage a profile page.

Frontend rules unchanged: public/user pages call the backend only through
`frontend/lib/api.ts`; React renders backend-owned state and never owns
authorization, scheduler, QA, or provider policy.

## 21. Database Boundary (Users, Sessions, Ownership, Saved Data)

Status: authorized for v1. PostgreSQL is the system of record for metadata and
user-facing state. File/object storage remains the system of record for heavy
content (raw/translated chapter text, covers, logs, exports).

Database owns:

- Users and roles, auth-provider identities.
- Sessions (or session references) and ownership links.
- Saved data: library items, reading progress, ratings/reviews, requests.
- Catalog metadata: novels, chapters (with storage keys + checksums), tags.
- Job/usage records: crawl jobs, translation jobs, provider requests.
- Audit logs and system settings.

Database does NOT own:

- Raw chapter text, translated chapter text, covers, exports, or logs — those
  live in file/object storage; the database stores their keys/paths/checksums.

Boundary rules:

- All database access lives behind a dedicated `db` boundary (engine, session,
  models) consumed by `services/*`. Routers never touch the session directly.
- Use SQLAlchemy + Alembic. Every schema change ships a reviewed migration that
  is reversible (up/down tested).
- Storage-path knowledge stays in the storage boundary; the database stores keys,
  not absolute filesystem paths. The frontend never receives raw paths.
- Migration from file-backed runtime to database is parallel-run with a one-time
  backfill, not a big-bang deletion of file-backed code.

## 22. Object Storage Boundary (Deployed Content, Assets, Exports)

Status: authorized for v1 deployment.

- Development: local `storage/` folder remains acceptable; runtime data stays
  private and untracked.
- Public deployment: S3-compatible object storage (Cloudflare R2, Backblaze B2,
  AWS S3, or MinIO) for raw/translated chapter text, covers/assets, logs, and
  exports.
- The database stores object keys and checksums; object storage stores bytes.
- Object storage must not be served as open static files where it would expose
  unpublished content or runtime internals; access goes through safe storage
  readers and API/export services.
- Credentials for object storage are secrets — never logged, never returned to
  the frontend, never committed.
