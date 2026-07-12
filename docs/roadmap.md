# Project Roadmap

This is the single source of truth for release gates, phase order, and feature milestones.
Status and details are updated directly as release verification progresses.

---

## Milestone M0 — CI Confidence
- **Status:** Blocked
- **Description:** Stabilize deployment builds and integration testing in the CI environment.
- **Scope:**
  - Add PostgreSQL service and required `DATABASE_URL` to GitHub Actions workflow.
  - Run database-dependent tests in CI instead of skipping.
  - Verify that dual-service Docker image build (`admin` and `reader` images) finishes green on push.
- **Blockers:**
  - DEBT-002: Actions build fails on remote GHCR push credentials.
  - DEBT-003: Postgres service missing in CI Actions.
- **Acceptance gates:**
  - `ci.yml` passes on main branch with database tests active.
  - `build.yml` outputs Docker image tags to registry.

## Milestone M1 — Glossary and Router Repair
- **Status:** Blocked
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
- **Status:** In progress
- **Description:** Health checks, PDF resolution, backups, and storage retention safety.
- **Sub-Milestones:**
  - **M2a (Health Probes):** Replace static `/health` routes with database, storage, and worker probes. Expose diagnostic details without leaking secrets. (DEBT-001)
  - **M2b (PDF Exporter):** Remove registered PDF stub exporter from registry. Document formal deprecation. (DEBT-007)
  - **M2c (Storage & Backups):** Schedule local backups, configure retention times, clean fetch caches, prune events and activity logs, and lock writes atomically. (DEBT-010, DEBT-025, DEBT-034, DEBT-035, DEBT-036)
- **Acceptance gates:**
  - Focused health tests, backup manager tests, and cleanup execution tests pass.
  - Multi-process lock mechanism prevents concurrent write conflicts.

## Milestone M3 — Deployment Readiness
- **Status:** Planned
- **Description:** Production configs, proxy routing, rate-limit testing, and deployment guide verification.
- **Scope:**
  - Set up Redis rate limiting and verify multi-instance behavior. (DEBT-039)
  - Configure Caddy routes matching ordered admin/auth/public split backend targets.
  - Setup ESLint configs and check within the CI build. (DEBT-026, DEBT-032)
  - Verify S3 storage backend with real integration checks. (DEBT-061)
  - Implement production configuration validator and startup checks. (DEBT-055)
  - Harden TLS, proxy, CORS, CSRF, cookies, and security headers. (DEBT-055)
  - Add deploy smoke checks, rollback procedure, and migration gate. (DEBT-055)

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
- **Status:** Planned
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
