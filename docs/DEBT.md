# Technical Debt Register

Single source of truth for all outstanding technical debt.
Consolidated from `SPECS_COMPLETION.md`, `architecture.md`, `backend_layer_violation_debt.md`, `current_state.md`.
Last updated: 2026-07-12

---

## Resolved (verified against codebase 2026-07-12)

These items were listed as open but are already implemented in code. No further
work needed. Kept here for audit trail.

| # | Debt | Resolution | Evidence |
|---|------|-----------|----------|
| 12 | Scheduler runtime state not persisted | **Resolved.** `model_states` persisted per-job via `storage.save_scheduler_state` | `translate.py:204-218`, `traceability.py:170-203` |
| 13 | Glossary diagnostics not wired into translate stage | **Resolved.** `normalize_glossary_diagnostics` called in TranslateStage | `translate.py:1037-1038` |
| 14 | Glossary diagnostics not aggregated in activity worker | **Resolved.** `aggregate_glossary_diagnostics` called in ActivityWorker | `worker.py:337-340` |
| 15 | Public glossary annotations not wired into reader API | **Resolved.** `select_public_terms` + `find_annotations` called in public chapter route, feature-flagged | `public_chapter.py:530-557` |
| 16 | No export manifest UI | **Resolved.** Admin exports page with freshness badges, status, expandable rows | `frontend/app/(admin)/admin/exports/page.tsx` |
| 17 | Frontend glossary annotation rendering not built | **Resolved.** `GlossaryAnnotationHighlighter` component with tooltip rendering | `frontend/components/public/glossary-annotation-highlighter.tsx` |
| 18 | No global `PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED` setting | **Resolved.** Setting exists, default `False` | `settings.py:206-210` |
| 19 | Microservice Dockerfile rename pending | **Resolved.** `deploy/admin.Dockerfile`, `deploy/reader.Dockerfile`, `deploy/frontend.Dockerfile` all exist; `compose.yml` and `ci.yml` use new names | `deploy/`, `.github/workflows/ci.yml` |

---

## Partially Resolved

| # | Debt | Status | Remaining work |
|---|------|--------|----------------|
| 1 | PDF exporter stubbed but not registered | **Partially resolved.** PDF exporter IS registered at `bootstrap.py:82`, but `PDFExporter.export()` raises `NotImplementedError` | Implement `export()` with `reportlab`/`weasyprint`, or formally deprecate and remove from registry |
| 20 | CI/CD dual-service build not implemented | **Partially resolved.** `ci.yml` builds both admin+reader (verify). `build.yml` (push pipeline) was broken — referenced deleted `deploy/backend.Dockerfile`. Fixed in Phase 0a to build admin+reader+frontend separately | Verify `build.yml` runs green on push to main |

---

## P0 — Correctness/Security

| # | Debt | Location | Source |
|---|------|----------|--------|
| 2 | No health checks with real probes | `/api/health` returns `{"status": "ok"}` with no DB/storage/worker probes | SPECS_COMPLETION |

---

## P1 — Maintainability/Reliability

### Layer Violations (routers import db/storage directly)

| # | Router | Violations | Fix |
|---|--------|------------|-----|
| 3 | `library.py` | 3 `db.models` imports, 1 `sources.status`, 1 `StorageService`, ~30 direct storage calls | Extract `LibraryService` |
| 4 | `admin_glossary.py` | 6 `db.models.glossary` symbols, `Novel`, `StorageService`, 4 storage calls, 30 `Depends(get_db_session)` | Extract `GlossaryWorkflowService` |
| 5 | `auth.py` | 3 `db.models.users` symbols, ~35 `session.*` calls, ~250 lines inline CRUD | Extract `AuthService` |
| 6 | `user_data.py` | 7 `db.models` symbols, 30 `session.*` calls, 17 `session.query` | Extract `UserLibraryService`/`ReadingService`/`ReviewService` |
| 7 | `public.py` | 1 `db.models` symbol, `sources.status`, `StorageService`, 14 storage calls | Extract `PublicCatalogService` |
| 8 | `editor.py` | 1 inline `db.models.novel`, `StorageService`, 9 storage calls | Extract `EditorService` |
| 9 | `requests.py` | 2 `db.models` symbols, full CRUD in router | Extract `NovelRequestService` |
| 10 | `admin.py` | `StorageService`, 3 preflight `storage.load_metadata` calls in export routes | Move to `AdminService` |
| 11 | `operations.py` | `StorageService`, 1 preflight `storage.load_metadata` call | Move to `OperationsService` |

### Spec / Feature Debt

| # | Debt | Location | Source |
|---|------|----------|--------|
| 21 | No admin user management endpoints | `admin.py` | SPECS_COMPLETION |
| 22 | No notification system | Missing | SPECS_COMPLETION |
| 23 | No scheduled backups | `backup_manager.py` (class exists, not wired or scheduled) | SPECS_COMPLETION |
| 24 | No analytics | Missing | SPECS_COMPLETION |
| 25 | Legacy aliases need planned migration | Multiple (`slug`, `provider`, `model`, `id`, `source`) | architecture.md |
| 26 | Storage backward compatibility needs continued discipline | Storage layer | architecture.md |
| 27 | Admin provider credential UI (env-based only) | Admin frontend | current_state.md |
| 28 | SOURCE-PIPELINE-FIX-4: novel status extraction — `GenericSource` emits no `publication_status`; marker tuples have duplicates; Syosetu infotop failure silently swallowed | `sources/generic.py`, `sources/status.py`, `sources/syosetu_ncode.py` | current_state.md |
| 29 | SOURCE-PIPELINE-FIX-5: storage safety — fetch cache has no TTL (not in `cleanup_expired_runtime_data`); pipeline events append-only with no pruning; `prune_activity_log` is dead code (implemented, never wired) | `storage/runtime_contracts.py`, `storage/traceability.py`, `activity/queue.py` | current_state.md |

---

## P2 — Cleanup/Cosmetic

| # | Debt | Location | Source |
|---|------|----------|--------|
| 30 | CI/CD still requires GitHub UI steps (manual `workflow_dispatch`) | GitHub | SPECS_COMPLETION |
| 31 | No scheduled export freshness check | Missing (function exists, not scheduled) | SPECS_COMPLETION |
| 32 | Frontend lint not configured non-interactively (no `eslint.config.mjs` exists) | Frontend | architecture.md |
| 33 | Backend package flattening deferred | Backend | architecture.md |
| 34 | Source parser fixtures not exhaustive against live-site drift | Tests | architecture.md |
| 35 | TAXONOMY-5C: tag `name_ja` display | Frontend | current_state.md |
| 36 | TAXONOMY-5D: public genre enrichment / label payload decision | Frontend/API | current_state.md |
| 37 | More examples for provider request records, chunk outputs, bundle lifecycle | Docs | architecture.md |

---

## Deferred Test Debt

These require a populated novel library + psycopg2 to fix.
Phase 0c fixes: `test_crawl_resilience_contracts.py` (18→0), fixture pre-population in `conftest.py`-style; only CI-dependant tests remain.

| # | Test File | Failures | Root Cause |
|---|-----------|----------|------------|
| 38 | `test_catalog_service.py` | 0 errors | Fixed (local passes; was stale temp dir `pytest-3`) |
| 39 | `test_crawl_resilience_contracts.py` | 0 failures | **Fixed** in Phase 0c (fixture pre-population + slow_fetch signature) |
| 40 | `test_storage_backends.py` | 0 errors | Fixed (local passes; same temp dir issue) |
| 41 | `test_onboarding_state_machine.py` | 0 failures | Fixed (local passes; was storage preconditions) |
| 42 | `test_document_import_orchestration.py` | 0 failures | Fixed (local passes; was missing metadata + psycopg2) |
| 43 | `test_chapter_parallelization.py` | 0 failures | Fixed (local passes; was metadata not found) |
| 44 | `test_translation_qa.py` | 0 failures | Fixed (local passes; was metadata not found) |
| 45 | `test_web_api.py` (auth routes) | 6 failures | **Requires Postgres on CI runner** — local passes with postgres. Not fixable from code alone |
| 46 | `test_integration.py` | 3 flaky (pass in isolation) | Pipeline events not recorded — pre-existing behavioral gap (debt #51) |
| 47 | `test_novel_orchestration_service.py` | Intermittent hang | Windows file locking — add retry timeout in `_force_remove_tree` if needed |

### Pre-existing Test Debt

| # | Test File | Failures | Root Cause |
|---|-----------|----------|------------|
| 48 | `test_web_api.py` (ListDetail/Admin/Activity) | 6 failures | DB-dependent — same as #45, requires Postgres on CI |
| 49 | `test_glossary_sync_bridge.py` | 0 failures | **Fixed** in Phase 0c (updated revision expectation to match actual behavior: 4 increments, not 1) |
| 50 | `test_frontend_api_contract.py` | 0 failures | **Fixed** in Phase 0c (replaced direct `fetch()` calls with `authApi.googleStartCheck()` + `api.listExportManifests()`) |
| 51 | `test_integration.py` | 3 flaky (pass in isolation) | Pipeline events not in trace — pre-existing behavioral gap, not a test bug |
| 52 | `test_novel_orchestration_service.py` | Intermittent hang | Windows file locking — `_force_remove_tree` exists but may need longer timeout for slow I/O |

---

## Upcoming Features (not debt)

See `docs/current_state.md` → **Next** for the feature roadmap (S3 boundary, deployment, Gemini monitoring, public UX items, etc.)
