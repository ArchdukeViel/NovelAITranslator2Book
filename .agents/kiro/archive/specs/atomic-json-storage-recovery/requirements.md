# Requirements: Atomic JSON Storage Recovery

## Introduction

The backend uses hybrid persistence: PostgreSQL stores structured state, while JSON/file storage stores novel metadata, raw chapter bundles, translated chapter versions, edit history, image manifests, and metadata backups. The deep research reports identify storage atomicity as a high-severity durability risk, especially around `metadata.json`: the code backs up the old file and then writes new JSON directly. Unless the low-level write helper already uses temp-file-and-rename semantics, a crash, disk-full event, interrupted process, or concurrent write can leave partially written JSON.

This spec adds atomic JSON/text writes and recovery behavior for critical storage artifacts without changing the storage file formats or database schema.

## Requirements

### REQ-1: Atomic JSON/Text Write Helper

Critical JSON/text storage writes must be atomic from the reader's perspective.

- REQ-1.1: Add or update a storage-level helper that writes text/JSON through a temporary file in the same directory as the target.
- REQ-1.2: The helper must write all bytes to the temporary file, flush the file handle, and call `fsync` on the temporary file before rename.
- REQ-1.3: The helper must replace the target using an atomic rename operation such as `os.replace`.
- REQ-1.4: The helper must best-effort `fsync` the parent directory after rename on platforms where that is supported.
- REQ-1.5: Temporary files must not be placed in a different filesystem or global temp directory.
- REQ-1.6: Temporary filenames must be unique enough to avoid collision between concurrent writes.
- REQ-1.7: If the write fails before rename, the existing target file must remain unchanged.
- REQ-1.8: If the write fails after temp file creation, stale temp files may remain but must not be used by normal readers.

### REQ-2: Preserve Existing Storage Formats

The change must improve durability without changing existing JSON schemas.

- REQ-2.1: Existing `metadata.json` schema must remain unchanged.
- REQ-2.2: Existing metadata backup file schema must remain unchanged.
- REQ-2.3: Existing raw chapter bundle schema must remain unchanged.
- REQ-2.4: Existing translated chapter bundle/version schema must remain unchanged.
- REQ-2.5: Existing edit history schema must remain unchanged.
- REQ-2.6: Existing readers must continue to load files written before this change.

### REQ-3: Apply Atomic Writes to Critical JSON Artifacts

Critical storage write paths must use the atomic helper.

- REQ-3.1: `metadata.json` writes in the novel storage layer must use atomic writes.
- REQ-3.2: Metadata backup writes must use atomic writes.
- REQ-3.3: Raw chapter bundle writes must use atomic writes if they are JSON/text files.
- REQ-3.4: Translated chapter/version bundle writes must use atomic writes if they are JSON/text files.
- REQ-3.5: Translation edit history writes must use atomic writes if they are JSON/text files.
- REQ-3.6: Image binary asset writes are out of scope unless they currently go through the same text/JSON helper.
- REQ-3.7: The implementation must inspect existing storage helper boundaries first and apply the atomic helper at the lowest shared layer that safely covers these paths.

### REQ-4: Metadata Backup Compatibility

Existing backup behavior must be preserved.

- REQ-4.1: Before replacing an existing `metadata.json`, the current valid file must still be backed up according to the existing backup retention policy.
- REQ-4.2: Backup filenames and retention rules must remain backward compatible.
- REQ-4.3: If backup creation fails, existing behavior should be preserved unless the current code treats backup failure as fatal.
- REQ-4.4: Atomic replacement must happen after backup creation when the target file already exists.
- REQ-4.5: The new write path must not create extra backup files for failed pre-rename writes.

### REQ-5: Corruption Detection and Recovery

When critical JSON is corrupted, storage should recover from the latest valid backup where that behavior is safe and explicit.

- REQ-5.1: Loading `metadata.json` for a single novel must detect invalid JSON.
- REQ-5.2: On invalid `metadata.json`, the storage layer must look for the latest valid metadata backup.
- REQ-5.3: If a valid backup exists, the storage layer must return that backup data instead of crashing.
- REQ-5.4: Recovery must log a warning that includes the novel identifier and the backup file used.
- REQ-5.5: Recovery may optionally restore the latest valid backup back to `metadata.json`, but only if implemented atomically.
- REQ-5.6: If no valid backup exists, the current behavior of warning/raising/returning `None` must be preserved consistently with the existing caller contract.
- REQ-5.7: Listing novels must continue to tolerate corrupted metadata files and continue scanning other novels.

### REQ-6: Temporary File Cleanup

Stale temp files must not accumulate indefinitely.

- REQ-6.1: Normal successful writes must remove or replace their temporary files.
- REQ-6.2: Failed writes must make a best-effort attempt to remove their temporary file.
- REQ-6.3: Startup cleanup is optional, but if implemented it must only remove temp files matching the storage helper's own temp naming pattern.
- REQ-6.4: Readers must ignore temp files.

### REQ-7: Concurrency Safety

Atomic writes must improve crash safety and must not make concurrent writes worse.

- REQ-7.1: Concurrent writers must not share the same temporary filename.
- REQ-7.2: Readers must only ever see the old complete file or the new complete file, not a partial temp file.
- REQ-7.3: This spec does not require cross-process write locking.
- REQ-7.4: Existing in-process locks should remain in place where they already exist.
- REQ-7.5: If storage paths already use per-novel or per-chapter locks, the implementation must not remove them.

### REQ-8: Observability

Storage recovery and write failures must be diagnosable.

- REQ-8.1: Atomic write failures must include target path context in logs or raised exceptions.
- REQ-8.2: Metadata recovery from backup must log a warning.
- REQ-8.3: Failed recovery attempts must log enough detail to identify which target file and backups were inspected.
- REQ-8.4: Logs must not include full chapter text, translated content, or sensitive provider configuration.

### REQ-9: Tests

Focused tests must prove the new durability behavior.

- REQ-9.1: Add tests for atomic helper success: target contains complete new JSON after write.
- REQ-9.2: Add tests for pre-rename failure: existing target remains unchanged.
- REQ-9.3: Add tests for invalid temp file not being read by normal loaders.
- REQ-9.4: Add tests for metadata write preserving backup behavior.
- REQ-9.5: Add tests for corrupted `metadata.json` recovering from latest valid backup.
- REQ-9.6: Add tests for corrupted `metadata.json` with no valid backup preserving existing failure behavior.
- REQ-9.7: Add tests for novel listing skipping corrupted metadata and continuing.
- REQ-9.8: Add tests for unique temp filenames across repeated writes.
- REQ-9.9: Add tests for raw chapter or translation bundle write path if those paths are covered by the shared helper.

## Non-Goals

- This spec does not change JSON schemas.
- This spec does not introduce a database migration.
- This spec does not replace file storage with PostgreSQL.
- This spec does not add distributed locks.
- This spec does not add object storage transactional semantics.
- This spec does not change public reader behavior.
- This spec does not change crawl, translation, or glossary business logic.

