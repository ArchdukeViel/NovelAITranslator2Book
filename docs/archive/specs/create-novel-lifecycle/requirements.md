# Requirements: Create-Novel Lifecycle

## Introduction

Novel creation is currently an implicit side-effect of the scrape operation. When an owner calls `POST /{novel_id}/scrape`, `scrape_metadata` writes `metadata.json` to file storage under a derived folder path. The DB row (`novels` table) is created separately and lazily by calling `POST /{novel_id}/refresh-catalog-projection`. There is no single, documented, owner-only endpoint that atomically creates both the storage record and the DB row. There is also no pre-existence guard on the scrape endpoint, so any well-formed `novel_id` can trigger a scrape without a prior explicit creation step.

The result is a lifecycle with two gaps. First, the "add a novel" user story has no canonical entry point — operators must know the implicit create-via-scrape pattern and then remember to call refresh-catalog-projection to get a usable DB row. Second, there is no end-to-end integration test that walks from creation to public chapter read, making lifecycle regressions silent until production.

This spec adds a canonical `POST /novels` create endpoint, wires automatic DB row creation into the scrape path, and adds the explicit integration test that proves the full lifecycle works deterministically.

## Requirements

### REQ-1: Canonical Create-Novel Endpoint

An owner-only endpoint must exist that explicitly creates a novel record as the first step before any scraping or translation.

- REQ-1.1: A new endpoint `POST /api/admin/novels` must be added to `backend/src/novelai/api/routers/library.py` (or a new novels router). It must be owner-only.
- REQ-1.2: The request body must accept: `novel_id: str` (the storage key slug), `title: str`, `source_url: str | None = None`, `source_key: str | None = None`, `language: str = "ja"`.
- REQ-1.3: The endpoint must validate `novel_id` using the existing `validate_storage_identifier` function. Return HTTP 422 on invalid slug.
- REQ-1.4: If a novel with `novel_id` already exists in storage (i.e. `storage.load_metadata(novel_id)` returns non-None) OR in the DB (i.e. `db.query(Novel).filter_by(slug=novel_id).one_or_none()` returns non-None), return HTTP 409 Conflict with message `"Novel already exists"`.
- REQ-1.5: The endpoint must write a minimal `metadata.json` to storage via `storage.save_metadata(novel_id, minimal_metadata_dict)` containing: `novel_id`, `title`, `source_url`, `source_key`, `language`, `origin_type` (`"url"` when `source_url` is present, else `"library"`), `chapters: []`.
- REQ-1.6: The endpoint must create the DB `Novel` row via `CatalogService.get_or_create_novel(novel_id, minimal_metadata)` in the same DB session.
- REQ-1.7: The response must return: `novel_id`, `title`, `source_url`, `source_key`, `language`, `created_at` (ISO string), `db_id` (the integer primary key of the created `Novel` row).
- REQ-1.8: The endpoint must be idempotent for the DB row: if the storage record was created but the DB row creation failed, a retry must succeed (the DB `get_or_create_novel` must not error on an existing storage record with no DB row).

### REQ-2: Automatic DB Row Creation After Scrape

When a scrape operation successfully writes metadata to storage, the DB `Novel` row must be created or updated automatically.

- REQ-2.1: `OperationsService.scrape_novel` must call `CatalogService.reconcile_catalog_projection(novel_id)` (or `get_or_create_novel`) after `scrape_metadata` completes successfully.
- REQ-2.2: The DB reconciliation must be best-effort: if it fails, the scrape result must still be returned successfully and the failure must be logged at `WARNING` level.
- REQ-2.3: The same automatic reconciliation must apply to `OperationsService.preliminary_crawl_novel` — after the preliminary crawl writes metadata, the DB row must be created/updated.
- REQ-2.4: This is additive: operators who already call `refresh-catalog-projection` manually will see no change. The automatic reconciliation and the manual endpoint both converge on the same DB state.

### REQ-3: `translate_novel` Returns Meaningful Error on Missing Novel

When `translate_novel` is called for a `novel_id` that does not exist in storage, it must return a clear error.

- REQ-3.1: The existing `OperationError(404, "Novel not found")` guard in `OperationsService.translate_novel` must remain. This req confirms and locks the behavior.
- REQ-3.2: The error response must include `novel_id` in the detail: `{"error": "Novel not found", "novel_id": "..."}`.
- REQ-3.3: A test must confirm this guard fires when `storage.load_metadata` returns `None`.

### REQ-4: End-to-End Lifecycle Integration Test

An integration test must prove the full owner-driven lifecycle from creation to public chapter read.

- REQ-4.1: A new test file `backend/tests/test_novel_lifecycle_integration.py` must be created.
- REQ-4.2: `test_create_to_public_read_lifecycle` must execute these steps against real filesystem fixtures (using `tmp_path`):
  1. `POST /api/admin/novels` with a minimal `novel_id`, `title`, `source_url` → assert HTTP 201 and `db_id` in response
  2. Simulate metadata write (as if scrape completed): call `storage.save_metadata(novel_id, {...with chapters...})` directly
  3. `POST /{novel_id}/refresh-catalog-projection` → assert HTTP 200 and `changed_fields` includes chapter projection fields
  4. Simulate chapter translation: call `storage.save_translated_chapter(novel_id, chapter_id, text)` directly
  5. `POST /{novel_id}/refresh-catalog-projection` again → assert `translated_count = 1`
  6. `GET /api/public/catalog` → assert the novel appears in the list
  7. `GET /api/public/novels/{slug}/chapters/{chapter_id}` → assert HTTP 200 and `text` in response
- REQ-4.3: The test must not make any real HTTP requests to source sites (all scrape-like operations use storage stubs).
- REQ-4.4: The test must cover the 409 conflict path: a second `POST /api/admin/novels` with the same `novel_id` → HTTP 409.

### REQ-5: Permission and Audit Tests

- REQ-5.1: A test must confirm that `POST /api/admin/novels` returns HTTP 403 for unauthenticated callers.
- REQ-5.2: A test must confirm that the created `Novel` DB row has `is_published=False`, `glossary_status="glossary_pending"`, and `language` matching the request.
- REQ-5.3: A test must confirm that `POST /api/admin/novels` with an invalid `novel_id` (e.g. `"../../../etc"` or empty string) returns HTTP 422.

### REQ-6: Migration and Existing Novels Compatibility

- REQ-6.1: The new create endpoint must not affect or invalidate any existing storage novels or DB rows.
- REQ-6.2: All pre-existing novels that were created via the scrape-then-refresh-catalog-projection pattern must continue to work without migration.
- REQ-6.3: The automatic DB reconciliation added in REQ-2 must not break existing callers who already call `refresh-catalog-projection` manually.

## Non-Goals

- This spec does not add a frontend UI for novel creation.
- This spec does not add ownership transfer or novel deletion endpoints.
- This spec does not change how scraping or translation works internally.
- This spec does not add rate limiting beyond what already exists.
- This spec does not make `POST /{novel_id}/scrape` require a prior create call. The implicit create-via-scrape pattern remains valid for backward compatibility.
