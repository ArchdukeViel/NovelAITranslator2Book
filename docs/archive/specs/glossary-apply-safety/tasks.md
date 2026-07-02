# Tasks: Glossary Apply Safety and Reversibility

## Task List

- [x] 1. Add `GLOSSARY_APPLY` to `ChapterVersionKind` and update storage normalization
  - [x] 1.1 Add `GLOSSARY_APPLY = "glossary_apply"` to `ChapterVersionKind` enum in `backend/src/novelai/core/chapter_state.py` (REQ-7.1)
  - [x] 1.2 Update `_normalize_version_kind` in `backend/src/novelai/storage/translations.py` to recognize and return `"glossary_apply"` (REQ-7.2)
  - [x] 1.3 Confirm `list_translated_chapter_versions` returns `version_kind` from the version dict — it should already; verify and adjust if not (REQ-7.3)

- [x] 2. Add `batch_id` support to translation storage
  - [x] 2.1 Add optional `batch_id: str | None = None` parameter to `save_translated_chapter` and store it in the version dict when provided (REQ-3.2)
  - [x] 2.2 Add `batch_id` to `_append_edit_history` and store it in the edit history entry when provided (REQ-3.3)
  - [x] 2.3 Include `batch_id` in the dict returned by `load_translated_chapter` (default `None`) (REQ-3.2)
  - [x] 2.4 Include `batch_id` in each version dict returned by `list_translated_chapter_versions` (REQ-3.2)

- [x] 3. Add `delta_fraction` to `GlossaryApplyPreviewService`
  - [x] 3.1 Add `delta_fraction: float` field to the per-chapter preview result model in `backend/src/novelai/services/glossary_apply_preview.py` (REQ-5.1)
  - [x] 3.2 Implement delta fraction computation: simulate replacements on active translation text, compute `abs(len(simulated) - len(original)) / max(1, len(original))` (REQ-5.1)
  - [x] 3.3 Add `max_delta_fraction: float = 0.15` parameter to `ApplyPreviewServiceRequest` (REQ-5.3)
  - [x] 3.4 Pre-classify chapters as `blocked` with `block_reason = "delta_fraction_exceeded"` when `delta_fraction > max_delta_fraction` (REQ-5.3)
  - [x] 3.5 Update `GlossaryApplyPreviewResponse` schema in `admin_glossary.py` to expose `delta_fraction` per chapter (REQ-5.2)

- [x] 4. Create `services/glossary_rewrite.py` — safe text replacement engine
  - [x] 4.1 Create `backend/src/novelai/services/glossary_rewrite.py` with `apply_glossary_replacements(text, replacements, *, protect_markers=True) -> tuple[str, int]` (REQ-2.3, REQ-2.2)
  - [x] 4.2 Implement marker span detection for `[CHAPTER ...]` and `[P pNNNN]` patterns (REQ-2.3)
  - [x] 4.3 Implement right-to-left replacement application with committed-span tracking to prevent double-replacement (REQ-2.3)
  - [x] 4.4 Implement longest-match priority: sort candidates by span length descending before position sort (REQ-8.6)
  - [x] 4.5 Skip any replacement whose span overlaps a marker span or committed span (REQ-2.3, REQ-8.7)

- [x] 5. Add `apply_glossary_to_chapters` orchestration function
  - [x] 5.1 Add `apply_glossary_to_chapters` async function to `backend/src/novelai/services/orchestration/glossary.py` with the signature defined in the design (REQ-6.1, REQ-6.2)
  - [x] 5.2 Implement preview phase: call `GlossaryApplyPreviewService.preview()` with `max_delta_fraction` (REQ-6.3)
  - [x] 5.3 Implement dry_run early return: return result with per-chapter delta_fraction, no storage writes (REQ-1.3)
  - [x] 5.4 Implement apply loop: skip blocked chapters always; skip needs_review unless force_needs_review; call `apply_glossary_replacements` from `glossary_rewrite.py` (REQ-1.4, REQ-2.1)
  - [x] 5.5 Add final delta_fraction re-check after actual replacement (protect against preview/apply drift) (REQ-2.1)
  - [x] 5.6 Call `save_translated_chapter` with `version_kind=GLOSSARY_APPLY`, `glossary_revision`, `batch_id`, `base_version_id` for each successfully applied chapter (REQ-3.1, REQ-3.2)
  - [x] 5.7 Wrap each chapter write in try/except; on I/O exception mark chapter `failed`, continue loop (REQ-2.4)
  - [x] 5.8 Return `ApplyGlossaryResult` dataclass with per-chapter results and summary counts (REQ-1.5)
  - [x] 5.9 Define `ApplyGlossaryResult` and `ChapterApplyResult` dataclasses (in `orchestration/glossary.py` or a new `services/glossary_apply_models.py`) (REQ-1.5)
  - [x] 5.10 Bind `apply_glossary_to_chapters` onto `NovelOrchestrationService` following existing binding patterns (REQ-6.4)

- [x] 6. Add commit endpoint to `admin_glossary.py`
  - [x] 6.1 Define `GlossaryApplyCommitRequest` Pydantic model (REQ-1.2)
  - [x] 6.2 Define `GlossaryApplyCommitResponse` and `GlossaryApplyChapterResult` Pydantic models (REQ-1.5)
  - [x] 6.3 Add `POST /novels/{novel_id}/glossary/apply/commit` endpoint calling `orchestration.apply_glossary_to_chapters` (REQ-1.1)
  - [x] 6.4 Return HTTP 200 with partial-failure info in the response body; do not raise HTTP errors for individual chapter failures (REQ-2.4)

- [x] 7. Add rollback endpoints
  - [x] 7.1 Add `POST /novels/{novel_id}/chapters/{chapter_id}/versions/{version_id}/activate` endpoint (owner-only) in admin chapter router (REQ-4.1, REQ-4.2)
  - [x] 7.2 Define `ChapterVersionActivateResponse` Pydantic model with `chapter_id`, `activated_version_id`, `previous_version_id`, `activated_at` (REQ-4.3)
  - [x] 7.3 Return HTTP 404 when `version_id` is not found in the chapter bundle (REQ-4.4)
  - [x] 7.4 Define `GlossaryApplyRollbackRequest` (field: `batch_id: str`) and `GlossaryApplyRollbackResponse` models (REQ-4.5, REQ-4.6)
  - [x] 7.5 Add `POST /novels/{novel_id}/glossary/apply/rollback` endpoint: iterate chapters, find versions with matching `batch_id`, activate their `base_version_id` (REQ-4.5)
  - [x] 7.6 Return per-chapter result with `status = "success" | "failed" | "skipped_not_found"` (REQ-4.6)

- [x] 8. Write tests
  - [x] 8.1 Create `backend/tests/test_glossary_apply_engine.py`
  - [x] 8.2 Write apply engine tests: all-safe, mixed safe/needs_review (default skip), force_needs_review, blocked-never-written, delta_fraction_guard, partial_failure, dry_run_no_writes, batch_id_stored (REQ-8.2)
  - [x] 8.3 Write rollback tests: single chapter rollback, 404 for unknown version, bulk rollback by batch_id, skips chapters without batch_id (REQ-8.3)
  - [x] 8.4 Write preview delta_fraction tests: field present, chapter over threshold pre-blocked (REQ-8.4)
  - [x] 8.5 Write version metadata assertion tests: applied version carries glossary_revision, base_version_id, batch_id, kind=glossary_apply (REQ-8.5)
  - [x] 8.6 Write overlap tests: longer match wins, no double-replacement (REQ-8.6)
  - [x] 8.7 Write marker protection tests: [P pNNNN] and [CHAPTER ...] markers never altered (REQ-8.7)
  - [x] 8.8 Run `pytest backend/tests/test_glossary_apply_engine.py --tb=short -q` and confirm all pass
  - [x] 8.9 Run `ruff check backend/src/novelai/services/glossary_rewrite.py backend/src/novelai/services/orchestration/glossary.py` and fix any issues
  - [x] 8.10 Run `pyright backend/src/novelai/services/glossary_rewrite.py backend/src/novelai/services/orchestration/glossary.py` and fix type errors
