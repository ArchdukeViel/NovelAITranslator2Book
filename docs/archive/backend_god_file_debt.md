# Backend God File Split Debt

This document tracks the god files identified for splitting in the backend
reorganization. Each entry includes the current line count, the proposed split,
and the risk assessment.

## Status: Complete

All 6 god files have been split. Each split follows the re-export pattern:
the core file keeps shared models/helpers and re-exports functions from the
split files for backward compatibility.

### Completed splits

- **1.** `operations.py` (689 L -> 667 L + helpers) -- `get_novel_translation_lock`,
  `ExportOperationResult`, `OperationError`, `require_novel_meta` extracted to
  `operations_helpers.py` (32 L). Minimal extraction (~22 lines); further thinning
  is optional.
- **2.** `translate.py` (1392 L -> 993 L + 3 helper files) -- context/extraction/prompt
  helpers in `translate_result_assembly.py` (230 L), provider error mapping + audit
  records in `translate_provider_call.py` (119 L), cache lookup + chunk persistence
  in `translate_cache_lookup.py` (268 L). Matches the original 4-file plan.
- **3.** `library.py` (1027 L -> 383 L + 2 routers) -- catalog projection + publish/
  unpublish + health in `library_detail.py` (268 L); source-metadata, chapters,
  reader, progress, checkpoints in `library_actions.py` (383 L). Matches original
  3-file plan.
- **4.** `public.py` (1215 L -> 385 L + 3 routers) -- catalog browse + genres in
  `public_catalog.py` (332 L); novel detail + chapter list in `public_novel.py`
  (65 L); chapter reader + tags search + reader text helpers in `public_chapter.py`
  (509 L). Matches the 3-file plan.
- **5.** `admin_glossary.py` (1941 L -> 1321 L + 4 routers) -- CRUD endpoints +
  shared models/helpers stay in core; candidate import in
  `admin_glossary_candidates.py` (118 L); apply preview/commit/rollback +
  chapter version activate in `admin_glossary_apply.py` (280 L); provider
  suggestion preview/apply + adapter in `admin_glossary_provider.py` (180 L);
  suggestion review/accept/reject in `admin_glossary_suggestions.py` (135 L).
  Matches the 5-file plan.
- **6.** `translation.py` (2259 L -> 1053 L + 4 split files) -- core orchestration
  stays; resume/restart logic in `translation_resume.py` (86 L); progress
  aggregation in `translation_progress.py` (62 L); metadata translation +
  estimation in `translation_metadata.py` (622 L); lineage + delta retranslation
  in `translation_lineage.py` (596 L). Matches the 5-file plan.

### Summary

| File | Before | After | Split files |
|---|---|---|---|
| `operations.py` | 689 | 667 | `operations_helpers.py` (32) |
| `translate.py` (stage) | 1392 | 993 | `translate_cache_lookup.py` (268), `translate_provider_call.py` (119), `translate_result_assembly.py` (230) |
| `library.py` | 1027 | 383 | `library_detail.py` (268), `library_actions.py` (383) |
| `public.py` | 1215 | 385 | `public_catalog.py` (332), `public_novel.py` (65), `public_chapter.py` (509) |
| `admin_glossary.py` | 1941 | 1321 | `admin_glossary_candidates.py` (118), `admin_glossary_apply.py` (280), `admin_glossary_provider.py` (180), `admin_glossary_suggestions.py` (135) |
| `translation.py` | 2259 | 1053 | `translation_metadata.py` (622), `translation_lineage.py` (596), `translation_resume.py` (86), `translation_progress.py` (62) |

### Notes

- All splits use the re-export pattern: core files keep shared models/helpers
  and re-export functions from split files. This keeps existing imports
  working without changes to callers.
- Layer violations (DB/storage calls in routers) are tracked separately in
  `docs/backend_layer_violation_debt.md`. The file splits do not fix layer
  violations — they only divide the files.
