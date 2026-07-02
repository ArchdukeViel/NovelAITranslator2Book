# Design: Translation Resume Hardening

## Overview

Three targeted changes to existing files, plus contract tests. No new modules, no schema changes, no pipeline stage changes. The changes are: add a per-chapter lock dict to the translation orchestration loop, widen the checkpoint restore condition, and set `context.metadata["checkpoint_restored"]`. The rest of the spec is test coverage proving the existing contracts hold.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/core/errors.py` | Add `TranslationInProgressError` |
| `backend/src/novelai/services/orchestration/translation.py` | Add `_translation_locks` dict; add lock acquisition; widen restore condition; set `checkpoint_restored` metadata |
| `backend/tests/test_translation_cache_contract.py` | New — cache reuse contract tests |
| `backend/tests/test_translation_resume_contract.py` | New — checkpoint restore and duplicate-run tests |

### Files Not Touched

- `translation/pipeline/stages/translate.py` — `_load_existing_chunk_output` is unchanged; tests verify its existing behavior
- `storage/jobs.py` — checkpoint restore/create functions unchanged
- `translation/service.py` — `translate_chapter` unchanged
- `translation_cache.py` — unchanged (owned by `prompt-translation-hardening`)

## Component Design

### 1. `TranslationInProgressError` in `errors.py`

```python
class TranslationInProgressError(RuntimeError):
    """Raised when a translation job is already running for the given chapter."""
```

### 2. Per-Chapter Lock in `orchestration/translation.py`

At module level:
```python
import asyncio
_translation_locks: dict[str, asyncio.Lock] = {}
```

Helper function:
```python
def _get_translation_lock(novel_id: str, chapter_id: str) -> asyncio.Lock:
    key = f"{novel_id}:{chapter_id}"
    if key not in _translation_locks:
        _translation_locks[key] = asyncio.Lock()
    return _translation_locks[key]
```

In the chapter translation loop (inside `translate_chapters` or the single-chapter translate body, before checkpoint restore):
```python
lock = _get_translation_lock(novel_id, chapter_id)
if not await asyncio.wait_for(asyncio.shield(lock.acquire()), timeout=0) if not lock.locked() else False:
    raise TranslationInProgressError(
        f"Translation is already in progress for {novel_id}/{chapter_id}"
    )
```

Simpler implementation using `lock.locked()` check + immediate acquire attempt:
```python
lock = _get_translation_lock(novel_id, chapter_id)
acquired = lock.locked() is False and lock._locked is False  # not reliable cross-version

# Cleanest approach: try_acquire with timeout=0
try:
    acquired = await asyncio.wait_for(lock.acquire(), timeout=0.0)
except asyncio.TimeoutError:
    raise TranslationInProgressError(
        f"Translation is already in progress for {novel_id}/{chapter_id}"
    )
try:
    # ... chapter translation body ...
finally:
    lock.release()
```

This is the canonical pattern: `wait_for(lock.acquire(), timeout=0.0)` raises `TimeoutError` when the lock is held, which we convert to `TranslationInProgressError`.

### 3. Widened Restore Condition in `orchestration/translation.py`

Current:
```python
state_before = self.storage.load_chapter_state(novel_id, chapter_id)
if state_before and state_before.get("error_count", 0) > 0:
    self._restore_latest_checkpoint_for_resume(novel_id, chapter_id)
```

New:
```python
state_before = self.storage.load_chapter_state(novel_id, chapter_id)
should_restore = (state_before is None) or (state_before.get("error_count", 0) > 0)
if should_restore:
    restored = self._restore_latest_checkpoint_for_resume(novel_id, chapter_id)
    # Pass restore result into context if available
    # (context may not exist at this point in the orchestration layer;
    #  the flag is set inside _restore_latest_checkpoint_for_resume instead — see below)
```

`_restore_latest_checkpoint_for_resume` in `NovelOrchestrationService` does not currently have access to `context`. The `context.metadata["checkpoint_restored"]` flag is best set in `TranslationService.translate_chapter` or via a new callback mechanism. The simplest approach: add a return-value flag to the orchestration translate helper and propagate it into the pipeline state metadata before `translate_chapter` is called.

Alternative (simpler): expose `checkpoint_restored: bool` as a parameter passed into `translate_chapter` via `state.metadata["checkpoint_restored"] = True` in the orchestration layer after calling `_restore_latest_checkpoint_for_resume`.

```python
checkpoint_restored = self._restore_latest_checkpoint_for_resume(novel_id, chapter_id) if should_restore else False
# ... later, when building translate_chapter kwargs:
state.metadata["checkpoint_restored"] = checkpoint_restored
```

This does not require touching `translate_chapter` signature. The field is readable from `context.metadata["checkpoint_restored"]` in any downstream stage or audit tool.

### 4. Test Design

#### `test_translation_cache_contract.py`

Uses `unittest.mock.MagicMock` and `unittest.mock.patch` to mock `StorageService`, provider calls, and `_load_existing_chunk_output`. The six-field tests operate directly against `TranslateStage._load_existing_chunk_output` with fake `context.chunk_states` and `context.metadata`.

```python
def _make_context(
    source_text_hash: str = "abc",
    prompt_version: str = "v1",
    glossary_hash: str = "gh1",
    style_preset: str | None = None,
    json_output: bool = False,
    consistency_mode: bool = False,
):
    context = mock_pipeline_context()
    context.chunk_states = {
        "chunk_0": {
            "source_text_hash": source_text_hash,
            "prompt_version": prompt_version,
            "glossary_hash": glossary_hash,
            "style_preset": style_preset,
            "json_output": json_output,
            "consistency_mode": consistency_mode,
            "translated_text": "Cached translation.",
            "status": "succeeded",
        }
    }
    return context

def test_cache_reuse_all_six_fields_match():
    stage = TranslateStage(...)
    context = _make_context()
    result = stage._load_existing_chunk_output(context, chunk_id="chunk_0", chunk_text="...", ...)
    assert result == "Cached translation."

def test_cache_miss_on_glossary_hash_change():
    stage = TranslateStage(...)
    context = _make_context(glossary_hash="different")
    result = stage._load_existing_chunk_output(context, chunk_id="chunk_0", chunk_text="...", ...)
    assert result is None  # cache miss
```

#### `test_translation_resume_contract.py`

Uses async fixtures (pytest-asyncio):

```python
@pytest.mark.asyncio
async def test_duplicate_run_raises_translation_in_progress_error(mock_orchestration):
    import asyncio
    # Start first call (hold the lock manually)
    first_run = asyncio.create_task(mock_orchestration.translate_chapter("novel1", "ch1"))
    await asyncio.sleep(0)  # yield to let first task acquire lock
    with pytest.raises(TranslationInProgressError):
        await mock_orchestration.translate_chapter("novel1", "ch1")
    first_run.cancel()

@pytest.mark.asyncio
async def test_different_chapters_do_not_block(mock_orchestration):
    # Both should run concurrently
    results = await asyncio.gather(
        mock_orchestration.translate_chapter("novel1", "ch1"),
        mock_orchestration.translate_chapter("novel1", "ch2"),
    )
    assert len(results) == 2
```

For checkpoint restore tests, mock `storage.load_chapter_state` and `storage.list_checkpoints`:

```python
def test_checkpoint_restore_on_missing_state(mocker, storage):
    mocker.patch.object(storage, "load_chapter_state", return_value=None)
    mocker.patch.object(storage, "list_checkpoints", return_value=[{"checkpoint_name": "before_translate"}])
    restore_mock = mocker.patch.object(storage, "restore_from_checkpoint", return_value=True)
    ...
    # trigger the translate orchestration
    restore_mock.assert_called_once()
```

## Migration and Backward Compatibility

- `TranslationInProgressError` is a new class — no existing code catches `RuntimeError` generically except in broad exception handlers that should still catch this.
- The widened restore condition (None state → restore) is backward-compatible: on a clean first-run chapter there are no checkpoints, so `_restore_latest_checkpoint_for_resume` returns `False` and no change in behavior.
- `context.metadata["checkpoint_restored"]` is an additive metadata field; downstream stages that don't read it are unaffected.
- `_translation_locks` is module-level and in-process; existing single-process workflows are unchanged. In a multi-process worker setup, two processes can still race (that is a Non-Goal).

## Acceptance Criteria

1. Two concurrent async calls to translate the same chapter result in the second raising `TranslationInProgressError`.
2. After the first call completes, a second call on the same chapter succeeds.
3. Two calls on different chapters of the same novel proceed in parallel without blocking each other.
4. A chapter with `state.error_count=0` but no chapter state file (state is `None`) triggers checkpoint restore when a checkpoint exists.
5. All six cache-field tests pass: a matching record is reused; changing any single field causes a cache miss.
6. `context.metadata["checkpoint_restored"]` is `True` after a successful restore, `False` otherwise.
