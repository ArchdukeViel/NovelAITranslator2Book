# Technical Debt Register

Single source of truth for technical debt and its resolution history. Resolved
entries remain as evidence; active counts include Pending, Ongoing, and
implemented items whose operational acceptance remains pending. Explicitly
Deferred items are tracked but excluded from the active count.

---

## Executive Summary

- **Total active debt entries:** 27
- **V1 launch blockers:** 5 (DEBT-075 through DEBT-079)
- **Critical security/data integrity:** 0

---

## V1 Launch Blockers

### DEBT-001 — Health endpoint lacks real probes
- **Milestone:** Milestone 2a (Health Probes)
- **Category:** Backend | Observability
- **Priority:** Blocker
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/services/health_service.py`, `backend/src/novelai/api/routers/health.py`
- **Description:** `/api/health` returns static `{"status": "ok"}`. Missing actual DB probe, storage probe, and worker state check.
- **Completion criteria:**
  - `/health` and `/api/health` return live/ready checks.
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
- **Affected areas:** `backend/src/novelai/export/pdf_exporter.py`, `backend/src/novelai/runtime/bootstrap.py`, `backend/src/novelai/services/export_service.py`
- **Description:** PDFExporter registered but raises NotImplementedError. No font policy or generator dependency available.
- **Completion criteria:** Remove active registration, deprecate format, reject requests, preserve historical manifests.
- **Resolution:** Removed `PDFExporter` import and `register_exporter("pdf", ...)` from `bootstrap_exporters()`. `ExportService.export("pdf", ...)` and `export_pdf()` raise `UnsupportedExportFormatError` with safe deprecation message. `OperationsService` catches this and returns `OperationError(400)`. Historical manifests with `format: "pdf"` are preserved (manifest service stores format as free-form string). 10 PDF deprecation tests pass.

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

### DEBT-021 — Legacy aliases need planned migration
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Data Migration
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** Global codebase
- **Description:** Code uses old fields (`slug`, `provider`, `model`, `id`, `source`) instead of canonical names.
- **Completion criteria:** Global renaming check updates callers to matching canonical names.

### DEBT-022 — Storage backward compatibility discipline
- **Milestone:** Milestone 2c (Backup & Storage)
- **Category:** Storage | Data Migration
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/src/novelai/storage/`
- **Description:** Lack of strict schema version enforcement for saved JSON models.
- **Completion criteria:** Storage read/write tests verify compatibility with older formats.
- **Resolution:** Canonical metadata, chapter bundles, glossaries, and versioned
  runtime records now accept supported older or unversioned historical shapes,
  reject invalid and future schema versions through a storage-layer error, and
  prevent attempted writes from replacing incompatible artifacts. Contract tests
  cover legacy reads, current-version writes, invalid/future rejection, and
  preservation after failed writes.

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
- **Status:** Pending
- **Affected areas:** Public chapter routes, highlighter component
- **Description:** Annotation lookup implemented in backend; highlighter component exists but not wired in main reader.
- **Completion criteria:** Highlight badges render inline when public reader page loads.

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
- **Description:** Nested `<main>` landmarks, no skip link, no reduced-motion rules, no focus management, glossary annotations not rendered.
- **Completion criteria:** Single main landmark, skip link, reduced-motion CSS, focus management, accessible reader controls.

### DEBT-059 — Public reader performance budget
- **Milestone:** Milestone M4 (Reader/Catalog UX)
- **Category:** Frontend | Backend
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/app/(public)/`, `backend/src/novelai/api/routers/public_*.py`
- **Description:** No documented latency/payload budgets, no cache-control headers, no bundle analysis, no request-count tests.
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
- **Resolution:** Added reusable bounded database engines, PostgreSQL connection timeouts, renewable scheduled-job leases, real cron/timezone evaluation, split R2 snapshot credentials, streamed encrypted PostgreSQL exports, retention, and redacted SMTP alerts. Live R2 permission-boundary tests proved the three credential roles. On 2026-07-18 two consecutive scheduler-created R2 snapshots passed full checksum verification, and a scheduler-created encrypted PostgreSQL backup was automatically restored into a clean PostgreSQL 17 target at Alembic head `8b7f3d1a2c4e` with 30 public tables and zero invalid constraints. The opt-in hosted PostgreSQL/R2 suite passes, and alert cooldown plus secret redaction have direct tests. Remaining acceptance requires real stale/failure SMTP delivery and successful hosted verification workflow evidence.

### DEBT-076 — Clean PostgreSQL migration lacks Supabase auth compatibility
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Database | CI/CD
- **Priority:** Blocker
- **Status:** Ongoing
- **Affected areas:** `backend/alembic/versions/`, `.github/workflows/ci.yml`
- **Description:** The latest clean PostgreSQL CI migration fails because a
  migration expects Supabase's `auth` schema, while the vanilla PostgreSQL 16
  service does not provide it.
- **Completion criteria:** A clean PostgreSQL service and the hosted Supabase
  project both migrate to head through an explicit, tested compatibility path.
- **Implementation note (2026-07-18):** CI now installs a minimal, fail-closed
  `auth.uid()` compatibility shim before Alembic runs on vanilla PostgreSQL.
  The shim and workflow wiring have focused tests. Hosted CI confirmation on a
  fresh run remains required before resolving this debt.

### DEBT-077 — CI exclusions and workflow success signals are misleading
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Testing | CI/CD
- **Priority:** Blocker
- **Status:** Ongoing
- **Affected areas:** `.github/workflows/ci.yml`, `.github/workflows/build.yml`
- **Description:** Known test exclusions and the aggregate build job can report
  success without proving the complete behavior or image publication implied by
  the workflow name.
- **Completion criteria:** Every exclusion is justified or removed, migration
  and auth regressions run in CI, and aggregate jobs distinguish a skipped
  publication from a verified image push.
- **Implementation note (2026-07-18):** Previously excluded files now run in
  explicit bounded matrix shards, Docker builds depend on both backend suites,
  and the aggregate publication result fails unless image publication succeeds.
  A hosted Actions run remains required before resolving this debt.

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
- **Implementation note (2026-07-18):** Tracked workflows now pin actions to
  immutable commit SHAs and scope write permissions to the publication job.
  The default-branch ruleset, allowed-actions policy, and live scanner status
  still require owner verification in GitHub settings.

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
    - `_get_failed_ids` treats the newest activity with status `completed` or `failed` as authoritative — its `failures` list (even empty) overrides all older activities. Cancelled, pending, queued, and running activities are skipped. `metadata.crawl_result` is read first, falling back to `metadata.result` only for compatibility.
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
  - Single route: `GET /api/admin/library/summary` (operationId `library_summary_api_admin_library_summary_get`). Historical accidental aliases under `/novels/admin/library/summary` and `/api/novels/admin/library/summary` were removed by deleting `library.read_router` from `novels.router` in `backend/src/novelai/api/routers/novels.py`.
- **Tests:**
  - 50 backend library-summary tests, including hardened cold-concurrent exactly-one-build, fake-clock expiry, forced-refresh single-flight joining active build, **successive-generation waiter-retention race**, **invalidation-epoch stale-build rejection** (proving only one stable rebuild after invalidation), **concurrent failed-generation propagation** with 8+ threads, **strengthened normal-callers-join-forced-build**, **incompatible-identity waits-and-rebuilds**, real `Path` prefix normalization, Windows-style string prefix normalization (spying on the backend argument), crawl-failure semantics (newest-clean overrides older failure, cancelled/running activities ignored, malformed payload does not resurrect, duplicates dedup, dict and scalar formats normalize, stored chapters excluded from failed, pending remains `max(total - scraped - failed, 0)`).
  - 7 Admin Library frontend tests in `frontend/app/(admin)/admin/library/__tests__/page.test.tsx`, including a real background-refetch failure test (initial success followed by a settled failed refetch: previous values remain, exactly one amber background warning, no initial-load warning, no explicit-refresh warning; Retry triggers the normal query refetch; a later successful refetch removes the warning).
  - 57 storage tests pass.
  - 2 previously failing web-API tests stay green: `test_list_novels_includes_legacy_syosetu_folder_without_metadata`, `test_publish_refreshes_projection_and_exposes_safe_summary`.
  - Full Vitest suite passes (609 frontend tests across 52 files).
- **Verification:** Implementation and local verification complete (Ruff, Pyright, TypeScript typecheck, lint, and architecture guard all clean; all focused and full test suites green locally).
  Authenticated production read-only verification against the intended configured environment remains operator-pending.
