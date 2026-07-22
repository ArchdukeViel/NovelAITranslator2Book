# Tasks: Create-Novel Lifecycle

## Task List

- [x] 1. Add `POST /api/admin/novels` create endpoint to `library.py`
  - [x] 1.1 Define `NovelCreateRequest` Pydantic model with fields: `novel_id`, `title`, `source_url`, `source_key`, `language` (REQ-1.2)
  - [x] 1.2 Define `NovelCreateResponse` Pydantic model with fields: `novel_id`, `title`, `source_url`, `source_key`, `language`, `created_at`, `db_id` (REQ-1.7)
  - [x] 1.3 Implement `POST /` handler (owner-only, status_code=201) in `backend/src/novelai/api/routers/library.py` (REQ-1.1)
  - [x] 1.4 Validate `novel_id` using `validate_storage_identifier`; return HTTP 422 on invalid slug (REQ-1.3)
  - [x] 1.5 Check for existing novel in both storage and DB; return HTTP 409 when found (REQ-1.4)
  - [x] 1.6 Write minimal `metadata.json` via `storage.save_metadata(novel_id, minimal_meta)` with `title`, `source_url`, `source_key`, `language`, `origin_type`, `chapters: []` (REQ-1.5)
  - [x] 1.7 Create DB row via `CatalogService(storage, session).get_or_create_novel(novel_id, minimal_meta)` (REQ-1.6)
  - [x] 1.8 Return `NovelCreateResponse` with the created novel's DB primary key (REQ-1.7)

- [x] 2. Add post-scrape DB reconciliation to `OperationsService`
  - [x] 2.1 In `OperationsService.scrape_novel` in `backend/src/novelai/services/orchestration/operations.py`, after `scrape_metadata` completes, add best-effort `CatalogService.reconcile_catalog_projection` call wrapped in try/except with `WARNING` log on failure (REQ-2.1, REQ-2.2)
  - [x] 2.2 Apply the same post-metadata best-effort reconciliation to `OperationsService.preliminary_crawl_novel` (REQ-2.3)

- [x] 3. Confirm and lock `translate_novel` 404 guard
  - [x] 3.1 Verify the existing `OperationError(404, "Novel not found")` guard in `translate_novel` is present and covers the `storage.load_metadata` returns `None` path (REQ-3.1)
  - [x] 3.2 Update the error detail to include `novel_id`: return `{"error": "Novel not found", "novel_id": novel_id}` (REQ-3.2)

- [x] 4. Write integration test
  - [x] 4.1 Create `backend/tests/test_novel_lifecycle_integration.py` (REQ-4.1)
  - [x] 4.2 Write `test_create_to_public_read_lifecycle` covering all 8 steps: create → save metadata → refresh projection → save translation → refresh again → publish → public catalog → public chapter read (REQ-4.2)
  - [x] 4.3 Write `test_409_on_duplicate_create` (REQ-4.4)

- [x] 5. Write permission and validation tests
  - [x] 5.1 Write `test_create_requires_owner_role` — unauthenticated → 403 (REQ-5.1)
  - [x] 5.2 Write `test_created_novel_db_defaults` — `is_published=False`, `glossary_status="glossary_pending"`, correct `language` (REQ-5.2)
  - [x] 5.3 Write `test_create_invalid_novel_id_returns_422` — path traversal and empty string cases (REQ-5.3)
  - [x] 5.4 Write `test_translate_without_novel_returns_404` — `novel_id` in detail (REQ-3.3)

- [x] 6. Verify, lint, and type-check
  - [x] 6.1 Run `pytest backend/tests/test_novel_lifecycle_integration.py --tb=short -q` and confirm all pass
  - [x] 6.2 Run `ruff check backend/src/novelai/api/routers/library.py backend/src/novelai/services/orchestration/operations.py` and fix issues
  - [x] 6.3 Run `pyright backend/src/novelai/api/routers/library.py backend/src/novelai/services/orchestration/operations.py` and fix type errors
