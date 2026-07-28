# Project Roadmap

This is the single source of truth for release gates, phase order, and feature milestones.
Status and details are updated directly as release verification progresses.

Milestone status distinguishes code completion from operational acceptance. A
milestone may be implemented while live evidence or a current CI regression
keeps its acceptance gate open.

<!-- Update the "Current Operational State" section below when milestone
     status changes. It is the live snapshot, not a historical record. -->

---

## Milestone M0 — CI Confidence
- **Status:** Complete; CI regressions closed
- **Description:** Stabilize deployment builds and integration testing in the CI environment.
- **Evidence:**
  - CI run (PR #1): <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29230504497> — all gates pass (backend-lint, backend-tests, frontend-check, docker-build)
  - Build run (main push): <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29231656072> — three Docker images pushed to GHCR with SHA + latest tags
  - Clean PostgreSQL compatibility run: <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29941138116> — passed migration, lint, backend, frontend, and E2E
  - Publication run: <https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/29941617651> — pushed admin, reader, and frontend images
  - Acceptance gate 1: `ci.yml` passes on main with database tests active ✓
  - Acceptance gate 2: `build.yml` outputs Docker image tags to registry ✓
- **Scope:**
  - Add PostgreSQL service and required `DATABASE_URL` to GitHub Actions workflow.
  - Run database-dependent tests in CI instead of skipping.
  - Verify that dual-service Docker image build (`admin` and `reader` images) finishes green on push.
- **Regressions closed:**
  - DEBT-076 resolved: clean PostgreSQL CI migration passes with `auth.uid()` compatibility shim and hosted CI evidence.
  - DEBT-077 resolved: CI exclusions justified, aggregation distinguishes skipped from published, hosted CI evidence confirms truthful gate.
- **Acceptance gates:**
  - `ci.yml` passes on main branch with database tests active.
  - `build.yml` outputs Docker image tags to registry.

## Milestone M1 — Glossary and Router Repair
- **Status:** Done
- **Description:** Fix the runtime GLOSSARY router dependency cycle and test-drift blocker.
- **Scope:**
  - Refactor circular glossary module imports.
  - Fix prompt quality policy test drift (expected prompt assertion mismatch).
  - Enforce the router layer guard (prevent direct storage/DB imports in API endpoints).
- **Blockers:**
  - DEBT-006: admin_glossary routers cyclic imports block test runner collection.
  - DEBT-073: test_glossary_prompt_injection test expects stale prompt text.
- **Acceptance gates:**
  - `test_admin_glossary_api.py` passes.
  - Router layer validation script returns green.

## Milestone M2 — Operational Safety (Phase 2)
- **Status:** Implemented; managed-service acceptance partial
- **Description:** Health checks, PDF resolution, backups, and storage retention safety.
- **Sub-Milestones:**
  - **M2a (Health Probes):** Replace static `/health` routes with database, storage, and worker probes. Expose diagnostic details without leaking secrets. (DEBT-001) — Resolved
  - **M2b (PDF Exporter):** Remove registered PDF stub exporter from registry. Document formal deprecation. (DEBT-007) — Resolved
  - **M2c (Storage & Backups):** Schedule local backups, configure retention times, clean fetch caches, prune events and activity logs, and lock writes atomically. (DEBT-010, DEBT-025, DEBT-034, DEBT-035, DEBT-036) — Resolved
- **Acceptance gates:**
  - Focused health tests, backup manager tests, and cleanup execution tests pass. — Verified (111 focused tests pass)
  - Multi-process lock mechanism prevents concurrent write conflicts. — Verified (11 file lock tests pass on Windows)
- **Evidence:**
  - `python -m ruff check .` — All checks passed
  - `python -m pyright` — 0 errors, 0 warnings
  - `python -m pytest` for all focused test files — 111 passed
  - Router boundary guard — no matches (clean)
  - `git diff --check` — no integrity issues
  - DEBT-075 records completed scheduler-created R2 and database recovery
    evidence; alert-delivery and hosted-test evidence remain.

## Milestone M3 — Deployment Readiness
- **Status:** Implemented; hosted deployment acceptance pending
- **Description:** Production config validator, Redis rate limiting with cross-instance verification, security headers/proxy/CORS hardening, Caddy/Compose route verification, frontend ESLint + CI lint step, S3 integration test harness, deploy smoke checks, updated deployment/operations documentation.
- **Scope:**
  - Set up Redis rate limiting and verify multi-instance behavior. (DEBT-039)
  - Configure Caddy routes matching ordered admin/auth/public split backend targets.
  - Setup ESLint configs and check within the CI build. (DEBT-026, DEBT-032)
  - Verify S3 storage backend with real integration checks. (DEBT-061)
  - Implement production configuration validator and startup checks. (DEBT-055)
  - Harden TLS, proxy, CORS, CSRF, cookies, and security headers. (DEBT-055)
  - Add deploy smoke checks, rollback procedure, and migration gate. (DEBT-055)

## Milestone M3.5 — Free Hosted Preview and Production Topology
- **Status:** In progress
- **Description:** Establish a disposable free hosted preview without claiming
  production reliability, then prove the paid always-on production topology.
- **Scope:**
  - Vercel Hobby hosts the personal/non-commercial preview frontend.
  - One Render Free monolith hosts the preview backend with continuous worker,
    scheduler, backup/restore jobs, maintenance, and SMTP disabled.
  - Supabase Free and development-only R2 scopes support preview data.
  - Production uses an always-on container backend, managed Redis, tested SMTP,
    monitoring, and the existing Supabase/R2 data services.
- **Acceptance gates:**
  - Preview OAuth, cookies, CORS, CSRF, host validation, health, and rollback are
    verified against the chosen domains.
  - Production upgrades are selected before commercial or reliability-sensitive
    use, and DEBT-079 is closed with deployment evidence.
- **Implementation note (2026-07-18):** The repository now defines a Render
  Free monolith Blueprint and a Vercel frontend configuration. Hosted domain,
  OAuth, security-boundary, R2-scope, health, and rollback evidence remain.

## Milestone M4 — Reader and Catalog UX
- **Status:** Planned
- **Description:** Polish discovery index, tags, SEO, accessibility, performance, error states, and legal/takedown workflow.
- **Scope:**
  - Integrate public reader glossary highlighter. (DEBT-037)
  - Configure public SEO tags, sitemaps, and robots.txt. (DEBT-038)
  - Enable Japanese tag name translation badge display. (DEBT-029)
  - Enforce taxonomy genre payload contracts. (DEBT-030)
  - Add shared frontend error/empty/loading states. (DEBT-056)
  - Establish public reader accessibility baseline. (DEBT-058)
  - Establish public reader performance budget and cache contract. (DEBT-059)
  - Implement legal/takedown workflow with HTTP 451 enforcement. (DEBT-060)

## Milestone M5 — Admin Operations Polish
- **Status:** Complete locally — implementation, validation, review, documentation, and local commits complete
- **Description:** Admin dashboards, user control, alerts, audit viewer, and credential management.
- **Scope:**
  - Admin user management CRUD endpoints. (DEBT-008)
  - Provider credentials settings management page. (DEBT-023)
  - Scheduled export freshness checker tasks. (DEBT-033)
  - Aggregated metrics collectors and Grafana panels. (DEBT-011, DEBT-040, DEBT-052)
  - Enable LLM-based translation QA checks. (DEBT-053)
  - Implement owner-only audit log viewer. (DEBT-054)

## Milestone M6 — Gated Community Features (Phase 3)
- **Status:** Deferred
- **Description:** User folders, public contributions, and rankings.
- **Gated requirements:**
  - Do not implement public contribution credentials until section 13 readiness gate is met.
  - Do not enable catalog search rankings before spam moderation rules are implemented.

## Milestone M7 — Launch Readiness
- **Status:** Planned
- **Description:** Final operator go/no-go evidence collection and launch decision.
- **Scope:**
  - Verify core product flows end-to-end.
  - Verify public reader safety, accessibility, performance, and SEO.
  - Verify admin operations, audit viewer, and takedown workflow.
  - Verify backups, restore drill, health checks, and maintenance.
  - Verify production hardening, security, and privacy.
  - Verify monitoring and rollback readiness.
  - Document known issues and launch blockers.
  - Provide a clear go/no-go decision process.
- **Acceptance gates:**
  - `docs/operations/launch-checklist.md` exists with status, owner, evidence, blocker, waiver, and decision fields.
  - All M0-M5 dependencies resolved or explicitly waived.

---

## Current Operational State

High-level operational snapshot.
For the technical debt register and launch blockers, see [`docs/DEBT.md`](DEBT.md).

### Launch Status

- **Launch readiness:** Not ready. Core managed-service implementation is
  mature, but hosted CI confirmation, alert delivery, hosted deployment,
  reader/admin polish, and final launch evidence remain open.
- **Current launch blockers:** DEBT-075, DEBT-079, DEBT-094: managed-service
  acceptance, hosted topology acceptance, Render Blueprint schema validation,
  and alert-delivery evidence.

### Core Infrastructure Config

- **Backend:** FastAPI monolith (default) with split deployment options under `DEPLOY_MODE=split`.
- **Frontend:** Next.js 15 App Router.
- **Database:** SQLAlchemy and Alembic remain authoritative; the current hosted
  database is Supabase PostgreSQL 17. A managed database does not replace the
  repository migration layer.
- **Storage:** Cloudflare R2 is the current S3-compatible object store. Application
  data and independent recovery snapshots use private, separately scoped buckets.
- **Worker:** Background activity worker defaults to in-process (`JOB_WORKER_ENABLED=true`). Async queue support via Redis/RQ exists.
- **Translation:** Gemini only. The approved chain is
  `gemini-3.1-flash-lite` then `gemma-4-31b-it`, using the Gemini API. Public
  contribution credentials remain gated and are not a current launch feature.
- **Settings:** Configured via `pydantic-settings` in `backend/src/novelai/config/settings.py`. Canonical environment variable is `ENV` (not `APP_ENV`).

### Validation Status

- **Local checks:** Phase 3 validation passes: Ruff format/check on all 63 changed
  Python files, Pyright with 0 errors and 0 warnings, 388 focused backend tests,
  frontend typecheck/lint plus 675 tests across 56 files, production build with
  43/43 static pages, and the router guard with zero forbidden imports.
- **Latest CI:** The clean-PostgreSQL `auth.uid()` compatibility path is fixed
  and verified on a hosted Actions run (DEBT-076 resolved).
- **Build workflow:** The aggregate result now distinguishes a successful image
  publication from a skipped publication; hosted confirmation confirmed on a
  follow-up run (DEBT-077 resolved).
- **Hosted services:** Supabase security advisors last reported zero WARN
  findings. On 2026-07-18 two scheduler-created R2 snapshots passed full
  checksum verification, and a scheduler-created encrypted database backup was
  automatically restored into a clean PostgreSQL 17 target with the current
  Alembic head, 30 public tables, and zero invalid constraints. The opt-in
  hosted PostgreSQL and isolated-prefix real-R2 suites also pass (3 tests) with
  all temporary objects removed.

### Known Gaps (Not Launch-Ready)

- Alert cooldown and secret redaction have direct regression coverage; real
  stale/failure SMTP delivery to the operator inbox remains unproven.
- The free preview domains and the always-on production topology need acceptance.
- Owner-only audit viewer and the remaining M5 admin operations are locally implemented, reviewed, validated, and committed.
- No takedown workflow; no HTTP 451 enforcement.
- No measured performance or accessibility gate.
- No launch readiness evidence or go/no-go decision.

### Implemented Features (Phase 2 Live Library Summary)

Status legend:
- Implemented — code shipped; contract + tests in place.
- Locally validated — passing on local dev backend and frontend test runs.
- CI validated — passing on GitHub Actions workflow.
- Production verified — passing against an authenticated, owner-provisioned read-only call against the production environment.

- **Live Admin Library Summary** (`GET /api/admin/library/summary`): derives per-novel counts from a single recursive R2 listing pass. Counts: total, scraped, translated, failed, pending. 30s TTL, explicit `refresh=true` bypass. Catalog-identity-aware cache (DB slugs vs storage union). [Implemented / Locally validated / CI validated / Production verified: pending]
- **Single-flight concurrency** via per-generation `_BuildGeneration` object, condition variable, and generation counter. [Implemented / Locally validated / CI validated / Production verified: pending]
- **Invalidation epoch** (`self._invalidation_epoch`): monotonic counter. If the epoch advances during a build, the result is not published to cache. [Implemented / Locally validated / Production verified: pending]
- **Crawl failure history semantics**: the newest activity with `status` in (`completed`, `failed`) is authoritative. [Implemented / Locally validated / Production verified: pending]
- **Immutable cached state** (`tuple[NovelSummaryCounts, ...]`); outward responses are fresh dicts/lists. [Implemented / Locally validated]
- **Catalog-identity-aware caching**: cache key includes sorted unique DB slugs; identity change forces rebuild. [Implemented / Locally validated]
- **Frontend join**: `summary.data.items` merged into novel rows via `Map(novel_id → item)`. [Implemented / Locally validated]
- **Settled background-refetch failure detection** via `summary.isRefetchError`. [Implemented / Locally validated / Production verified: pending]
- **Three distinct error states**: initial failure, settled background failure, explicit-refresh failure. [Implemented / Locally validated]
- **Route uniqueness**: admin behavior is registered only under `/api/admin/*`. [Implemented / Locally validated]
- **Invalidation**: immediate after full-crawl deletion and metadata replacement; best-effort after chapter/translation/glossary/activation saves. [Implemented / Locally validated]
- **Tests**: 50 library-summary tests; 57 storage tests; 609 frontend tests across 52 files. [Implemented / Locally validated / CI validated: pending]
- **Production verification**: Remains operator-pending.

---

## Spec Backlog

21 roadmap-linked specs remain in `.agents/kiro/specs/`.
45 archived specs moved to `docs/archive/specs/` on 2026-07-22.

### Roadmap-Linked Specs (21)

| Spec | Debt / Milestone |
|---|---|
| `admin-audit-log-viewer` | DEBT-054 (M5) |
| `admin-user-management` | DEBT-008 (M5) |
| `analytics-baseline` | DEBT-011 (M5) |
| `contact-support-legal-pages` | DEBT-043 (M4) |
| `deep-health-readiness-checks` | DEBT-001 (M2a) |
| `deployment-production-hardening` | DEBT-055 (M3, Resolved) |
| `frontend-error-boundary-and-empty-states` | DEBT-056 (M4) |
| `launch-readiness-checklist` | DEBT-057 (M7) |
| `maintenance-cron` | DEBT-042 (M2c) |
| `metric-dashboard-baseline` | DEBT-040 (M3) |
| `notification-system` | DEBT-009 (M5) |
| `pdf-exporter=registration` | DEBT-007 (M2b) |
| `public-reader-accessibility-baseline` | DEBT-058 (M4) |
| `public-reader-graceful-degradation` | M4 |
| `public-reader-performance-budget` | DEBT-059 (M4) |
| `public-reader-seo-discovery-baseline` | DEBT-038 (M4) |
| `rate-limit-and-abuse-protection-baseline` | DEBT-039 (M3, Resolved) |
| `scheduled-backups-and-restore-drills` | DEBT-010 (M2c) |
| `scheduled-export-freshness-check` | DEBT-033 (M5) |
| `scheduler-runtime-state-persistence` | DEBT-036 (M2c) |
| `terms-dmca-takedown-workflow` | DEBT-060 (M4) |
