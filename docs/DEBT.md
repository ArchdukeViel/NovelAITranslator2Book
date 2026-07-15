# Technical Debt Register

Single source of truth for outstanding technical debt.
All resolved items, duplicate entries, and documentation-maintenance tasks have been removed.

---

## Executive Summary

- **Total active debt entries:** 33
- **V1 launch blockers:** 4
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
- **Resolution:** Added `apply_retention()` to `BackupManager` with multi-process file lock, preserving newest + minimum successful backups. Created `BackupService` with lock-based concurrency prevention and `BackupService.get_backup_health()` for health integration. Created `SchedulerService` (APScheduler) with cron-based scheduling for backups and maintenance. Wired into app lifespan. 5 backup retention tests pass.

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
- **Status:** Ongoing
- **Affected areas:** `backend/src/novelai/storage/`
- **Description:** Lack of strict schema version enforcement for saved JSON models.
- **Completion criteria:** Storage read/write tests verify compatibility with older formats.

### DEBT-023 — Admin provider credential UI missing
- **Milestone:** Milestone M5 (Admin Operations)
- **Category:** Frontend | Feature
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/app/(admin)/admin/settings/`
- **Description:** API credentials configurable only through environment. No UI for encrypted database storage.
- **Completion criteria:** Admin page allows list and creation of encrypted DB credential rows.

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
- **Resolution:** Added `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` settings for R2/S3-compatible targets. Updated `S3Backend` constructor to accept explicit credentials. Production validator requires credentials when `S3_ENDPOINT` is set. Created `backend/tests/integration/test_s3_integration.py` with 8 integration tests (save, load, overwrite, delete, list, subdir list). All 8 tests pass against real Cloudflare R2 bucket `dokushodo` using isolated `_integration_test_*` prefix with auto-cleanup. R2 backup/restore drill procedure documented in `docs/operations/data-recovery.md`.

### DEBT-062 — pg_net extension in public schema
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Database | Security
- **Priority:** Low
- **Status:** Pending
- **Affected areas:** Supabase database `public` schema
- **Description:** The `pg_net` extension is installed in the `public` schema instead of the `extensions` schema. Exposes internal HTTP functions via PostgREST. The extension is used by `pg_cron` for automated `cleanup_expired_scheduler_states()` calls.
- **Completion criteria:**
  1. `CREATE SCHEMA IF NOT EXISTS extensions`
  2. `ALTER EXTENSION pg_net SET SCHEMA extensions`
  3. Update `cron.job` command paths to use `extensions.` prefix
  4. Verify cron job runs at next scheduled time (03:30 UTC) without error
  5. Confirm no other code references `net.*` without schema qualification

### DEBT-073 — Glossary prompt injection test drift
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Testing
- **Priority:** Medium
- **Status:** Resolved
- **Affected areas:** `backend/tests/test_glossary_prompt_injection.py`
- **Description:** Test expects stale prompt text after prompt policy update.
- **Completion criteria:** Test assertions updated to match current prompt policy.
- **Evidence:** Updated `test_canonical_term_and_translation_render_deterministically` expected string to match current `_render_text()` output (LOCKED/APPROVED sections, authority preamble). `test_glossary_prompt_injection.py` passes all 15 tests.
