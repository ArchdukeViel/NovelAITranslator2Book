# NovelAI Architecture

## 0. Document Status

Status: canonical project architecture.

Last reviewed: 2026-06-05.

This is the single active architecture reasoning file for NovelAI. It is the source of truth for future Codex prompts, implementation decisions, project boundaries, refactor rules, and architecture audits.

Historical architecture notes may be archived under `docs/archive/architecture/`, but active architecture decisions should be reflected here. Do not reintroduce scattered prompt packs, pasted scratch files, generated reports, or project tree exports into `docs/architecture/`.

Current mode:

```text
single-owner / controlled-admin
file-backed runtime storage
scheduler-enabled for admin-owned provider/model routing
scheduler state visible in admin activity/job screens
baseline owner/admin security hardened
not public-contribution ready
not multi-tenant
not database-backed
```

This document intentionally does not claim that public auth, `owner_admin` roles, public contribution credentials, encrypted user credential storage, database support, batch mode, billing, organizations, or multi-admin teams exist. They do not exist unless later code and tests prove otherwise.

## 1. Product Boundary

NovelAI is a web-based Japanese novel ingestion, translation, editing, library, and export system.

The product has four conceptual surfaces:

1. Owner/admin surface: crawl/import sources, manage requests, manage jobs, translate chapters, edit output, configure providers, inspect activity/scheduler state, and export.
2. Public reader surface: browse published translated novels and read published chapters.
3. Future registered user surface: request novel/chapter translations and optionally contribute Gemini API quota for approved public-library jobs. This is blocked and not implemented.
4. Backend runtime: source ingestion, input import, translation pipeline, storage, usage/cost tracking, activity logging, scheduler state, security controls, and export generation.

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

Explicitly not implemented:

- Public user authentication.
- `owner_admin` role model.
- Object-level authorization for user-owned objects.
- Public contribution credentials.
- Encrypted user credential storage.
- Credential revocation/deletion/audit lifecycle.
- Per-credential usage limits.
- Public contribution consent flow.
- Database migration.
- Batch mode.
- Billing, organizations, or multi-admin teams.
- Backend package flattening from `backend/src/novelai` to another layout.

## 3. Non-Goals and Blocked Phases

Do not implement these during normal reliability or scheduler work:

- Prompt 12 public contribution credentials.
- Auth/user accounts.
- `owner_admin` roles.
- Public credential UI.
- Credential pooling or marketplace behavior.
- Database support.
- Batch mode.
- Billing, organizations, or multi-admin teams.
- Broad folder migrations or package flattening.

Prompt 12 remains blocked while the public contribution readiness gate is Not Ready. Do not fake user ownership with browser localStorage IDs, request-provided user names, unsigned cookies, or frontend-only flags.

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

No public contribution credential UI exists. Do not add it until the readiness gate is Ready.

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

## 12. Public Contribution Readiness Gate

Verdict: Not Ready.

Prompt 12 must not be implemented while this gate remains Not Ready.

Current blockers:

- No authenticated registered users.
- No `owner_admin` authorization boundary.
- No object-level authorization.
- No encrypted credential storage.
- No credential revocation/deletion/audit lifecycle.
- No per-credential usage limits.
- No contribution consent flow.
- No scheduler enforcement of contributed credential scope.
- No separation between public-user credential management and admin credential management.

Do not fake users with localStorage, request-provided user IDs, unsigned cookies, or frontend-only flags.

Before Prompt 12, the project needs:

1. Real authentication/account boundary.
2. Backend role/permission boundary with `owner_admin`.
3. Object-level authorization for credentials, requests, jobs, activities, novels, and exports.
4. Request approval semantics tied to authenticated requester/reviewer identities.
5. Encrypted credential storage.
6. Credential revoke/delete lifecycle.
7. Security audit logging.
8. Contribution consent capture.
9. Usage limits and scheduler scope enforcement.
10. Tests proving user A cannot access user B's objects and raw keys are never returned after creation.

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

Prompt 12 public contribution credentials remain blocked.

Prompt 13A baseline owner/admin security hardening is implemented. Full contribution-mode security remains future work because it depends on real auth, roles, object-level authorization, encrypted credential storage, and audit/consent boundaries.

## 14. Current Debt Register

P0 - correctness/security risk:

- Public contribution mode is blocked; do not implement credentials before auth, roles, object authorization, encrypted storage, audit, usage limits, and consent.
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
5. Add public auth/role/product boundary only if public contribution remains desired.
6. Run Prompt 12 only after the public contribution readiness gate says Ready.

Do not add new source sites before FetchService, source quality gates, and parser fixtures are stable.

Do not add batch mode before synchronous translation, scheduler, provider errors, storage contracts, and QA are reliable.

Do not add database support just to avoid designing storage contracts. Database migration is a product/scale decision, not a shortcut.

## 16. Codex Prompting Rules

Use this header in future Codex prompts:

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
