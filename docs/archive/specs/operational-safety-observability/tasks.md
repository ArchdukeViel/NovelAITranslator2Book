# Tasks: Operational Safety and Observability

## Task List

- [x] 1. Fix `BackupManager._save_manifest` to use `atomic_write`
  - [x] 1.1 Import `atomic_write` from `novelai.utils` in `backend/src/novelai/services/backup_manager.py` (REQ-1.1)
  - [x] 1.2 Replace the `write_text` call in `_save_manifest` with `atomic_write(self._backup_manifest, serialized_json_string)` (REQ-1.1, REQ-1.2)
  - [x] 1.3 Confirm manifest schema and `_load_manifest` recovery behavior are unchanged (REQ-1.3)

- [x] 2. Add logging to `_read_json_file` on parse failure
  - [x] 2.1 Add `import logging` and `logger = logging.getLogger(__name__)` to `backend/src/novelai/storage/runtime_contracts.py` if not already present (REQ-2.1)
  - [x] 2.2 Add `WARNING` log in the `JSONDecodeError` except branch of `_read_json_file`: `logger.warning("Corrupt JSON file: %s — returning default.", path.name)` (REQ-2.1, REQ-2.2)
  - [x] 2.3 Add check for empty/whitespace content before `json.loads`: if `not text.strip()`, log `DEBUG` and return default (REQ-5.1)
  - [x] 2.4 Leave `OSError` branch silent (REQ-2.3)
  - [x] 2.5 Confirm function still returns `default` in all error cases (REQ-2.4)

- [x] 3. Add catalog refresh to `BackupManager.restore_backup`
  - [x] 3.1 Add optional `storage: StorageService | None = None` and optional `session_scope_factory` parameters to `BackupManager.__init__` (REQ-3.4)
  - [x] 3.2 Store them as `self._storage` and `self._session_scope_factory` instance attributes (REQ-3.4)
  - [x] 3.3 After successful tar extraction in `restore_backup`, call `safely_refresh_catalog_projection_after_storage_write` when `self._storage is not None` (REQ-3.1, REQ-3.2)
  - [x] 3.4 Pass `novel_id`, `self._storage`, `context="backup_restore"`, and `self._session_scope_factory` to the refresh call (REQ-3.2)
  - [x] 3.5 Confirm `restore_backup` still returns success when refresh is skipped or raises (REQ-3.3, REQ-3.5)
  - [x] 3.6 Confirm existing callers that do `BackupManager(base_dir)` without `storage` are unaffected (REQ-3.5)

- [x] 4. Add correlation `request_id` to `TranslateStage`
  - [x] 4.1 At the start of `TranslateStage.run()` in `backend/src/novelai/translation/pipeline/stages/translate.py`, read `context.metadata.get("request_id")` (REQ-4.1)
  - [x] 4.2 Generate a UUID4 `request_id` when the value is absent or empty; store in `context.metadata["request_id"]` (REQ-4.1, REQ-4.4)
  - [x] 4.3 Include `request_id` in each chunk record written to runtime tracking files (REQ-4.2)
  - [x] 4.4 Include `request_id` in each chunk attempt record (REQ-4.2)
  - [x] 4.5 Include `request_id` in the error detail dict when max-attempts-exceeded error is raised (REQ-4.3)
  - [x] 4.6 Confirm `request_id` is not logged at `DEBUG` or any level in `translate.py` (REQ-4.5)

- [x] 5. Expand `RUNTIME_STATE_DEFINITIONS` with translation runtime files and backup manifest
  - [x] 5.1 Add `runtime_chunks`, `runtime_chunk_attempts`, `runtime_bundles`, `runtime_outputs` entries to `RUNTIME_STATE_DEFINITIONS` in `backend/src/novelai/services/admin_service.py` with `affects_process=True` (REQ-6.1, REQ-6.2, REQ-6.3)
  - [x] 5.2 Add `backup_manifest` entry with `affects_process=False` (REQ-7.1, REQ-7.2)
  - [x] 5.3 Confirm `GET /admin/runtime-state` returns all new entries including ones with `exists=False` when files are absent (REQ-6.4)
  - [x] 5.4 Confirm `DELETE /admin/runtime-state/{key}` works for new translation runtime keys (REQ-6.5)

- [x] 6. Block `DELETE /admin/runtime-state/backup_manifest`
  - [x] 6.1 Add key-specific guard in the `DELETE /admin/runtime-state/{key}` handler in `backend/src/novelai/api/routers/admin.py`: if `key == "backup_manifest"`, return HTTP 422 with message `"backup_manifest cannot be cleared via this endpoint."` (REQ-7.3)

- [x] 7. Add `GET /novels/{novel_id}/checkpoints` endpoint to library router
  - [x] 7.1 Define `ChapterCheckpointFile`, `ChapterCheckpoints`, and `NovelCheckpointsResponse` Pydantic models in `backend/src/novelai/api/routers/library.py` (REQ-8.1, REQ-8.2)
  - [x] 7.2 Implement `GET /{novel_id}/checkpoints` endpoint (owner-only): iterate `storage.list_stored_chapters(novel_id)`, for each call `storage.list_checkpoints(novel_id, chapter_id)`, collect non-empty results (REQ-8.3)
  - [x] 7.3 Build response using checkpoint `name` and `timestamp` fields — no raw filesystem paths (REQ-8.4)
  - [x] 7.4 Confirm endpoint is read-only; no writes (REQ-8.5)

- [x] 8. Write malformed artifact recovery tests
  - [x] 8.1 Create `backend/tests/test_malformed_artifact_recovery.py` (REQ-9.1)
  - [x] 8.2 Write tests for `_load_chapter_bundle`: truncated JSON → `None`, empty file → `None`, array instead of dict → `None` (REQ-9.1, REQ-9.2)
  - [x] 8.3 Write tests for `load_chapter_state`: truncated JSON → `None`, empty file → `None` (REQ-9.2)
  - [x] 8.4 Write tests for `load_glossary`: malformed JSON → `[]`, empty file → `[]` (REQ-9.2)
  - [x] 8.5 Write test for `_read_json_file`: malformed JSON → `{}` and `WARNING` log emitted (REQ-9.3)
  - [x] 8.6 Write test for `_read_json_file`: empty/whitespace file → `{}` and `DEBUG` log emitted (REQ-9.5)
  - [x] 8.7 Write test for `BackupManager._load_manifest`: corrupted manifest → `{}` returned (REQ-9.4)

- [x] 9. Write backup restore catalog refresh tests
  - [x] 9.1 Create `backend/tests/test_backup_restore_catalog_refresh.py` (REQ-10.1)
  - [x] 9.2 Write `test_restore_calls_refresh_when_storage_supplied` — mock `safely_refresh_catalog_projection_after_storage_write`, assert called once (REQ-10.1)
  - [x] 9.3 Write `test_restore_succeeds_even_if_refresh_raises` — confirm restore result is success despite exception in refresh (REQ-10.2)
  - [x] 9.4 Write `test_restore_skips_refresh_when_storage_none` — assert refresh mock not called when `storage=None` (REQ-10.3)

- [x] 10. Verify, lint, and type-check all changes
  - [x] 10.1 Run `pytest backend/tests/test_malformed_artifact_recovery.py backend/tests/test_backup_restore_catalog_refresh.py --tb=short -q` and confirm all pass
  - [x] 10.2 Run `ruff check backend/src/novelai/services/backup_manager.py backend/src/novelai/storage/runtime_contracts.py backend/src/novelai/services/admin_service.py backend/src/novelai/translation/pipeline/stages/translate.py backend/src/novelai/api/routers/admin.py backend/src/novelai/api/routers/library.py` and fix any issues
  - [x] 10.3 Run `pyright backend/src/novelai/services/backup_manager.py backend/src/novelai/storage/runtime_contracts.py backend/src/novelai/services/admin_service.py` and fix type errors
