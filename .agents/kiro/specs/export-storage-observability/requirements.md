# Requirements: Export Storage Observability

## Introduction

The repository supports export functionality for formats such as EPUB, HTML, and Markdown, but the deep research reports did not fully surface the export artifact paths, sidecar schemas, or operational visibility. Export is downstream of crawling, translation, editing, glossary policy, and active-version selection, so failures or stale exports can confuse users even when the translation pipeline itself works.

This spec adds observability and contract coverage for exported artifacts. The implementation must first inspect the actual export service and storage paths, then persist compact export manifests and expose export status through admin/activity surfaces.

## Requirements

### REQ-1: Export Path and Artifact Inventory

The implementation must identify and document existing export artifacts before changing code.

- REQ-1.1: Inspect the existing `ExportService` or equivalent export implementation.
- REQ-1.2: Identify supported export formats such as EPUB, HTML, Markdown, or other existing formats.
- REQ-1.3: Identify where export files are written.
- REQ-1.4: Identify any existing sidecar metadata files, manifests, temporary files, and cleanup behavior.
- REQ-1.5: Identify which code reads/downloads export artifacts.
- REQ-1.6: Do not invent path contracts before inspecting the current implementation.

### REQ-2: Export Manifest

Each completed export must have a compact manifest or equivalent metadata record.

- REQ-2.1: Manifest must include `export_id`.
- REQ-2.2: Manifest must include `novel_id`.
- REQ-2.3: Manifest must include `format`.
- REQ-2.4: Manifest must include output filename or storage key.
- REQ-2.5: Manifest must include file size in bytes when available.
- REQ-2.6: Manifest must include content hash/checksum when practical.
- REQ-2.7: Manifest must include created timestamp.
- REQ-2.8: Manifest must include source chapter count and exported chapter count.
- REQ-2.9: Manifest must include active translation version IDs or a bounded summary of versions used.
- REQ-2.10: Manifest must include export status: `pending`, `running`, `succeeded`, `failed`, or `deleted`.

### REQ-3: Export Version and Freshness Tracking

Exports must be traceable to the input state used to create them.

- REQ-3.1: Manifest must record the novel metadata revision or metadata updated timestamp when available.
- REQ-3.2: Manifest must record translation version IDs used for exported chapters where practical.
- REQ-3.3: Manifest should record glossary revision/hash if glossary metadata is available.
- REQ-3.4: Manifest should record export options that affect output, such as format, title mode, chapter range, image inclusion, and style/template.
- REQ-3.5: Admin APIs should be able to report whether an export is stale relative to current metadata, active translation versions, or glossary revision where supported.
- REQ-3.6: Stale detection must not delete or overwrite old exports automatically.

### REQ-4: Export Activity Metadata

Export activities must expose progress and result details.

- REQ-4.1: Export activity metadata must include export format.
- REQ-4.2: Export activity metadata must include progress counts when export processes chapters.
- REQ-4.3: Export activity metadata must include final output artifact reference on success.
- REQ-4.4: Export activity metadata must include failure category and safe message on failure.
- REQ-4.5: Export activity metadata must not include full chapter text.
- REQ-4.6: Existing activity records without export metadata must remain loadable.

### REQ-5: Export Failure Classification

Export failures must be categorized.

- REQ-5.1: Include `missing_translation` when an exported chapter lacks required translated content.
- REQ-5.2: Include `missing_asset` when required image/assets are unavailable.
- REQ-5.3: Include `render_error` when output generation fails.
- REQ-5.4: Include `write_error` when artifact write fails.
- REQ-5.5: Include `invalid_options` when export request options are invalid.
- REQ-5.6: Include `unknown` for unexpected failures.
- REQ-5.7: Failure messages must be safe and must not include full chapter text or secrets.

### REQ-6: Admin Export APIs

Admins must be able to inspect export artifacts and status.

- REQ-6.1: Admin novel detail or export route must list available export artifacts.
- REQ-6.2: Each listed export must include manifest fields and stale status where available.
- REQ-6.3: Admin API must expose latest export per format.
- REQ-6.4: Admin API must expose failed export attempts where activity metadata exists.
- REQ-6.5: Strict response models must be updated if they would otherwise drop export fields.
- REQ-6.6: Public APIs must not expose unpublished export artifacts.

### REQ-7: Admin UI Visibility

Admin UI must make export status understandable.

- REQ-7.1: Novel/admin UI must show available export formats and latest artifact time.
- REQ-7.2: UI must show export status: running, succeeded, failed, stale.
- REQ-7.3: UI must show exported chapter count.
- REQ-7.4: UI must show stale reason when available.
- REQ-7.5: UI must show safe failure message for failed exports.
- REQ-7.6: UI may provide re-export action using existing export flow.

### REQ-8: Storage Contract and Cleanup

Export storage behavior must be documented and tested.

- REQ-8.1: Document export artifact paths or helper-owned storage contract.
- REQ-8.2: Document export manifest schema.
- REQ-8.3: Document temporary file behavior.
- REQ-8.4: Document whether old exports are retained, replaced, or pruned.
- REQ-8.5: Tests must prove export artifacts and manifests are written in expected locations or round-trip through helper APIs.
- REQ-8.6: If cleanup/delete export exists, tests must prove manifest status changes or files are removed according to current behavior.

### REQ-9: Backward Compatibility

Existing export behavior must remain compatible.

- REQ-9.1: Existing export formats must still generate.
- REQ-9.2: Existing download routes must still work.
- REQ-9.3: Existing export artifacts without manifests must remain accessible if current behavior supports them.
- REQ-9.4: New manifest/metadata fields must be additive.
- REQ-9.5: No public reader behavior changes are allowed.

### REQ-10: Tests

Focused tests must cover export artifacts, manifests, failures, and admin visibility.

- REQ-10.1: Test export writes artifact and manifest.
- REQ-10.2: Test manifest records format, file size, chapter count, and version inputs.
- REQ-10.3: Test latest export per format is discoverable.
- REQ-10.4: Test stale detection when active translation version changes.
- REQ-10.5: Test failure classification for missing translation.
- REQ-10.6: Test failure classification for write/render error using fakes/mocks.
- REQ-10.7: Test existing legacy export artifact remains accessible.
- REQ-10.8: Test admin API exposes export metadata.
- REQ-10.9: Test public APIs do not expose unpublished export artifacts.
- REQ-10.10: Test UI export status rendering if frontend changes.

## Non-Goals

- This spec does not redesign export output formats.
- This spec does not implement a new EPUB/HTML/Markdown renderer.
- This spec does not publish exports publicly by default.
- This spec does not change translation version selection rules.
- This spec does not replace storage contract tests for core chapter/translation storage.
- This spec does not require cloud object storage.

