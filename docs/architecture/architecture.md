# NovelAI Architecture

## 0. Document Status

**Status**: canonical project architecture
**Last reviewed**: 2026-06-09

This is the single active architecture reasoning file for NovelAI. Historical notes are archived under `docs/archive/architecture/`.

## 1. Current Mode

```text
single-owner / controlled-admin public platform
Postgres-backed metadata (12 models), file-backed chapter content
Redis/RQ background workers for crawl and translation jobs
guest/user/owner authentication (backend-enforced)
public reader + user library/progress/ratings/requests
scheduler-enabled for admin-owned provider/model routing
baseline owner/admin security hardened
```

## 2. Product Boundary

NovelAI is a web-based Japanese novel ingestion, translation, editing, library, and export system.

**Surfaces**:
1. **Owner/admin surface**: crawl/import sources, manage jobs, translate chapters, edit output, configure providers, inspect activity/scheduler state, export.
2. **Public reader surface**: browse published translated novels and read published chapters.
3. **Registered user surface**: sign up, log in, save novels to library, track reading progress, rate/review, request novels/chapters.
4. **Contribution surface** (later gated phase): registered users contribute Gemini/OpenAI provider quota. Blocked pending §12.

## 3. Backend Architecture

```
backend/src/novelai/
  activity/          Background activity queue, runner, worker, progress, events
  api/               FastAPI app, routers, dependencies, error handlers, schemas
  api/auth/          Session management, role enforcement
  config/            Settings and workflow profiles
  core/              Shared domain errors and primitive types
  db/                SQLAlchemy engine, session, models
  db/models/         ORM models: User, Novel, Chapter, CrawlJob, TranslationJob, etc.
  export/            Exporter interfaces and concrete output formats
  glossary/          Glossary and term memory logic
  infrastructure/    HTTP fetching, throttle, cache
  inputs/            Non-web input adapters
  prompts/           Prompt builders, templates, response parsing
  providers/         LLM provider interfaces and implementations
  runtime/           Dependency container, bootstrap, CLI runtime
  services/          Application use cases and orchestration
  shared/            Cross-domain protocols, pipeline contracts
  sources/           Web source parsers/adapters and source registry
  storage/           File-backed persistence boundary
  translation/       Translation stages, QA, scheduler, post-processing
  worker/            RQ worker tasks and queue management
```

**Layer rules**:
- API routers stay thin. Use-case logic belongs in `services/`.
- Source-specific parsing belongs in `sources/*`.
- HTTP fetching/throttling/cache belongs in `infrastructure/http/*`.
- Provider-specific API details belong in `providers/*`.
- Prompt construction belongs in `prompts/*`.
- Persistence belongs behind `storage/*`.
- Frontend calls backend only through `frontend/lib/api.ts`.

**Dependency direction**:
```
api -> services -> domain modules -> storage/providers/sources/export
translation -> prompts -> providers
scheduler -> providers through provider registry
frontend -> backend API only
```

**Forbidden direction**:
```
storage -> api
providers -> api
providers -> storage
sources -> services
frontend -> storage files
translation stages -> FastAPI request objects
React -> scheduler/provider/storage/QA policy
```

## 4. Translation Pipeline Architecture

**Canonical flow**:
```
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

**Core contracts**:
- `Paragraph`: `paragraph_id`, `chapter_id`, `text`, `char_count`
- `TranslationChunk`: `chunk_id`, `novel_id`, `chapter_ids`, `paragraph_ids`, `source_text`, `char_count`, `previous_context`, `paragraph_refs`

**Rules**:
- `SmartSegmentStage` owns segmentation.
- Paragraph IDs are deterministic within a chapter (e.g., `p0001`).
- Chunk IDs are deterministic (e.g., `c0001`).
- Every translated unit must preserve `novel_id`, `chapter_id`, `paragraph_id`, `chunk_id`.
- `TranslationQAStage` must run after provider output and before final save.
- QA checks: empty output, source-identical output, suspicious length ratios, placeholders, provider refusal/error text, paragraph/chapter mapping integrity.

## 5. Multi-Model Scheduler Architecture

**Status**: implemented for admin-owned provider/model routing.

**Responsibilities**:
- Select `provider_key` and `provider_model`.
- Track per-model RPM/RPD state, cooldown, daily quota exhaustion.
- Pause jobs when every eligible model is cooling down or exhausted.
- Expose `paused_reason`, `resume_after`, `model_states` through activity/job progress.
- Record provider/model per chunk attempt.

**Model statuses**: `available`, `cooling_down`, `daily_exhausted`, `disabled`, `failed`

**The scheduler must not**:
- Bypass prompt construction, glossary handling, cache-key rules, provider request recording, chunk status tracking, or QA.
- Leak provider credentials or request headers.
- Randomly rotate models when consistency matters.
- Retranslate successful chunks after pause/resume unless explicitly forced.

## 6. Source Ingestion Architecture

```
SourceRegistry
-> SourceAdapter.detect / normalize
-> FetchService (shared HTTP client, SSRF-safe URL validation, per-domain throttle, fetch cache)
-> Source parser (metadata, chapter list, chapter payload, images/assets)
-> SourceQualityGate
-> StorageService
```

**Rules**:
- Source registry is the only source lookup mechanism.
- Source-specific selectors stay in `sources/*`.
- Source adapters do not write storage files directly or call translation providers.
- Generic source is fallback and must carry confidence/warnings.
- Source tests use offline fixtures; they must not require live websites.

**Implemented**: FetchService foundation, URL safety/SSRF protection, per-domain throttle, fetch cache, source quality gates, Generic confidence scoring, offline fixtures for Syosetu/Novel18, Kakuyomu, Generic.

## 7. Storage and Runtime Data Architecture

Storage is file-backed under `storage/novel_library` (private, gitignored).

**Canonical storage remains chapter-based**:
- chapter raw snapshot
- parsed chapter
- final translated chapter
- translation versions / edits
- chapter state

**Runtime records**: novel metadata, raw scraped chapters, parsed data, translated output, translation cache, usage data, activity log, pipeline events, chunk states, provider request records, scheduler state, fetch cache, export artifacts.

**Rules**:
- Raw scraped chapter files should not be silently deleted after translation.
- Provider request records must not store API keys, authorization headers, cookies, raw secrets, or raw tracebacks.
- Frontend must never receive raw filesystem paths.
- `storage/novel_library` must never be served as static files.

## 8. API and Frontend Contract Architecture

**Canonical names**: `source_key`, `source_novel_id`, `source_url`, `novel_id`, `chapter_id`, `paragraph_id`, `chunk_id`, `bundle_id`, `provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`, `credential_id`, `requesting_user_id`, `credential_owner_user_id`, `prompt_version`, `glossary_hash`

**Compatibility aliases** (debt, tolerated): `id`, `source`, `provider`, `model`, `slug`

**Error envelope**:
```json
{
  "code": "PROVIDER_ERROR",
  "message": "Human-readable summary",
  "explanation": "What this usually means",
  "details": {},
  "trace_id": "optional"
}
```

**Rules**:
- Public/frontend-facing errors must not include raw tracebacks, API keys, authorization headers, cookies, provider secrets, or unsafe filesystem internals.
- Frontend API calls go through `frontend/lib/api.ts`.
- Progress payloads: `status`, `current_stage`, `current_label`, `completed`, `total`, `errors`, `warnings`, `paused_reason`, `resume_after`, `model_states`.

## 9. Frontend Architecture

```
frontend/app/               Next.js App Router pages and route groups
frontend/components/        Reusable UI, admin, and public components
frontend/lib/               API client, shared types, client utilities
```

**Admin routes**: `frontend/app/(admin)/admin/*` (dashboard, crawler, translation, library, editor, activity, requests, settings)

**Public routes**: `frontend/app/(public)/*` (novel catalog, chapter reader)

**Contract layer**:
- `frontend/lib/api.ts` is the only browser/backend API client.
- Admin pages render workflows and call typed API functions.
- React displays scheduler state, QA state, provider state returned by the backend. React does not decide those policies.
- No public contribution credential UI exists until §12 opens.

## 10. Security Architecture

**Protected data classification**:

**Critical**: Provider API keys, admin/session tokens, encryption keys, `.env` and deployment secrets, backups containing runtime state.

**High**: Raw scraped chapters, parsed chapters, translation chunks, provider request/response records, unpublished translations, job events/logs.

**Medium**: Published translated chapters, public metadata, public assets.

**Baseline protections implemented**:
- Path traversal protection for storage-backed identifiers.
- Runtime storage isolation; `storage/novel_library` is private.
- API/log secret redaction for API keys, bearer tokens, cookies, authorization headers, passwords.
- Structured error envelopes; unknown 500s do not expose tracebacks.
- FetchService SSRF protection.
- Git ignore policy for runtime storage, secrets, logs.

**URL safety rejects**: private/internal targets, non-http schemes, embedded URL credentials, localhost, metadata hostnames, loopback, private ranges, link-local, reserved, multicast, unspecified addresses.

## 11. Authentication and Session Architecture

**Status**: implemented for v1.

**Single owner-admin rule**:
- Exactly one owner. The owner is the only admin.
- No admin-invitation flow, no staff/team permissions in v1.
- Owner is seeded via secure backend bootstrap (env/CLI), never via public signup.

**Role model** (backend-enforced):
```
guest  - unauthenticated; read public catalog/chapters, search only
user   - authenticated; library, reading progress, history, ratings/reviews, requests
owner  - authenticated; all dangerous operations (crawl, translate, providers, usage, logs, edit/delete, settings, user management)
```

**Enforcement**:
- Authorization is enforced in the backend API, not by hiding frontend routes.
- Every dangerous router requires `require_role("owner")` dependency.
- Object-level authorization: user may only read/write their own saved data.
- Ownership is established only by backend session/authorization layer.

**Session strategy**:
- HTTP-only, same-site session cookies with server-side session state.
- JWT is NOT the v1 default.
- Google OAuth is the first/primary intended login method for public users.

## 12. Database Boundary

**Status**: implemented. Supabase PostgreSQL 16 with SQLAlchemy 2.x ORM.

**Database owns**:
- Users and roles, auth-provider identities.
- Sessions and ownership links.
- Saved data: library items, reading progress, ratings/reviews, requests.
- Catalog metadata: novels, chapters (with storage keys + checksums), tags.
- Job/usage records: crawl jobs, translation jobs, provider requests.
- Audit logs and system settings.

**Database does NOT own**:
- Raw chapter text, translated chapter text, covers, exports, logs — those live in file/object storage; database stores keys/paths/checksums.

**ORM models** (12 total):
- `User`, `LibraryItem`, `ReadingProgress`, `ReadingHistory`, `Review`, `NovelRequest`
- `Novel`, `Chapter`
- `CrawlJob`, `TranslationJob`, `ProviderRequest`
- `AuditLog`, `SystemSetting`

**Rules**:
- All database access lives behind `db/` boundary consumed by `services/*`.
- Routers never touch the session directly.
- Storage-path knowledge stays in storage boundary; database stores keys, not absolute filesystem paths.
- Supabase RLS policies enforce guest/user/owner access at the database level (see `docs/sql/rls_policies.sql`).

## 13. Public Contribution Credentials — Later Gated Phase

**Verdict**: Later gated phase (NOT in v1, NOT blocked indefinitely).

Public API contribution (registered users donating Gemini/OpenAI provider quota) opens only after ALL of the following exist and are tested:

- Encrypted contributed-credential storage (encryption at rest; raw keys never returned, logged, or exposed).
- Explicit contribution consent capture per credential.
- Credential revocation/deletion lifecycle.
- Per-credential usage limits and scheduler enforcement of contributed credential scope.
- Security audit records for credential create/use/revoke/delete.
- Strict object-level authorization (user A cannot access user B's credentials, requests, jobs, activities, novels, or exports).
- Per-user ownership of each contributed credential.
- Credential validation before activation.
- Usage ledger recording every contributed-credential request.
- Provider isolation so a contributed credential is used only for its own provider and scope.
- Abuse and rate-limit controls.
- Owner disable controls to globally suspend contribution or disable a specific credential.

**Gate prerequisites** (build order):
1. Real authentication/account boundary (§11).
2. Backend role/permission boundary (guest/user/owner).
3. Object-level authorization.
4. Request approval semantics tied to authenticated requester/reviewer identities.
5. Encrypted credential storage.
6. Credential revoke/delete lifecycle.
7. Security audit logging.
8. Contribution consent capture.
9. Usage limits and scheduler scope enforcement.
10. Tests proving user A cannot access user B's objects and raw keys are never returned.

Do not fake users with localStorage, request-provided user IDs, unsigned cookies, or frontend-only flags.

## 14. Current Debt Register

**P0 — correctness/security risk**:
- Public contribution credentials are a later gated phase (§13); do not implement before gate conditions are met.
- Runtime provider request records and chunk output records must remain complete for scheduler-managed paths.
- Successful chunk reuse after pause/resume needs continued hardening.
- Private runtime storage must stay isolated from frontend/static serving.

**P1 — maintainability/reliability risk**:
- Temporary bundle lifecycle needs hardening around retry, debug retention, cleanup.
- Kakuyomu/Generic FetchService migration if legacy direct HTTP behavior remains.
- `operations.py` and `admin.py` remain thicker than ideal; thin through service extraction.
- Legacy aliases (`id`, `source`, `provider`, `model`) need planned migration.
- Storage backward compatibility needs continued discipline.
- Source parser fixtures are representative, not exhaustive against live-site drift.

**P2 — cleanup/cosmetic**:
- Frontend lint not configured non-interactively.
- Backend package flattening deferred.
- More examples for provider request records, chunk outputs, bundle lifecycle may help future maintainers.

## 15. Non-Goals and Blocked Phases

**Still blocked/gated** (do NOT implement):
- Public contribution credentials (later gated phase, §13).
- Public credential UI.
- Credential pooling or marketplace behavior.
- Batch mode.
- Billing, organizations, multi-admin teams.
- Broad folder migrations or package flattening.

## 16. Future Roadmap

**Recommended order**:
1. Scheduler runtime persistence and resume hardening.
2. Migrate remaining source adapters to FetchService.
3. Thin routers by moving remaining orchestration into services.
4. Optional backend package flattening as a dedicated mechanical migration.
5. Object storage boundary for deployed content/assets/exports (S3/R2/B2).
6. Data migration script from file-backed storage to Postgres (parallel-run).
7. Open the contribution-credentials gated phase only after §13's conditions are met and tested.

Do not add new source sites before FetchService, source quality gates, and parser fixtures are stable.

Do not add batch mode before synchronous translation, scheduler, provider errors, storage contracts, and QA are reliable.

## 17. Validation Commands

**Backend**:
```bash
./.venv/Scripts/python -m pytest backend/tests -q
./.venv/Scripts/python -m pyright
```

**Frontend**:
```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

**Docs and git hygiene**:
```bash
git status --short
git diff --stat
git diff --check
```

## 18. Agent Prompting Rules

Use this header in future agent prompts:

```
You are working inside the NovelAI project. Follow docs/architecture/architecture.md as the highest project-level design authority.

Non-negotiable rules:
- Keep API routers thin.
- Put use-case logic in services/orchestration.
- Put source parsing only in source adapters/parsers.
- Put HTTP fetching, throttling, and fetch cache in infrastructure/http.
- Put persistence only behind storage services.
- Put prompt construction only in prompts.
- Put provider-specific API logic only in providers.
- Put scheduler policy in translation/service/job layer, not providers or React.
- Frontend must call backend only through frontend/lib/api.ts.
- Preserve canonical names: source_key, novel_id, chapter_id, paragraph_id, chunk_id, provider_key, provider_model, activity_id, job_id, request_id.
- Add/update tests for every changed contract.
- Do not implement public contribution credentials until §13 gate conditions are met.
- Raw API keys must never be returned, logged, or exposed after creation.
- Storage runtime data must not be served directly.
- Before editing, identify which architectural boundary owns the change.
```

When asked for a review, prioritize architecture violations, bugs, behavioral regressions, missing tests, and contract drift.

When asked for cleanup, avoid package flattening, broad migrations, and unrelated refactors unless explicitly requested.

---

## 18. Permission Matrix

Single-owner platform with guest/user/owner roles. Enforced in the backend, never the frontend.

| Capability | Guest | User | Owner |
|---|---|---|---|
| View public catalog | Yes | Yes | Yes |
| Read public chapters | Yes | Yes | Yes |
| Search/filter novels | Yes | Yes | Yes |
| Save to library | No | Yes | Yes |
| Track reading progress | No | Yes | Yes |
| Rate/review | No | Yes | Yes |
| Request novel/chapter | Limited | Yes (rate-limited) | Yes |
| Start crawler | No | No | Yes |
| Start translation | No | Request only | Yes |
| Edit metadata | No | No | Yes |
| Delete/unpublish content | No | No | Yes |
| View logs/errors | No | No | Yes |
| Configure providers | No | No | Yes |
| View provider/API usage | No | No | Yes |
| Manage users | No | No | Yes |
| Change system settings | No | No | Yes |

**Core rule**: Owner does dangerous operations. Users request things. Guests read public content.

RLS policies at `docs/sql/rls_policies.sql` enforce this at the database level.
