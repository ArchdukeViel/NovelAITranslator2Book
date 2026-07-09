# Requirements: Storage Contract and Schema Tests

## Introduction

NovelAITranslator2Book uses a hybrid persistence model: PostgreSQL stores structured state and searchable projections, while file/JSON storage stores the heavier canonical artifacts such as novel metadata, raw chapter bundles, translated chapter versions, edit history, metadata backups, and image manifests. The deep research reports found that the storage layer clearly has helper-managed paths and versioned translation artifacts, but the exact on-disk contract is not documented in one place and is not clearly locked by tests.

This spec adds explicit storage contract documentation and contract tests for the existing storage layout. The goal is to make backups, migrations, repair scripts, and future refactors safer without changing the current storage schema.

## Requirements

### REQ-1: Document Canonical Storage Contracts

The project must include a storage contract document describing the file artifacts the backend owns.

- REQ-1.1: Create a storage contract document under the repository documentation or backend documentation area.
- REQ-1.2: The document must describe novel metadata storage, including path, ownership, writer, reader, and schema outline.
- REQ-1.3: The document must describe metadata backup storage, including path pattern, retention behavior, writer, reader, and schema outline.
- REQ-1.4: The document must describe raw chapter bundle storage, including helper-owned path, writer, reader, and schema outline.
- REQ-1.5: The document must describe translated chapter/version storage, including active version semantics, writer, reader, and schema outline.
- REQ-1.6: The document must describe translation edit history storage, including writer, reader, and schema outline.
- REQ-1.7: The document must describe chapter image asset storage and image manifest metadata.
- REQ-1.8: The document must explicitly state which data belongs in PostgreSQL versus file/JSON storage.
- REQ-1.9: The document must include compatibility notes for readers of older storage artifacts.

### REQ-2: Preserve Existing Storage Layout and Schemas

This spec must document and test the current contract, not redesign storage.

- REQ-2.1: No database migration may be introduced.
- REQ-2.2: Existing JSON file formats must remain backward compatible.
- REQ-2.3: Existing path helpers must remain the source of truth for path generation.
- REQ-2.4: Existing readers must continue loading artifacts written before this spec.
- REQ-2.5: Existing writers must continue emitting fields required by current readers.
- REQ-2.6: Any optional new metadata added for documentation/testing must be additive and ignored safely by older readers.

### REQ-3: Contract Tests for Path Generation

Storage path generation must be covered by tests.

- REQ-3.1: Add tests for novel metadata path generation.
- REQ-3.2: Add tests for metadata backup path pattern and ordering.
- REQ-3.3: Add tests for raw chapter bundle path generation.
- REQ-3.4: Add tests for translated chapter/version path generation or helper-owned storage location.
- REQ-3.5: Add tests for edit history path generation or helper-owned storage location.
- REQ-3.6: Add tests for image asset path generation or helper-owned storage location.
- REQ-3.7: Tests must use the existing storage helper APIs rather than hard-coding private path strings when possible.
- REQ-3.8: If exact paths are intentionally private, tests must assert observable round-trip behavior and document that the path is helper-owned.

### REQ-4: Contract Tests for JSON Schema Shape

The expected JSON shapes must be locked by tests.

- REQ-4.1: Add tests for `metadata.json` required and optional top-level fields.
- REQ-4.2: Add tests for raw chapter bundle schema, including `raw.id`, `raw.scraped_at`, `raw.text`, `raw.paragraphs`, `raw.images`, and optional `raw.source_blocks`.
- REQ-4.3: Add tests for chapter-level provenance fields such as `source_key`, `source_url`, `origin_type`, `origin_uri_or_path`, `document_type`, `unit_type`, `input_adapter_key`, `context_group_id`, `import_order`, `region_metadata`, and `ocr_artifacts` when present.
- REQ-4.4: Add tests for translated chapter version schema, including active version metadata and version list behavior.
- REQ-4.5: Add tests for edit history schema.
- REQ-4.6: Add tests for image manifest entries, including downloaded asset metadata and download error fields.
- REQ-4.7: Tests must distinguish required fields from optional fields.
- REQ-4.8: Tests must allow additive fields unless the reader contract explicitly rejects them.

### REQ-5: Round-Trip Compatibility Tests

Each major storage artifact must have save/load round-trip tests.

- REQ-5.1: Saving and loading novel metadata must preserve required fields.
- REQ-5.2: Saving and loading raw chapters must preserve text, paragraphs, images, and provenance.
- REQ-5.3: Saving and loading translated chapters must preserve active version selection and version metadata.
- REQ-5.4: Listing translated chapter versions must return all saved versions in a deterministic order.
- REQ-5.5: Activating a translated chapter version must update the active version without deleting older versions.
- REQ-5.6: Saving edited translations must append or preserve edit history according to existing behavior.
- REQ-5.7: Image asset save/load or manifest update behavior must be tested through existing storage APIs.

### REQ-6: Backward-Compatible Loader Fixtures

The project must include legacy fixture samples for storage compatibility.

- REQ-6.1: Add minimal fixture JSON for a legacy `metadata.json`.
- REQ-6.2: Add minimal fixture JSON for a legacy raw chapter bundle.
- REQ-6.3: Add minimal fixture JSON for a legacy translated chapter bundle/version list.
- REQ-6.4: Add minimal fixture JSON for edit history if the format is stable and known.
- REQ-6.5: Fixture files must not contain copyrighted novel text; use synthetic text.
- REQ-6.6: Tests must verify current loaders can read these fixtures.
- REQ-6.7: If a legacy shape requires normalization, tests must assert the normalized output.

### REQ-7: Storage Contract Validation Helpers

Reusable validation helpers should make contract tests clear and maintainable.

- REQ-7.1: Add test helpers or lightweight schema assertions for metadata documents.
- REQ-7.2: Add schema assertions for raw chapter bundles.
- REQ-7.3: Add schema assertions for translation version bundles.
- REQ-7.4: Add schema assertions for edit history.
- REQ-7.5: Avoid introducing a heavy runtime JSON schema dependency unless the project already uses one.
- REQ-7.6: Validation helpers must be test-only unless the codebase already has a runtime validation pattern.

### REQ-8: Migration and Repair Tool Safety Notes

The storage contract document must help future maintainers write migrations safely.

- REQ-8.1: Document canonical writer and reader functions for each artifact.
- REQ-8.2: Document whether an artifact is canonical storage, derived projection, cache, backup, or asset.
- REQ-8.3: Document whether missing optional fields should be defaulted by loaders.
- REQ-8.4: Document whether additive fields are allowed.
- REQ-8.5: Document how SQL projection state relates to file storage.
- REQ-8.6: Document manual recovery notes for corrupted metadata and stale translation versions.

### REQ-9: Tests

Focused tests must lock the storage contract.

- REQ-9.1: Create a new test module for storage contract tests.
- REQ-9.2: Add metadata path and schema tests.
- REQ-9.3: Add metadata backup path/order tests.
- REQ-9.4: Add raw chapter bundle round-trip and schema tests.
- REQ-9.5: Add translated chapter version round-trip and active-version tests.
- REQ-9.6: Add edit history tests.
- REQ-9.7: Add image manifest/asset tests where existing APIs support it.
- REQ-9.8: Add legacy fixture loader tests.
- REQ-9.9: Run existing storage tests to confirm no behavior changed.

## Non-Goals

- This spec does not change storage schemas.
- This spec does not add a database migration.
- This spec does not implement atomic writes; that belongs to `atomic-json-storage-recovery`.
- This spec does not redesign file storage paths.
- This spec does not add a migration framework.
- This spec does not add public API endpoints.
- This spec does not change crawl, translation, glossary, or reader behavior.

