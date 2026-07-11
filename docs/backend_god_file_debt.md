# Backend God File Split Debt

This document tracks the god files identified for splitting in the backend
reorganization. Each entry includes the current line count, the proposed split,
and the risk assessment.

## Status: Partially addressed

The following splits were completed:
- **1.** `operations.py` (748 L -> 370 L + helpers) -- `get_novel_translation_lock`,
  `ExportOperationResult`, `OperationError`, `require_novel_meta` extracted to
  `operations_helpers.py`.
- **2.** `translate.py` (1473 L -> 1130 L + 2 helper files) -- 20+ static/context
  helpers extracted to `translate_context_helpers.py` (context/extraction/prompt)
  and `translate_provider_call.py` (provider error mapping + audit records).
- **3.** `library.py` (1173 L -> 880 L + detail router) -- catalog projection,
  publish/unpublish, and health endpoints extracted to `library_detail.py`.
  `novels.py` updated to include both routers.

The remaining files:

### 4. `backend/src/novelai/api/routers/public.py` (1395 L)

**Concerns mixed:** Catalog browse, novel detail, chapter list, chapter read.

**Proposed split:**
- `public_catalog.py` -- catalog browse
- `public_novel.py` -- novel detail
- `public_chapter.py` -- chapter list + read

**Risk:** Medium. Clear endpoint boundaries, but shared helpers and
Pydantic models need careful extraction.

### 5. `backend/src/novelai/api/routers/admin_glossary.py` (2194 L)

**Concerns mixed:** CRUD, candidate import, apply preview/commit/rollback,
provider suggestions, suggestion review/accept/reject.

**Proposed split:**
- `admin_glossary.py` -- CRUD endpoints (target ~600 L)
- `admin_glossary_candidates.py` -- candidate import
- `admin_glossary_apply.py` -- apply preview/commit/rollback
- `admin_glossary_suggestions.py` -- suggestion review/accept/reject
- `admin_glossary_provider.py` -- provider suggestion flow

**Risk:** High. Many shared Pydantic models and helpers. Router registration
in `api/app.py` needs updating.

### 6. `backend/src/novelai/services/orchestration/translation.py` (2489 L)

**Concerns mixed:** Job lifecycle, chapter parallelism, scheduler dispatch,
glossary merge, post-process, metadata translation, lineage/delta computation.

**Proposed split:**
- `translation.py` -- core orchestration (target ~800 L)
- `translation_resume.py` -- resume/restart logic
- `translation_progress.py` -- progress recording
- `translation_metadata.py` -- metadata translation helpers
- `translation_lineage.py` -- lineage/delta computation

**Risk:** High. 60+ functions with subtle interdependencies. Each helper may
depend on others. Splitting requires careful extraction of shared state.

## Priority Order (remaining)

1. `public.py` (medium risk, ~880 L after removal of novelai_shared refs)
2. `admin_glossary.py` (high risk, many shared models)
3. `translation.py` (highest risk, most complex)
