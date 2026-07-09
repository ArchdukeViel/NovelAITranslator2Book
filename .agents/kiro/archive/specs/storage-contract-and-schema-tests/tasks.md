# Tasks: Storage Contract and Schema Tests

## Task List

- [x] 1. Preflight Storage Contract Review
  - [x] 1.1 Inspect `backend/src/novelai/storage/novels.py` for metadata paths, backup paths, metadata history, and loader behavior.
  - [x] 1.2 Inspect `backend/src/novelai/storage/chapters.py` for raw chapter bundle paths, schema, image manifest fields, and provenance fields.
  - [x] 1.3 Inspect `backend/src/novelai/storage/translations.py` for translated chapter version storage, active version selection, and edit history.
  - [x] 1.4 Inspect image asset storage helpers such as `save_chapter_image_asset` and `clear_chapter_image_assets`.
  - [x] 1.5 Inspect catalog projection refresh code to understand DB-vs-file ownership boundaries.
  - [x] 1.6 Inspect existing storage tests and fixtures to reuse conventions.
  - [x] 1.7 Identify whether docs should live under `docs/` or `backend/docs/`.

- [x] 2. Create Storage Contract Document
  - [x] 2.1 Create `docs/storage-contract.md` or `backend/docs/storage-contract.md`. (REQ-1.1)
  - [x] 2.2 Add overview of canonical file storage vs PostgreSQL projection. (REQ-1.8)
  - [x] 2.3 Add artifact index table with artifact, ownership, writer, reader, and notes. (REQ-1)
  - [x] 2.4 Document novel metadata storage contract. (REQ-1.2)
  - [x] 2.5 Document metadata backup storage contract. (REQ-1.3)
  - [x] 2.6 Document raw chapter bundle storage contract. (REQ-1.4)
  - [x] 2.7 Document chapter image asset and image manifest contract. (REQ-1.7)
  - [x] 2.8 Document translated chapter version storage and active-version semantics. (REQ-1.5)
  - [x] 2.9 Document translation edit history storage contract. (REQ-1.6)
  - [x] 2.10 Document compatibility rules for legacy and additive fields. (REQ-1.9)
  - [x] 2.11 Document migration and repair notes. (REQ-8)

- [x] 3. Add Synthetic Legacy Fixtures
  - [x] 3.1 Create `backend/tests/fixtures/storage_contract/`. (REQ-6)
  - [x] 3.2 Add `legacy_metadata.json` with minimal synthetic metadata. (REQ-6.1)
  - [x] 3.3 Add `legacy_chapter_bundle.json` with minimal synthetic raw chapter data. (REQ-6.2)
  - [x] 3.4 Add `legacy_translation_bundle.json` with minimal synthetic translated version data. (REQ-6.3)
  - [x] 3.5 Add `legacy_edit_history.json` if edit history schema is stable and known. (REQ-6.4)
  - [x] 3.6 Ensure fixtures contain no copyrighted text. (REQ-6.5)
  - [x] 3.7 Keep fixtures minimal and focused on compatibility.

- [x] 4. Create Storage Contract Test Module
  - [x] 4.1 Create `backend/tests/test_storage_contracts.py`. (REQ-9.1)
  - [x] 4.2 Reuse existing temp storage fixtures where available.
  - [x] 4.3 Reuse existing `StorageService` construction helpers where available.
  - [x] 4.4 Avoid real network, crawler, or translation provider calls.

- [x] 5. Add Test-Only Schema Assertion Helpers
  - [x] 5.1 Add `assert_metadata_contract(payload)` helper. (REQ-7.1)
  - [x] 5.2 Add `assert_raw_chapter_contract(payload)` helper. (REQ-7.2)
  - [x] 5.3 Add `assert_translation_version_contract(payload)` helper. (REQ-7.3)
  - [x] 5.4 Add `assert_edit_history_contract(payload)` helper. (REQ-7.4)
  - [x] 5.5 Keep helpers test-only unless the project already has runtime validation patterns. (REQ-7.6)
  - [x] 5.6 Do not add a heavy JSON schema dependency unless already used. (REQ-7.5)

- [x] 6. Write Metadata Contract Tests
  - [x] 6.1 Test novel metadata path generation or helper-owned round trip. (REQ-3.1)
  - [x] 6.2 Test `save_metadata` then `load_metadata` preserves required fields. (REQ-5.1)
  - [x] 6.3 Test metadata schema required and optional fields. (REQ-4.1)
  - [x] 6.4 Test additive unknown fields are preserved or ignored according to current loader behavior. (REQ-4.8)
  - [x] 6.5 Test legacy metadata fixture loads successfully. (REQ-6.6)

- [x] 7. Write Metadata Backup Contract Tests
  - [x] 7.1 Test metadata backup path pattern. (REQ-3.2)
  - [x] 7.2 Test metadata backup ordering is deterministic and newest-first or matches existing behavior. (REQ-3.2)
  - [x] 7.3 Test metadata backup schema shape. (REQ-1.3)
  - [x] 7.4 Test backup retention behavior if existing tests do not already cover it.

- [x] 8. Write Raw Chapter Bundle Contract Tests
  - [x] 8.1 Test raw chapter bundle path generation or helper-owned round trip. (REQ-3.3, REQ-3.8)
  - [x] 8.2 Test `save_chapter` then `load_chapter` preserves text, paragraphs, and images. (REQ-5.2)
  - [x] 8.3 Test required `raw` fields: `id`, `scraped_at`, `text`, `paragraphs`, `images`. (REQ-4.2)
  - [x] 8.4 Test optional `raw.source_blocks` when present. (REQ-4.2)
  - [x] 8.5 Test provenance fields such as `source_key`, `source_url`, `origin_type`, `document_type`, `input_adapter_key`, and `context_group_id` when present. (REQ-4.3)
  - [x] 8.6 Test legacy raw chapter fixture loads successfully. (REQ-6.6)

- [x] 9. Write Image Asset and Manifest Contract Tests
  - [x] 9.1 Test image asset path generation or helper-owned round trip. (REQ-3.6, REQ-3.8)
  - [x] 9.2 Test image manifest entries preserve source URL and saved asset metadata where available. (REQ-4.6)
  - [x] 9.3 Test manifest entries can represent `download_error`. (REQ-4.6)
  - [x] 9.4 Test image asset APIs through existing storage helpers, not direct filesystem assumptions where possible. (REQ-5.7)

- [x] 10. Write Translation Version Contract Tests
  - [x] 10.1 Test translated chapter storage path generation or helper-owned round trip. (REQ-3.4, REQ-3.8)
  - [x] 10.2 Test `save_translated_chapter` then `load_translated_chapter` preserves active version text and metadata. (REQ-5.3)
  - [x] 10.3 Test `list_translated_chapter_versions` returns all saved versions in deterministic order. (REQ-5.4)
  - [x] 10.4 Test activating a version changes active version without deleting older versions. (REQ-5.5)
  - [x] 10.5 Test translated version schema fields such as version ID, kind, provider, model, timestamps, text, and active state. (REQ-4.4)
  - [x] 10.6 Test legacy translation fixture loads successfully. (REQ-6.6)

- [x] 11. Write Edit History Contract Tests
  - [x] 11.1 Test edit history path generation or helper-owned round trip. (REQ-3.5, REQ-3.8)
  - [x] 11.2 Test `save_edited_translation` then `load_translation_edit_history` preserves edit records. (REQ-5.6)
  - [x] 11.3 Test edit history schema fields such as text, editor, note/reason, timestamp, and base version when available. (REQ-4.5)
  - [x] 11.4 Test legacy edit history fixture loads successfully if fixture exists. (REQ-6.6)

- [x] 12. Add PostgreSQL vs File Storage Documentation Checks
  - [x] 12.1 Document SQL `Novel` row ownership versus file metadata ownership. (REQ-8.5)
  - [x] 12.2 Document SQL `Chapter` row status/storage-key projection versus raw/translated file bundles. (REQ-8.5)
  - [x] 12.3 Document glossary SQL ownership separately from file translation artifacts. (REQ-8.5)
  - [x] 12.4 Document catalog projection refresh as the preferred repair path for stale SQL projection where applicable. (REQ-8.6)

- [x] 13. Backward Compatibility Checks
  - [x] 13.1 Confirm no database migration files were created. (REQ-2.1)
  - [x] 13.2 Confirm no storage JSON schema changes were introduced. (REQ-2.2)
  - [x] 13.3 Confirm path helpers remain the source of truth for path generation. (REQ-2.3)
  - [x] 13.4 Confirm older fixture artifacts load through current loaders. (REQ-2.4, REQ-6.6)
  - [x] 13.5 Confirm current writers still emit fields required by current readers. (REQ-2.5)

- [x] 14. Run Verification
  - [x] 14.1 Run `pytest backend/tests/test_storage_contracts.py --tb=short -q`.
  - [x] 14.2 Run existing storage test suite, if present. (REQ-9.9)
  - [x] 14.3 Run `ruff check` on the new test module and any touched docs-related support files.
  - [x] 14.4 Run the configured backend type checker if Python helpers were added outside tests.
  - [x] 14.5 Fix test, lint, and type failures caused by this work.

- [x] 15. Final Acceptance Review
  - [x] 15.1 Verify storage contract document describes all major file/JSON artifacts. (REQ-1)
  - [x] 15.2 Verify contract tests cover path generation or observable helper-owned round trips. (REQ-3)
  - [x] 15.3 Verify contract tests cover schema shapes for metadata, raw chapters, translation versions, edit history, and image manifests. (REQ-4)
  - [x] 15.4 Verify save/load round trips pass for each major storage artifact. (REQ-5)
  - [x] 15.5 Verify legacy synthetic fixtures load successfully. (REQ-6)
  - [x] 15.6 Verify tests distinguish required, optional, and additive fields. (REQ-4.7, REQ-4.8)
  - [x] 15.7 Verify no storage schemas or DB schemas changed. (REQ-2)
  - [x] 15.8 Verify focused and existing storage tests pass. (REQ-9)

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Document Canonical Storage Contracts | 1, 2, 12, 15 |
| REQ-2 Preserve Existing Layout and Schemas | 2, 6-13, 15 |
| REQ-3 Path Generation Tests | 6, 7, 8, 9, 10, 11 |
| REQ-4 JSON Schema Shape Tests | 5, 6, 8, 9, 10, 11, 15 |
| REQ-5 Round-Trip Compatibility Tests | 6, 8, 9, 10, 11 |
| REQ-6 Legacy Fixture Compatibility | 3, 6, 8, 10, 11, 13 |
| REQ-7 Validation Helpers | 5 |
| REQ-8 Migration and Repair Safety Notes | 2, 12 |
| REQ-9 Tests | 4, 6-11, 14, 15 |

## Definition of Done

- [x] Storage contract document exists.
- [x] Major file/JSON artifacts are documented with owner, writer, reader, schema outline, and compatibility notes.
- [x] PostgreSQL projection versus canonical file storage is documented.
- [x] Contract tests cover metadata, backups, raw chapters, images, translation versions, and edit history.
- [x] Legacy synthetic fixtures are present and load through current loaders.
- [x] Tests use storage helpers rather than ad hoc path construction where possible.
- [x] No DB migration or storage schema change is introduced.
- [x] Focused and existing storage tests pass.

