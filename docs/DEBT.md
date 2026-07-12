# Technical Debt Register

Single source of truth for all outstanding technical debt.
Consolidated from `SPECS_COMPLETION.md`, `architecture.md`, `backend_layer_violation_debt.md`, `current_state.md`.
Last updated: 2026-07-12

---

## Executive Summary

- **Total active debt entries:** 54 (including newly discovered)
- **V1 launch blockers:** 3 (health probes, CI/CD build verification, DB-dependent tests on CI)
- **Critical security/data-integrity:** 0
- **Incomplete Phase 0 work:** 2 (CI/CD build.yml verification, test_crawl_resilience_contracts fixture fix)
- **Incomplete Phase 1 work:** 1 (circular import in admin_glossary routers)
- **Remaining phases (2+):** 48 entries across architecture, backend, frontend, storage, testing, operations, CI/CD, documentation

---

## V1 Launch Blockers

### DEBT-001 — Health endpoint lacks real probes
- **Origin:** SPECS_COMPLETION / deep-health-readiness-checks spec
- **Category:** Backend | Observability
- **Priority:** Blocker
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/health.py`
- **Current state:** `/api/health` returns `{"status": "ok"}` with no DB, storage, or worker probes.
- **Missing work:** Implement liveness/readiness probes checking PostgreSQL connectivity, storage accessibility, Redis (if configured), and worker queue health.
- **Reason deferred:** Requires design decision on probe granularity and failure modes.
- **Risk:** Cannot reliably use in Kubernetes/Docker health checks; deployments may route traffic to unhealthy instances.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `/api/health/live` returns 200 if process is alive
  - [ ] `/api/health/ready` returns 200 only if DB + storage + Redis (if used) are reachable
  - [ ] Integration test verifies probe behavior under failure conditions
- **Validation commands:**
  - `curl http://localhost:8000/api/health/live`
  - `curl http://localhost:8000/api/health/ready`
- **Notes:** See `deep-health-readiness-checks` spec for full requirements.

### DEBT-002 — CI/CD build.yml not verified green on push to main
- **Origin:** Phase 0a (cicd-pipeline spec)
- **Category:** CI/CD
- **Priority:** Blocker
- **Status:** Implemented but unverified
- **Affected areas:**
  - `.github/workflows/build.yml`
  - `deploy/admin.Dockerfile`
  - `deploy/reader.Dockerfile`
  - `deploy/frontend.Dockerfile`
- **Current state:** `build.yml` was fixed to reference new Dockerfile names (admin/reader/frontend) instead of deleted `backend.Dockerfile`. Local Docker builds succeed. Not yet verified on GitHub Actions push to main.
- **Missing work:** Push to main and verify workflow completes with all three images pushed to GHCR with SHA and `latest` tags.
- **Reason deferred:** Requires GitHub Actions runner access.
- **Risk:** Broken production deployments if build fails silently.
- **Dependencies:** DEBT-003 (GitHub secrets for GHCR)
- **Completion criteria:**
  - [ ] `build.yml` runs green on push to main
  - [ ] Three images published: `novelai-backend-admin`, `novelai-backend-reader`, `novelai-frontend`
  - [ ] Both `sha-{commit}` and `latest` tags present
- **Validation commands:**
  - `git push origin main` (then check Actions tab)
- **Notes:** See `cicd-pipeline` spec and `docs/cicd-manual-setup.md`.

### DEBT-003 — DB-dependent tests fail on CI (no Postgres runner)
- **Origin:** Phase 0c / e2e-integration-testing spec
- **Category:** Testing | CI/CD
- **Priority:** Blocker
- **Status:** Blocked
- **Affected areas:**
  - `backend/tests/test_web_api.py` (auth routes: 6 failures)
  - `backend/tests/test_web_api.py` (ListDetail/Admin/Activity: 6 failures)
  - `backend/tests/test_integration.py` (3 flaky)
- **Current state:** Tests pass locally with PostgreSQL but CI runner lacks Postgres service. `test_web_api.py` auth routes and integration tests require real DB.
- **Missing work:** Add PostgreSQL service to GitHub Actions CI workflow, or migrate tests to use testcontainers/sqlite where feasible.
- **Reason deferred:** CI infrastructure change required; testcontainers adds complexity.
- **Risk:** No CI coverage for auth, catalog, admin, activity APIs.
- **Dependencies:** GitHub Actions workflow modification.
- **Completion criteria:**
  - [ ] CI workflow includes `services.postgres` or equivalent
  - [ ] All `test_web_api.py` tests pass on CI
  - [ ] `test_integration.py` flakiness resolved or documented
- **Validation commands:**
  - `python -m pytest backend/tests/test_web_api.py -v`
  - `python -m pytest backend/tests/test_integration.py -v`

---

## Critical Security and Data-Integrity Debt

*None currently identified.*

---

## Incomplete Phase 0 Work

### DEBT-004 — Phase 0a: CI/CD dual-service build verification
- **Origin:** Phase 0a (cicd-pipeline spec)
- **Category:** CI/CD
- **Priority:** Critical
- **Status:** Implemented but unverified
- **Affected areas:**
  - `.github/workflows/build.yml`
  - `deploy/admin.Dockerfile`
  - `deploy/reader.Dockerfile`
  - `deploy/frontend.Dockerfile`
- **Current state:** Dockerfile references fixed. Local builds work. Not verified on GitHub Actions.
- **Missing work:** Verify `build.yml` runs green on push to main with all three images.
- **Reason deferred:** Requires GitHub Actions execution.
- **Risk:** Production deployments may fail.
- **Dependencies:** DEBT-002
- **Completion criteria:**
  - [ ] Verified green build on main branch
- **Validation commands:**
  - Push to main and monitor Actions

### DEBT-005 — Phase 0c: test_crawl_resilience_contracts.py fixture pre-population
- **Origin:** Phase 0c (crawl-fetch-observability spec)
- **Category:** Testing
- **Priority:** High
- **Status:** Fixed locally, not verified on CI
- **Affected areas:**
  - `backend/tests/test_crawl_resilience_contracts.py`
  - `backend/tests/conftest.py`
- **Current state:** Fixed locally (18→0 failures) via fixture pre-population and `slow_fetch` signature fix. Not run on CI due to DEBT-003.
- **Missing work:** Verify fix holds on CI once Postgres is available.
- **Reason deferred:** Blocked on CI Postgres.
- **Risk:** Regression undetected.
- **Dependencies:** DEBT-003
- **Completion criteria:**
  - [ ] Test passes on CI
- **Validation commands:**
  - `python -m pytest backend/tests/test_crawl_resilience_contracts.py -v`

---

## Incomplete Phase 1 Work

### DEBT-006 — Circular import in admin_glossary routers
- **Origin:** Phase 1 (glossary-management-consolidation spec)
- **Category:** Backend | Architecture
- **Priority:** Critical
- **Status:** Not started (newly discovered)
- **Affected areas:**
  - `backend/src/novelai/api/routers/admin_glossary.py`
  - `backend/src/novelai/api/routers/admin_glossary_provider.py`
- **Current state:** `admin_glossary.py` imports from `admin_glossary_provider.py` (line 17-26), and `admin_glossary_provider.py` imports from `admin_glossary.py` (line 17-26). This creates a circular import that will fail at runtime when both modules are loaded.
- **Missing work:** Refactor shared models/helpers (`CandidateImportAction`, `CandidateImportMode`, `GlossaryProviderCandidateSummary`, `GlossaryProviderSuggestionRequest`, `GlossaryProviderSuggestionResponse`, `_provider_error_status`, `_require_novel`, `_safe_provider_error_detail`) into a separate shared module (e.g., `admin_glossary_shared.py`).
- **Reason deferred:** Discovered during documentation audit; not in original Phase 1 scope.
- **Risk:** Runtime import failure when both routers are loaded; blocks any code that imports both.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Shared models/helpers extracted to `admin_glossary_shared.py`
  - [ ] Both routers import from shared module
  - [ ] No circular import at runtime
  - [ ] All glossary admin endpoints functional
- **Validation commands:**
  - `python -c "from novelai.api.routers import admin_glossary, admin_glossary_provider; print('OK')"`
  - `python -m pytest backend/tests/test_admin_glossary_api.py -v`

---

## Remaining Phases (Phase 2+)

### DEBT-007 — PDF exporter stubbed but not implemented
- **Origin:** pdf-exporter-registration spec
- **Category:** Backend | Feature
- **Priority:** Medium
- **Status:** Partial (registered but raises NotImplementedError)
- **Affected areas:**
  - `backend/src/novelai/runtime/bootstrap.py:82`
  - `backend/src/novelai/export/pdf_exporter.py`
- **Current state:** `PDFExporter` class exists and is registered in bootstrap, but `export()` method raises `NotImplementedError`.
- **Missing work:** Implement `export()` using `reportlab` or `weasyprint`, or formally deprecate and remove from registry.
- **Reason deferred:** Low priority; EPUB/HTML/Markdown exports work.
- **Risk:** Admin export UI shows PDF option that fails at runtime.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `PDFExporter.export()` produces valid PDF
  - [ ] Integration test covers PDF export
  - [ ] Or: exporter removed from registry and UI
- **Validation commands:**
  - `python -c "from novelai.export.pdf_exporter import PDFExporter; print(PDFExporter.__doc__)"`

### DEBT-008 — No admin user management endpoints
- **Origin:** admin-user-management spec
- **Category:** Backend | Feature
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/admin.py`
- **Current state:** No endpoints for listing/creating/disabling admin users. Only owner bootstrap exists.
- **Missing work:** Implement admin user CRUD with role management.
- **Reason deferred:** Single-owner model sufficient for MVP.
- **Risk:** Cannot delegate admin access without sharing owner credentials.
- **Dependencies:** Auth service extraction (DEBT-012)
- **Completion criteria:**
  - [ ] `GET/POST/PATCH/DELETE /api/admin/users` endpoints
  - [ ] Role-based access control (owner vs admin)
  - [ ] Tests for admin user management

### DEBT-009 — No notification system
- **Origin:** notification-system spec
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** New module needed
- **Current state:** No notification infrastructure.
- **Missing work:** Design and implement notification service (email, in-app, webhook).
- **Reason deferred:** Post-MVP feature.
- **Risk:** Users not informed of job completion, errors, mentions.
- **Dependencies:** Email delivery (SMTP config)

### DEBT-010 — No scheduled backups
- **Origin:** scheduled-backups-and-restore-drills spec
- **Category:** Operations | Data Integrity
- **Priority:** High
- **Status:** Partial (backup_manager.py class exists, not wired/scheduled)
- **Affected areas:**
  - `backend/src/novelai/services/backup_manager.py`
- **Current state:** `BackupManager` class implemented but no scheduler integration, no cron, no restore drills.
- **Missing work:** Wire into scheduler (APScheduler or cron), configure retention, document restore procedure.
- **Reason deferred:** Requires production deployment context.
- **Risk:** Data loss unrecoverable without tested backups.
- **Dependencies:** Production deployment (DEBT-018)
- **Completion criteria:**
  - [ ] Automated daily backup to configured destination
  - [ ] Restore procedure documented and tested
  - [ ] Retention policy enforced

### DEBT-011 — No analytics
- **Origin:** metric-dashboard-baseline / analytics-baseline specs
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** New module needed
- **Current state:** No analytics collection or dashboard.
- **Missing work:** Implement event tracking, aggregation, and admin dashboard.
- **Reason deferred:** Post-MVP.

### DEBT-012 — AuthService not extracted (router imports db.models directly)
- **Origin:** architecture.md §3 / auth-authorization spec
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/auth.py`
- **Current state:** Router has ~250 lines of inline CRUD with `db.models.users` and `session.*` calls.
- **Missing work:** Extract `AuthService` to `services/auth_service.py`, add factory to `dependencies.py`, thin router to HTTP adapter.
- **Reason deferred:** Part of router layer violation cleanup (9 services planned, 0 extracted for auth).
- **Risk:** Violates layer rules; hard to test; CI guard will fail if not fixed.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `AuthService` class with all auth logic
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin (< 50 lines)
  - [ ] Tests pass

### DEBT-013 — LibraryService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/library.py`
- **Current state:** 3 `db.models` imports, 1 `sources.status`, 1 `StorageService`, ~30 direct storage calls.
- **Missing work:** Extract `LibraryService`, add factory, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `LibraryService` in `services/library_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin

### DEBT-014 — GlossaryWorkflowService not extracted
- **Origin:** architecture.md §3 / glossary-management-consolidation spec
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/admin_glossary.py`
  - `backend/src/novelai/api/routers/admin_glossary_candidates.py`
  - `backend/src/novelai/api/routers/admin_glossary_apply.py`
  - `backend/src/novelai/api/routers/admin_glossary_provider.py`
  - `backend/src/novelai/api/routers/admin_glossary_suggestions.py`
- **Current state:** 5 split routers, all importing `db.models.glossary`, `Novel`, `StorageService`, with direct storage calls.
- **Missing work:** Extract unified `GlossaryWorkflowService`, add factory, thin all 5 routers.
- **Dependencies:** DEBT-006 (circular import fix)
- **Completion criteria:**
  - [ ] `GlossaryWorkflowService` in `services/glossary_workflow_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] All 5 routers thin

### DEBT-015 — UserLibraryService / ReadingService / ReviewService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/user_data.py`
- **Current state:** 7 `db.models` symbols, 30 `session.*` calls, 17 `session.query`.
- **Missing work:** Extract three services, add factories, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Three services in `services/`
  - [ ] Factories in `dependencies.py`
  - [ ] Router thin

### DEBT-016 — PublicCatalogService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/public.py`
- **Current state:** 1 `db.models` symbol, `sources.status`, `StorageService`, 14 storage calls.
- **Missing work:** Extract `PublicCatalogService`, add factory, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `PublicCatalogService` in `services/public_catalog_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin

### DEBT-017 — EditorService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/editor.py`
- **Current state:** 1 inline `db.models.novel`, `StorageService`, 9 storage calls.
- **Missing work:** Extract `EditorService`, add factory, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `EditorService` in `services/editor_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin

### DEBT-018 — NovelRequestService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/requests.py`
- **Current state:** 2 `db.models` symbols, full CRUD in router.
- **Missing work:** Extract `NovelRequestService`, add factory, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `NovelRequestService` in `services/novel_request_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin

### DEBT-019 — AdminService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/admin.py`
- **Current state:** `StorageService`, 3 preflight `storage.load_metadata` calls in export routes.
- **Missing work:** Extract `AdminService`, add factory, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `AdminService` in `services/admin_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin

### DEBT-020 — OperationsService not extracted
- **Origin:** architecture.md §3
- **Category:** Backend | Architecture
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/api/routers/operations.py`
- **Current state:** `StorageService`, 1 preflight `storage.load_metadata` call.
- **Missing work:** Extract `OperationsService`, add factory, thin router.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `OperationsService` in `services/operations_service.py`
  - [ ] Factory in `dependencies.py`
  - [ ] Router thin

### DEBT-021 — Legacy aliases need planned migration
- **Origin:** architecture.md §3 / storage-contract-and-schema-tests spec
- **Category:** Backend | Data Migration
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** Multiple (`slug`, `provider`, `model`, `id`, `source` aliases throughout codebase)
- **Current state:** Canonical names defined (`source_key`, `source_novel_id`, `source_url`, `novel_id`, `chapter_id`, `paragraph_id`, `chunk_id`, `bundle_id`, `provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`, `credential_id`, `requesting_user_id`, `credential_owner_user_id`, `prompt_version`, `glossary_hash`). Legacy aliases still used in some code paths.
- **Missing work:** Systematic rename of all legacy aliases to canonical names in single change with all callers updated.
- **Reason deferred:** Large cross-cutting change; requires coordinated PR.
- **Risk:** Inconsistent naming causes bugs; CI guard only catches router imports.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All legacy aliases replaced with canonical names
  - [ ] No `id`, `source`, `provider`, `model`, `slug` as primary identifiers in new code
  - [ ] Tests pass

### DEBT-022 — Storage backward compatibility discipline
- **Origin:** architecture.md §3 / storage-contract-and-schema-tests spec
- **Category:** Storage | Data Migration
- **Priority:** Medium
- **Status:** Ongoing
- **Affected areas:** `backend/src/novelai/storage/`
- **Current state:** Loaders tolerate additive fields, legacy `raw/`/`translated/` fallback works, but no automated schema validation.
- **Missing work:** Add schema version checks, migration scripts for breaking changes, automated compatibility tests.
- **Reason deferred:** Ongoing discipline, not a one-time fix.
- **Risk:** Silent data corruption if schema assumptions violated.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Schema version field on all JSON families
  - [ ] Migration script template
  - [ ] Contract tests in `test_storage_contracts.py`

### DEBT-023 — Admin provider credential UI (env-based only)
- **Origin:** current_state.md / admin-user-management spec
- **Category:** Frontend | Feature
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:**
  - `frontend/app/(admin)/admin/settings/`
- **Current state:** Provider API keys only configurable via `.env` (`PROVIDER_GEMINI_API_KEY`). No UI to manage admin-owned credentials in DB (encrypted via `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`).
- **Missing work:** Build admin UI for credential CRUD, wire to encrypted DB storage.
- **Reason deferred:** Requires DB-backed credential storage (partially implemented) and UI.
- **Risk:** Operational burden; keys in `.env` not rotatable per-project.
- **Dependencies:** `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` setup
- **Completion criteria:**
  - [ ] Admin UI for credential list/create/edit/delete
  - [ ] Credentials encrypted at rest
  - [ ] Keys never returned to frontend (masked display only)

### DEBT-024 — SOURCE-PIPELINE-FIX-4: Novel status extraction issues
- **Origin:** current_state.md / crawl-fetch-observability spec
- **Category:** Backend | Sources
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/sources/generic.py`
  - `backend/src/novelai/sources/status.py`
  - `backend/src/novelai/sources/syosetu_ncode.py`
- **Current state:** `GenericSource` emits no `publication_status`; marker tuples have duplicates; Syosetu infotop failure silently swallowed.
- **Missing work:** Fix `GenericSource` to emit status; deduplicate markers; add error handling/logging for Syosetu infotop.
- **Reason deferred:** Requires source-specific fixes and testing against live sites.
- **Risk:** Incorrect novel status in catalog; silent failures hide source breakage.
- **Dependencies:** Source parser test fixtures
- **Completion criteria:**
  - [ ] `GenericSource` returns `publication_status`
  - [ ] Marker tuples deduplicated
  - [ ] Syosetu infotop errors logged and surfaced
  - [ ] Source contract tests pass

### DEBT-025 — SOURCE-PIPELINE-FIX-5: Storage safety gaps
- **Origin:** current_state.md / operational-safety-observability spec
- **Category:** Storage | Operations
- **Priority:** High
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/storage/runtime_contracts.py`
  - `backend/src/novelai/storage/traceability.py`
  - `backend/src/novelai/activity/queue.py`
- **Current state:** Fetch cache has no TTL (not in `cleanup_expired_runtime_data`); pipeline events append-only with no pruning; `prune_activity_log` implemented but never wired.
- **Missing work:** Add fetch cache TTL and cleanup; implement pipeline event pruning; wire `prune_activity_log` to scheduler.
- **Reason deferred:** Requires runtime data lifecycle design.
- **Risk:** Unbounded disk growth; stale cache serves stale content.
- **Dependencies:** Scheduler integration
- **Completion criteria:**
  - [ ] Fetch cache entries have TTL and are cleaned up
  - [ ] Pipeline events pruned by age/count
  - [ ] `prune_activity_log` runs on schedule
  - [ ] Disk usage stable under load

### DEBT-026 — Frontend lint not configured non-interactively
- **Origin:** architecture.md
- **Category:** Frontend | CI/CD
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `frontend/`
- **Current state:** No `eslint.config.mjs` exists; lint runs only interactively in IDE.
- **Missing work:** Add ESLint config, integrate into `ci.yml` frontend-check job.
- **Reason deferred:** Low priority vs backend CI.
- **Risk:** Code style drift; no automated frontend quality gate.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `eslint.config.mjs` with project rules
  - [ ] `npm run lint` passes in CI
  - [ ] `ci.yml` includes frontend lint step

### DEBT-027 — Backend package flattening deferred
- **Origin:** architecture.md
- **Category:** Backend | Architecture
- **Priority:** Low
- **Status:** Deferred
- **Affected areas:** `backend/src/novelai/`
- **Current state:** Package structure has `novelai/` root with submodules. Flattening would simplify imports but is cosmetic.
- **Missing work:** Flatten package structure if desired.
- **Reason deferred:** No functional benefit; risk of import breakage.
- **Risk:** None functional.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Decision made (flatten or keep)
  - [ ] If flatten: all imports updated, tests pass

### DEBT-028 — Source parser fixtures not exhaustive against live-site drift
- **Origin:** architecture.md
- **Category:** Testing | Sources
- **Priority:** Medium
- **Status:** Ongoing
- **Affected areas:** `backend/tests/fixtures/sources/`
- **Current state:** Fixtures exist for known sources but may not cover all HTML variations.
- **Missing work:** Periodically refresh fixtures against live sites; add regression tests for parsing changes.
- **Reason deferred:** Ongoing maintenance.
- **Risk:** Silent parsing failures when source sites change markup.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Fixture refresh process documented
  - [ ] Regression test for each source adapter

### DEBT-029 — TAXONOMY-5C: tag `name_ja` display
- **Origin:** current_state.md / taxonomy spec
- **Category:** Frontend
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** `frontend/components/public/`
- **Current state:** Japanese tag names stored in DB but not displayed in public UI.
- **Missing work:** Add `name_ja` display in tag badges/tooltips.
- **Reason deferred:** UI polish.
- **Risk:** None functional.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `name_ja` shown in public tag UI

### DEBT-030 — TAXONOMY-5D: public genre enrichment / label payload decision
- **Origin:** current_state.md / taxonomy spec
- **Category:** Frontend | API
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** `backend/src/novelai/api/routers/public.py`, `frontend/app/(public)/`
- **Current state:** Genre labels minimal; enrichment strategy undecided.
- **Missing work:** Decide on genre label payload (localized names, descriptions, icons) and implement.
- **Reason deferred:** Product decision needed.
- **Risk:** Inconsistent genre display.
- **Dependencies:** Product/design decision
- **Completion criteria:**
  - [ ] Genre label payload spec agreed
  - [ ] API returns enriched labels
  - [ ] Frontend renders them

### DEBT-031 — More examples for provider request records, chunk outputs, bundle lifecycle
- **Origin:** architecture.md / data-output-structure.md
- **Category:** Documentation
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** `docs/reference/data-output-structure.md`
- **Current state:** Examples exist but could be more comprehensive for runtime artifacts.
- **Missing work:** Add realistic examples for `provider_requests.json`, `chunks.json`, `chunk_attempts.json`, `bundles.json`, `outputs.json`.
- **Reason deferred:** Documentation polish.
- **Risk:** Harder to debug runtime issues.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Examples added for all runtime JSON families

### DEBT-032 — CI/CD still requires GitHub UI steps (manual workflow_dispatch)
- **Origin:** SPECS_COMPLETION / cicd-pipeline spec
- **Category:** CI/CD | Operations
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `.github/workflows/deploy.yml`
- **Current state:** Deploy workflow uses `workflow_dispatch` requiring manual trigger.
- **Missing work:** Add automatic deploy on tag push or main merge with environment protection rules.
- **Reason deferred:** Requires environment protection rule setup in GitHub UI.
- **Risk:** Manual deploy step is error-prone.
- **Dependencies:** GitHub Environments configured
- **Completion criteria:**
  - [ ] Deploy triggers automatically on version tag
  - [ ] Environment protection rules enforce approvals

### DEBT-033 — No scheduled export freshness check
- **Origin:** scheduled-export-freshness-check spec
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** New scheduler job needed
- **Current state:** Export freshness function exists but not scheduled.
- **Missing work:** Wire into scheduler (APScheduler or cron), define staleness threshold, notify admin.
- **Reason deferred:** Low priority.
- **Risk:** Stale exports served to readers.
- **Dependencies:** Scheduler infrastructure
- **Completion criteria:**
  - [ ] Scheduled job runs daily
  - [ ] Flags stale exports
  - [ ] Admin notification

### DEBT-034 — Pipeline events not recorded (causes test_integration.py flakiness)
- **Origin:** Pre-existing behavioral gap / translation-integration-test-suite spec
- **Category:** Backend | Testing
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:**
  - `backend/src/novelai/translation/pipeline/stages/translate.py`
  - `backend/src/novelai/storage/traceability.py`
- **Current state:** Pipeline events not consistently recorded; causes 3 flaky tests in `test_integration.py` that pass in isolation.
- **Missing work:** Ensure all pipeline stages emit traceability events; fix flaky tests.
- **Reason deferred:** Root cause in pipeline instrumentation.
- **Risk:** Flaky CI; incomplete observability.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All pipeline stages emit events
  - [ ] `test_integration.py` passes consistently
  - [ ] Events queryable via traceability API

### DEBT-035 — Windows file locking causes intermittent test hangs
- **Origin:** test_novel_orchestration_service.py
- **Category:** Testing | Platform
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:**
  - `backend/tests/test_novel_orchestration_service.py`
  - `backend/src/novelai/storage/service.py` (`_force_remove_tree`)
- **Current state:** Intermittent hangs on Windows due to file locking; `_force_remove_tree` exists but may need longer timeout/retry.
- **Missing work:** Increase retry timeout in `_force_remove_tree`; add Windows-specific test handling.
- **Reason deferred:** Windows-specific; low priority for Linux production.
- **Risk:** CI flakiness on Windows runners.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `_force_remove_tree` handles Windows locking reliably
  - [ ] Test passes consistently on Windows

### DEBT-036 — Scheduler runtime state persistence incomplete
- **Origin:** scheduler-runtime-state-persistence spec
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Partial
- **Affected areas:**
  - `backend/src/novelai/services/orchestration/translation.py`
  - `backend/src/novelai/storage/traceability.py`
- **Current state:** `model_states` persisted per-job via `storage.save_scheduler_state`, but not all scheduler state (cooldowns, exhaustion) fully captured.
- **Missing work:** Persist complete scheduler state (priority order, cooldown_until, exhausted_until, rpm/rpd counters).
- **Reason deferred:** Partial implementation in Phase 1.
- **Risk:** Scheduler loses state on restart; suboptimal model routing.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Full scheduler state persisted per job
  - [ ] State restored on job resume
  - [ ] Tests verify persistence/restore

### DEBT-037 — Public reader glossary annotations wiring incomplete
- **Origin:** public-reader-glossary-annotations-wiring spec
- **Category:** Frontend | Backend
- **Priority:** Medium
- **Status:** Partial
- **Affected areas:**
  - `backend/src/novelai/api/routers/public_chapter.py`
  - `frontend/components/public/glossary-annotation-highlighter.tsx`
- **Current state:** `select_public_terms` + `find_annotations` called in public chapter route, feature-flagged via `PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED`. Frontend component exists but may not be fully integrated in reader page.
- **Missing work:** Verify end-to-end integration; ensure annotations render in chapter reader.
- **Reason deferred:** Feature flag default `False`; needs UX validation.
- **Risk:** Feature exists but not user-visible.
- **Dependencies:** Frontend reader page integration
- **Completion criteria:**
  - [ ] Annotations visible in public chapter reader when enabled
  - [ ] Feature flag documented
  - [ ] E2E test covers annotation rendering

### DEBT-038 — Public reader SEO/discovery baseline
- **Origin:** public-reader-seo-discovery-baseline spec
- **Category:** Frontend | SEO
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** `frontend/app/(public)/`
- **Current state:** No sitemap, robots.txt, structured data, meta tags for public novels.
- **Missing work:** Implement SEO basics: sitemap.xml, robots.txt, JSON-LD structured data, Open Graph tags.
- **Reason deferred:** Post-MVP.
- **Risk:** Poor search visibility.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] `sitemap.xml` generated
  - [ ] `robots.txt` served
  - [ ] JSON-LD on novel/chapter pages
  - [ ] Open Graph tags

### DEBT-039 — Rate limit and abuse protection baseline
- **Origin:** rate-limit-and-abuse-protection-baseline spec
- **Category:** Backend | Security
- **Priority:** High
- **Status:** Partial
- **Affected areas:**
  - `backend/src/novelai/infrastructure/http/rate_limiter.py`
  - `backend/src/novelai/api/routers/dependencies.py`
- **Current state:** In-memory rate limiter implemented; Redis backend configurable via `WEB_RATE_LIMITER_BACKEND=redis` but not verified in multi-instance.
- **Missing work:** Verify Redis rate limiter works under load; add abuse detection (burst detection, IP blocking).
- **Reason deferred:** Requires multi-instance test environment.
- **Risk:** DoS vulnerability in production.
- **Dependencies:** Redis cluster
- **Completion criteria:**
  - [ ] Redis rate limiter verified under concurrent load
  - [ ] Abuse detection rules implemented
  - [ ] Admin UI for rate limit monitoring

### DEBT-040 — Metric dashboard baseline
- **Origin:** metric-dashboard-baseline spec
- **Category:** Observability
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** New Grafana/Prometheus setup or custom dashboard
- **Current state:** No metrics exposition or dashboard.
- **Missing work:** Add Prometheus metrics endpoint, configure Grafana dashboards for request latency, error rates, queue depth, translation throughput.
- **Reason deferred:** Requires monitoring stack.
- **Risk:** No production visibility.
- **Dependencies:** Prometheus/Grafana deployment
- **Completion criteria:**
  - [ ] `/metrics` endpoint exposes key metrics
  - [ ] Grafana dashboards provisioned
  - [ ] Alerts configured for critical thresholds

### DEBT-041 — Deep health readiness checks
- **Origin:** deep-health-readiness-checks spec
- **Category:** Backend | Observability
- **Priority:** High (part of DEBT-001)
- **Status:** Not started
- **Affected areas:** `backend/src/novelai/api/routers/health.py`
- **Current state:** Only basic `/api/health` exists.
- **Missing work:** Implement `/api/health/ready` with DB, storage, Redis, worker queue probes.
- **Dependencies:** DEBT-001
- **Completion criteria:** See DEBT-001

### DEBT-042 — Maintenance cron jobs
- **Origin:** maintenance-cron spec
- **Category:** Operations
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** New scheduler jobs
- **Current state:** No automated maintenance (cleanup, vacuum, index rebuild, backup verification).
- **Missing work:** Implement cron jobs for: `cleanup_expired_runtime_data` (14-day TTL), DB vacuum, backup verification, export freshness.
- **Reason deferred:** Requires scheduler infrastructure.
- **Risk:** Manual maintenance burden; runtime data accumulates.
- **Dependencies:** Scheduler infrastructure
- **Completion criteria:**
  - [ ] Daily cleanup job runs
  - [ ] Weekly vacuum job runs
  - [ ] Backup verification job runs
  - [ ] All jobs observable in admin UI

### DEBT-043 — Contact/support/legal pages
- **Origin:** contact-support-legal-pages spec
- **Category:** Frontend | Compliance
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** `frontend/app/(public)/`
- **Current state:** No contact, support, privacy, terms pages.
- **Missing work:** Add static pages with required legal content.
- **Reason deferred:** Pre-launch requirement.
- **Risk:** Legal non-compliance.
- **Dependencies:** Legal content
- **Completion criteria:**
  - [ ] `/contact`, `/privacy`, `/terms` pages exist
  - [ ] Content reviewed

### DEBT-044 — Analytics baseline
- **Origin:** analytics-baseline spec
- **Category:** Backend | Feature
- **Priority:** Low
- **Status:** Not started
- **Affected areas:** New module
- **Current state:** No analytics.
- **Missing work:** Implement event tracking (page views, reads, searches, signups), aggregation, admin dashboard.
- **Reason deferred:** Post-MVP.
- **Risk:** No product insights.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Event ingestion pipeline
  - [ ] Aggregation jobs
  - [ ] Admin dashboard

### DEBT-045 — Export manifest admin UI (already resolved per DEBT.md but verify)
- **Origin:** export-manifest-admin-ui spec
- **Category:** Frontend | Feature
- **Priority:** Medium
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `frontend/app/(admin)/admin/exports/page.tsx`
- **Current state:** Admin exports page with freshness badges, status, expandable rows implemented.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-046 — Frontend glossary annotation rendering (already resolved per DEBT.md but verify)
- **Origin:** frontend-glossary-annotation-rendering spec
- **Category:** Frontend | Feature
- **Priority:** Medium
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `frontend/components/public/glossary-annotation-highlighter.tsx`
- **Current state:** `GlossaryAnnotationHighlighter` component with tooltip rendering implemented.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-047 — Global PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED setting (already resolved)
- **Origin:** public-reader-glossary-annotations-wiring spec
- **Category:** Backend | Config
- **Priority:** Medium
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `backend/src/novelai/config/settings.py:206-210`
- **Current state:** Setting exists, default `False`.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-048 — Microservice Dockerfile rename (already resolved)
- **Origin:** microservice-split spec
- **Category:** CI/CD | Deployment
- **Priority:** High
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `deploy/admin.Dockerfile`
  - `deploy/reader.Dockerfile`
  - `deploy/frontend.Dockerfile`
  - `deploy/compose.yml`
  - `.github/workflows/ci.yml`
- **Current state:** All three Dockerfiles exist; compose and CI use new names.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-049 — Glossary diagnostics not wired into translate stage (already resolved)
- **Origin:** glossary-diagnostic-pipeline-wiring spec
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `backend/src/novelai/translation/pipeline/stages/translate.py:1037-1038`
- **Current state:** `normalize_glossary_diagnostics` called in TranslateStage.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-050 — Glossary diagnostics not aggregated in activity worker (already resolved)
- **Origin:** glossary-diagnostic-pipeline-wiring spec
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `backend/src/novelai/services/orchestration/worker.py:337-340`
- **Current state:** `aggregate_glossary_diagnostics` called in ActivityWorker.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-051 — Public glossary annotations not wired into reader API (already resolved)
- **Origin:** public-reader-glossary-annotations-wiring spec
- **Category:** Backend | Public API
- **Priority:** Medium
- **Status:** Resolved (verified in code)
- **Affected areas:**
  - `backend/src/novelai/api/routers/public_chapter.py:530-557`
- **Current state:** `select_public_terms` + `find_annotations` called in public chapter route, feature-flagged.
- **Missing work:** None.
- **Completion criteria:** Verified.

### DEBT-052 — Scheduler observability
- **Origin:** translation-scheduler-observability spec
- **Category:** Backend | Observability
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** New metrics/logging
- **Current state:** Scheduler state persisted but not exposed via metrics or admin UI.
- **Missing work:** Expose scheduler state (model availability, cooldowns, queue depth) via admin API and metrics.
- **Reason deferred:** Requires metrics infrastructure.
- **Risk:** Cannot debug scheduler decisions in production.
- **Dependencies:** DEBT-040 (metrics)
- **Completion criteria:**
  - [ ] Admin API endpoint for scheduler state
  - [ ] Metrics for scheduler decisions
  - [ ] Dashboard panel

### DEBT-053 — Translation QA hardening
- **Origin:** translation-qa-hardening spec
- **Category:** Backend | Translation
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `backend/src/novelai/translation/qa/`
- **Current state:** Basic QA checks exist; LLM QA disabled by default (`LLM_QA_ENABLED=false`).
- **Missing work:** Enable and tune LLM QA; add more heuristic checks; integrate QA failures into retry logic.
- **Reason deferred:** Requires LLM QA provider config and cost approval.
- **Risk:** Low-quality translations auto-activated.
- **Dependencies:** LLM QA provider setup
- **Completion criteria:**
  - [ ] LLM QA enabled and tuned
  - [ ] QA failures trigger retry/downgrade
  - [ ] Admin UI shows QA scores

### DEBT-073 — Glossary prompt injection test expects old prompt text
- **Origin:** Phase 1 (glossary-management-consolidation spec)
- **Category:** Testing
- **Priority:** Medium
- **Status:** Not started (newly discovered)
- **Affected areas:**
  - `backend/tests/test_glossary_prompt_injection.py:146`
- **Current state:** Test `test_canonical_term_and_translation_render_deterministically` expects old prompt text ("Use these approved translations consistently:") but implementation now uses "LOCKED (override any other translation):" and adds "The glossary is authoritative..." line.
- **Missing work:** Update test assertion to match current implementation, or revert implementation to match test (decide which is correct).
- **Reason deferred:** Discovered during documentation audit; not in original Phase 1 scope.
- **Risk:** Test failure blocks CI; prompt text drift undocumented.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Test passes
  - [ ] Prompt text documented in `docs/jp-en-prompt-quality-policy.md`
- **Validation commands:**
  - `python -m pytest backend/tests/test_glossary_prompt_injection.py::test_canonical_term_and_translation_render_deterministically -v`

---

## Cross-Cutting Architecture Debt

### DEBT-054 — Router layer violations (9 services to extract)
- **Origin:** architecture.md §3 / CI guard
- **Category:** Architecture
- **Priority:** High
- **Status:** Not started (9 services)
- **Affected areas:** All routers in `backend/src/novelai/api/routers/`
- **Current state:** 9 routers violate layer rules by importing `db.models`, `storage.service`, or `sources` directly. CI guard (`grep -rn "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --exclude="dependencies.py"`) will fail on any violation.
- **Missing work:** Extract 9 services (Auth, Library, GlossaryWorkflow, UserLibrary/Reading/Review, PublicCatalog, Editor, NovelRequest, Admin, Operations), add factories to `dependencies.py`, thin routers.
- **Reason deferred:** Large refactor; must be done atomically per service.
- **Risk:** CI failures; untestable routers; tight coupling.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All 9 services extracted
  - [ ] CI guard passes
  - [ ] All tests pass

---

## Test and Verification Debt

### DEBT-055 — CI-dependent test failures (Postgres required)
- **Origin:** Phase 0c / e2e-integration-testing spec
- **Category:** Testing | CI/CD
- **Priority:** Blocker
- **Status:** Blocked
- **Affected areas:** `backend/tests/test_web_api.py`, `backend/tests/test_integration.py`
- **Current state:** 12+ tests fail on CI due to missing Postgres; pass locally.
- **Missing work:** Add Postgres service to GitHub Actions or use testcontainers.
- **Dependencies:** GitHub Actions workflow change
- **Completion criteria:** See DEBT-003

### DEBT-056 — Flaky integration tests (pipeline events not recorded)
- **Origin:** translation-integration-test-suite spec
- **Category:** Testing
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `backend/tests/test_integration.py`
- **Current state:** 3 tests flaky (pass in isolation) due to missing pipeline events.
- **Missing work:** Fix pipeline event emission (DEBT-034) and stabilize tests.
- **Dependencies:** DEBT-034
- **Completion criteria:**
  - [ ] `test_integration.py` passes consistently

### DEBT-057 — Windows file locking in tests
- **Origin:** test_novel_orchestration_service.py
- **Category:** Testing | Platform
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `backend/tests/test_novel_orchestration_service.py`
- **Current state:** Intermittent hangs on Windows.
- **Missing work:** Fix `_force_remove_tree` retry logic.
- **Dependencies:** None
- **Completion criteria:** See DEBT-035

---

## Operational and Deployment Debt

### DEBT-058 — No scheduled backups (backup_manager exists but not wired)
- **Origin:** scheduled-backups-and-restore-drills spec
- **Category:** Operations | Data Integrity
- **Priority:** High
- **Status:** Partial
- **Affected areas:** `backend/src/novelai/services/backup_manager.py`
- **Current state:** Class implemented, no scheduler integration.
- **Missing work:** Wire to scheduler, configure retention, document restore.
- **Dependencies:** Production deployment
- **Completion criteria:** See DEBT-010

### DEBT-059 — No worker health endpoint
- **Origin:** current_state.md / operational-safety-observability spec
- **Category:** Backend | Observability
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `backend/src/novelai/services/orchestration/worker.py`
- **Current state:** In-process worker (`JOB_WORKER_ENABLED=true`) has no health endpoint.
- **Missing work:** Add `/api/health/worker` endpoint showing worker status, current job, queue depth.
- **Reason deferred:** Requires worker state exposure.
- **Risk:** Cannot monitor worker health in production.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Worker health endpoint implemented
  - [ ] Included in readiness probe (DEBT-001)

### DEBT-060 — No separate worker service in Docker Compose
- **Origin:** current_state.md / dockerize-application spec
- **Category:** Deployment
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `deploy/compose.yml`
- **Current state:** Worker runs in-process in backend (`JOB_WORKER_ENABLED=true`). No separate worker container.
- **Missing work:** Add `worker` service to compose.yml with own scaling.
- **Reason deferred:** In-process worker sufficient for low volume.
- **Risk:** Worker crashes take down API; no independent scaling.
- **Dependencies:** Redis/RQ for distributed queue
- **Completion criteria:**
  - [ ] `worker` service in compose.yml
  - [ ] Scales independently
  - [ ] Health check configured

### DEBT-061 — S3 storage backend not verified in production
- **Origin:** cloud-storage-s3 spec
- **Category:** Storage | Deployment
- **Priority:** Medium
- **Status:** Not started
- **Affected areas:** `backend/src/novelai/storage/s3_storage.py`
- **Current state:** S3 storage backend implemented (`STORAGE_BACKEND=s3`) but not tested in production-like environment.
- **Missing work:** Test with real S3/MinIO; verify multipart upload, presigned URLs, cleanup.
- **Reason deferred:** Requires S3 credentials and test bucket.
- **Risk:** Storage failures in production.
- **Dependencies:** S3-compatible storage
- **Completion criteria:**
  - [ ] Integration test with MinIO
  - [ ] Production smoke test

### DEBT-062 — Caddy TLS/automation not verified
- **Origin:** dockerize-application spec
- **Category:** Deployment | Security
- **Priority:** High
- **Status:** Not started
- **Affected areas:** `deploy/Caddyfile`, `deploy/compose.yml`
- **Current state:** Caddy configured for automatic HTTPS via Let's Encrypt but not tested with real domain.
- **Missing work:** Test with real domain; verify certificate renewal; configure OCSP stapling.
- **Reason deferred:** Requires real domain and DNS.
- **Risk:** TLS failures in production.
- **Dependencies:** Domain + DNS
- **Completion criteria:**
  - [ ] Valid cert issued for production domain
  - [ ] Auto-renewal verified
  - [ ] Security headers configured

---

## Documentation-Only Debt

### DEBT-063 — Architecture docs distinguish current vs planned
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/architecture/architecture.md`
- **Current state:** Architecture doc mixes implemented and planned architecture without clear distinction.
- **Missing work:** Add clear "Implemented" vs "Planned" markers; update module diagrams to match current code.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All sections labeled Implemented/Planned
  - [ ] Diagrams match actual code structure

### DEBT-064 — Frontend design doc reflects actual implementation
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/architecture/frontend-design.md`
- **Current state:** May document planned features as implemented.
- **Missing work:** Verify against actual frontend code; move unimplemented to DEBT.md.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All documented features exist in code
  - [ ] Unimplemented features moved to DEBT.md

### DEBT-065 — Public auth contract matches implementation
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/architecture/public-auth-contract.md`
- **Current state:** May document intended auth as enforced.
- **Missing work:** Verify against actual auth middleware, session handling, role checks.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Contract matches code behavior
  - [ ] Discrepancies documented as debt

### DEBT-066 — Storage contract matches implementation
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/storage-contract.md`, `docs/reference/data-output-structure.md`
- **Current state:** Generally accurate but may have drift.
- **Missing work:** Validate all paths, schemas, examples against code.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All documented paths exist
  - [ ] All schemas match code
  - [ ] Examples are valid

### DEBT-067 — Glossary system doc matches pipeline
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/glossary/glossary-system.md`
- **Current state:** Documents dual storage (file + DB) and sync bridge; verify all steps implemented.
- **Missing work:** Verify each pipeline step exists in code.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All documented flows implemented
  - [ ] Gaps moved to DEBT.md

### DEBT-068 — Prompt quality policy distinguishes policy vs implementation
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/jp-en-prompt-quality-policy.md`
- **Current state:** Documents policy well; may imply implementation completeness.
- **Missing work:** Add "Implementation Status" section per rule.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] Each policy rule marked Implemented/Partial/Not Implemented
  - [ ] Regression test coverage noted

### DEBT-069 — Environment docs match settings.py
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/environment.md`
- **Current state:** Comprehensive but may have drift from `settings.py`.
- **Missing work:** Diff against `settings.py`; add missing vars; remove obsolete.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] 1:1 mapping with `AppSettings` fields
  - [ ] No undocumented required vars

### DEBT-070 — CI/CD manual setup guide accurate
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/cicd-manual-setup.md`
- **Current state:** Documents manual steps; verify against actual workflow files.
- **Missing work:** Update for any workflow changes.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All manual steps still required
  - [ ] No steps automated that doc says manual

### DEBT-071 — Getting started guide commands work
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** High
- **Status:** In progress
- **Affected areas:** `docs/guides/GETTING_STARTED.md`
- **Current state:** Commands may have drift (e.g., `novelaibook` subcommands, Docker compose files).
- **Missing work:** Run all commands in clean environment; fix failures.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All commands execute successfully
  - [ ] Prerequisites accurate

### DEBT-072 — Python commands reference accurate
- **Origin:** This audit
- **Category:** Documentation
- **Priority:** Medium
- **Status:** In progress
- **Affected areas:** `docs/reference/python-commands.md`
- **Current state:** May reference old APIs.
- **Missing work:** Verify each command/API against current code.
- **Dependencies:** None
- **Completion criteria:**
  - [ ] All commands run
  - [ ] All APIs exist

---

## Resolved or Superseded Debt Archive

The following items were previously tracked but are now resolved or superseded:

- **DEBT-012 through DEBT-020 (router layer violations):** Superseded by DEBT-054 (consolidated entry)
- **DEBT-045, DEBT-046, DEBT-047, DEBT-048, DEBT-049, DEBT-050, DEBT-051:** Verified resolved in code
- **backend_layer_violation_debt.md:** Superseded by DEBT-054; archived
- **backend_god_file_debt.md:** All 6 god files split; archived
- **Phase 0a, 0c test fixes:** Verified resolved locally; CI verification pending (DEBT-004, DEBT-005)

---

## Validation Commands Summary

Run these to verify debt status:

```powershell
# Health probes
curl http://localhost:8000/api/health/live
curl http://localhost:8000/api/health/ready

# Circular import check
python -c "from novelai.api.routers import admin_glossary, admin_glossary_provider; print('OK')"

# Router layer guard (should pass when DEBT-054 done)
grep -rn "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --exclude="dependencies.py"

# Test suite (requires Postgres)
python -m pytest backend/tests/test_web_api.py -v
python -m pytest backend/tests/test_integration.py -v
python -m pytest backend/tests/test_crawl_resilience_contracts.py -v

# Frontend lint
cd frontend && npm run lint

# Type checks
python -m pyright
cd frontend && npm run typecheck

# Build verification
docker compose -f deploy/compose.yml build
```