# Tasks: Glossary Sync Bridge

## Task List

- [x] 1. Create `GlossarySyncService` and `GlossarySyncResult`
  - [x] 1.1 Create `backend/src/novelai/services/glossary_sync_service.py` with `GlossarySyncResult` dataclass (fields: `novel_id`, `dry_run`, `created`, `updated`, `skipped`, `errors`, `synced_terms`) (REQ-1.1, REQ-1.10)
  - [x] 1.2 Implement `GlossarySyncService.__init__` accepting `GlossaryRepository` and `StorageService` (REQ-1.2)
  - [x] 1.3 Implement `sync_from_file`: load file entries, resolve `platform_novel_id` via DB query on `Novel.slug`, raise `ValueError("novel_not_in_db")` when novel not found (REQ-1.3, REQ-1.4, REQ-1.6)
  - [x] 1.4 Filter eligible entries: `status in {"approved", "needs_manual_review"}` and non-empty `source` (REQ-1.5)
  - [x] 1.5 Implement create path: call `repository.create_glossary_entry` with the field mapping from design (REQ-1.7)
  - [x] 1.6 Implement upsert path: find existing entry by `canonical_term`, update `approved_translation`, `admin_notes`, `confidence`; update `status` only when existing status is `"candidate"` (REQ-1.8)
  - [x] 1.7 Implement `dry_run=True` path: count operations without DB writes, return result (REQ-1.9)
  - [x] 1.8 Wrap each entry operation in try/except; on error append `{"term": source, "error": str(exc)}` to errors and continue (REQ-1.10)

- [x] 2. Call `_increment_glossary_revision` once per sync run
  - [x] 2.1 After the entry loop, when `not dry_run and created + updated > 0`, call `repository._increment_glossary_revision(platform_novel_id)` exactly once (REQ-6.1, REQ-6.2)

- [x] 3. Hook sync into `review_glossary_terms`
  - [x] 3.1 In `backend/src/novelai/services/orchestration/glossary.py`, after `self.storage.save_glossary(novel_id, entries)`, add the sync call wrapped in try/except (REQ-2.1, REQ-2.2)
  - [x] 3.2 Add `"db_sync"` key to the return dict with `created`, `updated`, `skipped`, `error_count` from sync result (REQ-2.3)
  - [x] 3.3 Return `{"db_sync": {"skipped": True, "reason": "novel_not_in_db"}}` when `ValueError("novel_not_in_db")` is raised (REQ-2.4)
  - [x] 3.4 Return `{"db_sync": {"skipped": True, "reason": "sync_error"}}` on any other exception (REQ-2.2)

- [x] 4. Fix `platform_novel_id` resolution in `TranslateStage`
  - [x] 4.1 At the start of `TranslateStage.run()` in `backend/src/novelai/translation/pipeline/stages/translate.py`, check if `_platform_novel_id(context)` returns `None` (REQ-4.1, REQ-4.5)
  - [x] 4.2 When `None` and `context.novel_id` is a non-empty string, open a `session_scope()` and query `Novel` by `slug=context.novel_id` (REQ-4.1, REQ-4.4)
  - [x] 4.3 On successful resolution, store `novel_row.id` into `context.metadata["platform_novel_id"]` (REQ-4.2)
  - [x] 4.4 On query failure or `None` result, log at `DEBUG` level and continue (REQ-4.3)

- [x] 5. Add `POST /novels/{novel_id}/glossary/sync-to-db` endpoint
  - [x] 5.1 Define `GlossarySyncRequest` and `GlossarySyncResponse` Pydantic models in `admin_glossary.py` (REQ-3.1, REQ-3.3)
  - [x] 5.2 Implement the endpoint: call `GlossarySyncService(...).sync_from_file(novel_id, dry_run=body.dry_run)` (REQ-3.1)
  - [x] 5.3 Return HTTP 404 when `storage.load_metadata(novel_id)` is `None` (REQ-3.4)
  - [x] 5.4 Return HTTP 422 with `"novel_not_in_db"` when `ValueError("novel_not_in_db")` is raised (REQ-3.5)
  - [x] 5.5 Update `_LAST_SYNC_TIMESTAMPS[novel_id]` on successful non-dry-run sync (REQ-5.3)

- [x] 6. Add `GET /novels/{novel_id}/glossary/sync-status` endpoint
  - [x] 6.1 Add module-level `_LAST_SYNC_TIMESTAMPS: dict[str, str] = {}` to `admin_glossary.py` (REQ-5.3)
  - [x] 6.2 Define `GlossarySyncStatusResponse` Pydantic model (REQ-5.1)
  - [x] 6.3 Implement the endpoint: count file approved entries, count DB approved entries, compute `in_sync` and `recommendation` (REQ-5.1, REQ-5.2)
  - [x] 6.4 Return `last_sync_at` from `_LAST_SYNC_TIMESTAMPS` or `None` (REQ-5.3)

- [x] 7. Write tests
  - [x] 7.1 Create `backend/tests/test_glossary_sync_bridge.py`
  - [x] 7.2 Write `test_sync_creates_new_entries` (REQ-7.2)
  - [x] 7.3 Write `test_sync_upserts_existing_entry` (REQ-7.3)
  - [x] 7.4 Write `test_sync_does_not_downgrade_approved_to_candidate` (REQ-7.4)
  - [x] 7.5 Write `test_sync_skips_ignored_entries` (REQ-7.5)
  - [x] 7.6 Write `test_sync_dry_run_no_writes` (REQ-7.6)
  - [x] 7.7 Write `test_sync_increments_glossary_revision_once` (REQ-7.7)
  - [x] 7.8 Write `test_review_triggers_sync` (REQ-7.8)
  - [x] 7.9 Write `test_review_succeeds_even_if_sync_raises` (REQ-7.9)
  - [x] 7.10 Write `test_translate_stage_resolves_platform_novel_id` (REQ-7.10)
  - [x] 7.11 Write `test_translate_stage_no_glossary_injection_when_novel_not_in_db` (REQ-7.11)
  - [x] 7.12 Write `test_sync_status_endpoint_healthy` (REQ-7.12)
  - [x] 7.13 Write `test_sync_status_endpoint_sync_required` (REQ-7.13)
  - [x] 7.14 Run `pytest backend/tests/test_glossary_sync_bridge.py --tb=short -q` and confirm all pass
  - [x] 7.15 Run `ruff check backend/src/novelai/services/glossary_sync_service.py backend/src/novelai/services/orchestration/glossary.py backend/src/novelai/translation/pipeline/stages/translate.py` and fix issues
  - [x] 7.16 Run `pyright backend/src/novelai/services/glossary_sync_service.py` and fix type errors
