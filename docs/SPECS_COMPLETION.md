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

See consolidated register: [`docs/DEBT.md`](DEBT.md).

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

## Deferred Test Debt

See consolidated register: [`docs/DEBT.md`](DEBT.md) — deferred test debt section.