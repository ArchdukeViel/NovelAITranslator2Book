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
- **Status:** In progress (documented, planning code implementation)
- **Affected areas:** `backend/src/novelai/api/routers/health.py`
- **Description:** `/api/health` returns static `{"status": "ok"}`. Missing actual DB probe, storage probe, and worker state check.
- **Completion criteria:**
  - `/health` and `/api/health` return live/ready checks.
  - Ready check fails with 503 if DB or storage is down.
  - Probes sanitize credentials and raw error tracebacks.

### DEBT-002 — CI/CD build.yml not verified on push to main
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** CI/CD
- **Priority:** Blocker
- **Status:** Implemented but unverified
- **Affected areas:** `.github/workflows/build.yml`, Dockerfiles
- **Description:** Actions build file corrected to match current Dockerfile naming but needs remote run check to verify image pushes.
- **Completion criteria:** Workflow runs green on push to main, writing three GHCR image tags.

### DEBT-003 — DB-dependent tests fail on CI (no Postgres runner)
- **Milestone:** Milestone M0 (CI Confidence)
- **Category:** Testing | CI/CD
- **Priority:** Blocker
- **Status:** Blocked
- **Affected areas:** `.github/workflows/ci.yml`, test files
- **Description:** CI workflow lacks PostgreSQL service. Real DB tests fail on Actions run.
- **Completion criteria:** Actions yaml has `services.postgres` setup and all web/integration tests pass.

### DEBT-006 — Circular import in admin_glossary routers
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Architecture
- **Priority:** Blocker
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/api/routers/admin_glossary.py` and related split routers
- **Description:** Mutual imports between admin glossary and sub-routers block module load and test collection.
- **Completion criteria:** Extracted helper functions and model schema definitions to a clean non-circular shared file.

---

## Technical Debt Register (Phase 2+ / Roadmap)

### DEBT-007 — PDF exporter stubbed but not implemented
- **Milestone:** Milestone 2b (PDF Resolution)
- **Category:** Backend | Feature
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/export/pdf_exporter.py`
- **Description:** PDFExporter registered but raises NotImplementedError. No font policy or generator dependency available.
- **Completion criteria:** Remove active registration, deprecate format, reject requests, preserve historical manifests.

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
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/services/backup_manager.py`
- **Description:** BackupManager exists but has no container integration, scheduled trigger, or retention policy.
- **Completion criteria:** Scheduled task writes file backups, cleans old archives, and reports counts.

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
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/storage/`
- **Description:** Fetch cache lacks TTL cleanup. Pipeline events grow without bound.
- **Completion criteria:** Storage cleanup deletes old cache, prunes event lists, uses locks.

### DEBT-026 — Frontend lint not configured non-interactively
- **Milestone:** Milestone M3 (Deployment)
- **Category:** Frontend | CI/CD
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `frontend/`
- **Description:** ESLint configuration not run inside CI pipeline.
- **Completion criteria:** `eslint.config.mjs` present, `npm run lint` checked on Actions.

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
- **Status:** Pending
- **Affected areas:** Github actions deploy file
- **Description:** Deploy workflow triggered only via manual UI dispatch.
- **Completion criteria:** Auto-trigger deploy on pushed version tag.

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
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/translation/pipeline/`
- **Description:** Flaky integration tests because stage files omit trace events.
- **Completion criteria:** All pipeline stages write status files atomically.

### DEBT-035 — Windows file locking test flakiness
- **Milestone:** Milestone M2c (Backup & Storage)
- **Category:** Testing | Platform
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `backend/tests/`
- **Description:** Multi-process cleanup fails on Windows due to file handles remaining open.
- **Completion criteria:** Lock retries handled, and test runs pass on Windows platform.

### DEBT-036 — Scheduler state persistence incomplete
- **Milestone:** Milestone M2c (Backup & Storage)
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/services/orchestration/`
- **Description:** Scheduler state logs limits but cooldowns are lost on process reset.
- **Completion criteria:** Persist complete state parameters per job.

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
- **Status:** Pending
- **Affected areas:** Rate limiter dependency
- **Description:** Redis-backed limit counters not verified in split multi-process deployment.
- **Completion criteria:** Multi-instance tests confirm Redis rate limits block burst requests.

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
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/config/settings.py`, `backend/src/novelai/api/app.py`, `deploy/compose.yml`, `deploy/Caddyfile`
- **Description:** No production config validator, no trusted proxy/host policy, no security headers, no deploy smoke checks, no rollback procedure. Compose healthcheck targets wrong service.
- **Completion criteria:** Production validator, trusted proxy/host config, security headers, deploy smoke checks, rollback procedure, corrected healthcheck.

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
- **Status:** Pending
- **Affected areas:** `backend/src/novelai/storage/backends/s3.py`
- **Description:** S3 backend fields restored to settings but not validated in production deployment.
- **Completion criteria:** Real S3 integration tests, production config validation, backup/restore drill with S3.

### DEBT-073 — Glossary prompt injection test drift
- **Milestone:** Milestone M1 (Glossary/Router Repair)
- **Category:** Backend | Testing
- **Priority:** Medium
- **Status:** Pending
- **Affected areas:** `backend/tests/test_glossary_prompt_injection.py`
- **Description:** Test expects stale prompt text after prompt policy update.
- **Completion criteria:** Test assertions updated to match current prompt policy.
