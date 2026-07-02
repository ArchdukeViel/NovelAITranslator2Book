# Requirements: Translation Resume Hardening

## Introduction

The translation pipeline already has strong infrastructure for resumability: chunk-output records keyed by six cache fields (source text hash, prompt version, glossary hash, style preset, json_output, consistency_mode), per-chapter checkpoints that snapshot raw chapter + translated chapter + chapter state, and a `_restore_latest_checkpoint_for_resume` path that fires when `error_count > 0`. The scaffolding is good. What it lacks is a locked-down, contract-tested guarantee.

Three concrete gaps remain. First, **duplicate-run prevention**: there is no guard against two concurrent translation calls on the same `(novel_id, chapter_id)` pair. The crawl path has a per-novel `asyncio.Lock`, but the translation path does not. Two racing translate calls can produce interleaved chunk writes and corrupt the active version. Second, **checkpoint restore reliability**: restore fires only when `error_count > 0` in the persisted chapter state. If a process crash left `error_count = 0` (state was not yet written, or the checkpoint pre-dates any state), the restore is silently skipped. Third, **cache-reuse contract test coverage**: the six-field reuse check (`source_text_hash`, `prompt_version`, `glossary_hash`, `style_preset`, `json_output`, `consistency_mode`) is designed to be deterministic but lacks explicit contract tests proving that changing any one field forces re-translation, and that matching all six fields reuses the stored output.

This spec locks those contracts down with code and tests. It does not change the pipeline architecture.

## Requirements

### REQ-1: Per-Chapter Translation Lock (Duplicate-Run Prevention)

Concurrent translation calls on the same chapter must be serialized.

- REQ-1.1: A module-level `_translation_locks: dict[str, asyncio.Lock]` dict must be added to `backend/src/novelai/services/orchestration/translation.py`, keyed by `f"{novel_id}:{chapter_id}"`.
- REQ-1.2: The per-chapter lock must be acquired before the chapter translation body (before checkpoint restore and before `storage.create_checkpoint("before_translate")`) and released after the chapter translation completes (success or exception).
- REQ-1.3: The lock must be created on first access and reused on subsequent calls. Lock creation must be thread-safe (using a module-level `asyncio.Lock` as a creation guard, or simply relying on the GIL for dict creation — either is acceptable).
- REQ-1.4: A second concurrent call that fails to acquire the lock within a configurable timeout (default 0 seconds — immediate non-blocking check) must raise a `TranslationInProgressError` with the message `"Translation is already in progress for {novel_id}/{chapter_id}"`.
- REQ-1.5: `TranslationInProgressError` must be a subclass of `RuntimeError` defined in `backend/src/novelai/core/errors.py`.
- REQ-1.6: The lock dict must be module-level so it is shared across all callers within the same process.

### REQ-2: Checkpoint Restore Also Fires on Missing State

Checkpoint restore must fire not only when `error_count > 0` but also when chapter state is entirely absent (indicating a crash before state was written).

- REQ-2.1: The restore condition in `orchestration/translation.py` must be: `if state_before is None or state_before.get("error_count", 0) > 0`. A `None` chapter state (no state file) is treated identically to a failed state.
- REQ-2.2: When a checkpoint exists but no chapter state exists, restore must proceed normally.
- REQ-2.3: When neither checkpoint nor chapter state exists (clean first run), restore is silently skipped as before.
- REQ-2.4: The restore result (`True` / `False`) must be stored in `context.metadata["checkpoint_restored"]` so downstream stages and audit tools can observe whether a restore occurred.

### REQ-3: Cache-Reuse Contract Tests

The six-field chunk-output reuse check must be covered by deterministic contract tests.

- REQ-3.1: A new test file `backend/tests/test_translation_cache_contract.py` must be created.
- REQ-3.2: `test_cache_reuse_all_six_fields_match` — all six fields match a stored output record → stored output is returned, no provider call made.
- REQ-3.3: `test_cache_miss_on_source_text_change` — `source_text_hash` differs → re-translation triggered.
- REQ-3.4: `test_cache_miss_on_prompt_version_change` — `prompt_version` differs → re-translation triggered.
- REQ-3.5: `test_cache_miss_on_glossary_hash_change` — `glossary_hash` differs → re-translation triggered.
- REQ-3.6: `test_cache_miss_on_style_preset_change` — `style_preset` differs → re-translation triggered.
- REQ-3.7: `test_cache_miss_on_json_output_change` — `json_output` flips → re-translation triggered.
- REQ-3.8: `test_cache_miss_on_consistency_mode_change` — `consistency_mode` flips → re-translation triggered.
- REQ-3.9: `test_force_retranslate_bypasses_cache` — `force_retranslate=True` → stored output ignored regardless of all fields matching.

### REQ-4: Checkpoint Restore Contract Tests

- REQ-4.1: `test_checkpoint_restore_on_error_count_gt_zero` — chapter state has `error_count=1` → `_restore_latest_checkpoint_for_resume` is called.
- REQ-4.2: `test_checkpoint_restore_on_missing_state` — `load_chapter_state` returns `None` → `_restore_latest_checkpoint_for_resume` is called (new behavior from REQ-2.1).
- REQ-4.3: `test_no_checkpoint_restore_on_clean_first_run` — chapter state is `None` but no checkpoints exist → restore is skipped, no error.
- REQ-4.4: `test_checkpoint_restore_sets_metadata_flag` — after restore, `context.metadata["checkpoint_restored"]` is `True`.
- REQ-4.5: `test_restore_from_checkpoint_writes_all_three_artifacts` — `restore_from_checkpoint` with a checkpoint containing raw chapter + translated chapter + chapter state → all three `save_*` methods are called.
- REQ-4.6: `test_restore_from_checkpoint_partial_checkpoint` — checkpoint contains only raw chapter (translated chapter absent) → only `save_chapter` is called, no error.

### REQ-5: Duplicate-Run Lock Contract Tests

- REQ-5.1: `test_duplicate_run_raises_translation_in_progress_error` — two concurrent async calls on the same `(novel_id, chapter_id)` → second call raises `TranslationInProgressError`.
- REQ-5.2: `test_sequential_runs_succeed` — first call completes; second call on the same chapter then succeeds (lock released).
- REQ-5.3: `test_different_chapters_do_not_block` — concurrent calls on `chapter_id="ch1"` and `chapter_id="ch2"` of the same novel both proceed in parallel.
- REQ-5.4: `test_translation_in_progress_error_is_runtime_error` — assert `issubclass(TranslationInProgressError, RuntimeError)`.

### REQ-6: `translation_run_id` Traceability in Chunk Records

Chunk records must carry a `translation_run_id` that is stable within a run and distinct across runs.

- REQ-6.1: `_save_chunk_records` already writes `translation_run_id` from `context.metadata`. This must be confirmed to be non-None for every run. When `translation_run_id` is absent or empty in `context.metadata`, `TranslationService.translate_chapter` already generates `f"translation_run_{uuid4().hex}"`. The test `test_translation_run_id_always_set` must assert this guarantee.
- REQ-6.2: Two separate calls to `translate_chapter` for the same chapter (without an explicit `job_id`) must produce different `translation_run_id` values.
- REQ-6.3: A resume of the same `translation_run_id` (via explicit `job_id` matching) must reuse chunk states from the prior run via `_load_persisted_chunk_states`.

### REQ-7: Cross-Run Reuse Contract

Chunk outputs from a previous run must be reusable when all six cache fields match, even across runs.

- REQ-7.1: `_load_existing_chunk_output` currently falls back to a chapter-scoped query (no `translation_run_id` filter) when no explicit run ID is provided. This cross-run reuse must be tested and confirmed as intentional behavior.
- REQ-7.2: `test_cross_run_reuse_when_six_fields_match` — prior run stored an output; new run (different `translation_run_id`) has the same six fields → prior output is reused, no provider call.
- REQ-7.3: `test_no_cross_run_reuse_when_glossary_changed` — prior run stored an output; new run has a different `glossary_hash` → output not reused.

## Non-Goals

- This spec does not change the pipeline stages, prompt construction, or provider interface.
- This spec does not add distributed locking (Redis-based or DB-based). The `asyncio.Lock` is in-process only; multi-process / multi-worker duplicate-run prevention is a separate infrastructure concern.
- This spec does not change the `TranslationCache` (on-disk JSON) key schema. That is owned by `prompt-translation-hardening`.
- This spec does not add chapter-to-chapter continuity memory. That is a future feature.
- This spec does not change checkpoint file format.
