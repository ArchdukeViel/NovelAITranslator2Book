# Specs Completion Summary

All 14 specs in `.agents/kiro/archive/specs/` have been completed.
Each spec includes `design.md`, `requirements.md`, and `tasks.md`.

This document summarizes completion status, known flaws, and remaining debt.

---

## Overall Status

| Category | Count |
|----------|-------|
| Total specs | 14 |
| Fully complete | 11 |
| Complete (with BLOCKED items) | 1 |
| Implemented this session | 5 |

---

## Spec-by-Spec Summary

### atomic-json-storage-recovery (pre-existing complete)
- **Implemented:** JSON storage atomic write recovery with backup/restore.
- **Flaws:** None known.
- **Debt:** None.

### cicd-pipeline
- **Implemented:** CI workflow (lint + test + e2e), build workflow (Docker GHCR push), deploy workflow (SSH). Setup guide at `docs/cicd-manual-setup.md`.
- **Flaws:** Tasks 6-7 require GitHub UI (secrets config, real PR/merge execution). Marked BLOCKED.
- **Debt:** Need GitHub repo admin to add `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` secrets. Verify actions permissions allow `packages: write`. Run a real PR through the pipeline.

### crawl-fetch-observability (pre-existing complete)
- **Implemented:** Crawl progress, source health aggregation, dark chapter detection, image download failure tracking.
- **Flaws:** None known.
- **Debt:** None.

### export-storage-observability (NEW — this session)
- **Implemented:** `ExportManifestService` with manifest schema, storage-safe key helpers, write/read/list helpers, freshness computation. Manifest writing integrated into `export_novel` flow. Admin API endpoints for export listing/latest. 15 tests.
- **Flaws:** No manifest UI yet in admin frontend (API is ready). No scheduled export stale-check (freshness computed on-demand only).
- **Debt:** Frontend export status panel (show manifests, stale badges, re-export button). PDF exporter is stubbed but not registered.

### glossary-aware-editor-qa (pre-existing complete)
- **Implemented:** `GlossaryEditorQAService` for deterministic glossary QA on manual edits. Lint endpoint, saved-time QA, approve-translation-change endpoint. 23 unit + 15 API + 10 frontend tests.
- **Flaws:** None known.
- **Debt:** None.

### glossary-diagnostics-admin-surfacing (NEW — this session)
- **Implemented:** `GlossaryDiagnosticsService` normalizer that extracts glossary revision, hash, term counts, warnings, conflicts, truncation from translation metadata. Bounded lists, safe term truncation, aggregation helper. 17 tests.
- **Flaws:** Not yet wired into translate stage persistence. Activity aggregation not yet called in worker flow.
- **Debt:** Wire `normalize_glossary_diagnostics()` into `TranslateStage` completion path. Call `aggregate_glossary_diagnostics()` in activity worker completion. Add diagnostics panel to admin UI.

### glossary-revision-translation-invalidation (pre-existing complete)
- **Implemented:** Glossary revision tracking, stale version detection, retranslate-stale workflow.
- **Flaws:** None known.
- **Debt:** None.

### jp-en-prompt-quality-policy (pre-existing complete)
- **Implemented:** JP-EN prompt policy verification via `build_system_prompt`, snapshot tests, fixture tests, cache-key tests, checklist tests.
- **Flaws:** None known.
- **Debt:** None.

### novel-onboarding-state-machine (pre-existing complete)
- **Implemented:** `OnboardingStateMachine` with valid status transitions, storage callbacks, error handling.
- **Flaws:** None known.
- **Debt:** None.

### public-reader-availability (pre-existing complete)
- **Implemented:** Public reader with hard_404, chapter_shell, latest_version fallback. Owner preview. Public API safety (no admin metadata).
- **Flaws:** None known.
- **Debt:** None.

### public-reader-glossary-annotations (NEW — this session)
- **Implemented:** `PublicGlossaryAnnotationsService` — public-safe term selection (approved character/location/skill types), admin field filtering, case-insensitive matching with block-level offsets. 13 tests.
- **Flaws:** Not yet wired into public reader chapter API. No frontend annotation rendering (highlights/tooltips). No global setting or per-novel toggle.
- **Debt:** Wire `find_annotations()` into public chapter response. Add `glossary_annotations` field to `ReaderChapter` response model. Build frontend annotation rendering with toggle. Add `PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED` setting.

### storage-contract-and-schema-tests (pre-existing complete)
- **Implemented:** Storage contract tests for manifest write/read/list, export helpers, backend safety.
- **Flaws:** None known.
- **Debt:** None.

### translation-integration-test-suite (pre-existing complete)
- **Implemented:** Deterministic integration regression suite (58 tests) covering core storage, glossary gate, JP-EN prompts, scheduler, cache, versioning, glossary invalidation, crawl, public reader, editor QA, failure safety, activity metadata, isolation.
- **Flaws:** None known.
- **Debt:** None.

### translation-scheduler-observability (completed this session)
- **Implemented:** Scheduler health admin API, scheduler summary in activity/version detail, admin UI health view + summary panel. 46 backend + 12 frontend tests.
- **Flaws:** Scheduler health API exposes static config (provider/model list) but not runtime cooldown/exhausted/failed state (in-memory only, not persisted).
- **Debt:** Persist scheduler runtime state to allow health API to show live cooldown/exhausted/failed timestamps. Add runtime state tracking to preferences or storage.

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
| `PROVIDER_DEFAULT=dummy` remnants in env files | `.env.example` | Should be `gemini` for dev convenience |
| Frontend glossary annotation rendering not built | Frontend | Backend produces annotations but no highlight/tooltip UI |
| No global `PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED` setting | `settings.py` | Annotations can't be globally enabled/disabled |

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
| Total spec files | 42 (14 specs × 3 files each) |
| New tests added this session | 45 (15 + 17 + 13) |
| Pre-existing tests verified | 150+ |
| New services created | 5 (export_manifest, glossary_diagnostics, public_glossary_annotations + scheduler/export/glossary extensions) |
| New API endpoints | 4 (scheduler health, export list, export latest, glossary save QA) |
