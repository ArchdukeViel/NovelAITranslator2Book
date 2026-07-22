# Technical Debt Register

Single source of truth for technical debt and its resolution history. Resolved
entries remain as evidence; active counts include Pending, Ongoing, and
implemented items whose operational acceptance remains pending. Explicitly
Deferred items are tracked but excluded from the active count.

---

## Executive Summary

- **Total active debt entries:** 26
- **V1 launch blockers:** 4 (DEBT-075, DEBT-078, DEBT-079, DEBT-094)
- **Critical security/data integrity:** 0

---

## V1 Launch Blockers

### DEBT-001 — Health endpoint lacks real probes
- **Milestone:** Milestone 2a (Health Probes)
- **Category:** Backend | Observability
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/services/health_service.py`, `backend/src/novelai/api/routers/health.py`
- **Description:** The legacy `/api/health` endpoint returned static
  `{"status": "ok"}` without database, storage, or worker probes.
- **Completion criteria:**
  - `/health/live` provides process-only liveness and `/health/ready` provides
    dependency readiness.
  - Ready check fails with 503 if DB or storage is down.
  - Probes sanitize credentials and raw error tracebacks.
- **Resolution:** Implemented `HealthService` with bounded probes for database, storage, worker, and disk. Added `/health/live` (liveness), `/health/ready` (readiness, 503 on unhealthy), and `/api/admin/health` (owner-only diagnostics). Public responses redact paths, credentials, and stack traces. 16 health service tests + 8 API tests pass.

### DEBT-002 — CI/CD build.yml not verified on push to main
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** CI/CD
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `.github/workflows/build.yml`, Dockerfiles
- **Description:** Actions build file corrected to match current Dockerfile naming but needs remote run check to verify image pushes.
- **Completion criteria:** Workflow runs green on push to main, writing three GHCR image tags.
- **Resolution:** All three images pushed to GHCR with `latest` and SHA tags. Build run: <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29231656072>
  - `ghcr.io/archdukeviel/novelaitranslator2book/novelai-admin` (SHA + latest)
  - `ghcr.io/archdukeviel/novelaitranslator2book/novelai-reader` (SHA + latest)
  - `ghcr.io/archdukeviel/novelaitranslator2book/novelai-frontend` (SHA + latest)

### DEBT-003 — DB-dependent tests fail on CI (no Postgres runner)
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Testing | CI/CD
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `.github/workflows/ci.yml`, test files
- **Description:** CI workflow lacked PostgreSQL service. Real DB tests fail on Actions run.
- **Completion criteria:** Actions yaml has `services.postgres` setup and all web/integration tests pass.
- **Resolution:** Added `services.postgres` (postgres:16, port 5432, healthcheck) to backend-tests job. DATABASE_URL is set for alembic migration only; unit tests use SQLite in-memory isolation. ENV=test prevents bootstrap credential hydration. Verified green: <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29230504497>

### DEBT-006 — Circular import in admin_glossary routers
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Architecture
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/api/routers/admin_glossary.py` and related split routers
- **Description:** Mutual imports between admin glossary and sub-routers block module load and test collection.
- **Completion criteria:** Extracted helper functions and model schema definitions to a clean non-circular shared file.
- **Evidence:** Created `backend/src/novelai/api/schemas/admin_glossary.py` with all shared schemas, type aliases, and helpers, outside `api/routers/` to keep the router guard clean. Updated all 5 glossary routers, `app.py`, `main_admin.py`, 2 test files. Replaced lazy `_ensure_sub_routers_merged()` with eager module-level import. `test_admin_glossary_api.py` passes all 53 tests.

---

## Technical Debt Register (Phase 2+ / Roadmap)

### DEBT-007 — PDF exporter stubbed but not implemented
- **Milestone:** Milestone 2b (PDF Resolution)
- **Category:** Backend | Feature
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/runtime/bootstrap.py`, `backend/src/novelai/services/export_service.py`
- **Description:** PDFExporter registered but raises NotImplementedError. No font policy or generator dependency available.
- **Completion criteria:** Remove active registration, deprecate format, reject requests, preserve historical manifests.
- **Resolution:** Removed the dead `PDFExporter` implementation, its import,
  and `register_exporter("pdf", ...)` from `bootstrap_exporters()`.
  `ExportService.export("pdf", ...)` and `export_pdf()` raise
  `UnsupportedExportFormatError` with a safe deprecation message.
  `OperationsService` catches this and returns `OperationError(400)`.
  Historical manifests with `format: "pdf"` are preserved because the manifest
  service stores format as a free-form string.

### DEBT-008 — No admin user management endpoints
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Feature
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/api/routers/admin.py`
- **Description:** CRUD endpoints for listing, creating, and modifying admin users do not exist.
- **Completion criteria:** Functional admin CRUD endpoints restricted to owner.

### DEBT-009 — No notification system
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** New backend service
- **Description:** Lack of email or webhook alerts for job updates.
- **Completion criteria:** Event bus triggers SMTP alerts or webhooks.

### DEBT-010 — No scheduled backups
- **Milestone:** Milestone 2c (Backup & Storage)
- **Category:** Operations | Data Integrity
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/services/backup_manager.py`, `backend/src/novelai/services/backup_service.py`, `backend/src/novelai/services/scheduler_service.py`
- **Description:** BackupManager exists but has no container integration, scheduled trigger, or retention policy.
- **Completion criteria:** Scheduled task writes file backups, cleans old archives, and reports counts.
- **Resolution:** Added `apply_retention()` to `BackupManager` with multi-process file locking for filesystem backups. `BackupService` now creates manifest-last, conditionally copied, SHA-256-verified snapshots in a separately configured S3-compatible bucket when production storage uses S3. `SchedulerService` records actual success, failure, or lock-skip results instead of marking every attempt successful. The lightweight scheduler is asyncio-based and currently gates one run per UTC day; it does not use APScheduler or evaluate full cron syntax.

### DEBT-011 — No analytics dashboard
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** New dashboard service
- **Description:** Activity counts and resource usage are not gathered.
- **Completion criteria:** Ingest engine lists active reads, crawls, and token counts.

### DEBT-021 — Remove compatibility aliases and shims
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Data Migration
- **Priority:** Medium
- **Status:** Ongoing
- **Affected areas:** Global codebase
- **Description:** Forward-only architecture now forbids old fields (`slug`,
  `provider`, `model`, `id`, `source`), mirrored payload fields, route aliases,
  import shims, and deprecated library adapters.
- **Completion criteria:** All production callers and tests use canonical names;
  compatibility routes, imports, fields, and dependencies are removed.
- **Progress (2026-07-18):** Storage artifacts and crawl-result metadata are
  forward-only. Public catalog payloads and filters now use only
  `publication_status`, and module-level public-catalog test wrappers are
  removed. Runtime storage configuration now accepts and exposes only
  `NOVEL_LIBRARY_DIR`; the `DATA_DIR` environment/property alias is removed.
  The package-level meta-path compatibility loader and its legacy module import
  aliases are removed. Provider-registry lookups and registrations now reject
  unsupported keys instead of silently falling back to Gemini or ignoring the
  request, and provider errors require structured codes instead of accepting a
  legacy message-only constructor. `PreferencesService` provider key/model
  setter aliases are removed and all callers use the canonical preferred-
  provider methods. The translation pipeline now uses only `PipelineState`; the
  `PipelineContext` alias is removed. Auth router test-only token helpers and
  the dead auth-email accessor shim are removed; callers use `AuthService`
  directly. The public compatibility aggregator is removed; applications and
  tests register the three canonical public routers explicitly, while shared
  models/helpers live in `public_contracts.py`. The unused frontend
  `formatAdminErrorString` compatibility wrapper is removed; admin error UI
  uses the canonical structured `formatAdminError` result. The runtime
  container now exposes one canonical `preferences` singleton; its `settings`
  property alias and duplicate fixture store are removed. Translation
  orchestration no longer re-exports helpers from its lineage, metadata,
  progress, or resume modules; callers import from the owning modules. Static
  `/health` and `/api/health` aliases, the unused frontend health wrapper, and
  the unused application getter alias are removed; callers use the canonical
  health routes or module-level application. Source plugins now use the
  canonical `AdapterRegistry`, `source_key`, `can_handle`, `get_adapter`,
  `get_by_key`, and `list_adapters` contracts; the older module registry
  functions, `key`, `matches_url`, and mirrored `source` metadata are removed.
  Storage chapter-ID normalization now has one public implementation;
  `_logical_id_from_stem` is removed and all storage callers use
  `logical_id_from_stem`. Metadata quality, catalog taxonomy persistence, and
  stale retranslation now read only `source_key`; crawler metadata supplies
  canonical `source_key` and `source_novel_id`, and legacy `source` metadata
  fails the quality gate. Metadata storage also rejects the legacy top-level
  `source` and `status` fields at both write and read boundaries. The redundant
  `novels.status` database mirror is removed by a forward migration; ORM,
  backfill tooling, and tests now use only `publication_status`. Activity-worker
  source resolution and taxonomy origin persistence also use only
  `source_key`. Translation activity creation, persistence, execution, API
  responses, and frontend normalization now use only `provider_key` and
  `provider_model`. Scheduler policy normalization ignores legacy `provider`
  and `model` fields, and the obsolete `SegmentStage` compatibility subclass is
  removed; runtime and tests use `SmartSegmentStage` directly. The disposable
  translation cache now reads only exact canonical keys and no longer falls
  back to the obsolete provider/model/text hash format. The `jobs` router shim,
  hidden `/jobs/*` aliases, request-model aliases, query-parameter aliases, and
  startup migration from the obsolete `jobs/` runtime directory are removed;
  only the canonical activity router and `activity_log/` layout remain. Queue,
  worker, runner, package exports, runner status, and frontend types no longer
  expose `Job*`, `job_type`, `last_job_id`, or `jobs_processed` aliases.
  Workflow-step aliases and automatic preference migration from
  `workflow_profiles` to `llm_step_configs` are removed. Redirect-only
  `/register` and `/account/contribute` pages are removed in favor of the
  canonical `/login?mode=signup` and `/contribute` routes. The empty export
  orchestration compatibility module and dead PDF exporter stub are also
  removed; PDF requests still fail through the canonical controlled error.
  `WEB_API_KEY`, its dead dependency helper/re-export, and related environment
  guidance are removed; owner sessions and CSRF are the only admin web-auth
  contract. The duplicate backend `/novels/*` and `/api/novels/*` router mounts,
  their aggregator module, and the obsolete token-based HTML admin dashboard
  are removed. Caddy now sends public `/novels/*` browser pages to the frontend,
  while admin and public APIs use only `/api/admin/*` and `/api/public/*`.
  `TranslateStage` no longer re-exposes extracted result-assembly and cache
  persistence helpers as private static or instance methods. Production and
  tests import the owning modules directly; 75 focused pipeline, glossary, and
  smart-chunking tests pass with zero focused Pyright errors.
  Public glossary annotations now accept only the catalog's canonical alias
  record shape with string `alias_text`; string, `text`, object-attribute, and
  implicit stringification adapters are removed. The 137 focused annotation
  and public-router tests pass with zero focused Pyright errors.
  The runtime container, CLI worker entry points, activity worker, and Python
  command reference now expose only `activity_log`, `activity_worker`, and
  `activity_runner`; the remaining `jobs`, `job_worker`, and `job_runner`
  aliases and dynamic CLI fallback are removed. The 31 focused container,
  worker, and CLI tests pass (7 environment-dependent skips) with zero focused
  Pyright errors.
  Pipeline segmentation, persistence, translation, QA, result serialization,
  and tests now carry only `TranslationChunk` records. The mirrored string
  `chunks` field, fallback selection, synthesized `legacy_*` chunk IDs, and
  string-chunk helper branches are removed; deserialization rejects the old
  field explicitly. The 116 directly affected cache, pipeline, scheduler, and
  QA tests pass with zero focused Pyright errors.
  Admin request moderation no longer registers creation, voting, or source-
  candidate tombstone routes that existed only to return `410 Gone`; public
  request creation and owner list/get/status moderation remain canonical. Six
  focused authorization, moderation, and removed-route tests pass with zero
  focused Pyright errors.
  Reading history now requires the canonical JSON body, and reviews use only
  `PUT /api/user/reviews/{slug}`. Query-based history creation and the duplicate
  POST review route are removed; the frontend already used the canonical forms.
  All 43 user-data router tests pass with zero focused Pyright errors.
  Segment cache keys now require explicit `provider_key`, `provider_model`, and
  `prompt_version` keyword arguments; the empty compatibility defaults and the
  test preserving omitted parameters are removed. All runtime and test callers
  provide the complete cache identity. The 98 focused cache, prompt-policy, and
  glossary-invalidation tests pass with zero focused Pyright errors.
  `AdminService` now requires the canonical `StorageService`; its optional
  untyped storage parameter, global-settings path reconstruction, and missing-
  storage branches are removed. The same slice wires the previously unreachable
  bulk scheduler-state reader tracked by DEBT-112. All 135 focused admin,
  security, scheduler-observability, and storage tests pass with zero focused
  Pyright errors. Glossary editor QA now consumes only canonical `alias_text`
  and `alias_type` records; its `text`, arbitrary-string, `forbidden_variants`,
  and `known_variants` adapters are removed, and missing source context uses
  `missing_source_context` rather than a legacy-labeled result code. Translation
  source-language inference also reads only canonical adapter `source_key`
  (DEBT-113), and glossary revision lookup uses the canonical `Novel` model
  instead of a nonexistent repository hook (DEBT-114). All 86 focused glossary-
  QA, editor API, and pipeline tests pass with zero focused Pyright errors.
  The deprecated public-catalog `language` query parameter, its DB/storage
  filtering branches and tests, and the unreferenced frontend language
  navigation component are removed. The DB-path predicate now accepts only its
  actual `sort_by` input. All 118 public-router tests, focused Pyright/Ruff,
  frontend TypeScript, and ESLint pass.

### DEBT-022 — Forward-only storage schema enforcement
- **Milestone:** Milestone 2c (Backup & Storage)
- **Category:** Storage | Data Migration
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/`
- **Description:** Storage artifacts previously accepted unversioned and older
  formats plus alternate raw/translated directory layouts.
- **Completion criteria:** Only the exact current schema and canonical layout are
  readable; incompatible artifacts fail closed without implicit rewrites.
- **Resolution:** Metadata, chapter bundles, glossaries, and runtime records now
  require their exact current schema version. Legacy raw/translated directory
  fallbacks, bare glossary lists, unprefixed Syosetu folder lookup, and
  older/unversioned record acceptance were removed. Tests prove current writes,
  exact-version reads, rejection, and preservation after failed writes.

### DEBT-023 — Admin provider credential UI missing
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Frontend | Feature
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/app/(admin)/admin/settings/`, `backend/src/novelai/api/routers/admin_provider_credentials.py`
- **Description:** Owner-only encrypted credential CRUD/test routes exist, but
  the admin settings UI does not expose them. Environment credentials remain a
  separate operator configuration path.
- **Completion criteria:** Admin page can list, create, update, test, and revoke
  encrypted credential rows without rendering complete secret values.

### DEBT-024 — SOURCE-PIPELINE-FIX-4: Novel status extraction issues
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Sources
- **Priority:** High
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/sources/`
- **Description:** GenericSource misses publication status. Syosetu infotop errors swallowed.
- **Completion criteria:** Status parsed correctly; parser tests pass.

### DEBT-025 — SOURCE-PIPELINE-FIX-5: Storage safety gaps
- **Milestone:** Milestone 2c (Backup & Storage)
- **Category:** Storage | Operations
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/runtime_contracts.py`, `backend/src/novelai/storage/traceability.py`, `backend/src/novelai/services/maintenance_service.py`
- **Description:** Fetch cache lacks TTL cleanup. Pipeline events grow without bound.
- **Completion criteria:** Storage cleanup deletes old cache, prunes event lists, uses locks.
- **Resolution:** Added `cleanup_fetch_cache()` and `cleanup_pipeline_events()` to `runtime_contracts.py`. Switched `save_scheduler_state` and `append_pipeline_event` to use `_write_text_atomic` (atomic writes with fsync). Created `MaintenanceService` with allowlisted cleanup roots, dry-run support, path safety, and task isolation. 14 maintenance service tests pass.

### DEBT-026 — Frontend lint not configured non-interactively
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Frontend | CI/CD
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `frontend/`
- **Description:** ESLint configuration not run inside CI pipeline.
- **Completion criteria:** `eslint.config.mjs` present, `npm run lint` checked on Actions.
- **Resolution:** Created `frontend/eslint.config.mjs` with Next.js flat config. Added `npm run lint` step to `frontend-check` job in CI. Lint runs non-interactively.

### DEBT-027 — Backend package flattening deferred
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Backend | Architecture
- **Priority:** Low
- **Status:** Deferred
- **Affected areas:** `backend/src/novelai/`
- **Description:** Import routes complex due to modular subdirectory nesting.
- **Completion criteria:** Package flattened or architecture decision documented.

### DEBT-028 — Source parser fixtures drift
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Testing | Sources
- **Priority:** Medium
- **Status:** Ongoing
- **Affected areas:** `backend/tests/fixtures/sources/`
- **Description:** Offline test documents can drift from live novel site changes.
- **Completion criteria:** Regularly run manual check to verify selectors match live markup.

### DEBT-029 — TAXONOMY-5C: tag ja display
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** Tag badge components
- **Description:** Japanese tag names present in database but public UI displays English only.
- **Completion criteria:** Tag badges show Japanese rendering in tooltips.

### DEBT-030 — TAXONOMY-5D: genre payload decision
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend | API
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** Catalog APIs
- **Description:** Public catalog genre enrichment payload undetermined.
- **Completion criteria:** Catalog API serves localized names and metadata payload.

### DEBT-032 — CI/CD manual workflow trigger
- **Milestone:** Milestone M3 (Deployment)
- **Category:** CI/CD
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `.github/workflows/deploy.yml`
- **Description:** Deploy workflow now triggers automatically on version tag push (`v*`) in addition to manual dispatch. Tag-triggered deploys go to production environment.
- **Completion criteria:** Auto-trigger deploy on pushed version tag.
- **Resolution:** Added `push: tags: ['v*']` trigger to deploy.yml. Tag name (minus `v` prefix) is used as the image version. Tag-triggered deploys default to production environment. Manual dispatch still available with environment choice.

### DEBT-033 — No scheduled export freshness check
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** Export service
- **Description:** Freshness badge function exists but is never run on periodic tick.
- **Completion criteria:** Stale files flagged daily and reported in admin logs.

### DEBT-034 — Pipeline events not consistently recorded
- **Milestone:** Milestone M2c (Backup & Storage)
- **Category:** Backend | Testing
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/traceability.py`
- **Description:** Flaky integration tests because stage files omit trace events.
- **Completion criteria:** All pipeline stages write status files atomically.
- **Resolution:** `append_pipeline_event` now uses `_write_text_atomic` instead of `_write_text`, ensuring atomic writes with fsync. `save_scheduler_state` also switched to atomic writes. 11 atomic storage recovery tests pass.

### DEBT-035 — Windows file locking test flakiness
- **Milestone:** Milestone M2c (Backup & Storage)
- **Category:** Testing | Platform
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/file_lock.py`, `backend/src/novelai/utils/__init__.py`
- **Description:** Multi-process cleanup fails on Windows due to file handles remaining open.
- **Completion criteria:** Lock retries handled, and test runs pass on Windows platform.
- **Resolution:** Created `InterProcessFileLock` using `O_CREAT | O_EXCL` for cross-platform atomic lockfile creation. Windows PID liveness check uses `ctypes.windll.kernel32.OpenProcess`. Bounded retries with configurable backoff. Stale lock detection reclaims locks from crashed processes. Added fsync to `utils.atomic_write`. 11 file lock tests pass on Windows.

### DEBT-036 — Scheduler state persistence incomplete
- **Milestone:** Milestone M2c (Backup & Storage)
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/db/models/scheduler_runtime_state.py`, `backend/src/novelai/services/scheduler_runtime_state_service.py`, `backend/alembic/versions/d3e5f8a1b2c4_add_scheduler_runtime_states.py`
- **Description:** Scheduler state logs limits but cooldowns are lost on process reset.
- **Completion criteria:** Persist complete state parameters per job.
- **Resolution:** Added `SchedulerRuntimeState` ORM model with cooldown, failure, exhausted, heartbeat, and next-eligible fields. Created `SchedulerRuntimeStateService` with `mark_started/success/failure/cooldown/exhausted`, `update_heartbeat`, `cleanup_expired_states`, and `get_scheduler_health_summary`. DB state coexists with file-based state (DB is durable cross-restart, file is in-process cache). Alembic migration `d3e5f8a1b2c4` creates the table. 17 scheduler runtime state tests pass, including restart simulation.

### DEBT-037 — Public reader glossary annotations integration
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend | Backend
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** Public chapter routes, highlighter component
- **Description:** Annotation lookup implemented in backend; highlighter component exists but not wired in main reader.
- **Completion criteria:** Highlight badges render inline when public reader page loads.
- **Resolution:** The public chapter route now obtains annotations through the
  injected catalog service, selects only approved entries explicitly marked
  `public_visible`, and returns a bounded contract using canonical field names.
  The chapter page remaps block-relative matches onto displayed paragraphs and
  renders keyboard-focusable inline highlights with safe tooltips. Backend
  service/API tests and the frontend reader integration test cover the path.

### DEBT-038 — SEO metadata baseline
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend | SEO
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** Public reader pages
- **Description:** Robots, sitemaps, structured data schemas absent from public novel route.
- **Completion criteria:** Google validator confirms sitemap and structured schema tags.

### DEBT-039 — Rate limiter Redis validation
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Backend | Security
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** Rate limiter dependency
- **Description:** Redis-backed limit counters not verified in split multi-process deployment.
- **Completion criteria:** Multi-instance tests confirm Redis rate limits block burst requests.
- **Resolution:** Verified cross-instance behavior using two independent `RedisRateLimiter` instances sharing the same Redis (docker exec against `novel-ai-redis-1`). Instance A consumed 3/3 hits, Instance B saw the same counter and was blocked on hit 4. Cross-instance test with fakeredis also passes (`test_rate_limiter_redis_integration.py`, 5 tests). Fail-closed behavior verified: Redis connection errors raise `RuntimeError`, no silent memory fallback.

### DEBT-040 — Prometheus metrics endpoint
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Observability
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** API service
- **Description:** No metrics collector for error rates, database pools, or job lengths.
- **Completion criteria:** `/metrics` endpoint serves standard Prometheus format payload.

### DEBT-052 — Scheduler state visibility
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Observability
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** Admin panel
- **Description:** Persisted scheduler state not exposed in dashboard status views.
- **Completion criteria:** Admin endpoint returns formatted scheduler priority order and cooldown status.

### DEBT-053 — Translation QA checks tuning
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** QA services
- **Description:** Translation QA heuristics exist but LLM-based grading disabled by default.
- **Completion criteria:** LLM checker activated on translation, triggers retry on low confidence.

### DEBT-054 — Admin audit log viewer missing
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Backend | Frontend
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/api/routers/admin.py`, `frontend/app/(admin)/admin/audit/`
- **Description:** AuditLog model exists but no writer, API, or owner-only viewer. Audit events are not generated for sensitive actions.
- **Completion criteria:** Owner-only audit list/detail APIs, server-side redaction, frontend viewer with filters and pagination.

### DEBT-055 — Deployment production hardening gaps
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Backend | DevOps
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/config/settings.py`, `backend/src/novelai/config/production_validator.py`, `backend/src/novelai/api/middleware/security.py`, `backend/src/novelai/api/app.py`, `backend/src/novelai/main_admin.py`, `backend/src/novelai/main_reader.py`, `deploy/compose.yml`, `deploy/Caddyfile`, `deploy/scripts/deploy-smoke.ps1`
- **Description:** No production config validator, no trusted proxy/host policy, no security headers, no deploy smoke checks, no rollback procedure. Compose healthcheck targets wrong service.
- **Completion criteria:** Production validator, trusted proxy/host config, security headers, deploy smoke checks, rollback procedure, corrected healthcheck.
- **Resolution:** Added `production_validator.py` with fatal/warning/info severity, `SecurityHeadersMiddleware` (X-Content-Type-Options, Referrer-Policy, X-Frame-Options, HSTS), `get_client_ip` with trusted proxy CIDR validation, `is_allowed_host` for Host header validation. Added `SERVICE_ROLE` setting to distinguish admin/reader validation. Compose defaults to `WEB_RATE_LIMITER_BACKEND=redis`, `SERVICE_ROLE=admin` for backend, `SERVICE_ROLE=reader` for reader. Fixed healthcheck path (`/health/live` not `/api/health/live`). Added `deploy/scripts/deploy-smoke.ps1` for migration gate, health, route boundary, and security header verification. Rollback procedure documented in `docs/operations/deployment.md`. 18 production config tests + 19 security middleware tests pass.

### DEBT-056 — Frontend error boundaries and empty states
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/app/`, `frontend/components/`, `frontend/lib/public-api.ts`
- **Description:** No shared loading/empty/error/unavailable states. Public API error parsing exposes raw backend messages. No route-level error boundaries.
- **Completion criteria:** Shared state components, API error normalizer, route-level error/loading/not-found boundaries, safe frontend logging.

### DEBT-057 — Launch readiness checklist missing
- **Milestone:** Milestone M7 (Launch Readiness)
- **Category:** Operations
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `docs/operations/launch-checklist.md`
- **Description:** No operator go/no-go artifact. No evidence collection, waiver tracking, or rollback validation.
- **Completion criteria:** `docs/operations/launch-checklist.md` exists with status, owner, evidence, blocker, waiver, and decision fields.

### DEBT-058 — Public reader accessibility baseline
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/components/public/public-shell.tsx`, `frontend/app/(public)/`
- **Description:** Nested `<main>` landmarks, no skip link, no reduced-motion
  rules, and incomplete focus management remain in the public reader. Tag
  suggestions now provide the required `aria-selected` state.
- **Completion criteria:** Single main landmark, skip link, reduced-motion CSS, focus management, accessible reader controls.

### DEBT-059 — Public reader performance budget
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend | Backend
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/app/(public)/`, `backend/src/novelai/api/routers/public_*.py`
- **Description:** No documented latency/payload budgets, no cache-control
  headers, no bundle analysis, and no request-count tests. Public cover/brand
  images still use raw `<img>` elements and produce Next.js LCP warnings.
- **Completion criteria:** Documented budgets, cache-control headers, bundle analysis, request-count tests, annotation cap.

### DEBT-060 — Terms/DMCA takedown workflow missing
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Backend | Frontend
- **Priority:** High
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/api/routers/`, `frontend/app/(public)/dmca/`
- **Description:** No takedown models, intake endpoint, admin APIs/UI, enforcement checks, HTTP 451 tombstone, cache invalidation, sitemap exclusion, audit events.
- **Completion criteria:** Takedown models, public intake, owner-only admin APIs/UI, HTTP 451 enforcement, cache/sitemap invalidation, audit events.

### DEBT-061 — S3 storage backend validation
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Storage
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/backends/s3.py`, `backend/src/novelai/config/settings.py`, `backend/src/novelai/config/production_validator.py`, `backend/tests/integration/test_s3_integration.py`
- **Description:** S3 backend fields restored to settings but not validated in production deployment.
- **Completion criteria:** Real S3 integration tests, production config validation, backup/restore drill with S3.
- **Resolution:** Added `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` settings for R2/S3-compatible targets. Updated `S3Backend` constructor to accept explicit credentials. Production validator requires credentials when `S3_ENDPOINT` is set. Live verification on 2026-07-16 proved application read/write/delete on the production bucket, snapshot-source read with write denied, backup-target read/write/delete on the independent backup bucket, denied cross-bucket access, and complete isolated-prefix cleanup. R2 backup/restore procedures are documented in `docs/operations/data-recovery.md`.

### DEBT-062 — pg_net extension in public schema
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Database | Security
- **Priority:** Low
- **Status:** Resolved
- **Affected areas:** `backend/alembic/versions/2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py`, Supabase database
- **Description:** `pg_net` was installed in `public`, but live dependency and cron-job inspection confirmed that no application object or scheduled job used it. The scheduler-state cleanup uses `pg_cron` directly and does not require `pg_net`.
- **Resolution:** Alembic revision `3da9f497264c` removes `pg_net`, moves RLS helper functions and the cleanup function into the non-exposed `private` schema, reconciles all public-table RLS policies, and removes Data API grants from `scheduled_cron_log`. Live verification confirmed the extension is absent, the cleanup schedule remains active at 03:30 UTC, all public tables retain RLS, and the Supabase security advisor reports no warnings.

### DEBT-075 — Managed-service recovery and scheduling closure
- **Milestone:** Managed Services Closure
- **Category:** Database | Storage | Operations
- **Priority:** Blocker
- **Status:** Implemented; alert and hosted acceptance pending
- **Resolution:** Added reusable bounded database engines, PostgreSQL connection timeouts, renewable scheduled-job leases, real cron/timezone evaluation, split R2 snapshot credentials, streamed encrypted PostgreSQL exports, retention, and redacted SMTP alerts. Live R2 permission-boundary tests proved the three credential roles. On 2026-07-18 two consecutive scheduler-created R2 snapshots passed full checksum verification, and a scheduler-created encrypted PostgreSQL backup was automatically restored into a clean PostgreSQL 17 target at Alembic head `8b7f3d1a2c4e` with 30 public tables and zero invalid constraints. The opt-in hosted PostgreSQL/R2 suite passes, and alert cooldown plus secret redaction have direct tests. On 2026-07-22 the hosted Supabase project migrated to repository head `9c2e4a6b8d0f`; verification preserved all four novel rows, confirmed the legacy `novels.status` column absent and `publication_status` present, found every public table protected by RLS, and found zero security-advisor WARN findings. Remaining acceptance requires real stale/failure SMTP delivery and successful hosted verification workflow evidence.

### DEBT-076 — Clean PostgreSQL migration lacks Supabase auth compatibility
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Database | CI/CD
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `backend/alembic/versions/`, `.github/workflows/ci.yml`
- **Description:** The latest clean PostgreSQL CI migration fails because a
  migration expects Supabase's `auth` schema, while the vanilla PostgreSQL 16
  service does not provide it.
- **Completion criteria:** A clean PostgreSQL service and the hosted Supabase
  project both migrate to head through an explicit, tested compatibility path.
- **Resolution:** CI installs a minimal, fail-closed
  `auth.uid()` compatibility shim before Alembic runs on vanilla PostgreSQL.
  The hosted Supabase project migrated to repository head `9c2e4a6b8d0f` and
  passed post-migration schema and security checks on 2026-07-22. Local Docker
  verification replayed the shim and complete Alembic chain against fresh
  PostgreSQL 16, reaching that head. Hosted CI run
  <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29941138116>
  then passed the clean PostgreSQL service migration and all dependent tests at
  commit `74f83c8`.

### DEBT-077 — CI exclusions and workflow success signals are misleading
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Testing | CI/CD
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `.github/workflows/ci.yml`, `.github/workflows/build.yml`
- **Description:** Known test exclusions and the aggregate build job can report
  success without proving the complete behavior or image publication implied by
  the workflow name.
- **Completion criteria:** Every exclusion is justified or removed, migration
  and auth regressions run in CI, and aggregate jobs distinguish a skipped
  publication from a verified image push.
- **Resolution:** Previously excluded files now run in
  explicit bounded matrix shards, Docker builds depend on both backend suites,
  and the aggregate publication result fails unless image publication succeeds.
  Hosted CI run
  <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29941138116>
  passed backend lint, core and extended backend tests, frontend checks, E2E,
  and three Docker builds. The dependent publication run
  <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29941617651>
  pushed admin, reader, and frontend images and passed its aggregate gate.

### DEBT-078 — GitHub repository controls need hardening
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Security | Supply Chain | CI/CD
- **Priority:** Blocker
- **Status:** Ongoing
- **Affected areas:** `.github/workflows/`, GitHub repository settings
- **Description:** The default branch has no ruleset, Actions allows all actions,
  and immutable SHA pinning is not required. Live repository changes remain an
  owner-operated step documented in `docs/cicd-manual-setup.md`.
- **Completion criteria:** Required checks and review rules protect the default
  branch, Actions permissions are least-privilege, third-party actions are
  pinned or restricted, and security scanners remain green.
- **Implementation note (2026-07-22):** Tracked workflows now pin actions to
  immutable commit SHAs and scope write permissions to the publication job.
  Live inspection found push protection enabled with zero open CodeQL and
  secret-scanning alerts, but no default-branch ruleset, unrestricted Actions,
  and no required SHA policy. Those repository settings remain owner actions.

### DEBT-079 — Free preview and production deployment acceptance missing
- **Milestone:** Milestone M3.5 (Hosted Topology)
- **Category:** Deployment | Operations
- **Priority:** Blocker
- **Status:** Ongoing
- **Affected areas:** `docs/operations/deployment.md`, hosting configuration
- **Description:** The free hosted preview and production topology are defined,
  but domains, OAuth, cookies, CORS/CSRF, backend reachability, monitoring,
  rollback, and cost/reliability upgrade gates have not been proven live.
- **Completion criteria:** The disposable preview passes its reduced contract,
  and the always-on production topology passes the full launch checklist.
- **Implementation note (2026-07-18):** Added a tracked Render Free monolith
  Blueprint, Vercel frontend configuration, secure-cookie override, enforced
  host allowlisting, browser-origin CSRF checks, and regression tests. Live
  domains, OAuth, scoped R2 access, health/readiness, and rollback evidence are
  still required before resolution.

### DEBT-073 — Glossary prompt injection test drift
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Testing
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/tests/test_glossary_prompt_injection.py`
- **Description:** Test expects stale prompt text after prompt policy update.
- **Completion criteria:** Test assertions updated to match current prompt policy.
- **Evidence:** Updated `test_canonical_term_and_translation_render_deterministically` expected string to match current `_render_text()` output (LOCKED/APPROVED sections, authority preamble). `test_glossary_prompt_injection.py` passes all 15 tests.

### DEBT-063 — Storage abstraction leaks on object-store backends (Phase 1)
- **Milestone:** Milestone M3 (M3a Production Hardening)
- **Category:** Backend | Storage
- **Priority:** Critical
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/backends/{base,s3,filesystem}.py`, `backend/src/novelai/storage/service.py`, `backend/src/novelai/storage/{chapters,novels,translations}.py`
- **Description:** The S3 backend had no concept of directory presence. Code that called `_path_exists()` on a logical directory (e.g. `chapters/`, `metadata_backups/`) received `False` on S3/R2 because physical directory-marker objects do not exist. This caused `list_stored_chapters`, `list_translated_chapters`, `list_metadata_history`, `_folder_has_novel_data`, `_get_folder_name`, and other storage operations to silently return zero results when using R2. A secondary issue: chapter filenames were unpadded (`1.json`), which broke lexical ordering on object stores (`10.json` sorts before `2.json`).
- **Resolution:**
  - Added `has_keys(prefix) -> bool` to `StorageBackend` interface. S3 implementation uses `list_objects_v2(MaxKeys=1)`. Filesystem implementation uses `iterdir()`.
  - Added `StorageService._is_dir_present(path)` — a logical-directory presence check that normalizes the prefix and delegates to `backend.has_keys()`.
  - Replaced 14 `_path_exists(directory)` call sites in `chapters.py`, `novels.py`, and `translations.py` with `_is_dir_present(directory)`.
  - Chapter filenames changed to 4-digit zero-padded (`0001.json`) via `_chapter_filename()`. `list_stored_chapters` and `list_translated_chapters` convert padded stems back to logical IDs (`0001` → `1`) via `_logical_id_from_stem()`.
  - Added `StorageService._logical_id_from_stem()` static method.
- **Tests:** 10 unit tests + 10 S3 integration tests covering prefix presence, padding, listing, exclusion, recursive deletion, boundary separation. All pass.
- **Verification:** `count_stored_chapters("n2056dn")` returns 9 (was 0 before the fix) against live R2.
- **R2 canonical note:** Object-store directories are virtual prefixes. Storage-aware code must use the storage abstraction, not `Path.exists()` or `Path.is_dir()`.

### DEBT-064 — Live admin Library summary and catalog projection validation (Phase 2)
- **Milestone:** Milestone M3 (M3a Production Hardening)
- **Category:** Backend | Storage | Admin UI
- **Priority:** High
- **Status:** Resolved (code commit `004b631`; docs commit `1072c37`)
- **Affected areas:**
  - Backend:
    - `backend/src/novelai/services/library_summary_service.py`
    - `backend/src/novelai/storage/service.py` (`list_keys_under`, `read_payload`, `logical_id_from_stem`)
    - `backend/src/novelai/api/routers/library.py` (`GET /api/admin/library/summary`)
    - `backend/src/novelai/api/routers/admin_glossary_apply.py` (activation invalidation)
    - `backend/src/novelai/services/orchestration/{crawler,translation,importer,glossary}.py`
    - `backend/src/novelai/services/library_service.py` (delete invalidation)
    - `backend/src/novelai/runtime/container.py` (library_summary dependency)
  - Frontend:
    - `frontend/lib/api.ts` + `api-types.ts` (`adminApi.librarySummary` + types)
    - `frontend/app/(admin)/admin/library/page.tsx` (Failed/Pending columns, stable `["library-summary"]` key, explicit refresh mutation, single error banner per state, settled background-refetch failure detection)
    - `frontend/app/(admin)/admin/library/__tests__/page.test.tsx` (7 regression tests, including real background-refetch failure test)
- **Description:** Admin Library counts must derive from a single R2/S3 listing pass, not from stale SQL `Novel.chapter_count` and `Novel.translated_count`. SQL projection rows remain a cache, but the admin Library table no longer trusts them as authoritative. The endpoint must use immutable cached state, true single-flight concurrency, catalog-identity-aware cache, and fail-fast forced refresh semantics. Frontend must join `summary.data.items` to novel rows and distinguish initial failure, background failure, and explicit-refresh failure with no duplicate error banners.
- **Resolution:**
  - Backend service:
    - `LibrarySummaryService` rewritten with a true single-flight state machine: frozen `_CachedSummary` (immutable `tuple[NovelSummaryCounts, ...]` items). The active build is owned by `_active_generation: _BuildGeneration | None` and `_active_identity: tuple[str, ...]`. Per-generation `_BuildGeneration` dataclass carries `generation`, `identity`, `start_epoch`, `done`, `cache`, `error`, `invalidated`; each caller joining an active build keeps a direct reference to that object, so a later completion cannot delete an earlier waiter's outcome.
    - `Condition.wait_for(generation.done)` for non-busy-spinning waiters; check-and-set for `_active_generation` is atomic under the lock. Forced-refresh callers *join* the currently active same-identity build rather than allocate a generation.
    - **Generation-outcome lifetime:** each waiter retains the same `_BuildGeneration` instance via direct reference; the active slot is cleared only after the outcome is published. Generation N waiters are not destroyed when generation N+1 starts/completes. Build exceptions remain attached to the generation so every waiter receives the same exception.
    - **Invalidation epoch:** monotonic `self._invalidation_epoch` increments on `invalidate_cache()`. Each generation captures `start_epoch` at builder start. When the build completes: if `start_epoch == current_epoch` the result publishes to cache; otherwise the generation is marked `invalidated=True`, the result is **not** published, all attached callers are notified and re-enter the acquisition loop iteratively (not recursively) so exactly one starts a post-invalidation build. Repeated invalidation never silently publishes stale data.
    - Publication under one lock acquisition: cache + outcome + expiry + clear-active-state + `notify_all` together, so waiters cannot observe `no build in flight / no cache` between notify and outcome.
    - TTL is computed from `clock()` at successful build completion (never from start), with injectable `clock=fake_clock` for deterministic tests.
    - Storage abstraction public surface: `StorageService.list_keys_under(prefix)` normalizes `Path` inputs via `as_posix()` and strip backslashes for `str` inputs; `StorageService.read_payload(key)` is the canonical JSON decode-or-None entry; `StorageService.logical_id_from_stem()` is exposed publicly so the summary service no longer touches private storage helpers. Windows-style strings (`\\`) are normalized to POSIX prefixes; existing trailing slash is not doubled; empty string remains valid; no host absolute path is introduced.
    - `PurePosixPath(key).stem` for chapter-filename parsing — never host `Path`.
    - Outward `SummaryResponse` constructed via `_response_from_cache(cached, hit=...)`: fresh `cache={}` dict and fresh `items=[]` list per caller. Cached records remain frozen and never observe caller mutation.
  - Cache logic:
    - Catalog identity is `tuple(sorted(set(catalogued_novel_ids or [])))`. A cache entry is valid only when its identity matches and expired time has not passed. Concurrent calls with different identities do **not** share an incompatible result; waiters that arrive during an incompatible build wait it out and re-evaluate.
  - Crawl failure semantics:
    - `_get_failed_ids` treats the newest activity with status `completed` or `failed` as authoritative — its `failures` list (even empty) overrides all older activities. Cancelled, pending, queued, and running activities are skipped. `metadata.crawl_result` is the only supported result field.
    - If the failure payload is malformed/missing, the function returns an empty set instead of falling back to older failures (no resurrection of older failure data).
    - Result is normalized: dict (`chapter_id`/`id`), scalar strings, and ints are deduplicated into a `set[str]`. Stored chapter IDs are excluded from the failed count.
  - Invalidation coverage (best-effort helper `best_effort_invalidate(context=...)` on every storage-changing path, never masking caller failures):
    - `LibrarySummaryService.invalidate_cache`, `best_effort_invalidate()` after crawler `save_chapter` (cold/recrawl/delta, `context="scrape_chapter"`), after crawler `save_metadata` (preliminary + replacement metadata on full-crawl `delete_novel`, `context="scrape_metadata"`), after translation `save_translated_chapter` (delta, `context="translate_delta"`), after importer `save_chapter`, after glossary apply `save_translated_chapter`, after `activate_translated_chapter_version`, after `LibraryService.delete_novel`.
    - Full-crawl mode: invalidate immediately after `delete_novel` (and again after replacement `save_metadata`) so the cache does not describe deleted storage if later metadata fetching or chapter scraping fails.
  - Frontend:
    - `LibraryPage` joins `summary.data.items` to novel rows via `new Map(summary.data.items.map(item => [item.novel_id, item]))`. `mergedRows` memo depends on `rows`, `summaryMap`, `summaryInitialError`, `summaryInitialLoading` so summary arrival updates visible rows.
    - Stable `["library-summary"]` query key. Explicit refresh uses a `useMutation` calling `adminApi.librarySummary({refresh: true})`; on success it writes to the canonical key via `queryClient.setQueryData(["library-summary"], data)`.
    - Three distinct, mutually exclusive error states replace the three duplicate `summary.error` banners:
      - *Initial query failure* → destructive banner + Retry (refetches the query, no SQL fallback rendered).
      - *Settled background refetch failure* → detected via `summary.isRefetchError` (or equivalently `status === "error" && data !== undefined && fetchStatus === "idle"`). Renders amber banner + Retry preserving previous values. Initial-load error and explicit-refresh error remain mutually exclusive.
      - *Explicit refresh failure* → amber banner reading `refreshSummary.error` + Retry triggering the mutation. Previous good values remain visible.
    - "Retry retry" typo removed.
  - Single route: `GET /api/admin/library/summary` (operationId `library_summary_api_admin_library_summary_get`). Historical accidental aliases under `/novels/admin/library/summary` and `/api/novels/admin/library/summary` were removed; the duplicate router aggregator was subsequently deleted entirely.
- **Tests:**
  - 50 backend library-summary tests, including hardened cold-concurrent exactly-one-build, fake-clock expiry, forced-refresh single-flight joining active build, **successive-generation waiter-retention race**, **invalidation-epoch stale-build rejection** (proving only one stable rebuild after invalidation), **concurrent failed-generation propagation** with 8+ threads, **strengthened normal-callers-join-forced-build**, **incompatible-identity waits-and-rebuilds**, real `Path` prefix normalization, Windows-style string prefix normalization (spying on the backend argument), crawl-failure semantics (newest-clean overrides older failure, cancelled/running activities ignored, malformed payload does not resurrect, duplicates dedup, dict and scalar formats normalize, stored chapters excluded from failed, pending remains `max(total - scraped - failed, 0)`).
  - 7 Admin Library frontend tests in `frontend/app/(admin)/admin/library/__tests__/page.test.tsx`, including a real background-refetch failure test (initial success followed by a settled failed refetch: previous values remain, exactly one amber background warning, no initial-load warning, no explicit-refresh warning; Retry triggers the normal query refetch; a later successful refetch removes the warning).
  - 57 storage tests pass.
  - Noncanonical Syosetu folders without current metadata are ignored; canonical publish projection tests remain green.
  - Full Vitest suite passes (609 frontend tests across 52 files).
- **Verification:** Implementation and local verification complete (Ruff, Pyright, TypeScript typecheck, lint, and architecture guard all clean; all focused and full test suites green locally).
  Authenticated production read-only verification against the intended configured environment remains operator-pending.

### DEBT-080 — Standard development extra does not install the test suite
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Tooling | Testing | Reproducibility
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `pyproject.toml`, lockfiles, developer setup documentation
- **Description:** Project instructions identify `pip install -e ".[dev]"` as
  the standard editable development install, but tests import packages such as
  Hypothesis that are available only in the separate `test` extra. A fresh
  `.[dev]` environment therefore fails during test collection.
- **Completion criteria:** Choose one canonical local-development install,
  align extras and documentation, regenerate lockfiles, and prove a clean
  environment can collect and run the documented focused and full suites.
- **Resolution:** The canonical `.[dev]` extra now includes the complete test
  dependency set (`aiosqlite`, Hypothesis, `itsdangerous`, and Moto included), while the
  narrower `test` extra remains available for test-only environments. Both
  lockfiles were regenerated from `pyproject.toml`; a clean temporary Python
  3.13 environment installed `.[dev]`, collected the full backend suite, and
  ran a representative Hypothesis-backed test file successfully.

### DEBT-081 — Frontend hook dependency warnings remain in production builds
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Frontend | Quality
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** Admin activity, library, requests, auth guard, and shared
  table-sort components
- **Description:** The production build succeeds but reports multiple
  `react-hooks/exhaustive-deps` warnings for unstable row expressions, missing
  dependencies, unstable callbacks, and unnecessary dependencies.
- **Resolution:** Query-derived row arrays and the reauthentication callback are
  stable, the library summary memo lists every reactive dependency, and the
  table-sort hook no longer memoizes a module-level comparator. Focused tests,
  lint, type checking, and the production build pass with zero hook dependency
  warnings.

### DEBT-082 — Direct public routes bypassed publication visibility
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Security | Backend | Public Reader
- **Priority:** Critical
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/services/public_catalog_service.py`,
  public novel and chapter routes
- **Description:** Catalog listing excluded `Novel.is_published=false`, but the
  shared direct resolver could still return storage metadata for the same novel
  through its source ID or public title slug.
- **Resolution:** The shared resolver now applies the database publication gate
  to direct storage hits, DB hits, and alias scans. Regression tests prove 404
  responses for unpublished novel detail, title-slug detail, chapter listing,
  and chapter reader requests.

### DEBT-083 — Deprecated FastAPI test-client HTTP transport
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Testing | Dependencies
- **Priority:** Low
- **Status:** Resolved
- **Affected areas:** Backend test client, FastAPI/Starlette/httpx dependency set,
  generated lockfiles
- **Description:** Backend tests pass, but importing `fastapi.testclient` emits a
  `StarletteDeprecationWarning` that the current httpx-backed TestClient path is
  deprecated in favor of `httpx2`. This warning will become a maintenance risk
  as the framework stack advances.
- **Completion criteria:** Select a mutually compatible FastAPI, Starlette, and
  HTTP client dependency set; migrate the shared backend test-client setup;
  regenerate lockfiles; and run the backend suite with no test-client
  deprecation warning.
- **Resolution:** Added `httpx2` to both test-bearing dependency extras so
  Starlette 1.x selects its maintained test transport. Existing application
  outbound HTTP remains on `httpx`; no compatibility wrapper or duplicate test
  client abstraction was introduced. Regenerated lockfiles, full backend
  collection, and focused HTTP/security tests run without
  `StarletteDeprecationWarning`. A broad run likewise emitted no transport
  deprecation warning; its unrelated stale-fixture failures are tracked in
  DEBT-095.

### DEBT-084 — Missing Gemini credentials can silently select the dummy provider
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Providers | Data Integrity
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** Translation stage, novel orchestration, preferences,
  development/test provider configuration
- **Description:** Several translation paths automatically select the echoing
  dummy provider when a Gemini API key is unavailable. Outside an explicit test
  mode this can produce output that appears translated even though no real
  translation occurred.
- **Resolution:** Provider resolution now raises a structured
  `provider_configuration_error` before provider calls, scheduler-state writes,
  or translation persistence when Gemini credentials are missing. Production
  validation requires `PROVIDER_DEFAULT=gemini`; registry discovery and lookup
  hide/reject `dummy` outside `ENV=test`. Metadata translation remains
  non-fatal and records `unavailable` without calling the dummy provider.
  Regression tests prove missing credentials and production dummy selection
  make no provider call and create no translation runtime records.

### DEBT-085 — Pytest class-scoped instance fixtures are deprecated
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Testing | Dependencies
- **Priority:** Low
- **Status:** Resolved
- **Affected areas:** `backend/tests/test_microservice_split.py`
- **Description:** The microservice split tests declared class-scoped fixtures
  as instance methods, a pattern that pytest 10 removes.
- **Resolution:** Replaced the deprecated instance-method fixtures with
  module-scoped fixture functions. The focused microservice split suite runs
  without `PytestRemovedIn10Warning`.

### DEBT-086 — Architecture listed obsolete router-layer violations
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Documentation | Architecture
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `docs/architecture/architecture.md`, router-layer guard
- **Description:** The canonical architecture still listed already-removed
  direct router dependencies and incorrectly linked them to DEBT-054, which
  tracks the unrelated admin audit viewer.
- **Resolution:** Replaced the obsolete table with the enforced current router
  boundary and its canonical guard command. The guard reports no violations.

### DEBT-087 — Stale retranslation source contract lacked behavior coverage
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Testing | Data Contracts
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `OperationsService.retranslate_stale`, operations tests
- **Description:** The stale-retranslation route was registered, but no test
  proved whether workflow metadata used canonical `source_key` or the legacy
  `source` field.
- **Resolution:** Added focused behavior tests proving legacy-only metadata is
  rejected without scheduling translation and canonical `source_key` metadata
  completes the no-stale path without a provider call.

### DEBT-088 — File-to-database backfill emitted legacy novel fields
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Data Migration | Testing
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** File-to-database backfill, novel ORM, Alembic schema
- **Description:** The backfill still accepted `id` and `status` metadata and
  emitted the redundant `Novel.status` database field, with no focused test for
  the canonical projection.
- **Resolution:** The backfill now requires `novel_id`, normalizes only
  `publication_status`, and maps source identity from `source_key`. A forward
  migration removes `novels.status`, all ORM fixtures use
  `publication_status`, and focused tests enforce the backfill boundary.

### DEBT-089 — Frontend development tree contained vulnerable brace expansion
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Frontend | Security | Supply Chain
- **Priority:** High
- **Status:** Resolved locally; hosted rescan pending
- **Affected areas:** `frontend/package-lock.json`, GitHub Dependabot
- **Description:** Live Dependabot and local `npm audit` identified
  `GHSA-3jxr-9vmj-r5cp` in two transitive development-only
  `brace-expansion` paths.
- **Resolution:** Refreshed the lockfile to `brace-expansion` 1.1.16 and 5.0.7.
  Local `npm audit` reports zero vulnerabilities. GitHub alert closure requires
  pushing the lockfile and allowing Dependabot to rescan it.

### DEBT-090 — Frontend lint script uses deprecated Next.js wrapper
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Frontend | Tooling
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `frontend/package.json`, ESLint configuration, CI
- **Description:** `npm run lint` still invokes `next lint`, which Next.js marks
  deprecated and removes in Next.js 16.
- **Resolution:** The frontend lint script now runs `eslint .` against the
  existing flat configuration and Next.js Core Web Vitals rules. Generated
  `.next`, `.next-dev`, and dependency directories are explicitly ignored.
  Local lint completes non-interactively; remaining source warnings are tracked
  separately, and hosted confirmation remains part of DEBT-077.

### DEBT-091 — Next.js build infers an external workspace root
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Frontend | Build | Reproducibility
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `frontend/next.config.mjs`, local build environment
- **Description:** Next.js selects `C:\Akmal\package-lock.json` as the workspace
  root instead of this repository because multiple lockfiles are visible.
- **Resolution:** `frontend/next.config.mjs` now sets
  `outputFileTracingRoot` to the repository root explicitly. The production
  build emits no workspace-root warning and retains standalone output.

### DEBT-092 — Browse-page test leaks an unwrapped React state update
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Frontend | Testing
- **Priority:** Low
- **Status:** Resolved
- **Affected areas:** Browse-page tag-filter tests
- **Description:** The frontend suite passes but reports an update to
  `TagFilterSection` outside `act(...)`, weakening timing guarantees.
- **Resolution:** The debounce wait that triggers `TagFilterSection` state now
  runs inside async `act(...)`. The focused browse-page suite passes without
  the React state-update warning.

### DEBT-093 — Public image elements bypass Next.js optimization
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend | Performance
- **Priority:** Low
- **Status:** Resolved
- **Affected areas:** Public brand, novel card, and fallback-cover components
- **Description:** Production lint reports direct `<img>` elements on public
  routes, which can increase LCP and bandwidth.
- **Resolution:** Public brand and generated cover assets now use optimized
  `next/image` rendering with explicit dimensions or responsive sizes. Optional
  externally hosted cover URLs use a direct, unoptimized browser loader because
  their hosts are not trusted for the server-side image optimizer. Production
  lint/build emit no `no-img-element` warnings.

### DEBT-094 — Render Free Blueprint failed live schema validation
- **Milestone:** Milestone M3.5 (Hosted Topology)
- **Category:** Deployment | Configuration
- **Priority:** Blocker
- **Status:** Ongoing; account verification pending
- **Affected areas:** `render.yaml`
- **Description:** Live Render CLI validation rejected the Blueprint because
  `previews.generation: none` is not a current accepted value and Free services
  do not support `maxShutdownDelaySeconds`.
- **Progress (2026-07-22):** Removed both optional fields. Omitting
  `previews.generation` disables Blueprint preview environments, and the Free
  service uses Render's supported shutdown behavior. The Render CLI no longer
  reports either schema error, but validation now stops at the workspace-level
  `need_payment_info` gate. Complete Render's account/payment verification,
  then rerun live validation and deployment before resolving this debt.

### DEBT-095 — Backend tests still construct removed metadata aliases
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Testing | CI
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** Source-adapter, reader-availability, crawl,
  orchestration, recovery, and e2e test fixtures
- **Description:** Forward-only metadata enforcement removed `source` and
  `status`, but several tracked tests still construct or assert those aliases
  instead of `source_key` and `publication_status`. A full Python 3.13 run
  collected 2,569 tests but ended with 60 failures and 26 errors; representative
  isolated failures confirm stale fixture fields rather than the new HTTP test
  transport. Several affected files are assigned to GitHub Actions shards.
- **Completion criteria:** Replace removed metadata aliases throughout active
  tests, fix any remaining suite-isolation failures exposed afterward, and run
  the exact local equivalents of all backend CI shards successfully.
- **Resolution:** Active source, reader, crawl, orchestration, recovery, and e2e
  fixtures now use `source_key`, `publication_status`, and current schema
  versions. The e2e container rebuilds its storage-dependent service graph
  against isolated storage, so translation lineage and idempotency are tested
  in one boundary. Local CI-equivalent evidence includes 1,947 core tests,
  592 extended-shard tests, and 5 e2e tests passing; Ruff, Pyright, and the
  router-layer guard are clean.

### DEBT-096 — OpenAI vestiges contradict the Gemini-only provider contract
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Providers | Frontend | Dependencies
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** Python optional dependencies, public contribution page,
  provider registry, cost estimator, documentation, and provider-related test
  fixtures
- **Description:** Runtime provider registration correctly rejects OpenAI, but
  `pyproject.toml` still offers and installs an OpenAI extra, the gated public
  contribution page still lists OpenAI, and several tests present OpenAI as an
  active provider example. This contradicts the canonical Gemini-only
  architecture and unnecessarily expands the dependency surface.
- **Completion criteria:** Remove the OpenAI dependency extra and development
  install, remove OpenAI from product-facing UI and active-provider fixtures,
  retain provider-neutral persistence boundaries and generic secret-redaction
  defenses, regenerate lockfiles, and verify backend/frontend checks.
- **Resolution:** Removed the OpenAI extra and development dependency, removed
  OpenAI from the gated contribution UI and active-provider fixtures, limited
  the Gemini registry to `gemini-3.1-flash-lite` and `gemma-4-31b-it`, and
  converted the cost estimator and examples to the approved free-tier chain.
  Generic OpenAI-shaped secret redaction and explicit unsupported-provider
  rejection tests remain as security boundaries, not product support.

### DEBT-097 — Full filesystem rescrape changes the public storage slug
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Storage | Data Integrity | Public Routing
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** Filesystem storage backend, full-rescrape lifecycle,
  public catalog slug stability
- **Description:** Object-prefix deletion removed every file but left empty
  filesystem directories behind. A subsequent full scrape treated the empty
  former slug directory as a collision and appended a source suffix, changing
  the public catalog route for the same novel.
- **Resolution:** Filesystem object deletion now prunes empty parent-prefix
  directories up to, but never including, the configured storage root. Tests
  prove root confinement, and the e2e create/full-scrape/publish flow preserves
  the original canonical public slug.

### DEBT-098 — Workflow profile aliases survived the forward-only policy
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Backend | Configuration
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** Workflow-profile normalization and preferences tests
- **Description:** Workflow profiles still accepted and migrated the removed
  `term_extraction`, `term_translation`, `term_summary`, and `reembedding`
  aliases. This contradicted the explicit forward-only policy and could hide
  stale operator configuration.
- **Resolution:** Removed alias normalization and migration. Only canonical
  workflow step names are accepted; tests now prove a removed alias fails
  clearly.

### DEBT-099 — Split-mode tests did not exercise real entrypoints
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Deployment | Authentication | Testing
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `novelai.main_admin`, `novelai.main_reader`, Caddy route
  ownership, split-mode contract tests, deployment and architecture guidance
- **Description:** The split-mode test suite constructed a synthetic reader and
  used the monolith as its admin fixture. It therefore could not detect that
  session-dependent `/api/user/*` routes were registered on the sessionless
  reader while Caddy sent those requests to the frontend catch-all. The real
  admin entrypoint also lacked canonical library detail/action registrations
  that had previously arrived only through the removed compatibility router.
- **Completion criteria:** Test the real split entrypoints, assign every API
  namespace to exactly one process, host session-dependent routes only behind
  session middleware, route them explicitly through Caddy, prove the removed
  backend novel aliases are absent, and align canonical deployment guidance.
- **Resolution:** Split-mode tests now introspect the real `main_admin` and
  `main_reader` applications. The session-enabled admin process owns
  `/api/admin/*`, `/api/auth/*`, and `/api/user/*`; the sessionless reader owns
  only `/api/public/*` and public health. Caddy routes `/api/user/*` to port
  8000, canonical library detail/action routers are registered directly on the
  admin app, and 17 real-entrypoint contract tests enforce route exclusivity
  and absence of `/novels/*` and `/api/novels/*` backend aliases.

### DEBT-100 — Local Git object store is unreadable
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Tooling | Repository Integrity | Delivery
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** Local `.git` object database, pack indexes, commit graph,
  index cache-tree, reflogs, diff/stage/commit workflow
- **Description:** Read-only final review failed because Git could not read
  object `a24c652728060913ce2e2adf7675a8f877cf52e9`. `git fsck --full
  --no-dangling` then reported permission-denied access across loose objects,
  an unreadable pack index and commit graph, broken tree links, and invalid
  cache-tree and reflog pointers. Until the object database is made readable
  and verified, Git cannot produce a trustworthy diff or safely create the
  requested commit. The tested worktree changes remain present and unstaged.
- **Completion criteria:** Preserve the complete worktree patch outside Git;
  identify whether ACLs, file locking, storage corruption, or missing objects
  caused the failures; restore objects from a trusted remote or healthy clone
  without rewriting published history; rebuild only derived metadata after a
  backup; require a clean `git fsck`, readable `HEAD` and parent history, a
  complete diff, and successful intentional stage/commit verification.
- **Resolution:** Repository object access was restored without rewriting
  history. `git fsck --full --no-dangling` completes cleanly, `HEAD` and the
  previously unreadable blob are readable, and Git can again produce the
  complete worktree diff. Intentional staging and commit verification are
  recorded by the commits that include this resolution.

### DEBT-101 — Slow-test marker removed pipeline-stage CI coverage
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** CI/CD | Testing
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `.github/workflows/ci.yml`,
  `backend/tests/test_pipeline_stages.py`
- **Description:** Marking the pipeline-stage suite as slow while filtering
  slow tests from the core job caused the suite to run in no CI job.
- **Completion criteria:** Keep slow tests out of the core shard without
  removing them from CI coverage.
- **Resolution:** Added a dedicated `pipeline-stages` extended-test shard that
  runs the marked file explicitly.

### DEBT-102 — Maintenance cleanup script lacked path confinement
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Tooling | Filesystem Safety
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `deploy/cleanup.ps1`
- **Description:** The maintenance script recursively discovered and deleted
  cache directories without resolving each deletion target or proving it was
  inside the repository.
- **Completion criteria:** Resolve the repository from the script location,
  reject paths outside it and protected roots, use literal-path deletion, and
  support a non-mutating preview.
- **Resolution:** Added repository-bound path validation, protected-root
  exclusions, `-LiteralPath` removal, strict error handling, and PowerShell
  `-WhatIf` support.

### DEBT-103 — VS Code recommendations were ignored and misconfigured
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Developer Experience | Tooling
- **Priority:** Low
- **Status:** Resolved
- **Affected areas:** `.vscode/settings.json`, `.vscode/extensions.json`,
  `.gitignore`
- **Description:** Extension IDs were stored under an unsupported
  `extensions` settings key, and the entire `.vscode` directory was ignored,
  so the intended project setup could not be shared.
- **Completion criteria:** Use VS Code's canonical extension-recommendation
  file and track only the two approved project configuration files.
- **Resolution:** Moved extension IDs to `.vscode/extensions.json`, kept editor
  settings in valid JSONC-compatible settings, and narrowly unignored those
  two files while leaving other workspace-local state ignored.

### DEBT-104 — Slow markers broke test-module syntax
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Testing | Code Quality
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** Fourteen backend test modules marked as slow
- **Description:** Module-level `pytestmark` assignments were appended near the
  end of files, interrupting function and class bodies and preventing Ruff and
  pytest from parsing thirteen modules.
- **Completion criteria:** Put every marker at module scope and prove all
  affected modules parse and collect.
- **Resolution:** Moved all fourteen slow-marker assignments directly below
  their `pytest` imports. Ruff and focused pytest collection verify the files.

### DEBT-105 — CI passed a SQLAlchemy URL to raw psycopg
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** CI/CD | Database
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `.github/workflows/ci.yml`, vanilla PostgreSQL auth
  compatibility bootstrap
- **Description:** The bootstrap step called `psycopg.connect()` with the
  SQLAlchemy-only `postgresql+psycopg://` scheme, so CI failed before Alembic
  could run. The separate Alembic step correctly requires that scheme.
- **Completion criteria:** Use a native PostgreSQL URL only for the direct
  psycopg bootstrap and retain the SQLAlchemy URL for Alembic.
- **Resolution:** The bootstrap step now uses `postgresql://`; the migration
  step remains `postgresql+psycopg://` as required by application persistence.

### DEBT-106 — Locked transitive dependencies had high-severity advisories
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Supply Chain | Security
- **Priority:** High
- **Status:** Resolved locally; hosted rescan pending
- **Affected areas:** Python development lockfiles, frontend package override
- **Description:** Dependabot reported `pyasn1 0.6.3` vulnerable to resource
  exhaustion and quadratic-time denial of service, and `sharp 0.34.5`
  vulnerable through bundled libvips issues.
- **Completion criteria:** Require `pyasn1 >= 0.6.4` and `sharp >= 0.35.0`,
  regenerate authoritative lockfiles, and rerun backend/frontend verification.
- **Resolution:** Added secure dependency floors through the existing Python
  development extra and npm override, then regenerated pip, uv, and npm locks.
  Local resolution selects `pyasn1 0.6.4` and `sharp 0.35.3`; GitHub's three
  existing Dependabot alerts remain open until the commit is pushed and the
  dependency graph rescans it.

### DEBT-107 — Vanilla PostgreSQL migration replay lacked Supabase roles
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** CI/CD | Database | RLS
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `backend/sql/ci_vanilla_postgres_auth_compat.sql`, clean
  PostgreSQL migration replay
- **Description:** The CI compatibility shim supplied `auth.uid()` but not the
  inert `anon` and `authenticated` roles referenced by RLS migrations. A clean
  PostgreSQL 16 replay therefore failed at the scheduled-job lease policy.
- **Completion criteria:** Define idempotent, non-login CI roles without
  changing hosted Supabase or embedding an authentication implementation.
- **Resolution:** The CI-only shim now creates missing `anon` and
  `authenticated` roles as `NOLOGIN`. A disposable PostgreSQL 16 container
  verifies the raw bootstrap and complete Alembic upgrade from an empty DB.
  The focused security contract permits exactly those two inert role
  declarations and rejects login-capable or privileged role attributes.

### DEBT-108 — Local GitGuardian hook authentication is invalid
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Security | Developer Tooling | Secret Scanning
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** Local ggshield authentication, pre-commit secret scan
- **Description:** The staged GitGuardian hook exits before scanning with
  `Invalid API key`. No credential value was printed or committed. GitHub
  native secret scanning reports zero open alerts, but it is not a substitute
  for the required local pre-commit scan.
- **Completion criteria:** Re-authenticate ggshield locally without placing the
  token in chat, shell history, repository files, or logs; rerun the staged
  hook successfully; and record a zero-finding result or remediate findings.
- **Resolution:** GitGuardian was reconnected locally without exposing its API
  key. `ggshield secret scan commit-range HEAD~2..HEAD` and the staged
  pre-commit hook both complete successfully with zero findings.

### DEBT-109 — Text hooks could mutate byte-preserved archived specs
- **Milestone:** Milestone M7 (Final Hardening)
- **Category:** Documentation | Tooling | Archive Integrity
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `.pre-commit-config.yaml`, `docs/archive/specs/`
- **Description:** Generic trailing-whitespace and EOF fixers would rewrite
  historical spec content during the archive move, defeating the verified
  byte-identical preservation contract.
- **Completion criteria:** Preserve archived files exactly while continuing to
  scan active source and documentation normally.
- **Resolution:** Excluded only the archived-spec subtree from the two
  mutating text fixers. Ruff and GitGuardian scopes are unchanged, and hash
  comparison confirms all 164 moved files remain byte-identical.

### DEBT-110 — Email service default disagreed with documented local URL
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Backend | Configuration | CI/CD
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/config/settings.py`, auth email
  container construction
- **Description:** The documented development default for
  `PUBLIC_FRONTEND_URL` was `http://127.0.0.1:3000`, but the settings model
  defaulted to `None`. CI does not load a local `.env`, so constructing either
  email delivery implementation failed before tests could run.
- **Completion criteria:** Make the settings default match the canonical
  environment documentation, retain explicit production validation, and prove
  both no-op and SMTP container construction without a local environment file.
- **Resolution:** Set the development default to
  `http://127.0.0.1:3000`. Production still requires an explicit HTTPS value
  through the existing production validator and Compose contract. Focused
  email-service tests cover the canonical default and both delivery modes.

### DEBT-111 — Hosted CI exceeds the documented cache-hit duration target
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** CI/CD | Performance | Free-Tier Operations
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `.github/workflows/ci.yml`, GitHub Actions cache behavior
- **Description:** The first complete hardened CI run took 6 minutes 36 seconds,
  exceeding the operator guide's under-five-minute cache-hit target. Functional
  correctness is green, but repeated over-target runs increase feedback time
  and consume free hosted-runner minutes.
- **Completion criteria:** Record a representative warm-cache run below five
  minutes, or profile the critical path and reduce it without weakening lint,
  type, test, migration, E2E, or image-build coverage.
- **Resolution:** Follow-up hosted CI run
  <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29941879093>
  completed successfully in 3 minutes 42 seconds with warm caches. All lint,
  migration, backend, frontend, E2E, and three-image build gates remained
  enabled and green.

### DEBT-112 — Scheduler health could not read persisted scheduler states
- **Milestone:** Milestone M2c (Backup & Storage)
- **Category:** Backend | Observability | Storage
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** `StorageService`, admin scheduler health, scheduler-state
  tests
- **Description:** `load_all_scheduler_states()` existed in the traceability
  module but was not bound to the `StorageService` facade. `AdminService` was
  typed as accepting any optional storage object and swallowed the resulting
  attribute error, so scheduler health silently omitted persisted cooldown and
  exhaustion state.
- **Completion criteria:** Require the canonical storage dependency, expose the
  bulk scheduler-state reader through `StorageService`, remove filesystem and
  missing-storage fallbacks, and prove persisted state appears in scheduler
  health.
- **Resolution:** `AdminService` now requires `StorageService`; the legacy path
  reconstruction and optional-storage branches are removed. The facade binds
  `load_all_scheduler_states()`, and focused storage and scheduler-health tests
  verify bulk loading and persisted model-state reporting.

### DEBT-113 — Source adapter language inference read a removed alias
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Translation Pipeline | Data Integrity
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** translation result assembly, source adapters, pipeline
  regression tests
- **Description:** `infer_source_language()` still read the removed source-
  adapter `key` alias even though the canonical adapter contract exposes only
  `source_key`. Without explicit source-language metadata, known Japanese source
  adapters therefore fell through to an unknown language.
- **Completion criteria:** Read only `source_key` and prove a canonical Syosetu
  adapter infers Japanese without explicit language metadata.
- **Resolution:** Translation result assembly now reads `source_key`; focused
  pipeline coverage proves canonical adapter-based inference.

### DEBT-114 — Editor QA revision lookup called a nonexistent model hook
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Glossary | Data Integrity
- **Priority:** High
- **Status:** Resolved
- **Affected areas:** glossary editor QA service and editor API tests
- **Description:** Glossary editor QA attempted to resolve a novel through a
  nonexistent private `GlossaryRepository._novel_model()` hook, then swallowed
  the resulting exception. Persisted QA summaries therefore reported no
  glossary revision even when the novel had one.
- **Completion criteria:** Resolve revisions through the canonical `Novel` ORM
  model and prove linted editor saves persist the current revision.
- **Resolution:** Editor QA now loads `Novel` directly through the repository
  session, and the real editor API path verifies revision `5` is persisted in
  the QA summary.
