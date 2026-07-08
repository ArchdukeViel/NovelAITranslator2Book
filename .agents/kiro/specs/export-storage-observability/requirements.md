# Requirements: Export Storage Observability

## Introduction

The backend supports export functionality for formats such as EPUB, HTML, Markdown, or other configured formats. Export is downstream of crawling, translation, editing, glossary policy, active-version selection, metadata, templates, and asset storage. When exports fail, become stale, or are stored in unclear locations, admins have limited visibility into what happened.

This spec adds storage-backend-safe observability and contract coverage for export artifacts. The implementation must first inspect the current export service, artifact paths, storage helpers, download routes, and activity flow before introducing or testing any manifest contract.

This work must align with the existing storage backend abstraction and storage contract tests. It must not leak local filesystem paths, S3 bucket internals, signed URLs, credentials, prompts, source text, or translated chapter text.

## Scope

In scope:

- Reviewing and documenting current export paths and artifact behavior.
- Writing compact export manifests for new completed exports.
- Recording safe export progress, success, and failure metadata in activity records.
- Exposing export artifacts, latest exports, failure state, and stale state in admin APIs.
- Showing export status, stale reasons, failures, legacy state, and re-export actions in admin UI.
- Computing export freshness from current metadata, active translation versions, glossary state, assets, and export options where available.
- Adding storage-backend-safe helper coverage for manifest read/write/list behavior.
- Preserving existing export/download behavior.

Out of scope:

- Redesigning export output formats.
- Implementing new EPUB/HTML/Markdown renderers.
- Changing public reader availability.
- Changing active translation version selection.
- Changing translation version storage schemas.
- Changing glossary revision behavior.
- Changing scheduler/provider behavior.
- Rewriting legacy export artifacts.
- Publishing exports publicly by default.
- Replacing core storage contract tests for chapter and translation storage.

## Requirements

### REQ-1: Inspect and Document Existing Export Behavior

The implementation must identify current export behavior before changing production code.

- REQ-1.1: Inspect the existing `ExportService` or equivalent export implementation.
- REQ-1.2: Identify all supported export formats.
- REQ-1.3: Identify where export artifacts are currently written.
- REQ-1.4: Identify whether export paths currently use direct filesystem paths or storage backend abstractions.
- REQ-1.5: Identify existing sidecar metadata, manifests, temporary files, and cleanup behavior.
- REQ-1.6: Identify existing export activity/job flow.
- REQ-1.7: Identify existing export download routes.
- REQ-1.8: Identify existing admin export or novel-detail API fields.
- REQ-1.9: Document the current behavior before locking new tests.
- REQ-1.10: Do not invent path contracts before inspecting the current implementation.

### REQ-2: Use Storage-Backend-Safe Export Keys

Export observability must work across supported storage backends.

- REQ-2.1: Manifest and activity metadata must use storage-backend-safe keys instead of local absolute paths.
- REQ-2.2: Export code must use existing `StorageBackend` or storage helper APIs where available.
- REQ-2.3: New export storage helpers may be added only if they can be implemented for every supported backend.
- REQ-2.4: Export observability must not assume POSIX rename semantics for object storage.
- REQ-2.5: Export observability must not expose raw S3 bucket names, storage provider internals, or local filesystem paths.
- REQ-2.6: Temporary render files must not appear in listed exports.
- REQ-2.7: Existing download routes must remain valid.

### REQ-3: Write Export Manifests for Completed Exports

Each completed new export must have a compact manifest or equivalent metadata record.

- REQ-3.1: Successful exports must write a manifest.
- REQ-3.2: Manifest must include `export_id`.
- REQ-3.3: Manifest must include `novel_id`.
- REQ-3.4: Manifest must include `format`.
- REQ-3.5: Manifest must include export `status`.
- REQ-3.6: Manifest must include output filename.
- REQ-3.7: Manifest must include storage-safe `artifact_key`.
- REQ-3.8: Manifest must include storage-safe `manifest_key`.
- REQ-3.9: Manifest should include storage backend identifier only if safe and already consistent with storage admin patterns.
- REQ-3.10: Manifest must include created timestamp.
- REQ-3.11: Manifest should include completed timestamp when available.
- REQ-3.12: Manifest must include source chapter count and exported chapter count.
- REQ-3.13: Manifest must include file size in bytes when available.
- REQ-3.14: Manifest should include content hash/checksum when practical.
- REQ-3.15: Manifest must be written through storage helpers and atomic JSON write behavior where supported.

### REQ-4: Record Export Input State

Exports must be traceable to the input state used to create them.

- REQ-4.1: Manifest must record active translation version IDs used for exported chapters where practical.
- REQ-4.2: If storing every chapter/version pair would make the manifest too large, manifest must store a bounded sample plus `translation_version_count` and `translation_versions_hash`.
- REQ-4.3: Manifest must record novel metadata revision or metadata updated timestamp when available.
- REQ-4.4: Manifest should record glossary revision when available.
- REQ-4.5: Manifest should record glossary hash when available.
- REQ-4.6: Manifest should record asset manifest hash when available.
- REQ-4.7: Manifest must record export options that affect output.
- REQ-4.8: Export options may include format, title mode, chapter range, image inclusion, template, style, and template version.
- REQ-4.9: Input state must be derived from existing storage and metadata APIs.
- REQ-4.10: Input state must not store full chapter text.

### REQ-5: Support Export Status Values

Export status must use stable values.

- REQ-5.1: Support `pending` for requested exports not yet started.
- REQ-5.2: Support `running` for exports currently generating.
- REQ-5.3: Support `succeeded` for exports whose artifact was written and verified.
- REQ-5.4: Support `failed` for exports where no valid artifact was produced.
- REQ-5.5: Support `deleted` for artifacts removed by cleanup/delete operations where such operations exist.
- REQ-5.6: Support `legacy_unknown` for discoverable legacy artifacts without manifests.
- REQ-5.7: Completed successful export manifests should normally use `succeeded`.
- REQ-5.8: `pending` and `running` may live primarily in activity metadata.

### REQ-6: Classify Export Failures

Export failures must be categorized with safe messages.

- REQ-6.1: Include `missing_translation` when a required chapter has no translated content.
- REQ-6.2: Include `missing_asset` when a required image or asset is unavailable.
- REQ-6.3: Include `render_error` when output generation fails.
- REQ-6.4: Include `write_error` when artifact or manifest write fails.
- REQ-6.5: Include `verify_error` when artifact verification fails after write.
- REQ-6.6: Include `storage_error` when a storage backend operation fails.
- REQ-6.7: Include `invalid_options` when export request options are invalid.
- REQ-6.8: Include `unknown` for unexpected failures.
- REQ-6.9: Failure messages must be concise and safe.
- REQ-6.10: Failure metadata must not include stack traces, full chapter text, prompts, provider responses, local paths, secrets, or storage credentials.

### REQ-7: Verify Export Artifacts

Successful exports should be verified before being marked as completed.

- REQ-7.1: Verify artifact existence after write where supported.
- REQ-7.2: Verify file size where supported.
- REQ-7.3: Verify checksum/hash where practical.
- REQ-7.4: Verify manifest write completed.
- REQ-7.5: Verification failure must produce `verify_error` or `storage_error`.
- REQ-7.6: Verification must not require loading very large artifacts into memory when storage metadata APIs can provide size/hash.
- REQ-7.7: Checksum generation may be optional when too expensive or unsupported by a backend, but this must be documented.

### REQ-8: Compute Export Freshness

Admin APIs must be able to report whether an export is stale where data is available.

- REQ-8.1: Add or reuse a helper such as `compute_export_freshness`.
- REQ-8.2: Freshness must compare manifest input state against current input state.
- REQ-8.3: Mark stale with `translation_version_changed` when current active translated version differs from exported version.
- REQ-8.4: Mark stale with `metadata_changed` when novel metadata changed after export.
- REQ-8.5: Mark stale with `glossary_revision_changed` when current glossary revision is newer than exported glossary revision.
- REQ-8.6: Mark stale with `glossary_hash_changed` when current glossary hash differs from exported glossary hash.
- REQ-8.7: Mark stale with `export_options_changed` when relevant export options differ.
- REQ-8.8: Mark stale with `template_version_changed` when export template version changed.
- REQ-8.9: Mark stale with `asset_manifest_changed` when exported assets differ from current asset state.
- REQ-8.10: Mark stale with `unknown_legacy_manifest` when an export has no manifest or insufficient metadata.
- REQ-8.11: Mark stale with `current_state_unavailable` when current input state cannot be resolved.
- REQ-8.12: Staleness must be computed dynamically for admin display.
- REQ-8.13: Staleness must not automatically delete, overwrite, unpublish, or revoke download access.

### REQ-9: Record Export Activity Metadata

Export activities must expose progress, success, and failure metadata.

- REQ-9.1: Export activity metadata must include `export_id` when available.
- REQ-9.2: Export activity metadata must include export format.
- REQ-9.3: Export activity metadata must include status.
- REQ-9.4: Export activity metadata must include progress counts when export processes chapters.
- REQ-9.5: Export activity metadata should include the current chapter label or stage when available.
- REQ-9.6: On success, activity metadata must include manifest key, artifact key, file size, and checksum when available.
- REQ-9.7: On failure, activity metadata must include failure category, safe failure message, and failed timestamp.
- REQ-9.8: Activity metadata must be compact.
- REQ-9.9: Activity metadata must not contain full chapter text, prompts, stack traces, local paths, credentials, or raw storage-provider internals.
- REQ-9.10: Existing activity records without export metadata must remain loadable.
- REQ-9.11: Activity metadata updates must use existing safe merge/update helpers.

### REQ-10: Expose Export Data in Admin APIs

Admins must be able to inspect export artifacts and status.

- REQ-10.1: Extend existing admin export routes where possible instead of adding duplicates.
- REQ-10.2: If no suitable route exists, add narrow admin-only export list/detail routes.
- REQ-10.3: Admin APIs must list available manifest-backed export artifacts.
- REQ-10.4: Admin APIs should list discoverable legacy artifacts as `legacy_unknown` when safe.
- REQ-10.5: Listed exports must include status, format, created timestamp, filename, file size, and stale state where available.
- REQ-10.6: Admin APIs must expose latest export per format.
- REQ-10.7: Admin APIs must expose failed export attempts where activity metadata exists.
- REQ-10.8: Admin APIs may expose storage-safe keys only if consistent with existing admin storage patterns.
- REQ-10.9: Admin APIs should prefer application download routes over raw storage keys.
- REQ-10.10: Strict response models must be updated if they would otherwise drop export fields.
- REQ-10.11: Response changes must be additive.

### REQ-11: Keep Public APIs Safe

Public APIs must not expose unpublished or private export artifacts.

- REQ-11.1: Public reader APIs must not expose export manifests.
- REQ-11.2: Public reader APIs must not expose unpublished export artifact keys.
- REQ-11.3: Public APIs must not expose stale reasons or internal export status unless an existing public export feature already intentionally exposes safe published exports.
- REQ-11.4: Public APIs must not expose local paths, storage keys, bucket names, signed URLs, credentials, prompts, or chapter text.
- REQ-11.5: Public reader behavior must remain unchanged.

### REQ-12: Admin UI Visibility

Admin UI must make export status understandable.

- REQ-12.1: Novel/admin UI must show available export formats.
- REQ-12.2: UI must show latest export per format.
- REQ-12.3: UI must show export history where API supports it.
- REQ-12.4: UI must show export status: pending, running, succeeded, failed, stale, deleted, or legacy unknown.
- REQ-12.5: UI must show created and completed timestamps when available.
- REQ-12.6: UI must show file size when available.
- REQ-12.7: UI may show checksum when useful.
- REQ-12.8: UI must show source and exported chapter counts.
- REQ-12.9: UI must show stale badge and stale reasons when available.
- REQ-12.10: UI must show safe failure category and message for failed exports.
- REQ-12.11: UI must show legacy manifest-unavailable state.
- REQ-12.12: UI may provide re-export action using the existing export flow.
- REQ-12.13: UI may provide download/open action using existing authorized download flow.

### REQ-13: Document Export Storage Contract

Export storage behavior must be documented and tested.

- REQ-13.1: Document current export artifact paths or helper-owned storage contract after inspection.
- REQ-13.2: Document export manifest schema.
- REQ-13.3: Document export status values.
- REQ-13.4: Document failure categories.
- REQ-13.5: Document stale reason values.
- REQ-13.6: Document temporary render file behavior.
- REQ-13.7: Document whether old exports are retained, replaced, pruned, or marked deleted.
- REQ-13.8: Document storage-backend-safe key rules.
- REQ-13.9: Document legacy export behavior.
- REQ-13.10: Documentation must not claim path guarantees unsupported by current implementation.

### REQ-14: Add Storage Contract Coverage

Export storage behavior must be covered through storage helper APIs.

- REQ-14.1: Tests must prove manifest write/read round-trips through storage helpers.
- REQ-14.2: Tests must prove manifest listing works through storage helpers.
- REQ-14.3: Tests must prove artifact metadata lookup returns size where supported.
- REQ-14.4: Tests should prove checksum metadata where supported.
- REQ-14.5: Tests must prove export helpers do not require local filesystem paths.
- REQ-14.6: Object-storage/fake-S3 style tests must not expose bucket internals.
- REQ-14.7: Local storage tests must not leak absolute paths through admin API responses.
- REQ-14.8: Cleanup/delete tests must prove manifest status changes or files are removed according to current behavior when cleanup/delete exists.

### REQ-15: Support Legacy Exports

Existing exports without manifests must remain compatible.

- REQ-15.1: Existing export files must remain valid.
- REQ-15.2: Existing download routes must still work.
- REQ-15.3: Existing artifacts without manifests must remain accessible if current behavior supports them.
- REQ-15.4: Discoverable legacy exports may appear as `legacy_unknown`.
- REQ-15.5: Legacy exports may be marked stale with `unknown_legacy_manifest`.
- REQ-15.6: Legacy exports must not be rewritten automatically.
- REQ-15.7: Legacy exports must not be deleted automatically.
- REQ-15.8: If legacy exports cannot be discovered safely through the storage backend, only manifest-backed exports need to be listed.

### REQ-16: Preserve Backward Compatibility

Existing export behavior must remain compatible.

- REQ-16.1: Existing export formats must still generate.
- REQ-16.2: Existing export request options must remain supported.
- REQ-16.3: Existing download routes must remain valid.
- REQ-16.4: Existing admin export behavior must remain compatible.
- REQ-16.5: New manifest and metadata fields must be additive.
- REQ-16.6: No export format redesign is required.
- REQ-16.7: No public reader behavior changes are allowed.
- REQ-16.8: No storage schema migration is required unless current export metadata cannot be represented through existing storage abstractions.

### REQ-17: Security and Privacy

Export observability must not leak sensitive data.

- REQ-17.1: Do not expose local absolute paths in manifests.
- REQ-17.2: Do not expose local absolute paths in activity metadata.
- REQ-17.3: Do not expose local absolute paths in API responses.
- REQ-17.4: Do not expose storage credentials.
- REQ-17.5: Do not persist signed URLs in manifests.
- REQ-17.6: Do not expose S3 bucket names or provider internals unless an existing admin storage API already treats them as safe.
- REQ-17.7: Do not store full chapter text.
- REQ-17.8: Do not store full prompts.
- REQ-17.9: Do not store provider request or response bodies.
- REQ-17.10: Do not expose stack traces in user-visible failure metadata.
- REQ-17.11: Admin export APIs must use existing admin/owner authorization.

### REQ-18: Tests

Focused tests must cover export artifacts, manifests, storage helpers, failures, freshness, admin APIs, and compatibility.

- REQ-18.1: Test export writes artifact and manifest.
- REQ-18.2: Test manifest records format, filename, file size, chapter count, and status.
- REQ-18.3: Test manifest records translation version summary.
- REQ-18.4: Test manifest uses storage-safe keys instead of local absolute paths.
- REQ-18.5: Test latest export per format is discoverable.
- REQ-18.6: Test export activity metadata records progress.
- REQ-18.7: Test export activity metadata records success artifact metadata.
- REQ-18.8: Test missing translation failure is classified.
- REQ-18.9: Test missing asset failure is classified where supported.
- REQ-18.10: Test render failure is classified with mocks/fakes.
- REQ-18.11: Test write failure is classified with mocks/fakes.
- REQ-18.12: Test failed export does not publish invalid artifact.
- REQ-18.13: Test stale detection when active translation version changes.
- REQ-18.14: Test stale detection when metadata revision changes.
- REQ-18.15: Test stale detection when glossary revision/hash changes where available.
- REQ-18.16: Test stale detection when export options/template changes.
- REQ-18.17: Test legacy export artifact remains accessible when current behavior supports it.
- REQ-18.18: Test legacy export without manifest is represented as `legacy_unknown` when discoverable.
- REQ-18.19: Test admin API exposes export metadata.
- REQ-18.20: Test admin API exposes latest export by format.
- REQ-18.21: Test public APIs do not expose unpublished export artifacts.
- REQ-18.22: Test storage helper manifest write/read/list behavior.
- REQ-18.23: Test object-storage/fake-S3 style backend does not expose bucket internals where such backend tests exist.
- REQ-18.24: Test frontend export status rendering if frontend changes.
- REQ-18.25: Tests must not require live S3, live object storage, or external services.

## Non-Goals

- This spec does not redesign export output formats.
- This spec does not implement a new EPUB, HTML, or Markdown renderer.
- This spec does not publish exports publicly by default.
- This spec does not change active translation version selection rules.
- This spec does not change public reader behavior.
- This spec does not change glossary revision behavior.
- This spec does not change scheduler/provider behavior.
- This spec does not replace storage contract tests for core chapter/translation storage.
- This spec does not require cloud object storage.
- This spec does not rewrite or migrate legacy export artifacts.