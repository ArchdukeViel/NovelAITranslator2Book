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

- [ ] 1. Preflight Export Source Review
  - [ ] 1.1 Inspect `ExportService` or equivalent export implementation.
  - [ ] 1.2 Identify all supported export formats.
  - [ ] 1.3 Identify where export artifacts are currently written.
  - [ ] 1.4 Identify whether export paths use direct filesystem paths or storage backend abstractions.
  - [ ] 1.5 Identify existing sidecar metadata, manifests, temporary files, and cleanup behavior.
  - [ ] 1.6 Identify existing export activity/job flow.
  - [ ] 1.7 Identify existing export download routes.
  - [ ] 1.8 Identify existing admin export or novel-detail API fields.
  - [ ] 1.9 Inspect existing export tests and fixtures.
  - [ ] 1.10 Inspect storage backend contract tests and helper APIs.
  - [ ] 1.11 Document current behavior before changing production code.
  - [ ] 1.12 Do not invent new path contracts before this review is complete.

- [ ] 2. Define Storage-Backend-Safe Export Key Rules
  - [ ] 2.1 Define storage-safe `artifact_key`.
  - [ ] 2.2 Define storage-safe `manifest_key`.
  - [ ] 2.3 Confirm keys are relative logical storage keys, not local absolute paths.
  - [ ] 2.4 Confirm manifests do not expose S3 bucket names or storage provider internals.
  - [ ] 2.5 Confirm manifests do not persist signed URLs.
  - [ ] 2.6 Confirm admin APIs prefer application download routes over raw storage keys where possible.
  - [ ] 2.7 Ensure temporary render files are excluded from export listings.
  - [ ] 2.8 Preserve existing download route behavior.

- [ ] 3. Define Export Manifest Contract
  - [ ] 3.1 Define manifest schema.
  - [ ] 3.2 Include `export_id`.
  - [ ] 3.3 Include `novel_id`.
  - [ ] 3.4 Include `format`.
  - [ ] 3.5 Include `status`.
  - [ ] 3.6 Include output filename.
  - [ ] 3.7 Include storage-safe `artifact_key`.
  - [ ] 3.8 Include storage-safe `manifest_key`.
  - [ ] 3.9 Include created timestamp.
  - [ ] 3.10 Include completed timestamp when available.
  - [ ] 3.11 Include source chapter count.
  - [ ] 3.12 Include exported chapter count.
  - [ ] 3.13 Include file size in bytes when available.
  - [ ] 3.14 Include checksum/hash when practical.
  - [ ] 3.15 Include input version state or bounded input version summary.
  - [ ] 3.16 Ensure the manifest does not store full chapter text, prompts, provider payloads, local paths, or credentials.

- [ ] 4. Define Export Status and Failure Contracts
  - [ ] 4.1 Support `pending`.
  - [ ] 4.2 Support `running`.
  - [ ] 4.3 Support `succeeded`.
  - [ ] 4.4 Support `failed`.
  - [ ] 4.5 Support `deleted` where cleanup/delete behavior exists.
  - [ ] 4.6 Support `legacy_unknown` for discoverable artifacts without manifests.
  - [ ] 4.7 Define `missing_translation`.
  - [ ] 4.8 Define `missing_asset`.
  - [ ] 4.9 Define `render_error`.
  - [ ] 4.10 Define `write_error`.
  - [ ] 4.11 Define `verify_error`.
  - [ ] 4.12 Define `storage_error`.
  - [ ] 4.13 Define `invalid_options`.
  - [ ] 4.14 Define `unknown`.
  - [ ] 4.15 Ensure failure messages are concise, sanitized, and user-safe.

- [ ] 5. Add Export Storage Helpers
  - [ ] 5.1 Reuse existing `StorageBackend` APIs where available.
  - [ ] 5.2 Add export-specific helper methods only if they can work across every supported backend.
  - [ ] 5.3 Add helper to write export manifest.
  - [ ] 5.4 Add helper to read export manifest.
  - [ ] 5.5 Add helper to list manifest-backed exports.
  - [ ] 5.6 Add helper to look up artifact metadata such as size and checksum where supported.
  - [ ] 5.7 Avoid direct path joins outside storage helper boundaries.
  - [ ] 5.8 Avoid POSIX-only rename assumptions for object storage.
  - [ ] 5.9 Use atomic JSON write behavior where supported.
  - [ ] 5.10 Keep local and object-storage/fake-S3 behavior consistent.

- [ ] 6. Add Export Manifest Write Path
  - [ ] 6.1 Create manifest after successful export artifact generation.
  - [ ] 6.2 Place manifest next to artifact or in the existing export metadata location discovered during preflight.
  - [ ] 6.3 Write manifest through storage helpers.
  - [ ] 6.4 Verify manifest write completion where supported.
  - [ ] 6.5 Classify manifest write failure as `write_error` or `storage_error`.
  - [ ] 6.6 Ensure manifest creation does not alter export artifact format.
  - [ ] 6.7 Ensure manifest fields are additive.

- [ ] 7. Capture Export Input State
  - [ ] 7.1 Capture active translation version IDs for exported chapters where practical.
  - [ ] 7.2 If the full chapter/version list is too large, capture `translation_version_count`.
  - [ ] 7.3 If the full chapter/version list is too large, capture `translation_versions_hash`.
  - [ ] 7.4 If useful, capture a bounded `translation_versions_sample`.
  - [ ] 7.5 Capture novel metadata revision or updated timestamp when available.
  - [ ] 7.6 Capture glossary revision when available.
  - [ ] 7.7 Capture glossary hash when available.
  - [ ] 7.8 Capture asset manifest hash when available.
  - [ ] 7.9 Capture export options that affect output.
  - [ ] 7.10 Capture template/style/template version when available.
  - [ ] 7.11 Derive input state through existing storage and metadata APIs.
  - [ ] 7.12 Do not store full chapter text.

- [ ] 8. Verify Export Artifacts
  - [ ] 8.1 Verify artifact exists after write where supported.
  - [ ] 8.2 Verify file size where supported.
  - [ ] 8.3 Verify checksum/hash where practical.
  - [ ] 8.4 Verify manifest write completed.
  - [ ] 8.5 Classify verification failure as `verify_error` or `storage_error`.
  - [ ] 8.6 Avoid loading very large artifacts into memory when storage metadata APIs can provide size/hash.
  - [ ] 8.7 Document checksum as optional when backend support or artifact size makes it impractical.

- [ ] 9. Add Export Freshness Helper
  - [ ] 9.1 Add `compute_export_freshness` or equivalent helper.
  - [ ] 9.2 Compare manifest input state with current input state.
  - [ ] 9.3 Detect active translation version changes.
  - [ ] 9.4 Detect metadata revision changes.
  - [ ] 9.5 Detect glossary revision changes.
  - [ ] 9.6 Detect glossary hash changes.
  - [ ] 9.7 Detect export options changes.
  - [ ] 9.8 Detect template version changes.
  - [ ] 9.9 Detect asset manifest changes.
  - [ ] 9.10 Return `unknown_legacy_manifest` for legacy artifacts without manifests.
  - [ ] 9.11 Return `current_state_unavailable` when current input state cannot be resolved.
  - [ ] 9.12 Compute freshness dynamically for admin display.
  - [ ] 9.13 Ensure stale detection does not delete, overwrite, unpublish, or revoke download access.

- [ ] 10. Add Export Activity Metadata
  - [ ] 10.1 Add `export_id` to export activity metadata when available.
  - [ ] 10.2 Add export format.
  - [ ] 10.3 Add export status.
  - [ ] 10.4 Add progress counts while processing chapters when supported.
  - [ ] 10.5 Add current chapter label or stage when available.
  - [ ] 10.6 On success, add manifest key, artifact key, file size, and checksum when available.
  - [ ] 10.7 On failure, add failure category, safe failure message, and failed timestamp.
  - [ ] 10.8 Use existing safe activity metadata merge/update helpers.
  - [ ] 10.9 Ensure activity metadata does not contain full chapter text, prompts, stack traces, local paths, credentials, or raw storage-provider internals.
  - [ ] 10.10 Ensure existing activity records without export metadata still load.

- [ ] 11. Implement Export Failure Classification
  - [ ] 11.1 Classify missing active translation as `missing_translation`.
  - [ ] 11.2 Classify missing required image/asset as `missing_asset`.
  - [ ] 11.3 Classify renderer failure as `render_error`.
  - [ ] 11.4 Classify artifact or manifest write failure as `write_error`.
  - [ ] 11.5 Classify artifact verification failure as `verify_error`.
  - [ ] 11.6 Classify storage backend failure as `storage_error`.
  - [ ] 11.7 Classify invalid request options as `invalid_options`.
  - [ ] 11.8 Classify unexpected failures as `unknown`.
  - [ ] 11.9 Sanitize failure messages.
  - [ ] 11.10 Keep stack traces in logs only according to existing logging policy.

- [ ] 12. Add or Extend Admin Export APIs
  - [ ] 12.1 Prefer extending existing admin export routes.
  - [ ] 12.2 Add narrow admin-only export list/detail routes only if no suitable route exists.
  - [ ] 12.3 List manifest-backed export artifacts.
  - [ ] 12.4 List discoverable legacy artifacts as `legacy_unknown` when safe.
  - [ ] 12.5 Include status, format, created timestamp, filename, file size, and stale state.
  - [ ] 12.6 Include latest export per format.
  - [ ] 12.7 Include failed export attempts where activity metadata exists.
  - [ ] 12.8 Include stale reasons where freshness can be computed.
  - [ ] 12.9 Prefer application download routes over raw storage keys.
  - [ ] 12.10 Update strict response models if they would drop export fields.
  - [ ] 12.11 Keep response changes additive.

- [ ] 13. Confirm Public API Safety
  - [ ] 13.1 Confirm public reader APIs do not expose export manifests.
  - [ ] 13.2 Confirm public reader APIs do not expose unpublished artifact keys.
  - [ ] 13.3 Confirm public APIs do not expose stale reasons or internal export status unless an existing public export feature already intentionally exposes safe published exports.
  - [ ] 13.4 Confirm public APIs do not expose local paths, storage keys, bucket names, signed URLs, credentials, prompts, or chapter text.
  - [ ] 13.5 Confirm public reader behavior remains unchanged.

- [ ] 14. Update Admin Export UI
  - [ ] 14.1 Show available export formats.
  - [ ] 14.2 Show latest export per format.
  - [ ] 14.3 Show export history where API supports it.
  - [ ] 14.4 Show status badge for `pending`, `running`, `succeeded`, `failed`, `deleted`, and `legacy_unknown`.
  - [ ] 14.5 Show stale badge and stale reasons.
  - [ ] 14.6 Show created and completed timestamps when available.
  - [ ] 14.7 Show file size when available.
  - [ ] 14.8 Show checksum when useful.
  - [ ] 14.9 Show source and exported chapter counts.
  - [ ] 14.10 Show safe failure category and message.
  - [ ] 14.11 Show legacy manifest-unavailable state.
  - [ ] 14.12 Add re-export action using existing export flow if available.
  - [ ] 14.13 Add download/open action using existing authorized download flow if available.

- [ ] 15. Support Legacy Exports
  - [ ] 15.1 Keep existing export files valid.
  - [ ] 15.2 Keep existing download routes working.
  - [ ] 15.3 Keep existing artifacts without manifests accessible if current behavior supports them.
  - [ ] 15.4 Represent discoverable manifestless artifacts as `legacy_unknown`.
  - [ ] 15.5 Mark legacy artifacts stale with `unknown_legacy_manifest` where appropriate.
  - [ ] 15.6 Do not rewrite legacy artifacts automatically.
  - [ ] 15.7 Do not delete legacy artifacts automatically.
  - [ ] 15.8 If legacy exports cannot be discovered safely through storage backend APIs, list only manifest-backed exports.

- [ ] 16. Update Storage Contract Documentation
  - [ ] 16.1 Document current export artifact paths or helper-owned storage contract after preflight.
  - [ ] 16.2 Document export manifest schema.
  - [ ] 16.3 Document export status values.
  - [ ] 16.4 Document failure categories.
  - [ ] 16.5 Document stale reason values.
  - [ ] 16.6 Document temporary render file behavior.
  - [ ] 16.7 Document whether old exports are retained, replaced, pruned, or marked deleted.
  - [ ] 16.8 Document storage-backend-safe key rules.
  - [ ] 16.9 Document legacy export behavior.
  - [ ] 16.10 Avoid documenting unsupported path guarantees.

- [ ] 17. Add Backend Tests
  - [ ] 17.1 Create `backend/tests/test_export_storage_observability.py`.
  - [ ] 17.2 Test export writes artifact and manifest.
  - [ ] 17.3 Test manifest records format, filename, file size, chapter count, and status.
  - [ ] 17.4 Test manifest records translation version summary.
  - [ ] 17.5 Test manifest uses storage-safe keys instead of local absolute paths.
  - [ ] 17.6 Test latest export per format is discoverable.
  - [ ] 17.7 Test export activity metadata records progress.
  - [ ] 17.8 Test export activity metadata records success artifact metadata.
  - [ ] 17.9 Test missing translation failure is classified.
  - [ ] 17.10 Test missing asset failure is classified where supported.
  - [ ] 17.11 Test render failure is classified with mocks/fakes.
  - [ ] 17.12 Test write failure is classified with mocks/fakes.
  - [ ] 17.13 Test verification failure is classified.
  - [ ] 17.14 Test failed export does not publish invalid artifact.
  - [ ] 17.15 Test legacy export artifact remains accessible when current behavior supports it.
  - [ ] 17.16 Test legacy export without manifest is represented as `legacy_unknown` when discoverable.

- [ ] 18. Add Freshness and Admin API Tests
  - [ ] 18.1 Test stale detection when active translation version changes.
  - [ ] 18.2 Test stale detection when metadata revision changes.
  - [ ] 18.3 Test stale detection when glossary revision changes where available.
  - [ ] 18.4 Test stale detection when glossary hash changes where available.
  - [ ] 18.5 Test stale detection when export options change.
  - [ ] 18.6 Test stale detection when template version changes.
  - [ ] 18.7 Test stale detection returns `unknown_legacy_manifest` for manifestless exports.
  - [ ] 18.8 Test stale detection returns `current_state_unavailable` when current input state cannot be resolved.
  - [ ] 18.9 Test admin API exposes export metadata.
  - [ ] 18.10 Test admin API exposes latest export by format.
  - [ ] 18.11 Test admin API exposes failed export attempts when activity metadata exists.
  - [ ] 18.12 Test admin API does not expose local absolute paths.
  - [ ] 18.13 Test public APIs do not expose unpublished export artifacts.

- [ ] 19. Add Storage Contract Tests
  - [ ] 19.1 Test manifest write/read round-trips through storage helpers.
  - [ ] 19.2 Test manifest listing works through storage helpers.
  - [ ] 19.3 Test artifact metadata lookup returns size where supported.
  - [ ] 19.4 Test checksum metadata where supported.
  - [ ] 19.5 Test export helpers do not require local filesystem paths.
  - [ ] 19.6 Test local storage admin API responses do not leak absolute paths.
  - [ ] 19.7 Test object-storage/fake-S3 backend does not expose bucket internals where such backend tests exist.
  - [ ] 19.8 Test cleanup/delete behavior updates manifest status or removes files according to current behavior when cleanup/delete exists.
  - [ ] 19.9 Ensure tests do not require live S3, live object storage, or external services.

- [ ] 20. Add Frontend Tests If UI Changes
  - [ ] 20.1 Test latest export status renders.
  - [ ] 20.2 Test export history renders where available.
  - [ ] 20.3 Test stale badge renders.
  - [ ] 20.4 Test stale reason renders.
  - [ ] 20.5 Test failed export category and message render.
  - [ ] 20.6 Test legacy manifest-unavailable state renders.
  - [ ] 20.7 Test re-export action triggers existing export flow.
  - [ ] 20.8 Test download/open action uses existing authorized download flow.

- [ ] 21. Security and Privacy Review
  - [ ] 21.1 Confirm manifests do not expose local absolute paths.
  - [ ] 21.2 Confirm activity metadata does not expose local absolute paths.
  - [ ] 21.3 Confirm API responses do not expose local absolute paths.
  - [ ] 21.4 Confirm manifests do not expose storage credentials.
  - [ ] 21.5 Confirm manifests do not persist signed URLs.
  - [ ] 21.6 Confirm APIs do not expose bucket names or provider internals unless existing admin storage APIs already treat them as safe.
  - [ ] 21.7 Confirm manifests do not store full chapter text.
  - [ ] 21.8 Confirm manifests do not store full prompts.
  - [ ] 21.9 Confirm manifests do not store provider request or response bodies.
  - [ ] 21.10 Confirm user-visible failure metadata does not include stack traces.
  - [ ] 21.11 Confirm admin export APIs use existing admin/owner authorization.

- [ ] 22. Backward Compatibility Checks
  - [ ] 22.1 Confirm existing export formats still generate.
  - [ ] 22.2 Confirm existing export request options remain supported.
  - [ ] 22.3 Confirm existing download routes remain valid.
  - [ ] 22.4 Confirm existing admin export behavior remains compatible.
  - [ ] 22.5 Confirm new manifest and metadata fields are additive.
  - [ ] 22.6 Confirm no export format redesign was introduced.
  - [ ] 22.7 Confirm public reader behavior is unchanged.
  - [ ] 22.8 Confirm no storage schema migration is required unless current export metadata cannot be represented through existing storage abstractions.
  - [ ] 22.9 Confirm legacy artifacts are not rewritten or deleted automatically.

- [ ] 23. Run Verification
  - [ ] 23.1 Run focused export observability tests.
  - [ ] 23.2 Run existing export tests.
  - [ ] 23.3 Run existing storage backend tests.
  - [ ] 23.4 Run existing storage contract tests.
  - [ ] 23.5 Run existing admin API tests.
  - [ ] 23.6 Run public reader tests.
  - [ ] 23.7 Run frontend/admin export tests if UI changed.
  - [ ] 23.8 Run `ruff check` on changed backend source and test files.
  - [ ] 23.9 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 23.10 Fix test, lint, and type failures caused by this work.

- [ ] 24. Final Acceptance Review
  - [ ] 24.1 Verify current export paths and behavior are documented.
  - [ ] 24.2 Verify completed new exports write manifests.
  - [ ] 24.3 Verify manifests record artifact, format, file size, chapter counts, input version state, and safe storage keys.
  - [ ] 24.4 Verify manifests and APIs do not leak local paths, credentials, bucket internals, prompts, or chapter text.
  - [ ] 24.5 Verify export activity metadata exposes progress, success artifact metadata, or safe failure category/message.
  - [ ] 24.6 Verify admin APIs list exports and latest export per format.
  - [ ] 24.7 Verify admin APIs compute and expose stale state where data is available.
  - [ ] 24.8 Verify admin UI shows status, stale state, failures, legacy state, and re-export action.
  - [ ] 24.9 Verify existing export/download behavior remains compatible.
  - [ ] 24.10 Verify public APIs do not expose unpublished export artifacts.
  - [ ] 24.11 Verify storage contract tests cover manifest read/write/list behavior where applicable.
  - [ ] 24.12 Verify focused backend and frontend tests pass.

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

- [ ] Current export paths, storage behavior, download routes, and cleanup behavior are documented.
- [ ] Export manifests are written for completed new exports.
- [ ] Manifests use storage-backend-safe keys, not local absolute paths.
- [ ] Manifests record artifact, format, size, chapter counts, input version state, and output-affecting options.
- [ ] Export artifacts are verified where supported.
- [ ] Export freshness is computed dynamically for admin display.
- [ ] Export activity metadata records progress, success, and safe failure details.
- [ ] Export failures use stable categories.
- [ ] Admin APIs expose export history, latest export per format, stale state, and failed attempts.
- [ ] Admin UI shows status, stale reasons, failures, legacy state, re-export, and download/open affordances.
- [ ] Public APIs do not expose unpublished export artifacts.
- [ ] Storage contract tests cover export manifest read/write/list behavior where applicable.
- [ ] Legacy exports remain accessible when current behavior supports them.
- [ ] Existing export formats, request options, download routes, admin behavior, and public reader behavior remain compatible.
- [ ] Focused backend, storage contract, admin API, and frontend tests pass.