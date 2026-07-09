# Design: Atomic JSON Storage Recovery

## Overview

This design adds atomic write and backup recovery behavior for the repository's JSON/text storage layer. The goal is simple: storage readers should see either the previous complete file or the next complete file, never a partially written file. For `metadata.json`, the loader should also be able to recover from the latest valid backup when the primary file is corrupted.

The design preserves existing file formats and keeps the change concentrated in storage helpers.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/storage/base.py` or equivalent shared storage helper | Add atomic text/JSON write helper |
| `backend/src/novelai/storage/novels.py` | Use atomic write for `metadata.json`; recover from valid backups |
| `backend/src/novelai/storage/chapters.py` | Use atomic write for raw chapter bundles if JSON/text helper is local there |
| `backend/src/novelai/storage/translations.py` | Use atomic write for translation/version/edit history bundles if JSON/text helper is local there |
| `backend/tests/test_atomic_json_storage_recovery.py` | New focused tests |

### Files Not Touched

- DB models and migrations.
- Public reader routes.
- Translation pipeline logic.
- Crawler adapter behavior.
- Existing JSON schema definitions.

## Core Design

### 1. Atomic Write Helper

Add a shared helper at the lowest storage layer that currently owns `_write_text` or equivalent file writes.

Preferred API:

```python
def _write_text_atomic(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> None:
    ...
```

If the storage layer already has `_write_text(path, content)`, either:

- update `_write_text` to become atomic, or
- add `_write_text_atomic` and migrate critical JSON writes to it.

Updating `_write_text` is preferable if all current callers are text/JSON artifacts and should benefit from atomicity.

### 2. Atomic Write Algorithm

Algorithm:

1. Ensure `path.parent` exists.
2. Create a unique temp file inside `path.parent`.
3. Write `content` to the temp file.
4. Flush the file handle.
5. `os.fsync` the temp file descriptor.
6. Atomically replace the target using `os.replace(temp_path, path)`.
7. Best-effort `fsync` the parent directory.
8. Best-effort cleanup if an exception occurs before rename.

Sketch:

```python
def _write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    replaced = False

    try:
        with temp_path.open("w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_path, path)
        replaced = True
        _fsync_directory(path.parent)
    except Exception:
        if not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to remove temp file %s", temp_path, exc_info=True)
        raise
```

Directory fsync helper:

```python
def _fsync_directory(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        logger.debug("Directory fsync failed for %s", directory, exc_info=True)
    finally:
        os.close(fd)
```

On platforms where directory fsync is unsupported, failure is logged at debug level and ignored.

### 3. JSON Write Helper

If JSON serialization is duplicated, add a helper that serializes and writes atomically:

```python
def _write_json_atomic(path: Path, payload: Mapping[str, Any] | list[Any]) -> None:
    self._write_text_atomic(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
```

Keep existing formatting choices where possible. If existing code uses `indent=2`, preserve it. If it does not, avoid introducing unrelated formatting churn unless tests expect stable pretty JSON.

### 4. `metadata.json` Write Flow

Existing behavior appears to be:

1. Resolve novel directory.
2. Ensure directory exists.
3. Backup existing `metadata.json`.
4. Write new `metadata.json`.
5. Prune old backups.

New behavior:

1. Resolve novel directory.
2. Ensure directory exists.
3. If existing `metadata.json` exists, create backup using existing backup helper.
4. Write new `metadata.json` using atomic helper.
5. Prune old backups according to existing retention.

The backup file write should also use atomic write if it writes JSON/text.

Important detail: if the atomic write fails before rename, the old `metadata.json` remains in place. No extra backup should be created beyond the normal pre-write backup of the previous file.

### 5. Metadata Recovery

Add recovery only for `metadata.json` loading, because it already has explicit backups.

When `load_metadata(novel_id)` detects invalid JSON:

1. Log warning that primary metadata is corrupted.
2. Find backup files using existing backup history logic.
3. Sort backups newest first.
4. Try to parse each backup.
5. Return the first valid backup payload.
6. Log warning naming the selected backup.
7. Optionally restore the selected backup to `metadata.json` using atomic write.

Recommended default: return the backup data without auto-restoring first, unless the current storage conventions already repair files on read. This avoids surprising writes during reads. If auto-restore is added, make it explicit and atomic.

Sketch:

```python
def load_metadata(self, novel_id: str) -> dict[str, Any] | None:
    path = self._metadata_path(novel_id)
    try:
        return self._read_json(path)
    except json.JSONDecodeError:
        logger.warning("Corrupted metadata.json for novel %s", novel_id)
        recovered = self._load_latest_valid_metadata_backup(novel_id)
        if recovered is not None:
            logger.warning(
                "Recovered metadata for novel %s from backup %s",
                novel_id,
                recovered.backup_path,
            )
            return recovered.payload
        return None
```

If the existing contract raises instead of returning `None`, preserve that contract after recovery fails.

### 6. Backup Selection

Use existing metadata history helpers where possible.

Selection rules:

- Only inspect files in the existing metadata backup directory.
- Only inspect filenames matching the existing backup naming pattern.
- Prefer newest backup by timestamp/mtime using the same ordering as `list_metadata_history`.
- Skip invalid backup files and continue searching older backups.
- Do not delete invalid backups in this spec.

### 7. Chapter and Translation Bundle Writes

Raw chapter bundles, translated chapter bundles, translation versions, and edit histories should use atomic write if they are stored as JSON/text.

Implementation strategy:

- First inspect whether these storage modules already call a shared `_write_text` or `_persist_*_bundle` helper.
- If they use shared `_write_text`, making `_write_text` atomic may cover all of them.
- If they each write directly with `Path.write_text` or equivalent, update those writes to the atomic helper.

Do not change bundle schemas.

### 8. Temporary File Naming

Temp filename pattern:

```text
.<target-name>.<pid>.<uuid>.tmp
```

Example:

```text
.metadata.json.12345.7f1a1d8e2d4e4d7cb63dd6aebf8d47c1.tmp
```

This pattern:

- stays in the target directory,
- avoids cross-filesystem rename problems,
- is unique enough for concurrent writes,
- is easy to recognize for optional cleanup,
- is ignored by normal storage readers.

### 9. Failure Behavior

| Scenario | Expected behavior |
|---|---|
| Write succeeds | Target is fully replaced with new content |
| Write fails before rename | Old target remains unchanged; temp is best-effort removed |
| Process crashes before rename | Old target remains unchanged; temp may remain ignored |
| Process crashes after rename | New complete target is visible |
| Directory fsync fails | Write still succeeds; debug log only |
| Primary metadata corrupted, backup valid | Loader returns latest valid backup |
| Primary metadata corrupted, no backup valid | Existing failure contract is preserved |

## Migration and Backward Compatibility

- Existing JSON files remain readable.
- Existing backup files remain readable.
- No schema migrations are required.
- Existing callers continue using the same storage methods.
- Any stale temp files from failed writes are ignored by readers.
- Backup retention remains unchanged.

## Test Design

Create `backend/tests/test_atomic_json_storage_recovery.py`.

Focused tests:

- `test_atomic_write_replaces_target_with_complete_json`
- `test_atomic_write_failure_before_replace_preserves_existing_file`
- `test_atomic_write_uses_unique_temp_names`
- `test_metadata_save_preserves_existing_backup_behavior`
- `test_load_metadata_recovers_from_latest_valid_backup`
- `test_load_metadata_skips_invalid_backup_and_uses_older_valid_backup`
- `test_load_metadata_corrupt_without_backup_preserves_existing_failure_contract`
- `test_list_metadata_continues_after_corrupted_novel_metadata`
- `test_temp_files_are_ignored_by_metadata_listing`
- `test_chapter_bundle_write_uses_atomic_helper` if chapter bundles use the shared helper
- `test_translation_bundle_write_uses_atomic_helper` if translation bundles use the shared helper

Tests should use temporary directories and monkeypatching/mocking to simulate write failures. Do not rely on real process crashes.

## Acceptance Criteria

1. `metadata.json` writes are atomic from reader perspective.
2. Existing `metadata.json` remains unchanged if a new write fails before rename.
3. Metadata backup behavior and retention remain compatible.
4. Corrupted `metadata.json` can recover from the latest valid backup.
5. Invalid backup files are skipped while searching for a valid backup.
6. Novel listing continues when one novel has corrupted metadata.
7. Critical JSON/text artifact writes use the atomic helper where applicable.
8. Existing JSON schemas and DB schemas are unchanged.
9. Focused tests pass.

