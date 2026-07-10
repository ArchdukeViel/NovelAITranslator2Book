# Backend God File Split Debt

This document tracks the god files identified for splitting in the backend
reorganization. Each entry includes the current line count, the proposed split,
and the risk assessment.

## Status: Deferred

These splits were identified during the backend audit but deferred due to
scope and risk. Each requires deep understanding of the codebase and careful
extraction of shared helpers, Pydantic models, and router registrations.

## Files

### 1. `backend/src/novelai/services/orchestration/translation.py` (2489 L)

**Concerns mixed:** Job lifecycle, chapter parallelism, scheduler dispatch,
glossary merge, post-process, metadata translation, lineage/delta computation.

**Proposed split:**
- `translation.py` — core orchestration (target ~800 L)
- `translation_resume.py` — resume/restart logic
- `translation_progress.py` — progress recording
- `translation_metadata.py` — metadata translation helpers
- `translation_lineage.py` — lineage/delta computation

**Risk:** High. 60+ functions with subtle interdependencies. Each helper may
depend on others. Splitting requires careful extraction of shared state.

### 2. `backend/src/novelai/api/routers/admin_glossary.py` (2194 L)

**Concerns mixed:** CRUD, candidate import, apply preview/commit/rollback,
provider suggestions, suggestion review/accept/reject.

**Proposed split:**
- `admin_glossary.py` — CRUD endpoints (target ~600 L)
- `admin_glossary_candidates.py` — candidate import
- `admin_glossary_apply.py` — apply preview/commit/rollback
- `admin_glossary_suggestions.py` — suggestion review/accept/reject
- `admin_glossary_provider.py` — provider suggestion flow

**Risk:** High. Many shared Pydantic models and helpers. Router registration
in `api/app.py` needs updating.

### 3. `backend/src/novelai/translation/pipeline/stages/translate.py` (1473 L)

**Concerns mixed:** Cache lookup, provider call, retry/backoff, result assembly.

**Proposed split:**
- `translate.py` — orchestrator (target ~400 L)
- `translate_cache_lookup.py`
- `translate_provider_call.py`
- `translate_result_assembly.py`

**Risk:** Medium. Clear logical boundaries, but pipeline stage interface
must be preserved.

### 4. `backend/src/novelai/api/routers/public.py` (1395 L)

**Concerns mixed:** Catalog browse, novel detail, chapter list, chapter read.

**Proposed split:**
- `public_catalog.py` — catalog browse
- `public_novel.py` — novel detail
- `public_chapter.py` — chapter list + read

**Risk:** Medium. Clear endpoint boundaries, but shared helpers and
Pydantic models need careful extraction.

### 5. `backend/src/novelai/api/routers/library.py` (1173 L)

**Concerns mixed:** Admin library listing, multiple endpoint groups.

**Proposed split:**
- `library.py` — core listing (target ~400 L)
- `library_detail.py` — detail endpoints
- `library_actions.py` — action endpoints

**Risk:** Medium. Similar to public.py.

### 6. `backend/src/novelai/services/orchestration/operations.py` (748 L)

**Concerns mixed:** Operations service with repeated helpers.

**Proposed split:**
- `operations.py` — core (target ~400 L)
- `operations_helpers.py` — extracted helpers

**Risk:** Low. Architecture doc already started this thinning; it grew back.
Continue the extraction.

## Recommendation

Do these splits as separate PRs, one file at a time, with full test
verification after each. Estimated effort: 1-2 days per file.

## Priority Order

1. `operations.py` (lowest risk, smallest)
2. `translate.py` (clear boundaries)
3. `library.py` (medium risk)
4. `public.py` (medium risk)
5. `admin_glossary.py` (high risk, many shared models)
6. `translation.py` (highest risk, most complex)
