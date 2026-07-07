# Tasks: Atomic JSON Storage Recovery

## Task List

- [x] 1. Preflight Storage Write Review
  - [x] 1.1 Inspect `backend/src/novelai/storage/novels.py` for `save_metadata`, `load_metadata`, metadata backup creation, metadata history listing, and corrupted metadata handling.
  - [x] 1.2 Inspect the shared storage base/helper module for `_write_text`, `_read_text`, `_write_json`, or equivalent helpers.
  - [x] 1.3 Inspect `backend/src/novelai/storage/chapters.py` for raw chapter bundle write paths.
  - [x] 1.4 Inspect `backend/src/novelai/storage/translations.py` for translated chapter version and edit history write paths.
  - [x] 1.5 Identify all direct uses of `Path.write_text`, `open(..., "w")`, or non-atomic JSON/text writes under `backend/src/novelai/storage`.
  - [x] 1.6 Confirm current corrupted `metadata.json` behavior so tests can preserve the existing failure contract when no backup is valid.

- [x] 2. Add Atomic Text Write Helper
  - [x] 2.1 Add `_write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None` at the lowest shared storage helper layer. (REQ-1.1)
  - [x] 2.2 Ensure the target parent directory exists before writing. (REQ-1.1)
  - [x] 2.3 Create a unique temporary file in the same directory as the target. (REQ-1.5, REQ-1.6)
  - [x] 2.4 Write the full content to the temporary file.
  - [x] 2.5 Flush the temporary file handle.
  - [x] 2.6 Call `os.fsync` on the temporary file descriptor. (REQ-1.2)
  - [x] 2.7 Replace the target with `os.replace(temp_path, path)`. (REQ-1.3)
  - [x] 2.8 Best-effort `fsync` the parent directory after replace. (REQ-1.4)
  - [x] 2.9 Best-effort delete the temp file if an exception occurs before replace. (REQ-6.2)
  - [x] 2.10 Include target path context in raised/logged write failures. (REQ-8.1)

- [x] 3. Add Atomic JSON Helper If Useful
  - [x] 3.1 If JSON serialization is duplicated, add `_write_json_atomic(path: Path, payload: Any) -> None`.
  - [x] 3.2 Preserve existing JSON formatting behavior where practical. (REQ-2)
  - [x] 3.3 Ensure `ensure_ascii`, indentation, and key ordering do not create unrelated file churn unless existing code already uses those settings.

- [x] 4. Apply Atomic Writes to Metadata
  - [x] 4.1 Update `save_metadata` so `metadata.json` writes use the atomic helper. (REQ-3.1)
  - [x] 4.2 Preserve existing metadata schema. (REQ-2.1)
  - [x] 4.3 Preserve existing directory naming and file path behavior.
  - [x] 4.4 Preserve existing backup creation before replacing an existing `metadata.json`. (REQ-4.1, REQ-4.4)
  - [x] 4.5 Ensure backup creation failure behavior matches existing behavior. (REQ-4.3)
  - [x] 4.6 Ensure failed pre-rename writes leave the old `metadata.json` intact. (REQ-1.7)
  - [x] 4.7 Ensure failed writes do not create extra metadata backups beyond the normal pre-write backup. (REQ-4.5)

- [x] 5. Apply Atomic Writes to Metadata Backups
  - [x] 5.1 Update metadata backup file writes to use the atomic helper. (REQ-3.2)
  - [x] 5.2 Preserve backup filename format. (REQ-4.2)
  - [x] 5.3 Preserve backup retention and pruning behavior. (REQ-4.2)
  - [x] 5.4 Preserve backup JSON schema. (REQ-2.2)

- [x] 6. Apply Atomic Writes to Other JSON/Text Bundles
  - [x] 6.1 If raw chapter bundles use JSON/text writes, route them through the atomic helper. (REQ-3.3)
  - [x] 6.2 Preserve raw chapter bundle schema. (REQ-2.3)
  - [x] 6.3 If translated chapter/version bundles use JSON/text writes, route them through the atomic helper. (REQ-3.4)
  - [x] 6.4 Preserve translation bundle/version schema. (REQ-2.4)
  - [x] 6.5 If translation edit history uses JSON/text writes, route it through the atomic helper. (REQ-3.5)
  - [x] 6.6 Preserve edit history schema. (REQ-2.5)
  - [x] 6.7 Leave binary image asset writes unchanged unless they already go through the same helper. (REQ-3.6)

- [x] 7. Add Metadata Recovery From Backup
  - [x] 7.1 Update `load_metadata` to detect invalid JSON in primary `metadata.json`. (REQ-5.1)
  - [x] 7.2 Add helper to find metadata backup files using the existing backup directory and naming rules. (REQ-5.2)
  - [x] 7.3 Sort backups newest first using the existing metadata history ordering where possible. (REQ-5.2)
  - [x] 7.4 Attempt to parse backups in order.
  - [x] 7.5 Return the first valid backup payload. (REQ-5.3)
  - [x] 7.6 Log a warning including novel ID and backup path when recovery succeeds. (REQ-5.4)
  - [x] 7.7 Skip invalid backup files and continue searching.
  - [x] 7.8 If no valid backup exists, preserve the existing failure behavior. (REQ-5.6)
  - [x] 7.9 Do not delete invalid primary metadata or invalid backups in this spec.
  - [x] 7.10 If auto-restore is implemented, write restored metadata atomically. (REQ-5.5)

- [x] 8. Preserve Listing Behavior
  - [x] 8.1 Ensure novel listing continues when one novel has corrupted `metadata.json`. (REQ-5.7)
  - [x] 8.2 Ensure listing ignores temp files created by atomic writes. (REQ-6.4)
  - [x] 8.3 Ensure folders are still considered in-use according to existing rules.

- [x] 9. Temp File Cleanup and Safety
  - [x] 9.1 Use temp filenames matching the storage helper's own predictable pattern. (REQ-6.3)
  - [x] 9.2 Ensure successful writes do not leave temp files. (REQ-6.1)
  - [x] 9.3 Ensure failed writes best-effort remove temp files. (REQ-6.2)
  - [x] 9.4 Ensure readers do not load temp files. (REQ-6.4)
  - [x] 9.5 Ensure concurrent writes do not reuse the same temp filename. (REQ-7.1)

- [x] 10. Add Atomic Write Tests
  - [x] 10.1 Create `backend/tests/test_atomic_json_storage_recovery.py`. (REQ-9)
  - [x] 10.2 Write `test_atomic_write_replaces_target_with_complete_json`. (REQ-9.1)
  - [x] 10.3 Write `test_atomic_write_failure_before_replace_preserves_existing_file`. (REQ-9.2)
  - [x] 10.4 Write `test_temp_files_are_ignored_by_normal_loaders`. (REQ-9.3)
  - [x] 10.5 Write `test_atomic_write_uses_unique_temp_names`. (REQ-9.8)
  - [x] 10.6 Mock or monkeypatch the write/replace flow to simulate failure before `os.replace`.
  - [x] 10.7 Avoid tests that depend on real process crashes.

- [x] 11. Add Metadata Backup and Recovery Tests
  - [x] 11.1 Write `test_metadata_save_preserves_existing_backup_behavior`. (REQ-9.4)
  - [x] 11.2 Write `test_load_metadata_recovers_from_latest_valid_backup`. (REQ-9.5)
  - [x] 11.3 Write `test_load_metadata_skips_invalid_backup_and_uses_older_valid_backup`.
  - [x] 11.4 Write `test_load_metadata_corrupt_without_backup_preserves_existing_failure_contract`. (REQ-9.6)
  - [x] 11.5 Write `test_list_metadata_continues_after_corrupted_novel_metadata`. (REQ-9.7)
  - [x] 11.6 Assert recovery logs a warning without logging full chapter or translation text. (REQ-8.2, REQ-8.4)

- [x] 12. Add Bundle Coverage Tests Where Applicable
  - [x] 12.1 If chapter bundles use the shared helper, add a test proving chapter bundle writes call or benefit from the atomic helper. (REQ-9.9)
  - [x] 12.2 If translation bundles use the shared helper, add a test proving translation bundle writes call or benefit from the atomic helper. (REQ-9.9)
  - [x] 12.3 If edit history uses the shared helper, add a test proving edit history writes call or benefit from the atomic helper.
  - [x] 12.4 If these paths do not use JSON/text writes, document why they are out of scope in test comments or implementation notes.

- [x] 13. Backward Compatibility Checks
  - [x] 13.1 Confirm existing metadata files still load. (REQ-2.6)
  - [x] 13.2 Confirm existing metadata backups still load. (REQ-2.6)
  - [x] 13.3 Confirm existing raw chapter bundles still load. (REQ-2.6)
  - [x] 13.4 Confirm existing translated chapter versions still load. (REQ-2.6)
  - [x] 13.5 Confirm no DB migration files are created.
  - [x] 13.6 Confirm no JSON schema changes are introduced.
  - [x] 13.7 Confirm no public API response shape changes are introduced.

- [x] 14. Run Verification
  - [x] 14.1 Run `pytest backend/tests/test_atomic_json_storage_recovery.py --tb=short -q`.
  - [x] 14.2 Run existing storage tests, if present.
  - [x] 14.3 Run `ruff check` on changed storage modules and the new test file.
  - [x] 14.4 Run the repository's configured backend type checker, if present.
  - [x] 14.5 Fix test, lint, and type failures caused by this work.

- [x] 15. Final Acceptance Review
  - [x] 15.1 Verify `metadata.json` writes are atomic from reader perspective.
  - [x] 15.2 Verify old `metadata.json` remains unchanged if the new write fails before rename.
  - [x] 15.3 Verify metadata backup behavior and retention are preserved.
  - [x] 15.4 Verify corrupted `metadata.json` recovers from the latest valid backup.
  - [x] 15.5 Verify invalid backups are skipped while searching for a valid backup.
  - [x] 15.6 Verify novel listing continues when one novel has corrupted metadata.
  - [x] 15.7 Verify critical JSON/text artifact writes use the atomic helper where applicable.
  - [x] 15.8 Verify schemas and DB models are unchanged.
  - [x] 15.9 Verify focused tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Atomic JSON/Text Write Helper | 2, 9, 10, 15 |
| REQ-2 Preserve Existing Storage Formats | 3, 4, 5, 6, 13, 15 |
| REQ-3 Apply Atomic Writes to Critical Artifacts | 4, 5, 6, 12, 15 |
| REQ-4 Metadata Backup Compatibility | 4, 5, 11, 15 |
| REQ-5 Corruption Detection and Recovery | 7, 8, 11, 15 |
| REQ-6 Temporary File Cleanup | 2, 8, 9, 10 |
| REQ-7 Concurrency Safety | 2, 9, 10, 13 |
| REQ-8 Observability | 2, 7, 11 |
| REQ-9 Tests | 10, 11, 12, 14 |

## Definition of Done

- [x] Critical JSON/text writes use same-directory temp files and atomic replace.
- [x] Temp files are unique and ignored by readers.
- [x] Failed pre-rename writes preserve existing target files.
- [x] Metadata backup behavior remains compatible.
- [x] Corrupted `metadata.json` can recover from latest valid backup.
- [x] Corrupted metadata in one novel does not break novel listing.
- [x] Existing storage schemas and DB schemas are unchanged.
- [x] Focused tests, storage tests, lint, and type checks pass.

