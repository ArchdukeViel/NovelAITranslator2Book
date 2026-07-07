# Tasks: Export Storage Observability

## Task List

- [ ] 1. Preflight Export Source Review
  - [ ] 1.1 Inspect `ExportService` or equivalent export implementation. (REQ-1.1)
  - [ ] 1.2 Identify supported export formats. (REQ-1.2)
  - [ ] 1.3 Identify output artifact paths. (REQ-1.3)
  - [ ] 1.4 Identify existing sidecar metadata/manifest behavior. (REQ-1.4)
  - [ ] 1.5 Identify temporary file and cleanup behavior. (REQ-1.4)
  - [ ] 1.6 Identify download/read routes for export artifacts. (REQ-1.5)
  - [ ] 1.7 Inspect existing export tests and fixtures.
  - [ ] 1.8 Document current path contract before implementation. (REQ-1.6)

- [ ] 2. Define Export Manifest Contract
  - [ ] 2.1 Define manifest schema. (REQ-2)
  - [ ] 2.2 Include `export_id`. (REQ-2.1)
  - [ ] 2.3 Include `novel_id`. (REQ-2.2)
  - [ ] 2.4 Include `format`. (REQ-2.3)
  - [ ] 2.5 Include filename or storage key. (REQ-2.4)
  - [ ] 2.6 Include file size. (REQ-2.5)
  - [ ] 2.7 Include checksum when practical. (REQ-2.6)
  - [ ] 2.8 Include created timestamp. (REQ-2.7)
  - [ ] 2.9 Include source/exported chapter counts. (REQ-2.8)
  - [ ] 2.10 Include translation version IDs or bounded summary. (REQ-2.9)
  - [ ] 2.11 Include export status. (REQ-2.10)

- [ ] 3. Add Export Manifest Write Path
  - [ ] 3.1 Add helper to create export manifest after successful export.
  - [ ] 3.2 Place manifest next to artifact or in existing export metadata directory.
  - [ ] 3.3 Use atomic write helper if available.
  - [ ] 3.4 Ensure manifest write failure is classified safely. (REQ-5.4)
  - [ ] 3.5 Ensure manifest fields are additive and do not alter artifact format. (REQ-9.4)

- [ ] 4. Capture Export Input State
  - [ ] 4.1 Capture metadata revision or updated timestamp when available. (REQ-3.1)
  - [ ] 4.2 Capture active translation version IDs for exported chapters where practical. (REQ-3.2)
  - [ ] 4.3 Capture glossary revision/hash when available. (REQ-3.3)
  - [ ] 4.4 Capture export options that affect output. (REQ-3.4)
  - [ ] 4.5 Use bounded summary/hash if per-chapter version list is too large.

- [ ] 5. Add Export Freshness Helper
  - [ ] 5.1 Add helper to compare manifest input state to current novel state. (REQ-3.5)
  - [ ] 5.2 Detect active translation version changes.
  - [ ] 5.3 Detect metadata changes.
  - [ ] 5.4 Detect glossary revision/hash changes.
  - [ ] 5.5 Detect export option/template changes.
  - [ ] 5.6 Return stale reasons.
  - [ ] 5.7 Ensure stale detection does not delete or overwrite exports. (REQ-3.6)

- [ ] 6. Add Export Activity Metadata
  - [ ] 6.1 Add export format to activity metadata. (REQ-4.1)
  - [ ] 6.2 Add progress counts while processing chapters if supported. (REQ-4.2)
  - [ ] 6.3 Add final artifact reference on success. (REQ-4.3)
  - [ ] 6.4 Add manifest reference on success.
  - [ ] 6.5 Add failure category and safe message on failure. (REQ-4.4)
  - [ ] 6.6 Ensure metadata excludes full chapter text. (REQ-4.5)
  - [ ] 6.7 Ensure old activity records without export metadata still load. (REQ-4.6)

- [ ] 7. Add Export Failure Classification
  - [ ] 7.1 Add `missing_translation`. (REQ-5.1)
  - [ ] 7.2 Add `missing_asset`. (REQ-5.2)
  - [ ] 7.3 Add `render_error`. (REQ-5.3)
  - [ ] 7.4 Add `write_error`. (REQ-5.4)
  - [ ] 7.5 Add `invalid_options`. (REQ-5.5)
  - [ ] 7.6 Add `unknown`. (REQ-5.6)
  - [ ] 7.7 Ensure failure messages are safe. (REQ-5.7)

- [ ] 8. Add Admin Export APIs
  - [ ] 8.1 Extend existing export route or add admin export list route. (REQ-6.1)
  - [ ] 8.2 Return manifest fields and stale status. (REQ-6.2)
  - [ ] 8.3 Return latest export per format. (REQ-6.3)
  - [ ] 8.4 Expose failed export attempts where activity metadata exists. (REQ-6.4)
  - [ ] 8.5 Update strict response models if needed. (REQ-6.5)
  - [ ] 8.6 Ensure public APIs do not expose unpublished export artifacts. (REQ-6.6)

- [ ] 9. Update Admin Export UI
  - [ ] 9.1 Show available export formats and latest artifact time. (REQ-7.1)
  - [ ] 9.2 Show status badge. (REQ-7.2)
  - [ ] 9.3 Show exported chapter count. (REQ-7.3)
  - [ ] 9.4 Show stale reason. (REQ-7.4)
  - [ ] 9.5 Show safe failure message. (REQ-7.5)
  - [ ] 9.6 Add re-export action using existing flow if available. (REQ-7.6)

- [ ] 10. Update Storage Contract Documentation
  - [ ] 10.1 Document export artifact paths or helper-owned contract. (REQ-8.1)
  - [ ] 10.2 Document export manifest schema. (REQ-8.2)
  - [ ] 10.3 Document temporary file behavior. (REQ-8.3)
  - [ ] 10.4 Document retention/replacement/pruning behavior. (REQ-8.4)
  - [ ] 10.5 Document legacy export behavior.

- [ ] 11. Add Backend Tests
  - [ ] 11.1 Create `backend/tests/test_export_storage_observability.py`. (REQ-10)
  - [ ] 11.2 Test export writes artifact and manifest. (REQ-10.1)
  - [ ] 11.3 Test manifest records format, file size, chapter count, and version inputs. (REQ-10.2)
  - [ ] 11.4 Test latest export per format is discoverable. (REQ-10.3)
  - [ ] 11.5 Test stale detection when active translation version changes. (REQ-10.4)
  - [ ] 11.6 Test missing translation failure classification. (REQ-10.5)
  - [ ] 11.7 Test write/render failure classification with mocks. (REQ-10.6)
  - [ ] 11.8 Test legacy export artifact remains accessible. (REQ-10.7)
  - [ ] 11.9 Test admin API exposes export metadata. (REQ-10.8)
  - [ ] 11.10 Test public API does not expose unpublished export artifacts. (REQ-10.9)

- [ ] 12. Add Frontend Tests If UI Changes
  - [ ] 12.1 Test latest export status renders. (REQ-10.10)
  - [ ] 12.2 Test stale reason renders. (REQ-10.10)
  - [ ] 12.3 Test failed export message renders. (REQ-10.10)
  - [ ] 12.4 Test re-export action triggers existing export flow. (REQ-10.10)

- [ ] 13. Backward Compatibility Checks
  - [ ] 13.1 Confirm existing export formats still generate. (REQ-9.1)
  - [ ] 13.2 Confirm existing download routes still work. (REQ-9.2)
  - [ ] 13.3 Confirm legacy artifacts without manifest remain accessible if supported. (REQ-9.3)
  - [ ] 13.4 Confirm new manifest/metadata fields are additive. (REQ-9.4)
  - [ ] 13.5 Confirm public reader behavior is unchanged. (REQ-9.5)

- [ ] 14. Run Verification
  - [ ] 14.1 Run focused export observability tests.
  - [ ] 14.2 Run existing export tests.
  - [ ] 14.3 Run existing storage contract tests if present.
  - [ ] 14.4 Run admin frontend tests if UI changed.
  - [ ] 14.5 Run `ruff check` on changed backend files and tests.
  - [ ] 14.6 Run configured backend type checker if present.
  - [ ] 14.7 Fix test, lint, and type failures caused by this work.

- [ ] 15. Final Acceptance Review
  - [ ] 15.1 Verify export service writes manifest for completed exports.
  - [ ] 15.2 Verify manifest records output artifact, format, size, chapter count, and input version state.
  - [ ] 15.3 Verify export activity metadata exposes progress, success artifact, or safe failure category/message.
  - [ ] 15.4 Verify admin APIs list exports and latest export per format.
  - [ ] 15.5 Verify admin UI shows status, stale state, failures, and re-export action.
  - [ ] 15.6 Verify existing export/download behavior remains compatible.
  - [ ] 15.7 Verify public APIs do not expose unpublished export artifacts.
  - [ ] 15.8 Verify focused backend and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Export Inventory | 1, 10 |
| REQ-2 Export Manifest | 2, 3, 11 |
| REQ-3 Version/Freshness | 4, 5, 8, 11 |
| REQ-4 Activity Metadata | 6, 11 |
| REQ-5 Failure Classification | 7, 11 |
| REQ-6 Admin Export APIs | 8, 11, 15 |
| REQ-7 Admin UI Visibility | 9, 12, 15 |
| REQ-8 Storage Contract/Cleanup | 10, 11 |
| REQ-9 Backward Compatibility | 13, 15 |
| REQ-10 Tests | 11, 12, 14 |

## Definition of Done

- [ ] Export artifact paths and current behavior are documented.
- [ ] Export manifests are written for completed exports.
- [ ] Export activity metadata records progress/result/failure.
- [ ] Stale detection exists for supported input state dimensions.
- [ ] Admin APIs expose export artifact metadata.
- [ ] Admin UI shows export status and re-export affordance.
- [ ] Existing export and download behavior remains compatible.
- [ ] Public APIs do not expose unpublished export artifacts.
- [ ] Focused backend and frontend tests pass.

