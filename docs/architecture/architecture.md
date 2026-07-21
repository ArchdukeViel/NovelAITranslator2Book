# NovelAI Architecture

## 0. Document Status

**Status**: canonical project architecture
**Last reviewed**: 2026-07-18 (free-tier development and launch-gate reconciliation)

This is the single active architecture reasoning file for NovelAI. If another document
disagrees with this one, this document wins and the conflict should be reported
before implementation.

## 1. Current Mode

```text
single-owner / controlled-admin public reading platform
FastAPI backend under /api
Next.js public reader + owner/admin UI
Storage-backed canonical novel metadata and content, Postgres catalog/user domain rows
background crawl/translation activity worker
own server session auth implemented for dangerous admin operations
guest public catalog / novel detail / chapter reader implemented
Google OAuth and email/password public login implemented (backend routes + frontend plumbing)
public user library/progress/history/reviews/requests frontend re-enabled
CSRF enforcement and basic public rate limits implemented
production session secret fails closed when left at default
public contribution credentials intentionally gated
future admin API methods quarantined until backend routes exist
chapter-level parallel translation via asyncio.Semaphore + bounded gather
NVIDIA provider removed; Gemini-only fallback chain
S3-compatible storage backend implemented; object-store deployments use the storage abstraction
pipeline/scheduler hardened: job-runtime persistence, model-state tracking
microservice-split readiness: dual entry points, DEPLOY_MODE
```

NovelAI is currently a web-based Japanese novel ingestion, translation, editing,
export, and public reader system. It is being shaped toward a WTR-LAB-style
machine-translated novel platform in product shape, not branding.

## 2. Product Boundary

**Surfaces**:

| Surface | Current state |
|---|---|
| Owner/admin | Active. Single owner operates crawling, imports, translation jobs, editing, exports, provider config, activity, runtime state, requests, and worker controls. |
| Guest public reader | Active. Guests can browse the public catalog, view novel detail, list chapters, and read chapters. |
| Registered public users | Active. Google OAuth and email/password backend routes exist, public login/sign-up UI supports both public auth paths, and frontend hooks for library/progress/history/reviews/requests are re-enabled. Public users receive `role="user"` sessions only. |
| Public contribution credentials | Deferred and gated. Public credential UI/API must remain disabled until the contribution readiness gate is satisfied. |
| Community features | Deferred. Folders/lists/rankings/community surfaces require public auth, moderation, and abuse controls first. |

The owner does dangerous operations. Users request or save personal state only
after public auth is implemented. Guests read published content.

### 2.1 Deployment Profiles and Cost Boundary

The repository has three distinct deployment profiles. They must not be
described as interchangeable:

| Profile | Intended topology | Operational contract |
|---|---|---|
| Local full development | Local frontend/backend plus Docker Redis and an external/local PostgreSQL database | The only zero-cost profile expected to run the continuous worker, scheduler, backup jobs, restore verifier, and SMTP acceptance tests reliably. |
| Hosted free preview | Vercel Hobby frontend, one Render Free monolith, Supabase Free PostgreSQL, and development-only R2 scope | Disposable preview only. Worker, scheduled backup, restore verification, maintenance, and SMTP delivery stay disabled because a sleeping/ephemeral free web service cannot satisfy those contracts. |
| Production | Vercel frontend, paid always-on container backend, Supabase PostgreSQL, R2 application and backup buckets, managed Redis, SMTP, and external monitoring | Must pass the launch checklist, recovery evidence, OAuth/CORS/CSRF/host validation, rollback, monitoring, and budget gates before public use. |

Free-tier use is a development cost policy, not a reliability claim. Vercel
Hobby is limited to personal/non-commercial use, Supabase Free can pause, and
Render Free can sleep or restart. Production must upgrade any service whose
free-plan terms, capacity, availability, or data-protection behavior do not
meet the launch contract.

The frontend may be hosted on Vercel, but the current backend is not a Vercel
Functions workload. Its continuous scheduler, long translation jobs, split
admin/reader processes, PostgreSQL client tools, and restore verifier require
long-running compute unless a separately approved architecture redesigns
those contracts around durable external workflows.

## 3. Backend Architecture

```text
backend/src/novelai/
  activity/          Background activity queue, runner, worker, progress, events
  api/               FastAPI app, routers, dependencies, error handlers, schemas
  api/auth/          Session management, role enforcement
  config/            Settings and workflow profiles
  core/              Shared domain errors and primitive types
  db/                SQLAlchemy engine, session, models
  db/models/         ORM models for users, catalog, jobs, settings, audit data
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
  worker/            Background worker tasks and queue management
```

**Layer rules**:

- API routers stay thin. Use-case logic belongs in `services/` or
  `services/orchestration/`.
- Source-specific parsing belongs in `sources/*`.
- HTTP fetching, throttling, SSRF checks, and fetch cache belong in
  `infrastructure/http/*`.
- Provider-specific API details belong in `providers/*`.
- Prompt construction belongs in `prompts/*`.
- Persistence belongs behind `storage/*` and `db/*` boundaries.
- Scheduler policy belongs in backend translation/service/job layers, not React.

**Router layer violations (deferred — see DEBT-054):**

| Router | Violations | Target Service |
|--------|------------|----------------|
| `library.py` | 3 `db.models` imports, 1 `sources.status`, 1 `StorageService`, ~30 storage calls | `LibraryService` |
| `admin_glossary.py` + 4 split routers | 6 `db.models.glossary`, `Novel`, 2 `providers.*`, `StorageService`, 6 storage calls | `GlossaryWorkflowService` |
| `auth.py` | 3 `db.models.users`, ~25 `session.*` CRUD calls | `AuthService` |
| `user_data.py` | 7 `db.models` symbols, 27 `session.*` CRUD calls | `UserLibraryService`, `ReadingService`, `ReviewService` |
| `public.py` | 3 `db.models` symbols, 1 `sources.status`, `StorageService`, ~18 storage calls | `PublicCatalogService` |
| `editor.py` | 1 inline `db.models.novel`, `StorageService`, 12 storage calls | `EditorService` |
| `requests.py` | 2 `db.models` symbols, full CRUD | `NovelRequestService` |
| `admin.py` | `StorageService`, 3 preflight `storage.load_metadata` | `AdminService` |
| `operations.py` | `StorageService`, 1 preflight `storage.load_metadata` | `OperationsService` |

**Dependency direction**:

```text
api -> services -> domain modules -> storage/db/providers/sources/export
translation -> prompts -> providers
scheduler -> providers through provider registry
frontend -> backend API clients only
```

**Forbidden direction**:

```text
storage -> api
db -> api
providers -> api
providers -> storage/db
sources -> services
frontend -> storage files
translation stages -> FastAPI request objects
React -> scheduler/provider/storage/QA policy
```

## 4. Translation Pipeline Architecture

**Canonical flow**:

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

**Core contracts**:

- `Paragraph`: `paragraph_id`, `chapter_id`, `text`, `char_count`
- `TranslationChunk`: `chunk_id`, `novel_id`, `chapter_ids`,
  `paragraph_ids`, `source_text`, `char_count`, `previous_context`,
  `paragraph_refs`

**Rules**:

- `SmartSegmentStage` owns segmentation.
- Paragraph IDs are deterministic within a chapter, for example `p0001`.
- Chunk IDs are deterministic, for example `c0001`.
- Every translated unit must preserve `novel_id`, `chapter_id`,
  `paragraph_id`, and `chunk_id`.
- Chapter-level translation is parallelized via `asyncio.Semaphore` + bounded
  `asyncio.gather` with `return_exceptions=True`. Per-chapter failures do not
  erase successful outputs for other chapters in the same job.
- `TranslationQAStage` runs after provider output and before final save.
- QA checks include empty output, source-identical output, suspicious length
  ratios, placeholders, provider refusal/error text, and mapping integrity.

## 5. Multi-Model Scheduler Architecture

**Status**: implemented for admin-owned provider/model routing.

**Responsibilities**:

- Select `provider_key` and `provider_model`.
- Track per-model RPM/RPD state, cooldown, and daily quota exhaustion.
- Pause jobs when every eligible model is cooling down or exhausted.
- Expose `paused_reason`, `resume_after`, and `model_states` through
  activity/job progress.
- Record provider/model per chunk attempt.

**Model statuses**: `available`, `cooling_down`, `daily_exhausted`,
`disabled`, `failed`.

The scheduler must not bypass prompt construction, glossary handling, cache-key
rules, provider request recording, chunk status tracking, or QA. It must not
leak provider credentials or request headers.

## 6. Source Ingestion Architecture

```text
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
- Source adapters do not write storage files directly or call translation
  providers.
- Generic source is fallback and must carry confidence/warnings.
- Source tests use offline fixtures and must not require live websites.

## 7. Storage and Database Boundary

**Current storage model**:

- Metadata and user/job records are Postgres-backed.
- Heavy chapter content remains file-backed under `storage/novel_library`
  locally and must stay private.
- Future deployed content may move behind an object-storage boundary, but API
  responses still return keys/identifiers, not raw filesystem paths.

**Runtime records include** novel metadata, raw scraped chapters, parsed data,
translated output, translation cache, activity log, pipeline events, chunk
states, provider request records, scheduler state, fetch cache, export
artifacts, users, saved data, requests, settings, and audit data.

**Rules**:

- Raw scraped chapter files should not be silently deleted after translation.
- Provider request records must not store API keys, authorization headers,
  cookies, raw secrets, or raw tracebacks.
- Frontend must never receive raw filesystem paths.
- `storage/novel_library` must never be served as static files.
- Routers must not directly own database session logic.

## 8. API and Frontend Contract Architecture

**Canonical names**: `source_key`, `source_novel_id`, `source_url`,
`novel_id`, `chapter_id`, `paragraph_id`, `chunk_id`, `bundle_id`,
`provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`,
`credential_id`, `requesting_user_id`, `credential_owner_user_id`,
`prompt_version`, `glossary_hash`.

**Forward-only contracts**: compatibility aliases are not accepted or emitted.
Use the canonical names above in storage, API, backend, frontend, and tests.
Breaking contract changes update all callers in the same change; do not add
fallback readers, mirrored fields, route aliases, import shims, or deprecated
library adapters.

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

**Current API contract status**:

| Area | Current contract |
|---|---|
| Admin namespace | `/api/admin/*` is canonical for implemented owner/admin behavior. Legacy `/api/novels/*` compatibility routes may remain temporarily. |
| Dangerous admin routes | Protected by owner-session authorization through `require_role("owner")`. |
| Legacy API-key auth | Fail-closed; do not rely on it for dangerous routes. |
| Public reader | `frontend/lib/public-api.ts` calls `/api/public/*` catalog, novel, chapter list, and chapter endpoints. |
| Public auth | Google OAuth and email/password public auth implemented: `GET /api/auth/google/start`, `GET /api/auth/google/callback`, `POST /api/auth/register`, and `POST /api/auth/password/login` create or resume `role="user"` sessions only. `POST /api/auth/login` remains admin-only owner bootstrap login. CSRF enforcement and rate limits protect auth mutations. |
| Public user data | Backend `/api/user/*` routes exist and public frontend API methods/hooks are re-exported for library, progress, history, reviews, and requests. |
| Admin future APIs | Exported future admin methods for missing endpoints are quarantined. Do not advertise `/api/admin/users`, `/api/admin/controls`, contributed credentials, or provider activation until backend routes exist. |

Public/frontend-facing errors must not include raw tracebacks, API keys,
authorization headers, cookies, provider secrets, or unsafe filesystem internals.

## 9. Frontend Architecture

```text
frontend/app/               Next.js App Router pages and route groups
frontend/components/        Reusable UI, admin, and public components
frontend/hooks/public/      Public reader hooks
frontend/lib/               API clients, shared types, client utilities
```

**Admin routes**: `frontend/app/(admin)/admin/*`.

**Public routes**: `frontend/app/(public)/*`.

**Contract layer**:

- `frontend/lib/api.ts` owns admin/shared backend calls.
- `frontend/lib/public-api.ts` owns the public reader API client.
- Direct `fetch(...)` and `axios(...)` calls are allowed only in approved API
  client files.
- Public hooks export guest-safe reader hooks (`useCatalog`, `useNovel`,
  `useChapters`, `useChapter`), public auth hooks, and authenticated user
  hooks for library/progress/history/reviews/requests.
- Public login uses Google OAuth and email/password through public auth
  endpoints. Library/progress/history/reviews/requests
  hooks are available to authenticated users.
- Contribution credential actions must remain unavailable until the contribution
  readiness gate is satisfied.

## 10. Security Architecture

**Protected data classification**:

| Class | Data |
|---|---|
| Critical | Provider API keys, admin/session tokens, encryption keys, `.env` and deployment secrets, backups containing runtime state. |
| High | Raw scraped chapters, parsed chapters, translation chunks, provider request/response records, unpublished translations, job events/logs. |
| Medium | Published translated chapters, public metadata, public assets. |

Gemini free-tier requests may be used only for public or otherwise
non-sensitive source/translation text. Critical data, account data, private
operator data, credentials, backups, logs, and unpublished sensitive content
must never be sent to a free-tier model. The approved model chain is
`gemini-3.1-flash-lite` followed by `gemma-4-31b-it`; both use the Gemini API.

**Baseline protections implemented**:

- Owner-session authorization for dangerous backend routes.
- Translation fails closed when Gemini credentials are unavailable; the dummy
  provider is selectable only under `ENV=test` and cannot persist production
  translations.
- HTTP-only same-site session cookies.
- Production session secret fails closed when left at default value.
- Path traversal protection for storage-backed identifiers.
- Runtime storage isolation.
- API/log secret redaction.
- Structured error envelopes; unknown 500s do not expose tracebacks.
- FetchService SSRF protection.
- CSRF token enforcement for cookie-authenticated state-changing endpoints.
- Basic public rate limits for auth, library, progress, history, review, and request operations.
- Git ignore policy for runtime storage, secrets, logs.

## 11. Authentication and Session Architecture

**Current status**: owner/admin session auth plus Google OAuth and
email/password public auth are implemented. Password reset and email
verification are not implemented yet.

**Single owner-admin rule**:

- Exactly one owner. The owner is the only admin.
- No admin-invitation flow, staff teams, or multi-admin permissions in v1.
- Owner is seeded via secure backend bootstrap, not public signup.

**Role model**:

```text
guest  - unauthenticated; read public catalog/chapters
user   - authenticated public user; library, progress, history, ratings/reviews, requests
owner  - authenticated single owner; dangerous operations
```

**Current auth endpoints**:

- `POST /api/auth/login`: owner bootstrap login only.
- `POST /api/auth/logout`: clears current session.
- `GET /api/auth/me`: returns the current session user or guest.
- `GET /api/auth/csrf`: returns the session-bound CSRF token for
  state-changing cookie-auth requests.
- `POST /api/auth/register`: creates a public email/password `role="user"`
  account and session.
- `POST /api/auth/password/login`: verifies a public email/password account and
  creates a `role="user"` session.
- `GET /api/auth/google/start`: starts public Google OAuth.
- `GET /api/auth/google/callback`: validates Google OAuth and creates/resumes
  a `role="user"` session.

**Public auth implementation**:

- Public login UI uses Google OAuth (`GET /api/auth/google/start`) and
  email/password public endpoints, never the owner bootstrap `/api/auth/login`.
- Google OAuth and email/password auth create or resume `role="user"` sessions
  only; they never create or promote an owner account.
- Frontend login view offers "Continue with Google", email/password sign-in,
  and email/password sign-up. Google OAuth requires Dokushodo OAuth
  configuration.
- Public auth UI must not expose owner, admin, secret, or bootstrap wording.
- Owner bootstrap login is admin-only and separate from public sign-in/sign-up.
- Contribution credential UI remains gated and unavailable.

## 12. Implemented and Deferred State

| Area | Status |
|---|---|
| Owner-session auth boundary | Implemented and tested. |
| Dangerous route owner protection | Implemented and tested. |
| Fail-closed legacy API-key behavior | Implemented and tested. |
| Canonical `/api/admin/*` aliases for existing admin behavior | Implemented and tested. |
| Public contribution UI gate | Implemented and tested. |
| Public auth UX gate | Implemented and tested. |
| Public user API frontend quarantine | Implemented and tested. |
| Admin future API frontend quarantine | Implemented and tested. |
| Guest public catalog/novel/chapter reader | Implemented. |
| Google OAuth public login (backend + frontend) | Implemented. |
| Email/password public auth (backend + frontend) | Implemented. |
| Admin-only owner bootstrap login surface | Implemented. |
| Auth smoke after backend/frontend/admin-owner-login phases | Passed. |
| Public user library/progress/history/reviews/requests frontend | Implemented. |
| CSRF enforcement for cookie-auth mutations | Implemented. |
| Basic public rate limits | Implemented. |
| Production session secret fail-closed | Implemented. |
| Structured error handling + logging system | Implemented. StructuredHTTPException, PipelineContext, JsonFormatter, /health/errors endpoint, trace_id propagation. |
| Glossary auto-population | Implemented. SuggestionExtractor, GlossarySuggestionService, review/reject/apply API, pipeline integration. |
| Microservice-split readiness | Implemented. main_reader/main_admin entry points, DEPLOY_MODE dispatch (monolith/split), Docker Compose + Caddy split routing, 14 contract tests. |
| Advanced translation caching | Implemented. TranslationCacheService (SHA-256 keys, sharded file storage, TTL), pipeline integration, glossary invalidation, /api/admin/cache/* endpoints. |
| Adapter plugin system | Implemented. SourceAdapter ABC, AdapterRegistry (pkgutil auto-discovery, get_by_key, list_adapters), all adapters refactored, bootstrap registration. |
| Public contribution credential backend lifecycle | Deferred. |
| Server-side encryption/revocation/validation/usage ledger for contributed credentials | Deferred. |
| Admin user-management backend/UI | Deferred. |
| Admin controls config backend | Deferred. |
| Contributed credential oversight backend | Deferred. |
| WTR-style community folders/lists | Deferred. |
| Rankings/leaderboards/trending pages | Deferred. |
| Rich finder/tags/discovery | Partially present only as basic catalog parameters; richer UX deferred. |

## 13. Public Contribution Credentials - Later Gated Phase

**Verdict**: later gated phase, not in the current safe product surface.

Public API contribution, where registered users donate Gemini provider
quota, opens only after all of the following exist and are tested:

- Real public authentication/account boundary.
- Strict object-level authorization.
- Encrypted contributed-credential storage; raw keys never returned, logged, or
  exposed.
- Explicit contribution consent capture.
- Credential revocation/deletion lifecycle.
- Credential validation before activation.
- Per-credential usage limits and scheduler enforcement of contributed scope.
- Usage ledger recording every contributed-credential request.
- Security audit records for create/use/revoke/delete.
- Provider isolation so a contributed credential is used only for its own scope.
- Abuse and rate-limit controls.
- Owner approval/disable controls.

Do not fake users with localStorage IDs, request-provided names, unsigned
cookies, or frontend-only flags.

## 14. WTR-LAB-Inspired Product Gap Matrix

| Product area | WTR-LAB-style target | Current project state | Gap | Dependency | Priority |
|---|---|---|---|---|---|
| Public catalog | Browse translated novels publicly | Implemented basic guest catalog via `/api/public/catalog` | Needs stronger UX, pagination polish, status/sort clarity | Guest reader contract | High |
| Novel finder/search/filter | Finder with title/author/status/source filters | Basic catalog params exist | Rich finder UI and backend semantics incomplete | Catalog contract, metadata quality | High |
| Tags/genres | Tag and genre browsing | Architecture references tags, but active UX not proven | Tag data model/API/UI needs design | Metadata model, admin tagging | Medium |
| Ranking/leaderboard/trending | Popular/trending/ranking pages | Placeholder ranking page exists without fake metrics | Needs metrics, jobs, anti-gaming rules before live rankings | Public analytics, user events | Medium |
| Novel detail metadata | Cover, synopsis, source, chapter list, status | Basic novel detail/chapter list exists | Rich metadata, cover/assets, recommendations missing | Metadata ingestion, public UI | High |
| Chapter reader | Clean mobile reader with navigation | Implemented guest chapter reader | Reader preferences and polish deferred | Reader UX pass | High |
| Reading preferences | Font/theme/layout controls | Not established as complete | Preferences persistence and UX missing | Public auth for saved prefs; local guest prefs optional | Medium |
| Public login | Google/email login for users | Google OAuth plus email/password public login/sign-up implemented | OAuth deployment validation, password reset, and email verification later | Auth tests, deployment config | P0 |
| User library | Save novels to library | Implemented for authenticated public users | UX polish and update alerts remain | Public auth, `/api/user/*` ownership tests | P0 |
| Reading progress/history | Continue reading/history | Implemented for authenticated public users | UX polish and reader preferences remain | Public auth, ownership tests | P0 |
| Ratings/reviews | User ratings and reviews | Implemented for authenticated public users with basic controls | Moderation policy and anti-spam depth need more hardening | Public auth, moderation policy | High |
| Requests/requesters | Users request novels/chapters | Public request UI and account request history implemented | Owner approval semantics and audit depth need polish | Public auth, request ownership | High |
| Community folders/lists | User-created lists/folders/community discovery | Not implemented | Full feature missing | Public auth, moderation, abuse controls | Low |
| Admin import/crawl | Owner imports/crawls sources | Implemented active admin workflows | Needs ongoing source hardening | FetchService/source fixtures | High |
| Admin translation/job operations | Owner queues/translates/monitors jobs | Implemented active workflows | Needs operational polish and resume hardening | Worker/scheduler hardening | High |
| Admin moderation/approval | Owner reviews requests/content | Admin request review exists | Public request approval semantics and audit depth need work | Public user request contract | Medium |
| Contributed API credentials | Users donate provider quota safely | Intentionally gated and unavailable | Entire secure lifecycle missing | Auth, encryption, ledger, owner approval, abuse controls | Do not build yet |

## 15. Current Debt Register

See consolidated register: [`docs/DEBT.md`](../DEBT.md).

## 16. Dependency-Aware Roadmap

Roadmap phases and release gates are documented in the central roadmap file: [`docs/roadmap.md`](../roadmap.md).

## 17. Do Not Build Yet

- Do not route public login through owner bootstrap `/api/auth/login`. Public
  login must use Google OAuth or email/password public auth endpoints only.
- Do not re-enable contribution credentials until encryption, revocation,
  validation, usage ledger, owner approval, and abuse controls exist.
- Do not add fake `/api/admin/*` endpoints to satisfy future frontend methods.
- Do not add WTR-style community features before user auth, moderation, and
  abuse controls exist.
- Do not polish around broken contracts; stabilize the contract first.
- Do not implement batch mode, billing, organizations, multi-admin teams, or
  broad package flattening without a dedicated architecture update.
- Do not accept client-supplied `user_id` for user-owned data.
- Do not create or promote owner accounts through public OAuth or
  email/password registration.

## 18. Validation Commands

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

## 19. Agent Prompting Rules

Use this header in future agent prompts:

```text
You are working inside the NovelAI project. Follow docs/architecture/architecture.md as the highest project-level design authority.

Non-negotiable rules:
- Keep API routers thin.
- Put use-case logic in services/orchestration.
- Put source parsing only in source adapters/parsers.
- Put HTTP fetching, throttling, and fetch cache in infrastructure/http.
- Put persistence only behind storage and db services.
- Put prompt construction only in prompts.
- Put provider-specific API logic only in providers.
- Put scheduler policy in translation/service/job layers. React may surface admin UI controls that trigger backend endpoints, but policy logic stays backend-owned.
- Frontend must call backend only through approved frontend API clients.
- Preserve canonical names: source_key, novel_id, chapter_id, paragraph_id, chunk_id, provider_key, provider_model, activity_id, job_id, request_id.
- Add/update tests for every changed contract.
- Do not implement public contribution credentials until the contribution gate conditions are met.
- Raw API keys must never be returned, logged, or exposed after creation.
- Storage runtime data must not be served directly.
- Before editing, identify which architectural boundary owns the change.
```

When asked for a review, prioritize architecture violations, bugs, behavioral
regressions, missing tests, and contract drift.

## 20. Permission Matrix

Single-owner platform with guest/user/owner roles. Enforced in the backend, not
by hiding frontend routes.

| Capability | Guest | User | Owner |
|---|---|---|---|
| View public catalog | Yes | Yes | Yes |
| Read public chapters | Yes | Yes | Yes |
| Search/filter novels | Basic | Yes | Yes |
| Save to library | No | Yes | Yes |
| Track reading progress | No | Yes | Yes |
| Rate/review | No | Yes, rate-limited | Yes |
| Request novel/chapter | No | Yes, rate-limited | Yes |
| Start crawler | No | No | Yes |
| Start translation | No | No | Yes |
| Edit metadata/content | No | No | Yes |
| Delete/unpublish content | No | No | Yes |
| View logs/errors | No | No | Yes |
| Configure providers | No | No | Yes |
| View provider/API usage | No | No | Yes |
| Manage users | No | Deferred | Deferred owner feature |
| Change system settings | No | No | Deferred owner feature |

## Managed-Service Operational Boundary

- SQLAlchemy engines are process singletons keyed by effective configuration. Direct/session connections use bounded pools; transaction-pooler connections use `NullPool` without automatic prepared statements.
- Scheduled backup, maintenance, and database-export work requires a renewable PostgreSQL lease. Host-local file locks remain an additional filesystem safeguard, not the distributed coordinator.
- R2 application CRUD, snapshot-source reads, and backup-target writes use separate credentials. Snapshots stream through the application because the target credential must not read the production bucket.
- Free-plan managed PostgreSQL recovery uses encrypted logical exports stored independently from Supabase. Object snapshots and database dumps use separate committed prefixes and retention policies.

**Core rule**: owner does dangerous operations. Future users save personal
state and request things after public auth exists. Guests read public content.
