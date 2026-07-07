# Tasks: Glossary Diagnostics Admin Surfacing

## Task List

- [ ] 1. Preflight Diagnostics Review
  - [ ] 1.1 Inspect `TranslateStage` and translation context metadata for glossary-related fields.
  - [ ] 1.2 Inspect `GlossaryPromptInjectionService` output metadata.
  - [ ] 1.3 Inspect translation version save/load/list helpers.
  - [ ] 1.4 Inspect activity worker/queue metadata update paths for translation activities.
  - [ ] 1.5 Inspect admin activity detail API and response models.
  - [ ] 1.6 Inspect admin/editor chapter version APIs and response models.
  - [ ] 1.7 Inspect public reader chapter API to confirm diagnostics are not exposed.
  - [ ] 1.8 Inspect existing frontend admin activity and version UI components.
  - [ ] 1.9 Inspect existing glossary/translation tests and fixtures.

- [ ] 2. Define Compact Diagnostics Contract
  - [ ] 2.1 Define `glossary_diagnostics` dict shape. (REQ-2)
  - [ ] 2.2 Include `glossary_revision`. (REQ-1.3, REQ-2.8)
  - [ ] 2.3 Include `glossary_hash`. (REQ-1.4, REQ-2.9)
  - [ ] 2.4 Include `term_count_available`. (REQ-2.4)
  - [ ] 2.5 Include `term_count_injected`. (REQ-1.5, REQ-2.3)
  - [ ] 2.6 Include `prompt_block_truncated`. (REQ-1.6, REQ-2.5)
  - [ ] 2.7 Include `conflict_count`. (REQ-1.7, REQ-2.6)
  - [ ] 2.8 Include `warning_count`. (REQ-2.7)
  - [ ] 2.9 Include bounded safe `warnings` and `conflicts` lists. (REQ-2.10, REQ-7.4)
  - [ ] 2.10 Document that full prompt text is not stored. (REQ-1.8, REQ-7.1)

- [ ] 3. Add Diagnostics Normalizer
  - [ ] 3.1 Add `normalize_glossary_diagnostics(metadata)` helper. (REQ-2.1)
  - [ ] 3.2 Make missing fields safe and non-raising. (REQ-2.2)
  - [ ] 3.3 Convert raw injected term metadata to compact counts.
  - [ ] 3.4 Convert raw conflict metadata to compact count and bounded safe list.
  - [ ] 3.5 Convert raw warning metadata to compact count and bounded safe list.
  - [ ] 3.6 Detect prompt block truncation.
  - [ ] 3.7 Redact or omit unsafe free-form messages. (REQ-7.5)
  - [ ] 3.8 Add max item and max term length constants. (REQ-7.4)

- [ ] 4. Persist Per-Chapter Diagnostics
  - [ ] 4.1 Invoke normalizer during translation completion or before saving a translation version. (REQ-1.1)
  - [ ] 4.2 Store compact diagnostics under `glossary_diagnostics` in translation version metadata. (REQ-1.2)
  - [ ] 4.3 Store top-level `glossary_revision` if already part of version metadata. (REQ-1.3)
  - [ ] 4.4 Store top-level `glossary_hash` if already part of version metadata. (REQ-1.4)
  - [ ] 4.5 Preserve existing translation version fields. (REQ-8.5)
  - [ ] 4.6 Ensure legacy versions without diagnostics still load. (REQ-8.1)

- [ ] 5. Add Activity Diagnostics Summary
  - [ ] 5.1 Define `glossary_diagnostics_summary` activity metadata shape. (REQ-6)
  - [ ] 5.2 Count chapters with diagnostics. (REQ-6.1)
  - [ ] 5.3 Count chapters with conflicts. (REQ-6.2)
  - [ ] 5.4 Count chapters with truncated prompt blocks. (REQ-6.3)
  - [ ] 5.5 Count chapters with available terms but zero injected terms. (REQ-6.4)
  - [ ] 5.6 Sum total terms available and injected if useful.
  - [ ] 5.7 Compute aggregates from compact diagnostics only. (REQ-6.5)
  - [ ] 5.8 Persist summary in translation activity metadata. (REQ-1.2)
  - [ ] 5.9 Ensure activity records without diagnostics still load. (REQ-8.2)

- [ ] 6. Expose Diagnostics in Admin APIs
  - [ ] 6.1 Add diagnostics to translation activity detail response. (REQ-3.1)
  - [ ] 6.2 Add diagnostics to chapter translation/version detail response. (REQ-3.2)
  - [ ] 6.3 Add aggregate diagnostics to novel translation summary if practical. (REQ-3.3)
  - [ ] 6.4 Update strict response models if fields would be dropped. (REQ-3.5)
  - [ ] 6.5 Keep response changes additive. (REQ-3.4)
  - [ ] 6.6 Confirm public reader APIs do not include diagnostics. (REQ-3.6)

- [ ] 7. Add Filtering or Summary Support
  - [ ] 7.1 Add backend filter or summary for glossary conflicts if efficient. (REQ-5.1)
  - [ ] 7.2 Add backend filter or summary for truncated glossary blocks if efficient. (REQ-5.2)
  - [ ] 7.3 Add backend filter or summary for zero injected terms when approved terms existed if efficient. (REQ-5.3)
  - [ ] 7.4 If efficient filtering is not practical, document it as follow-up and expose aggregate fields first. (REQ-5.4)
  - [ ] 7.5 Avoid frontend filtering that scans full chapter text. (REQ-5.5)

- [ ] 8. Update Admin Activity UI
  - [ ] 8.1 Add glossary diagnostics summary panel to translation activity detail. (REQ-4.1)
  - [ ] 8.2 Show chapters with conflicts count. (REQ-4.4)
  - [ ] 8.3 Show truncated glossary block count. (REQ-4.3)
  - [ ] 8.4 Show zero-injected glossary term count where available.
  - [ ] 8.5 Add link to glossary management/review when diagnostics indicate issues. (REQ-4.6)
  - [ ] 8.6 Show "diagnostics not available" for legacy activities. (REQ-8.3)

- [ ] 9. Update Admin Chapter/Version UI
  - [ ] 9.1 Show glossary injected badge/count. (REQ-4.1)
  - [ ] 9.2 Show glossary revision/hash used by translation. (REQ-4.2)
  - [ ] 9.3 Show prompt block truncated warning. (REQ-4.3)
  - [ ] 9.4 Show warning/conflict counts. (REQ-4.4)
  - [ ] 9.5 Show bounded warning/conflict code list. (REQ-4.5)
  - [ ] 9.6 Avoid rendering full prompt text. (REQ-4.7)
  - [ ] 9.7 Show "diagnostics not available" for legacy versions. (REQ-8.3)

- [ ] 10. Security and Size Review
  - [ ] 10.1 Confirm diagnostics do not persist full provider prompts. (REQ-7.1)
  - [ ] 10.2 Confirm diagnostics do not persist raw source text. (REQ-7.2)
  - [ ] 10.3 Confirm diagnostics do not persist translated chapter text. (REQ-7.2)
  - [ ] 10.4 Confirm diagnostics do not persist provider API keys or hidden config. (REQ-7.3)
  - [ ] 10.5 Confirm warning/conflict lists are bounded. (REQ-7.4)
  - [ ] 10.6 Confirm public APIs do not expose diagnostics. (REQ-3.6)

- [ ] 11. Add Backend Tests
  - [ ] 11.1 Create `backend/tests/test_glossary_diagnostics_admin_surfacing.py`. (REQ-9)
  - [ ] 11.2 Test normalizer handles full raw metadata. (REQ-9.1)
  - [ ] 11.3 Test normalizer handles missing fields. (REQ-9.2)
  - [ ] 11.4 Test normalizer bounds warning/conflict lists. (REQ-9.7)
  - [ ] 11.5 Test translation completion persists per-chapter diagnostics. (REQ-9.3)
  - [ ] 11.6 Test translation activity metadata includes aggregate summary. (REQ-9.4)
  - [ ] 11.7 Test admin version/detail API includes diagnostics. (REQ-9.5)
  - [ ] 11.8 Test public reader API excludes diagnostics. (REQ-9.6)
  - [ ] 11.9 Test legacy translations without diagnostics still load. (REQ-9.9)

- [ ] 12. Add Frontend Tests If UI Is Changed
  - [ ] 12.1 Test activity summary renders.
  - [ ] 12.2 Test glossary conflict badge renders. (REQ-9.8)
  - [ ] 12.3 Test truncation warning renders. (REQ-9.8)
  - [ ] 12.4 Test glossary revision/hash renders when available.
  - [ ] 12.5 Test legacy "not available" state renders.

- [ ] 13. Backward Compatibility Checks
  - [ ] 13.1 Confirm versions without diagnostics load. (REQ-8.1)
  - [ ] 13.2 Confirm activities without diagnostics load. (REQ-8.2)
  - [ ] 13.3 Confirm glossary prompt injection behavior remains unchanged. (REQ-8.4)
  - [ ] 13.4 Confirm translation version schema changes are additive only. (REQ-8.5)
  - [ ] 13.5 Confirm public reader behavior is unchanged.

- [ ] 14. Run Verification
  - [ ] 14.1 Run focused glossary diagnostics backend tests.
  - [ ] 14.2 Run existing glossary prompt injection tests.
  - [ ] 14.3 Run existing translation version/storage tests.
  - [ ] 14.4 Run admin frontend tests if UI was changed.
  - [ ] 14.5 Run `ruff check` on changed backend files and tests.
  - [ ] 14.6 Run configured backend type checker if present.
  - [ ] 14.7 Fix test, lint, and type failures caused by this work.

- [ ] 15. Final Acceptance Review
  - [ ] 15.1 Verify per-chapter glossary diagnostics persist for new translations.
  - [ ] 15.2 Verify activity-level glossary diagnostics summary is available.
  - [ ] 15.3 Verify admin activity and chapter/version APIs expose diagnostics additively.
  - [ ] 15.4 Verify admin UI shows injection counts, truncation warnings, and conflict indicators.
  - [ ] 15.5 Verify diagnostics are bounded and do not store full prompt/source/translation text.
  - [ ] 15.6 Verify public reader APIs do not expose admin diagnostics.
  - [ ] 15.7 Verify legacy translations and activities remain compatible.
  - [ ] 15.8 Verify focused tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Persist Glossary Diagnostics | 2, 3, 4, 5, 11, 15 |
| REQ-2 Normalize Diagnostic Shape | 2, 3, 11 |
| REQ-3 Expose Diagnostics in Admin APIs | 6, 10, 11, 15 |
| REQ-4 Admin UI Visibility | 8, 9, 12, 15 |
| REQ-5 Filtering and Review Workflow | 7, 8, 9 |
| REQ-6 Diagnostics Aggregation | 5, 6, 8, 11, 15 |
| REQ-7 Security and Privacy | 2, 3, 10, 11, 15 |
| REQ-8 Backward Compatibility | 4, 5, 8, 9, 13, 15 |
| REQ-9 Tests | 11, 12, 14 |

## Definition of Done

- [ ] Compact glossary diagnostics contract is defined.
- [ ] Diagnostics normalizer is implemented and tested.
- [ ] New translation versions persist per-chapter diagnostics.
- [ ] Translation activities expose aggregate diagnostics.
- [ ] Admin APIs expose diagnostics additively.
- [ ] Admin UI shows glossary injection counts, conflicts, and truncation warnings.
- [ ] Diagnostics are bounded and do not store full prompts or chapter text.
- [ ] Public reader APIs do not expose diagnostics.
- [ ] Legacy translations and activities remain compatible.
- [ ] Focused backend and frontend tests pass.

