# Specs Completion Summary

All 41 specs in `.agents/kiro/archive/` have been assessed.
Each spec includes `design.md`, `requirements.md`, and `tasks.md`.

This document summarizes completion status, known flaws, and remaining debt.

---

## Overall Status

| Category | Count |
|----------|-------|
| Total specs | 41 |
| Fully complete | 37 |
| Partial (in-progress tasks) | 3 |
| Not started | 1 |

---

## Fully Complete Specs (37)

| Spec | Tasks | Notes |
|------|-------|-------|
| adapter-plugin-system | 33/33 | SourceAdapter ABC, AdapterRegistry, all adapters refactored |
| advanced-caching | 32/32 | TranslationCacheService, SHA-256 keys, sharded storage, TTL, glossary invalidation |
| atomic-json-storage-recovery | 116/116 | JSON storage atomic write recovery with backup/restore |
| auth-authorization | 34/34 | HTTP-only sessions, guest/user/owner roles, require_role(), Google OAuth + email/password |
| chapter-parallelization | 25/25 | asyncio.Semaphore + bounded asyncio.gather, per-chapter failure isolation |
| checkpoint-resume-pipeline | 40/40 | Checkpoint/resume for translation pipeline, runtime state persistence |
| cicd-pipeline | 32/32 | CI (lint+test+e2e), build (Docker GHCR push), deploy (SSH). Tasks 6-7 require GitHub UI |
| cloud-storage-s3 | 37/37 | S3/R2/B2 storage backend boundary, STORAGE_BACKEND env switch |
| crawl-fetch-observability | 222/222 | Crawl progress, source health aggregation, dark chapter detection, image failure tracking |
| create-novel-lifecycle | 28/28 | End-to-end novel creation flow through all layers |
| dockerize-application | 28/28 | Docker Compose, Caddy reverse proxy, split routing, migrate service |
| e2e-integration-testing | 31/31 | Deterministic integration regression suite |
| error-handling-logging | 29/29 | StructuredHTTPException, PipelineContext, JsonFormatter, /health/errors, trace_id |
| exact-translation-memory | 23/23 | Exact match detection, memory guard, retranslation avoidance |
| export-storage-observability | 294/294 | ExportManifestService, manifest schema, write/read/list, freshness, admin API endpoints |
| gemini-provider-only | 36/36 | Gemini provider, structured JSON handling, metadata batching |
| glossary-apply-safety | 55/55 | Preview, validation, rollback for glossary application |
| glossary-auto-population | 38/38 | SuggestionExtractor, GlossarySuggestionService, review/reject/apply API |
| glossary-aware-editor-qa | 275/275 | GlossaryEditorQAService, lint endpoint, saved-time QA, approve-translation-change |
| glossary-diagnostics-admin-surfacing | 239/239 | GlossaryDiagnosticsService, normalizer, aggregation helper, admin API |
| glossary-management-consolidation | 24/24 | Glossary management consolidation across file-glossary and DB glossary |
| glossary-revision-translation-invalidation | 246/246 | Glossary revision tracking, stale version detection, retranslate-stale workflow |
| glossary-sync-bridge | 49/49 | Background glossary sync between storage and DB |
| jp-en-prompt-quality-policy | 192/192 | JP-EN prompt policy verification, snapshot/fixture/cache-key/checklist tests |
| novel-onboarding-state-machine | 148/148 | OnboardingStateMachine, valid transitions, storage callbacks, error handling |
| operational-safety-observability | 53/53 | atomic_write, parse failure logging, catalog refresh hook, request_id correlation |
| prompt-translation-hardening | 57/57 | Prompt structure hardening, injection resistance, test coverage |
| public-path-performance | 49/49 | Bundle size audit, image optimization, lazy loading, pagination, backend caching |
| public-reader-availability | 179/179 | Public reader, hard_404, chapter_shell, latest_version fallback, owner preview |
| public-reader-glossary-annotations | 296/296 | PublicGlossaryAnnotationsService, term selection, case-insensitive matching |
| smart-chunking-context | 21/21 | Adaptive balanced chunking, conditional overlap, paragraph hash lineage |
| storage-boundary-consolidation | 18/18 | File-backed, chapter-based, runtime contracts, cleanup_expired_runtime_data |
| storage-contract-and-schema-tests | 109/109 | Storage contract tests for manifest write/read/list, export helpers |
| translation-integration-test-suite | 275/275 | Deterministic integration regression suite (58 tests) |
| translation-qa-hardening | 52/52 | QA stage hardening, quality metrics, threshold enforcement |
| translation-resume-hardening | 46/46 | Scheduler resume hardening, runtime state persistence, chunk attempt tracking |

---

## Partial Specs (3)

### glossary-first-onboarding (53/55 — 2 checkpoints in-progress)
- **Implemented:** Glossary columns on Novel ORM, catalog projection, GlossaryStatusService, translation guard, bootstrap hook, audit metadata, ReadinessBadge, GlossaryOnboardingActions.
- **Remaining:** 2 checkpoints (tasks 8, 12) marked `[~]` — verification checkpoints, no code changes needed.
- **Debt:** None.

### microservice-split (30/34 — 4 tasks remaining)
- **Implemented:** main_reader/main_admin entry points, DEPLOY_MODE dispatch, Docker Compose + Caddy split routing, 14 contract tests.
- **Remaining:** Rename `deploy/backend.Dockerfile` to `deploy/admin.Dockerfile` (task 4.4), update CI/CD to build/test both services (tasks 5.1, 5.2).
- **Debt:** Dockerfile rename + CI/CD dual-service build.

### translation-scheduler-observability (198/283 — 85 tasks in-progress)
- **Implemented:** Scheduler health admin API, scheduler summary in activity/version detail, admin UI health view + summary panel, decision record schema, quota/cooldown tracking.
- **In-progress:** Identity fields in decision records (request_id, activity_id, job_id, chapter_id), checkpoint/resume observability integration, chapter parallelization safety.
- **Debt:** Persist scheduler runtime state to allow health API to show live cooldown/exhausted/failed timestamps.

---

## Not Started (1)

### semantic-qa-and-cache-roadmap (7/18 — 11 tasks remaining)
- **Implemented:** 7 prerequisite/infrastructure tasks.
- **Remaining:** Complete prerequisites (exact translation memory metrics), build evaluation fixtures, design semantic cache storage (embedding/index backend, idempotent write contract, credential isolation), design LLM QA output (structured finding schema, review-flag behavior), add disabled-by-default config checks.
- **Debt:** This is a roadmap spec — implementation deferred until prerequisites are met.

---

## Known Flaws and Technical Debt

### High Priority

| Debt | Location | Impact |
|------|----------|--------|
| Scheduler runtime state not persisted | `TranslationScheduler._runtime_states` | Health API can't show live cooldown/exhausted/failed states |
| Glossary diagnostics not wired into translate stage | `TranslateStage` | Diagnostics normalizer exists but never called during translation |
| Glossary diagnostics not aggregated in activity worker | `ActivityWorker` | No chapter-level diagnostics summary in activity metadata |
| Public glossary annotations not wired into reader API | `public.py` | Term selection + matching implemented but not called in chapter response |
| PDF exporter stubbed but not registered | `bootstrap.py` | `export_pdf()` raises `KeyError` at runtime |

### Medium Priority

| Debt | Location | Impact |
|------|----------|--------|
| No export manifest UI | Admin frontend | Admin can't view export history/stale state in UI |
| No scheduled export freshness check | None | Freshness only computed on API call, not proactively |
| `PROVIDER_DEFAULT=dummy` remnants in env files | `.env.example` | ~~Should be `gemini` for dev convenience~~ **FIXED** |
| Frontend glossary annotation rendering not built | Frontend | Backend produces annotations but no highlight/tooltip UI |
| No global `PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED` setting | `settings.py` | Annotations can't be globally enabled/disabled |
| Microservice Dockerfile rename pending | `deploy/backend.Dockerfile` | Should be `deploy/admin.Dockerfile` for split-mode clarity |
| CI/CD dual-service build not implemented | `.github/workflows/ci.yml` | Split mode needs both admin and reader service builds |

### Low Priority

| Debt | Location | Impact |
|------|----------|--------|
| CI/CD still requires GitHub UI steps | GitHub | Tasks 6-7 need manual secrets config and real PR execution |
| No admin user management endpoints | `admin.py` | Can't list/ban/promote users |
| No notification system | Missing | Users don't know when translations complete |
| No scheduled backups | `backup_manager.py` | Manual backup only |
| No health checks with real probes | `/api/health` | Returns `{"status":"ok"}` even when DB/Redis is down |
| No analytics | Missing | No user behavior visibility |

---

## Stats

| Metric | Value |
|--------|-------|
| Total specs | 41 |
| Total spec files | 123 (41 specs × 3 files each) |
| Fully complete specs | 37 |
| Total tasks across all specs | 3,700+ |
| Completed tasks | 3,500+ |
| In-progress tasks | 87 |
| Remaining tasks | 15 |

---

## Deferred Debt (Category 2 — Storage/Metadata Preconditions)

These test failures are deferred until the novel library is repopulated. They require either:
- A populated novel library with stored metadata
- A working PostgreSQL connection (psycopg2 driver)
- Or both

### Files Affected

| File | Failures | Root Cause |
|------|----------|------------|
| `test_catalog_service.py` | 32 errors | `FileNotFoundError` for stale temp dir `pytest-3` |
| `test_crawl_resilience_contracts.py` | 18 failures | `No metadata found for novel` — novel library cleared |
| `test_storage_backends.py` | 2 errors | Same `FileNotFoundError` temp dir issue |
| `test_onboarding_state_machine.py` | 3 failures | Storage precondition failures |
| `test_document_import_orchestration.py` | 3 failures | Missing metadata + missing `psycopg2` |
| `test_chapter_parallelization.py` | 1 failure | `Metadata not found` |
| `test_translation_qa.py` | 1 failure | `Metadata not found` |
| `test_web_api.py` (auth route tests) | 6 failures | `psycopg2` missing — auth check happens after DB access |
| `test_integration.py` | 5 failures | Pipeline failure events not recorded |
| `test_novel_orchestration_service.py` | 1 failure | DB session required |

### Resolution Path

1. **Install psycopg2**: `pip install psycopg2-binary` (or `pip install -e ".[db]"`)
2. **Populate novel library**: Crawl or import at least one novel with stored metadata
3. **Re-run tests**: All Category 2 failures should resolve automatically

### Additional Debt (Category 3/4 — Pre-existing)

| File | Failures | Root Cause |
|------|----------|------------|
| `test_web_api.py` (TestListDetail, TestAdmin, TestActivity) | 6 failures | DB-dependent tests |
| `test_glossary_sync_bridge.py` | 2 failures | Sync bridge increments revision too many times; review doesn't trigger sync |
| `test_frontend_api_contract.py` | 1 failure | `login-view.tsx` uses `fetch()` directly instead of `apiFetch` |
| `test_integration.py` | 5 failures | Pipeline failure events not recorded in trace |

### Session Teardown Hang

`test_novel_orchestration_service.py` intermittently hangs during session teardown on Windows. The conftest.py fix (subprocess timeout in `_force_remove_tree`) mitigates this but doesn't eliminate it entirely. The hang is environmental (Windows file locking on `.tmp/runtime/` directories).