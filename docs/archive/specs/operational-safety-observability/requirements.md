# Requirements: Operational Safety and Observability

## Introduction

The storage layer uses `atomic_write` (temp file + `os.replace`) consistently for chapter bundles, chapter state, checkpoint files, and runtime contract files. This protects against mid-write corruption under most conditions. However, four concrete safety and observability gaps remain.

First, `BackupManager._save_manifest` uses plain `write_text` instead of `atomic_write`. A crash between clearing and rewriting the manifest file silently resets the backup inventory to empty on next load. Second, `_read_json_file` in `runtime_contracts.py` silently swallows `JSONDecodeError` with no log entry, making corrupt runtime files invisible until they cause downstream failures. Third, `BackupManager.restore_backup` does not trigger a catalog projection refresh after restore, leaving the public catalog stale until the next manual refresh or write event. Fourth, admin observability is fragmented: runtime-state visibility covers only 3 of the runtime files; translation runtime tracking files (chunks, bundles, outputs, attempts), backup manifest health, and checkpoint inventory have no admin API surface.

This spec fixes the concrete safety regressions and adds focused, incremental observability improvements that do not require architectural changes.

## Requirements

### REQ-1: Fix `BackupManager._save_manifest` Atomic Write

The backup manifest must be written atomically to prevent corruption on crash.

- REQ-1.1: `BackupManager._save_manifest` in `backend/src/novelai/services/backup_manager.py` must use `atomic_write` from `novelai.utils` instead of `path.write_text`.
- REQ-1.2: The `atomic_write` call must write the serialized JSON manifest to the same path as the current `write_text` call. No path change.
- REQ-1.3: The change must not alter the manifest schema or the `_load_manifest` recovery behavior.

### REQ-2: Add Logging to `_read_json_file` on Parse Failure

Silent JSON parse failures in runtime contract files must emit a log entry.

- REQ-2.1: `_read_json_file` in `backend/src/novelai/storage/runtime_contracts.py` must log a `WARNING` message when it catches `JSONDecodeError`, including the file path and a short description (`"Corrupt JSON file: {path} — returning default."`).
- REQ-2.2: The `WARNING` must not include the file content (to avoid logging potentially sensitive data).
- REQ-2.3: `OSError` may remain silent (disk errors are typically already visible in system logs).
- REQ-2.4: The function must continue to return the `default` value after logging.

### REQ-3: Catalog Refresh After Backup Restore

Restoring from a backup must trigger a catalog projection refresh.

- REQ-3.1: `BackupManager.restore_backup` must call `safely_refresh_catalog_projection_after_storage_write` after a successful tar extraction, following the same pattern as `CheckpointManager.restore_checkpoint`.
- REQ-3.2: The refresh must receive the `novel_id` of the restored novel.
- REQ-3.3: The refresh must be best-effort: if it fails, `restore_backup` must still return a success result and log a warning (same behavior as `safely_refresh_catalog_projection_after_storage_write` itself, which already swallows exceptions).
- REQ-3.4: `BackupManager` must accept `storage` and optional `session_scope_factory` parameters for the refresh call. These must be optional to preserve backward compatibility with callers that do not need catalog refresh.
- REQ-3.5: Existing callers of `restore_backup` that do not supply `storage` must continue to work; the refresh must be skipped when `storage` is `None`.

### REQ-4: Correlation ID Threading Through Translation Runtime Records

Translation runs must emit a `request_id` that is carried through chunk, attempt, and output records.

- REQ-4.1: `TranslateStage.run()` must generate or accept a `request_id` string. When not supplied via `context.metadata["request_id"]`, it must generate a new UUID4 value and store it in `context.metadata["request_id"]`.
- REQ-4.2: Each record written to `chunks.json`, `chunk_attempts.json`, and runtime output records must include the `request_id` field.
- REQ-4.3: `request_id` must also be included in pipeline error payloads emitted by `TranslateStage` when max attempts are exceeded.
- REQ-4.4: The `request_id` must be a string. Callers may supply any non-empty string; if empty or missing, `TranslateStage` generates a UUID4.
- REQ-4.5: The `request_id` must not be logged at `DEBUG` level or lower in a way that couples logs to a specific job system. It is stored in runtime JSON files only.

### REQ-5: Add Log Warning to `_read_json_file` on Stale/Empty File

Runtime files that exist but are empty or contain only whitespace should be distinguishable from clean missing files.

- REQ-5.1: `_read_json_file` must log a `DEBUG` message (not `WARNING`) when the file exists but is empty or whitespace-only, before returning the default.
- REQ-5.2: A missing file (does not exist) must remain completely silent (current behavior unchanged).

### REQ-6: Expand Admin Runtime-State Endpoint to Cover Translation Runtime Files

The `GET /admin/runtime-state` endpoint must cover translation runtime files in addition to the three currently tracked files.

- REQ-6.1: `RUNTIME_STATE_DEFINITIONS` in `backend/src/novelai/services/admin_service.py` must be extended with entries for the translation runtime files: `chunks` (`runtime/translation/chunks.json`), `chunk_attempts` (`runtime/translation/chunk_attempts.json`), `bundles` (`runtime/translation/bundles.json`), `outputs` (`runtime/translation/outputs.json`), and `fetch_cache` (if the path is known — skip if path is not confirmed).
- REQ-6.2: Each new entry must follow the same schema as existing entries: `label`, `filename` (relative to storage root), `description`, `affects_process`.
- REQ-6.3: New entries must set `affects_process = True` for runtime translation files (clearing them drops in-flight tracking).
- REQ-6.4: The `GET /admin/runtime-state` endpoint must return all entries. Entries for files that do not exist must be returned with `exists = False` rather than being omitted.
- REQ-6.5: The `DELETE /admin/runtime-state/{key}` endpoint must support the new keys. Deletion behavior must remain consistent with existing keys (delete the file if it exists; no-op if absent).

### REQ-7: Add Backup Manifest Health to Admin Runtime-State

The backup manifest must be visible through the admin runtime-state surface.

- REQ-7.1: Add a `backup_manifest` entry to `RUNTIME_STATE_DEFINITIONS` pointing to `backups/manifest.json` under the storage root. Set `affects_process = False`.
- REQ-7.2: The entry must follow the existing schema. No new endpoint is needed.
- REQ-7.3: `DELETE /admin/runtime-state/backup_manifest` must be blocked (return HTTP 405 or HTTP 422 with error `"backup_manifest cannot be cleared via this endpoint"`). Backup manifest must only be managed through backup endpoints.

### REQ-8: Checkpoint Inventory in Admin Surface

The admin must be able to see which chapters have checkpoints without querying the filesystem directly.

- REQ-8.1: A new endpoint `GET /novels/{novel_id}/checkpoints` must be added to the library router (owner-only).
- REQ-8.2: The endpoint must return a list of `{chapter_id, checkpoint_files: [{name, timestamp, size_bytes}]}` entries for all chapters that have at least one checkpoint file.
- REQ-8.3: The endpoint must call `storage.list_checkpoints(novel_id, chapter_id)` for each chapter found in `storage.list_stored_chapters(novel_id)`.
- REQ-8.4: The response must not expose raw filesystem paths.
- REQ-8.5: The endpoint must be read-only.

### REQ-9: Tests for Malformed Artifact Recovery

Every storage `_load_*` function must have at least one test that confirms safe fallback behavior on malformed input.

- REQ-9.1: A new test file `backend/tests/test_malformed_artifact_recovery.py` must test the following scenarios with a real or fake temp-file fixture:
  - Truncated JSON file returns `None` / `{}` / `[]` as appropriate
  - Empty file returns the safe default
  - File containing a JSON array where a dict is expected returns the safe default
  - File containing a JSON string returns the safe default
- REQ-9.2: Tests must cover: `_load_chapter_bundle` (chapters.py), `load_chapter_state` (jobs.py), `load_glossary` (glossary.py), `_read_json_file` (runtime_contracts.py).
- REQ-9.3: The test for `_read_json_file` must assert that a `WARNING` log is emitted when the file contains malformed JSON (after REQ-2 is implemented).
- REQ-9.4: A test must confirm that `BackupManager._load_manifest` returns `{}` when the manifest file is corrupted (empty or malformed JSON).
- REQ-9.5: A test must confirm that `_read_json_file` logs at `DEBUG` level when the file exists but is empty (REQ-5).

### REQ-10: Test for Catalog Refresh After Backup Restore

- REQ-10.1: A test must confirm that `BackupManager.restore_backup` calls `safely_refresh_catalog_projection_after_storage_write` when `storage` is provided.
- REQ-10.2: A test must confirm that `restore_backup` succeeds (returns success) even when the catalog refresh raises an exception.
- REQ-10.3: A test must confirm that `restore_backup` does not call `safely_refresh_catalog_projection_after_storage_write` when `storage=None`.

## Non-Goals

- This spec does not add HTTP-layer rate limiting or authentication changes.
- This spec does not add advisory file locking (fcntl/msvcrt). Concurrent write safety beyond `atomic_write` is a future concern requiring architecture decisions.
- This spec does not add a durable periodic checkpoint schedule (AutoCheckpointHandler persistence is a separate concern).
- This spec does not change the public API response shapes.
- This spec does not add a full traceability dashboard UI — only backend API and storage changes.
- This spec does not address the Windows `atomic_write` non-atomic window (requires OS-level locking strategy).
