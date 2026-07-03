# Tasks: Translation Resume Hardening

## Task List

- [x] 1. Add `TranslationInProgressError` to `errors.py`
  - [x] 1.1 Add `class TranslationInProgressError(RuntimeError): ...` to `backend/src/novelai/core/errors.py` (REQ-1.5)
  - [x] 1.2 Export it from `novelai.core.errors` public surface

- [x] 2. Add per-chapter translation lock
  - [x] 2.1 Add `_translation_locks: dict[str, asyncio.Lock] = {}` at module level in `backend/src/novelai/services/orchestration/translation.py` (REQ-1.1)
  - [x] 2.2 Add `_get_translation_lock(novel_id, chapter_id) -> asyncio.Lock` helper that creates or returns the lock for `f"{novel_id}:{chapter_id}"` (REQ-1.3)
  - [x] 2.3 In the chapter translation body (before checkpoint restore), acquire the lock with `await asyncio.wait_for(lock.acquire(), timeout=0.0)` (REQ-1.2)
  - [x] 2.4 Catch `asyncio.TimeoutError` and raise `TranslationInProgressError(f"Translation is already in progress for {novel_id}/{chapter_id}")` (REQ-1.4)
  - [x] 2.5 Wrap the chapter translation body in try/finally to ensure lock release on success and exception (REQ-1.2)

- [x] 3. Widen checkpoint restore condition
  - [x] 3.1 Change the restore condition in `orchestration/translation.py` from `if state_before and state_before.get("error_count", 0) > 0` to `if state_before is None or state_before.get("error_count", 0) > 0` (REQ-2.1)
  - [x] 3.2 Capture the boolean return value of `_restore_latest_checkpoint_for_resume` as `checkpoint_restored` (REQ-2.4)
  - [x] 3.3 Pass `checkpoint_restored` into the pipeline state metadata before calling `translate_chapter`: `state.metadata["checkpoint_restored"] = checkpoint_restored` (REQ-2.4)
  - [x] 3.4 Confirm that when neither checkpoint nor state exists, `checkpoint_restored` is `False` and no error is raised (REQ-2.3)

- [x] 4. Write cache-reuse contract tests
  - [x] 4.1 Create `backend/tests/test_translation_cache_contract.py` (REQ-3.1)
  - [x] 4.2 Write `test_cache_reuse_all_six_fields_match` — stored output returned when all six fields match (REQ-3.2)
  - [x] 4.3 Write `test_cache_miss_on_source_text_change` (REQ-3.3)
  - [x] 4.4 Write `test_cache_miss_on_prompt_version_change` (REQ-3.4)
  - [x] 4.5 Write `test_cache_miss_on_glossary_hash_change` (REQ-3.5)
  - [x] 4.6 Write `test_cache_miss_on_style_preset_change` (REQ-3.6)
  - [x] 4.7 Write `test_cache_miss_on_json_output_change` (REQ-3.7)
  - [x] 4.8 Write `test_cache_miss_on_consistency_mode_change` (REQ-3.8)
  - [x] 4.9 Write `test_force_retranslate_bypasses_cache` (REQ-3.9)

- [x] 5. Write checkpoint restore contract tests
  - [x] 5.1 Create `backend/tests/test_translation_resume_contract.py` (REQ-4.1)
  - [x] 5.2 Write `test_checkpoint_restore_on_error_count_gt_zero` (REQ-4.1)
  - [x] 5.3 Write `test_checkpoint_restore_on_missing_state` — new behavior (REQ-4.2)
  - [x] 5.4 Write `test_no_checkpoint_restore_on_clean_first_run` (REQ-4.3)
  - [x] 5.5 Write `test_checkpoint_restore_sets_metadata_flag` (REQ-4.4)
  - [x] 5.6 Write `test_restore_from_checkpoint_writes_all_three_artifacts` (REQ-4.5)
  - [x] 5.7 Write `test_restore_from_checkpoint_partial_checkpoint` (REQ-4.6)

- [x] 6. Write duplicate-run lock tests
  - [x] 6.1 Write `test_duplicate_run_raises_translation_in_progress_error` (REQ-5.1)
  - [x] 6.2 Write `test_sequential_runs_succeed` (REQ-5.2)
  - [x] 6.3 Write `test_different_chapters_do_not_block` (REQ-5.3)
  - [x] 6.4 Write `test_translation_in_progress_error_is_runtime_error` (REQ-5.4)

- [x] 7. Write `translation_run_id` and cross-run reuse tests
  - [x] 7.1 Write `test_translation_run_id_always_set` — assert `translation_run_id` is non-empty in context metadata (REQ-6.1)
  - [x] 7.2 Write `test_two_runs_produce_different_run_ids` (REQ-6.2)
  - [x] 7.3 Write `test_cross_run_reuse_when_six_fields_match` (REQ-7.2)
  - [x] 7.4 Write `test_no_cross_run_reuse_when_glossary_changed` (REQ-7.3)

- [x] 8. Verify, lint, and type-check
  - [x] 8.1 Run `pytest backend/tests/test_translation_cache_contract.py backend/tests/test_translation_resume_contract.py --tb=short -q` and confirm all pass
  - [x] 8.2 Run `ruff check backend/src/novelai/core/errors.py backend/src/novelai/services/orchestration/translation.py` and fix issues
  - [x] 8.3 Run `pyright backend/src/novelai/core/errors.py backend/src/novelai/services/orchestration/translation.py` and fix type errors
