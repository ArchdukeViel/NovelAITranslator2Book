# Technical Debt Register

Single source of truth for all outstanding technical debt.
Consolidated from `SPECS_COMPLETION.md`, `architecture.md`, `backend_layer_violation_debt.md`, `current_state.md`.
Last updated: 2026-07-11

---

## P0 — Correctness/Security

| # | Debt | Location | Source |
|---|------|----------|--------|
| 1 | PDF exporter stubbed but not registered | `bootstrap.py` | SPECS_COMPLETION |
| 2 | No health checks with real probes | `/api/health` | SPECS_COMPLETION |

---

## P1 — Maintainability/Reliability

### Layer Violations (routers import db/storage directly)

| # | Router | Violations | Fix |
|---|--------|------------|-----|
| 3 | `library.py` | 3 `db.models` imports, 1 `sources.status`, 1 `StorageService`, ~30 direct storage calls | Extract `LibraryService` |
| 4 | `admin_glossary.py` | 6 `db.models.glossary` symbols, `Novel`, 2 `providers.*` imports, `StorageService`, 6 storage calls | Extract `GlossaryWorkflowService` |
| 5 | `auth.py` | 3 `db.models.users` symbols, ~25 `session.*` calls | Extract `AuthService` |
| 6 | `user_data.py` | 7 `db.models` symbols, 27 CRUD operations | Extract `UserLibraryService`/`ReadingService`/`ReviewService` |
| 7 | `public.py` | 3 `db.models` symbols, `sources.status`, `StorageService`, ~18 storage calls | Extract `PublicCatalogService` |
| 8 | `editor.py` | 1 inline `db.models.novel`, `StorageService`, 12 storage calls | Extract `EditorService` |
| 9 | `requests.py` | 2 `db.models` symbols, full CRUD in router | Extract `NovelRequestService` |
| 10 | `admin.py` | `StorageService`, 3 preflight `storage.load_metadata` calls | Move to `AdminService` |
| 11 | `operations.py` | `StorageService`, 1 preflight `storage.load_metadata` call | Move to `OperationsService` |

### Spec / Feature Debt

| # | Debt | Location | Source |
|---|------|----------|--------|
| 12 | Scheduler runtime state not persisted | `TranslationScheduler._runtime_states` | SPECS_COMPLETION |
| 13 | Glossary diagnostics not wired into translate stage | `TranslateStage` | SPECS_COMPLETION |
| 14 | Glossary diagnostics not aggregated in activity worker | `ActivityWorker` | SPECS_COMPLETION |
| 15 | Public glossary annotations not wired into reader API | `public_chapter.py` | SPECS_COMPLETION |
| 16 | No export manifest UI | Admin frontend | SPECS_COMPLETION |
| 17 | Frontend glossary annotation rendering not built | Frontend | SPECS_COMPLETION |
| 18 | No global `PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED` setting | `settings.py` | SPECS_COMPLETION |
| 19 | Microservice Dockerfile rename pending | `deploy/backend.Dockerfile` → `admin.Dockerfile` | SPECS_COMPLETION |
| 20 | CI/CD dual-service build not implemented | `.github/workflows/ci.yml` | SPECS_COMPLETION |
| 21 | No admin user management endpoints | `admin.py` | SPECS_COMPLETION |
| 22 | No notification system | Missing | SPECS_COMPLETION |
| 23 | No scheduled backups | `backup_manager.py` | SPECS_COMPLETION |
| 24 | No analytics | Missing | SPECS_COMPLETION |
| 25 | Legacy aliases need planned migration | Multiple | architecture.md |
| 26 | Storage backward compatibility needs continued discipline | Storage layer | architecture.md |
| 27 | Admin provider credential UI (env-based only) | Admin frontend | current_state.md |
| 28 | SOURCE-PIPELINE-FIX-4: novel status extraction | Source pipeline | current_state.md |
| 29 | SOURCE-PIPELINE-FIX-5: storage safety (cache TTL, metadata backup, event pruning) | Source pipeline | current_state.md |

---

## P2 — Cleanup/Cosmetic

| # | Debt | Location | Source |
|---|------|----------|--------|
| 30 | CI/CD still requires GitHub UI steps | GitHub | SPECS_COMPLETION |
| 31 | No scheduled export freshness check | Missing | SPECS_COMPLETION |
| 32 | Frontend lint not configured non-interactively | Frontend | architecture.md |
| 33 | Backend package flattening deferred | Backend | architecture.md |
| 34 | Source parser fixtures not exhaustive against live-site drift | Tests | architecture.md |
| 35 | TAXONOMY-5C: tag `name_ja` display | Frontend | current_state.md |
| 36 | TAXONOMY-5D: public genre enrichment / label payload decision | Frontend/API | current_state.md |
| 37 | More examples for provider request records, chunk outputs, bundle lifecycle | Docs | architecture.md |

---

## Deferred Test Debt

These require a populated novel library + psycopg2 to fix:

| # | Test File | Failures | Root Cause |
|---|-----------|----------|------------|
| 38 | `test_catalog_service.py` | 32 errors | Stale temp dir `pytest-3` |
| 39 | `test_crawl_resilience_contracts.py` | 18 failures | Novel library cleared |
| 40 | `test_storage_backends.py` | 2 errors | Same temp dir issue |
| 41 | `test_onboarding_state_machine.py` | 3 failures | Storage preconditions |
| 42 | `test_document_import_orchestration.py` | 3 failures | Missing metadata + psycopg2 |
| 43 | `test_chapter_parallelization.py` | 1 failure | Metadata not found |
| 44 | `test_translation_qa.py` | 1 failure | Metadata not found |
| 45 | `test_web_api.py` (auth routes) | 6 failures | psycopg2 missing |
| 46 | `test_integration.py` | 5 failures | Pipeline events not recorded |
| 47 | `test_novel_orchestration_service.py` | 1 failure | DB session required |

### Pre-existing Test Debt

| # | Test File | Failures | Root Cause |
|---|-----------|----------|------------|
| 48 | `test_web_api.py` (ListDetail/Admin/Activity) | 6 failures | DB-dependent |
| 49 | `test_glossary_sync_bridge.py` | 2 failures | Sync bridge revision increment |
| 50 | `test_frontend_api_contract.py` | 1 failure | `fetch()` not `apiFetch` |
| 51 | `test_integration.py` | 5 failures | Pipeline events not in trace |
| 52 | `test_novel_orchestration_service.py` | Intermittent hang | Windows file locking |

---

## Upcoming Features (not debt)

See `docs/current_state.md` → **Next** for the feature roadmap (S3 boundary, deployment, Gemini monitoring, public UX items, etc.)
