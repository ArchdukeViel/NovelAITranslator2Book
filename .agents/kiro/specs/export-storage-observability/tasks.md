# Tasks: Export Storage Observability

## Overview

Implement storage-backend-safe observability for export artifacts.

This work must start by inspecting and documenting the current export service, artifact paths, storage helpers, download routes, and activity flow. Do not lock new path contracts or tests before the existing behavior is understood.

Scope boundaries:

- Do not redesign export formats.
- Do not implement a new renderer.
- Do not change active translation version selection.
- Do not change public reader behavior.
- Do not publish exports publicly by default.
- Do not rewrite or migrate legacy export artifacts.
- Do not leak local absolute paths, bucket names, signed URLs, credentials, prompts, source text, or translated chapter text.
- Use storage-backend-safe keys and existing storage abstractions.

## Task List

- [x] 1. Preflight Export Source Review
  - [x] 1.1 Inspect `ExportService` or equivalent export implementation.
  - [x] 1.2 Identify all supported export formats.
  - [x] 1.3 Identify where export artifacts are currently written.
  - [x] 1.4 Identify whether export paths use direct filesystem paths or storage backend abstractions.
  - [x] 1.5 Identify existing sidecar metadata, manifests, temporary files, and cleanup behavior.
  - [x] 1.6 Identify existing export activity/job flow.
  - [x] 1.7 Identify existing export download routes.
  - [x] 1.8 Identify existing admin export or novel-detail API fields.
  - [x] 1.9 Inspect existing export tests and fixtures.
  - [x] 1.10 Inspect storage backend contract tests and helper APIs.
  - [x] 1.11 Document current behavior before changing production code.
  - [x] 1.12 Do not invent new path contracts before this review is complete.

- [x] 2. Define Storage-Backend-Safe Export Key Rules
  - [x] 2.1 Define storage-safe `artifact_key`.
  - [x] 2.2 Define storage-safe `manifest_key`.
  - [x] 2.3 Confirm keys are relative logical storage keys, not local absolute paths.
  - [x] 2.4 Confirm manifests do not expose S3 bucket names or storage provider internals.
  - [x] 2.5 Confirm manifests do not persist signed URLs.
  - [x] 2.6 Confirm admin APIs prefer application download routes over raw storage keys where possible.
  - [x] 2.7 Ensure temporary render files are excluded from export listings.
  - [x] 2.8 Preserve existing download route behavior.

- [x] 3. Define Export Manifest Contract
  - [x] 3.1 Define manifest schema.
  - [x] 3.2 Include `export_id`.
  - [x] 3.3 Include `novel_id`.
  - [x] 3.4 Include `format`.
  - [x] 3.5 Include `status`.
  - [x] 3.6 Include output filename.
  - [x] 3.7 Include storage-safe `artifact_key`.
  - [x] 3.8 Include storage-safe `manifest_key`.
  - [x] 3.9 Include created timestamp.
  - [x] 3.10 Include completed timestamp when available.
  - [x] 3.11 Include source chapter count.
  - [x] 3.12 Include exported chapter count.
  - [x] 3.13 Include file size in bytes when available.
  - [x] 3.14 Include checksum/hash when practical.
  - [x] 3.15 Include input version state or bounded input version summary.
  - [x] 3.16 Ensure the manifest does not store full chapter text, prompts, provider payloads, local paths, or credentials.

- [x] 4. Define Export Status and Failure Contracts
  - [x] 4.1 Support `pending`.
  - [x] 4.2 Support `running`.
  - [x] 4.3 Support `succeeded`.
  - [x] 4.4 Support `failed`.
  - [x] 4.5 Support `deleted` where cleanup/delete behavior exists.
  - [x] 4.6 Support `legacy_unknown` for discoverable artifacts without manifests.
  - [x] 4.7 Define `missing_translation`.
  - [x] 4.8 Define `missing_asset`.
  - [x] 4.9 Define `render_error`.
  - [x] 4.10 Define `write_error`.
  - [x] 4.11 Define `verify_error`.
  - [x] 4.12 Define `storage_error`.
  - [x] 4.13 Define `invalid_options`.
  - [x] 4.14 Define `unknown`.
  - [x] 4.15 Ensure failure messages are concise, sanitized, and user-safe.

- [x] 5. Add Export Storage Helpers
  - [x] 5.1 Reuse existing `StorageBackend` APIs where available.
  - [x] 5.2 Add export-specific helper methods only if they can work across every supported backend.
  - [x] 5.3 Add helper to write export manifest.
  - [x] 5.4 Add helper to read export manifest.
  - [x] 5.5 Add helper to list manifest-backed exports.
  - [x] 5.6 Add helper to look up artifact metadata such as size and checksum where supported.
  - [x] 5.7 Avoid direct path joins outside storage helper boundaries.
  - [x] 5.8 Avoid POSIX-only rename assumptions for object storage.
  - [x] 5.9 Use atomic JSON write behavior where supported.
  - [x] 5.10 Keep local and object-storage/fake-S3 behavior consistent.

- [x] 6. Add Export Manifest Write Path
  - [x] 6.1 Create manifest after successful export artifact generation.
  - [x] 6.2 Place manifest next to artifact or in the existing export metadata location discovered during preflight.
  - [x] 6.3 Write manifest through storage helpers.
  - [x] 6.4 Verify manifest write completion where supported.
  - [x] 6.5 Classify manifest write failure as `write_error` or `storage_error`.
  - [x] 6.6 Ensure manifest creation does not alter export artifact format.
  - [x] 6.7 Ensure manifest fields are additive.

- [x] 7. Capture Export Input State
  - [x] 7.1 Capture active translation version IDs for exported chapters where practical.
  - [x] 7.2 If the full chapter/version list is too large, capture `translation_version_count`.
  - [x] 7.3 If the full chapter/version list is too large, capture `translation_versions_hash`.
  - [x] 7.4 If useful, capture a bounded `translation_versions_sample`.
  - [x] 7.5 Capture novel metadata revision or updated timestamp when available.
  - [x] 7.6 Capture glossary revision when available.
  - [x] 7.7 Capture glossary hash when available.
  - [x] 7.8 Capture asset manifest hash when available.
  - [x] 7.9 Capture export options that affect output.
  - [x] 7.10 Capture template/style/template version when available.
  - [x] 7.11 Derive input state through existing storage and metadata APIs.
  - [x] 7.12 Do not store full chapter text.

- [x] 8. Verify Export Artifacts
  - [x] 8.1 Verify artifact exists after write where supported.
  - [x] 8.2 Verify file size where supported.
  - [x] 8.3 Verify checksum/hash where practical.
  - [x] 8.4 Verify manifest write completed.
  - [x] 8.5 Classify verification failure as `verify_error` or `storage_error`.
  - [x] 8.6 Avoid loading very large artifacts into memory when storage metadata APIs can provide size/hash.
  - [x] 8.7 Document checksum as optional when backend support or artifact size makes it impractical.

- [x] 9. Add Export Freshness Helper
  - [x] 9.1 Add `compute_export_freshness` or equivalent helper.
  - [x] 9.2 Compare manifest input state with current input state.
  - [x] 9.3 Detect active translation version changes.
  - [x] 9.4 Detect metadata revision changes.
  - [x] 9.5 Detect glossary revision changes.
  - [x] 9.6 Detect glossary hash changes.
  - [x] 9.7 Detect export options changes.
  - [x] 9.8 Detect template version changes.
  - [x] 9.9 Detect asset manifest changes.
  - [x] 9.10 Return `unknown_legacy_manifest` for legacy artifacts without manifests.
  - [x] 9.11 Return `current_state_unavailable` when current input state cannot be resolved.
  - [x] 9.12 Compute freshness dynamically for admin display.
  - [x] 9.13 Ensure stale detection does not delete, overwrite, unpublish, or revoke download access.

- [x] 10. Add Export Activity Metadata
  - [x] 10.1 Add `export_id` to export activity metadata when available.
  - [x] 10.2 Add export format.
  - [x] 10.3 Add export status.
  - [x] 10.4 Add progress counts while processing chapters when supported.
  - [x] 10.5 Add current chapter label or stage when available.
  - [x] 10.6 On success, add manifest key, artifact key, file size, and checksum when available.
  - [x] 10.7 On failure, add failure category, safe failure message, and failed timestamp.
  - [x] 10.8 Use existing safe activity metadata merge/update helpers.
  - [x] 10.9 Ensure activity metadata does not contain full chapter text, prompts, stack traces, local paths, credentials, or raw storage-provider internals.
  - [x] 10.10 Ensure existing activity records without export metadata still load.

- [x] 11. Implement Export Failure Classification
  - [x] 11.1 Classify missing active translation as `missing_translation`.
  - [x] 11.2 Classify missing required image/asset as `missing_asset`.
  - [x] 11.3 Classify renderer failure as `render_error`.
  - [x] 11.4 Classify artifact or manifest write failure as `write_error`.
  - [x] 11.5 Classify artifact verification failure as `verify_error`.
  - [x] 11.6 Classify storage backend failure as `storage_error`.
  - [x] 11.7 Classify invalid request options as `invalid_options`.
  - [x] 11.8 Classify unexpected failures as `unknown`.
  - [x] 11.9 Sanitize failure messages.
  - [x] 11.10 Keep stack traces in logs only according to existing logging policy.

- [x] 12. Add or Extend Admin Export APIs
  - [x] 12.1 Prefer extending existing admin export routes.
  - [x] 12.2 Add narrow admin-only export list/detail routes only if no suitable route exists.
  - [x] 12.3 List manifest-backed export artifacts.
  - [x] 12.4 List discoverable legacy artifacts as `legacy_unknown` when safe.
  - [x] 12.5 Include status, format, created timestamp, filename, file size, and stale state.
  - [x] 12.6 Include latest export per format.
  - [x] 12.7 Include failed export attempts where activity metadata exists.
  - [x] 12.8 Include stale reasons where freshness can be computed.
  - [x] 12.9 Prefer application download routes over raw storage keys.
  - [x] 12.10 Update strict response models if they would drop export fields.
  - [x] 12.11 Keep response changes additive.

- [x] 13. Confirm Public API Safety
  - [x] 13.1 Confirm public reader APIs do not expose export manifests.
  - [x] 13.2 Confirm public reader APIs do not expose unpublished artifact keys.
  - [x] 13.3 Confirm public APIs do not expose stale reasons or internal export status unless an existing public export feature already intentionally exposes safe published exports.
  - [x] 13.4 Confirm public APIs do not expose local paths, storage keys, bucket names, signed URLs, credentials, prompts, or chapter text.
  - [x] 13.5 Confirm public reader behavior remains unchanged.

- [x] 14. Update Admin Export UI
  - [x] 14.1 Show available export formats.
  - [x] 14.2 Show latest export per format.
  - [x] 14.3 Show export history where API supports it.
  - [x] 14.4 Show status badge for `pending`, `running`, `succeeded`, `failed`, `deleted`, and `legacy_unknown`.
  - [x] 14.5 Show stale badge and stale reasons.
  - [x] 14.6 Show created and completed timestamps when available.
  - [x] 14.7 Show file size when available.
  - [x] 14.8 Show checksum when useful.
  - [x] 14.9 Show source and exported chapter counts.
  - [x] 14.10 Show safe failure category and message.
  - [x] 14.11 Show legacy manifest-unavailable state.
  - [x] 14.12 Add re-export action using existing export flow if available.
  - [x] 14.13 Add download/open action using existing authorized download flow if available.

- [x] 15. Support Legacy Exports
  - [x] 15.1 Keep existing export files valid.
  - [x] 15.2 Keep existing download routes working.
  - [x] 15.3 Keep existing artifacts without manifests accessible if current behavior supports them.
  - [x] 15.4 Represent discoverable manifestless artifacts as `legacy_unknown`.
  - [x] 15.5 Mark legacy artifacts stale with `unknown_legacy_manifest` where appropriate.
  - [x] 15.6 Do not rewrite legacy artifacts automatically.
  - [x] 15.7 Do not delete legacy artifacts automatically.
  - [x] 15.8 If legacy exports cannot be discovered safely through storage backend APIs, list only manifest-backed exports.

- [x] 16. Update Storage Contract Documentation
  - [x] 16.1 Document current export artifact paths or helper-owned storage contract after preflight.
  - [x] 16.2 Document export manifest schema.
  - [x] 16.3 Document export status values.
  - [x] 16.4 Document failure categories.
  - [x] 16.5 Document stale reason values.
  - [x] 16.6 Document temporary render file behavior.
  - [x] 16.7 Document whether old exports are retained, replaced, pruned, or marked deleted.
  - [x] 16.8 Document storage-backend-safe key rules.
  - [x] 16.9 Document legacy export behavior.
  - [x] 16.10 Avoid documenting unsupported path guarantees.

- [x] 17. Add Backend Tests
  - [x] 17.1 Create `backend/tests/test_export_storage_observability.py`.
  - [x] 17.2 Test export writes artifact and manifest.
  - [x] 17.3 Test manifest records format, filename, file size, chapter count, and status.
  - [x] 17.4 Test manifest records translation version summary.
  - [x] 17.5 Test manifest uses storage-safe keys instead of local absolute paths.
  - [x] 17.6 Test latest export per format is discoverable.
  - [x] 17.7 Test export activity metadata records progress.
  - [x] 17.8 Test export activity metadata records success artifact metadata.
  - [x] 17.9 Test missing translation failure is classified.
  - [x] 17.10 Test missing asset failure is classified where supported.
  - [x] 17.11 Test render failure is classified with mocks/fakes.
  - [x] 17.12 Test write failure is classified with mocks/fakes.
  - [x] 17.13 Test verification failure is classified.
  - [x] 17.14 Test failed export does not publish invalid artifact.
  - [x] 17.15 Test legacy export artifact remains accessible when current behavior supports it.
  - [x] 17.16 Test legacy export without manifest is represented as `legacy_unknown` when discoverable.

- [x] 18. Add Freshness and Admin API Tests
  - [x] 18.1 Test stale detection when active translation version changes.
  - [x] 18.2 Test stale detection when metadata revision changes.
  - [x] 18.3 Test stale detection when glossary revision changes where available.
  - [x] 18.4 Test stale detection when glossary hash changes where available.
  - [x] 18.5 Test stale detection when export options change.
  - [x] 18.6 Test stale detection when template version changes.
  - [x] 18.7 Test stale detection returns `unknown_legacy_manifest` for manifestless exports.
  - [x] 18.8 Test stale detection returns `current_state_unavailable` when current input state cannot be resolved.
  - [x] 18.9 Test admin API exposes export metadata.
  - [x] 18.10 Test admin API exposes latest export by format.
  - [x] 18.11 Test admin API exposes failed export attempts when activity metadata exists.
  - [x] 18.12 Test admin API does not expose local absolute paths.
  - [x] 18.13 Test public APIs do not expose unpublished export artifacts.

- [x] 19. Add Storage Contract Tests
  - [x] 19.1 Test manifest write/read round-trips through storage helpers.
  - [x] 19.2 Test manifest listing works through storage helpers.
  - [x] 19.3 Test artifact metadata lookup returns size where supported.
  - [x] 19.4 Test checksum metadata where supported.
  - [x] 19.5 Test export helpers do not require local filesystem paths.
  - [x] 19.6 Test local storage admin API responses do not leak absolute paths.
  - [x] 19.7 Test object-storage/fake-S3 backend does not expose bucket internals where such backend tests exist.
  - [x] 19.8 Test cleanup/delete behavior updates manifest status or removes files according to current behavior when cleanup/delete exists.
  - [x] 19.9 Ensure tests do not require live S3, live object storage, or external services.

- [x] 20. Add Frontend Tests If UI Changes
  - [x] 20.1 Test latest export status renders.
  - [x] 20.2 Test export history renders where available.
  - [x] 20.3 Test stale badge renders.
  - [x] 20.4 Test stale reason renders.
  - [x] 20.5 Test failed export category and message render.
  - [x] 20.6 Test legacy manifest-unavailable state renders.
  - [x] 20.7 Test re-export action triggers existing export flow.
  - [x] 20.8 Test download/open action uses existing authorized download flow.

- [x] 21. Security and Privacy Review
  - [x] 21.1 Confirm manifests do not expose local absolute paths.
  - [x] 21.2 Confirm activity metadata does not expose local absolute paths.
  - [x] 21.3 Confirm API responses do not expose local absolute paths.
  - [x] 21.4 Confirm manifests do not expose storage credentials.
  - [x] 21.5 Confirm manifests do not persist signed URLs.
  - [x] 21.6 Confirm APIs do not expose bucket names or provider internals unless existing admin storage APIs already treat them as safe.
  - [x] 21.7 Confirm manifests do not store full chapter text.
  - [x] 21.8 Confirm manifests do not store full prompts.
  - [x] 21.9 Confirm manifests do not store provider request or response bodies.
  - [x] 21.10 Confirm user-visible failure metadata does not include stack traces.
  - [x] 21.11 Confirm admin export APIs use existing admin/owner authorization.

- [x] 22. Backward Compatibility Checks
  - [x] 22.1 Confirm existing export formats still generate.
  - [x] 22.2 Confirm existing export request options remain supported.
  - [x] 22.3 Confirm existing download routes remain valid.
  - [x] 22.4 Confirm existing admin export behavior remains compatible.
  - [x] 22.5 Confirm new manifest and metadata fields are additive.
  - [x] 22.6 Confirm no export format redesign was introduced.
  - [x] 22.7 Confirm public reader behavior is unchanged.
  - [x] 22.8 Confirm no storage schema migration is required unless current export metadata cannot be represented through existing storage abstractions.
  - [x] 22.9 Confirm legacy artifacts are not rewritten or deleted automatically.

- [x] 23. Run Verification
  - [x] 23.1 Run focused export observability tests.
  - [x] 23.2 Run existing export tests.
  - [x] 23.3 Run existing storage backend tests.
  - [x] 23.4 Run existing storage contract tests.
  - [x] 23.5 Run existing admin API tests.
  - [x] 23.6 Run public reader tests.
  - [x] 23.7 Run frontend/admin export tests if UI changed.
  - [x] 23.8 Run `ruff check` on changed backend source and test files.
  - [x] 23.9 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 23.10 Fix test, lint, and type failures caused by this work.

- [x] 24. Final Acceptance Review
  - [x] 24.1 Verify current export paths and behavior are documented.
  - [x] 24.2 Verify completed new exports write manifests.
  - [x] 24.3 Verify manifests record artifact, format, file size, chapter counts, input version state, and safe storage keys.
  - [x] 24.4 Verify manifests and APIs do not leak local paths, credentials, bucket internals, prompts, or chapter text.
  - [x] 24.5 Verify export activity metadata exposes progress, success artifact metadata, or safe failure category/message.
  - [x] 24.6 Verify admin APIs list exports and latest export per format.
  - [x] 24.7 Verify admin APIs compute and expose stale state where data is available.
  - [x] 24.8 Verify admin UI shows status, stale state, failures, legacy state, and re-export action.
  - [x] 24.9 Verify existing export/download behavior remains compatible.
  - [x] 24.10 Verify public APIs do not expose unpublished export artifacts.
  - [x] 24.11 Verify storage contract tests cover manifest read/write/list behavior where applicable.
  - [x] 24.12 Verify focused backend and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Inspect and Document Existing Export Behavior | 1, 16, 24 |
| REQ-2 Use Storage-Backend-Safe Export Keys | 2, 5, 12, 13, 19, 21, 24 |
| REQ-3 Write Export Manifests for Completed Exports | 3, 6, 17, 24 |
| REQ-4 Record Export Input State | 7, 17, 18, 24 |
| REQ-5 Support Export Status Values | 4, 10, 12, 14, 17 |
| REQ-6 Classify Export Failures | 4, 11, 17, 21, 24 |
| REQ-7 Verify Export Artifacts | 8, 17, 19, 24 |
| REQ-8 Compute Export Freshness | 9, 18, 24 |
| REQ-9 Record Export Activity Metadata | 10, 17, 24 |
| REQ-10 Expose Export Data in Admin APIs | 12, 18, 24 |
| REQ-11 Keep Public APIs Safe | 13, 18, 21, 24 |
| REQ-12 Admin UI Visibility | 14, 20, 24 |
| REQ-13 Document Export Storage Contract | 16, 24 |
| REQ-14 Add Storage Contract Coverage | 19, 23, 24 |
| REQ-15 Support Legacy Exports | 15, 17, 18, 22 |
| REQ-16 Preserve Backward Compatibility | 22, 23, 24 |
| REQ-17 Security and Privacy | 2, 13, 21, 24 |
| REQ-18 Tests | 17, 18, 19, 20, 23 |

## Definition of Done

- [x] Current export paths, storage behavior, download routes, and cleanup behavior are documented.
- [x] Export manifests are written for completed new exports.
- [x] Manifests use storage-backend-safe keys, not local absolute paths.
- [x] Manifests record artifact, format, size, chapter counts, input version state, and output-affecting options.
- [x] Export artifacts are verified where supported.
- [x] Export freshness is computed dynamically for admin display.
- [x] Export activity metadata records progress, success, and safe failure details.
- [x] Export failures use stable categories.
- [x] Admin APIs expose export history, latest export per format, stale state, and failed attempts.
- [x] Admin UI shows status, stale reasons, failures, legacy state, re-export, and download/open affordances.
- [x] Public APIs do not expose unpublished export artifacts.
- [x] Storage contract tests cover export manifest read/write/list behavior where applicable.
- [x] Legacy exports remain accessible when current behavior supports them.
- [x] Existing export formats, request options, download routes, admin behavior, and public reader behavior remain compatible.
- [x] Focused backend, storage contract, admin API, and frontend tests pass.