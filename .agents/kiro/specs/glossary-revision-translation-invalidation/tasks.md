# Tasks: Glossary Revision Translation Invalidation

## Task List

- [ ] 1. Preflight Glossary and Translation Review
  - [ ] 1.1 Inspect glossary DB models for `glossary_revision` ownership.
  - [ ] 1.2 Inspect glossary create/update/delete approval flows and confirm when revision increments.
  - [ ] 1.3 Inspect `GlossaryPromptInjectionService` and prompt glossary metadata output.
  - [ ] 1.4 Inspect `TranslateStage` for glossary metadata already attached to translation context.
  - [ ] 1.5 Inspect translation cache key generation.
  - [ ] 1.6 Inspect `storage/translations.py` version save/load/list helpers.
  - [ ] 1.7 Inspect admin/editor version APIs and response models.
  - [ ] 1.8 Inspect existing retranslation activity/endpoint behavior.
  - [ ] 1.9 Inspect existing translation and glossary tests.

- [ ] 2. Define Glossary Snapshot Helper
  - [ ] 2.1 Add `GlossarySnapshot` helper or equivalent typed structure. (REQ-1, REQ-3)
  - [ ] 2.2 Include `revision`.
  - [ ] 2.3 Include `hash`.
  - [ ] 2.4 Include approved term count.
  - [ ] 2.5 Ensure hash generation is stable and deterministic.
  - [ ] 2.6 Exclude volatile timestamp-only fields from the hash unless intentionally required.
  - [ ] 2.7 Add unit tests for deterministic hash ordering.

- [ ] 3. Verify or Fix Glossary Revision Increment
  - [ ] 3.1 Confirm approved term creation increments `Novel.glossary_revision`. (REQ-5.1)
  - [ ] 3.2 Confirm approved translation update increments revision. (REQ-5.1)
  - [ ] 3.3 Confirm approved term deletion/deactivation increments revision. (REQ-5.1)
  - [ ] 3.4 Confirm enforcement level changes increment revision. (REQ-5.1)
  - [ ] 3.5 Confirm aliases used in prompt injection increment revision when changed. (REQ-5.1)
  - [ ] 3.6 Add missing revision increments if any path is incomplete.
  - [ ] 3.7 Add tests for each meaningful revision increment path.

- [ ] 4. Store Glossary Metadata on New Translation Versions
  - [ ] 4.1 Pass current glossary snapshot into translation result/version save path. (REQ-1.1, REQ-1.2)
  - [ ] 4.2 Store `glossary_revision` on new translation versions. (REQ-1.1)
  - [ ] 4.3 Store `glossary_hash` when available. (REQ-1.2)
  - [ ] 4.4 Store `glossary_term_count` when available. (REQ-1.3)
  - [ ] 4.5 Store `glossary_stale=false` for newly created versions using current glossary. (REQ-1.4)
  - [ ] 4.6 Preserve all existing translation version fields. (REQ-1.6)
  - [ ] 4.7 Ensure storage loaders tolerate missing glossary fields on old versions. (REQ-1.5, REQ-9.1)

- [ ] 5. Include Glossary Identity in Cache Keys
  - [ ] 5.1 Locate translation cache key builder. (REQ-2)
  - [ ] 5.2 Add `glossary_revision` to cache key identity. (REQ-2.1)
  - [ ] 5.3 Add `glossary_hash` to cache key identity when available. (REQ-2.2)
  - [ ] 5.4 Preserve existing key dimensions such as provider, model, language, prompt settings, and source identity. (REQ-2.3)
  - [ ] 5.5 Ensure old cache entries without glossary revision are not reused for non-zero current revision. (REQ-2.5, REQ-9.4)
  - [ ] 5.6 Add tests proving cache keys differ after glossary revision changes. (REQ-10.3)

- [ ] 6. Add Stale Detection Helpers
  - [ ] 6.1 Add helper to compare version glossary metadata to current glossary snapshot. (REQ-3.1)
  - [ ] 6.2 Mark version stale when version revision is lower than current revision. (REQ-3.2)
  - [ ] 6.3 Mark version stale when current hash exists and stored hash differs. (REQ-3.3)
  - [ ] 6.4 Treat missing glossary metadata as legacy/unknown. (REQ-3.4)
  - [ ] 6.5 Add optional stale reason values: `fresh`, `legacy_missing_revision`, `revision_mismatch`, `hash_mismatch`.
  - [ ] 6.6 Ensure helper does not change active version selection. (REQ-3.5, REQ-7.1)

- [ ] 7. Expose Staleness in Storage Load/List
  - [ ] 7.1 Update `load_translated_chapter` or admin-specific loaders to compute active version freshness. (REQ-4.2)
  - [ ] 7.2 Update `list_translated_chapter_versions` to include freshness fields. (REQ-4.1)
  - [ ] 7.3 Include `current_glossary_revision` where helpful. (REQ-4.1)
  - [ ] 7.4 Include `glossary_stale_reason` where helpful.
  - [ ] 7.5 Ensure historical versions are evaluated independently. (REQ-5.5)
  - [ ] 7.6 Keep response changes additive. (REQ-4.4)

- [ ] 8. Add Aggregate Stale Translation Count
  - [ ] 8.1 Add helper to count chapters whose active translation is glossary-stale. (REQ-4.3)
  - [ ] 8.2 Use existing translated chapter listing helpers.
  - [ ] 8.3 Avoid expensive full text reads when version metadata is sufficient.
  - [ ] 8.4 Expose count in admin novel summary if practical. (REQ-4.3)
  - [ ] 8.5 Keep aggregate optional if performance or API shape makes it unsafe for first implementation.

- [ ] 9. Add Retranslate Stale Operation
  - [ ] 9.1 Decide whether to add a new endpoint or extend existing retranslation endpoint with `stale_only=true`. (REQ-6.1)
  - [ ] 9.2 Support a single chapter. (REQ-6.2)
  - [ ] 9.3 Support all stale chapters in a novel. (REQ-6.3)
  - [ ] 9.4 Reuse existing translation locks. (REQ-6.7)
  - [ ] 9.5 Reuse existing activity/job tracking. (REQ-6.7)
  - [ ] 9.6 Force retranslation only for stale selected chapters.
  - [ ] 9.7 Save a new translation version rather than overwriting stale version. (REQ-6.5)
  - [ ] 9.8 Ensure new version uses current glossary revision/hash. (REQ-6.4)
  - [ ] 9.9 Ensure new version is fresh after completion. (REQ-6.6)

- [ ] 10. Preserve Active Version Semantics
  - [ ] 10.1 Confirm stale detection does not deactivate active versions. (REQ-7.1)
  - [ ] 10.2 Preserve existing auto-activate behavior for newly saved translations. (REQ-7.2, REQ-7.3)
  - [ ] 10.3 If existing behavior requires manual activation, keep using existing version controls. (REQ-7.4)
  - [ ] 10.4 Confirm public reader still uses active version selection. (REQ-7.5)

- [ ] 11. Update Admin API Response Models
  - [ ] 11.1 Add `glossary_revision` to version list/detail response models. (REQ-4.1)
  - [ ] 11.2 Add `glossary_hash` where available. (REQ-4.1)
  - [ ] 11.3 Add `current_glossary_revision`. (REQ-4.1)
  - [ ] 11.4 Add `glossary_stale`. (REQ-4.1, REQ-4.2)
  - [ ] 11.5 Add `glossary_stale_reason` where useful.
  - [ ] 11.6 Add aggregate `stale_translation_count` to novel summary if implemented. (REQ-4.3)
  - [ ] 11.7 Ensure strict response models do not drop new fields. (REQ-4.5)

- [ ] 12. Update Admin UI
  - [ ] 12.1 Show stale glossary badge in translation/version UI. (REQ-8.1)
  - [ ] 12.2 Show version glossary revision vs current revision. (REQ-8.3)
  - [ ] 12.3 Show stale translation count in novel summary if API provides it. (REQ-8.2)
  - [ ] 12.4 Add retranslate stale action. (REQ-8.4)
  - [ ] 12.5 Keep stale warnings out of public reader UI. (REQ-8.5)

- [ ] 13. Add Backend Tests
  - [ ] 13.1 Create `backend/tests/test_glossary_revision_translation_invalidation.py`. (REQ-10)
  - [ ] 13.2 Test new translation versions store `glossary_revision`. (REQ-10.1)
  - [ ] 13.3 Test new translation versions store `glossary_hash` when available. (REQ-10.2)
  - [ ] 13.4 Test cache keys differ after glossary revision changes. (REQ-10.3)
  - [ ] 13.5 Test active version staleness after glossary revision increments. (REQ-10.4)
  - [ ] 13.6 Test historical versions compute staleness independently. (REQ-10.5)
  - [ ] 13.7 Test legacy versions without glossary metadata remain loadable. (REQ-10.6)
  - [ ] 13.8 Test retranslate-stale creates a new fresh version. (REQ-10.7)
  - [ ] 13.9 Test stale detection does not deactivate active version. (REQ-10.8)
  - [ ] 13.10 Test admin API responses include freshness fields. (REQ-10.9)

- [ ] 14. Add Frontend Tests If UI Is Changed
  - [ ] 14.1 Test stale badge rendering. (REQ-10.10)
  - [ ] 14.2 Test tooltip/revision display.
  - [ ] 14.3 Test retranslate stale action calls API.
  - [ ] 14.4 Test fresh version removes stale badge after data refresh.

- [ ] 15. Backward Compatibility Checks
  - [ ] 15.1 Confirm translation versions without glossary metadata still load. (REQ-9.1)
  - [ ] 15.2 Confirm existing active version selection still works. (REQ-9.2)
  - [ ] 15.3 Confirm existing glossary gate behavior remains intact. (REQ-9.3)
  - [ ] 15.4 Confirm old cache entries are not reused incorrectly. (REQ-9.4)
  - [ ] 15.5 Confirm no DB migration is needed if `Novel.glossary_revision` already exists. (REQ-9.5)

- [ ] 16. Run Verification
  - [ ] 16.1 Run focused glossary revision invalidation tests.
  - [ ] 16.2 Run existing glossary tests.
  - [ ] 16.3 Run existing translation storage tests.
  - [ ] 16.4 Run existing translation cache tests.
  - [ ] 16.5 Run frontend/admin tests if UI was changed.
  - [ ] 16.6 Run `ruff check` on changed backend files and tests.
  - [ ] 16.7 Run configured backend type checker if present.
  - [ ] 16.8 Fix test, lint, and type failures caused by this work.

- [ ] 17. Final Acceptance Review
  - [ ] 17.1 Verify new translation versions store glossary revision metadata.
  - [ ] 17.2 Verify cache keys vary by glossary revision/hash.
  - [ ] 17.3 Verify active and historical versions classify as fresh, stale, or legacy/unknown.
  - [ ] 17.4 Verify glossary edits make older translations visibly stale.
  - [ ] 17.5 Verify admin APIs expose glossary freshness fields additively.
  - [ ] 17.6 Verify admin can retranslate stale chapters and produce fresh versions.
  - [ ] 17.7 Verify stale detection does not deactivate active versions.
  - [ ] 17.8 Verify legacy versions without glossary metadata remain loadable.
  - [ ] 17.9 Verify existing glossary gate and prompt injection behavior remain intact.
  - [ ] 17.10 Verify focused tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Store Glossary Revision on Versions | 2, 4, 7, 13, 17 |
| REQ-2 Include Glossary Revision in Cache Keys | 5, 13, 15, 17 |
| REQ-3 Detect Stale Translation Versions | 6, 7, 13, 17 |
| REQ-4 Expose Freshness in Admin APIs | 7, 8, 11, 13, 17 |
| REQ-5 Mark/Recompute Staleness After Glossary Changes | 3, 6, 7, 13, 17 |
| REQ-6 Retranslate Stale Chapters | 9, 13, 17 |
| REQ-7 Preserve Active Version Semantics | 10, 13, 15, 17 |
| REQ-8 Admin UI Visibility | 12, 14, 17 |
| REQ-9 Backward Compatibility | 4, 5, 10, 15, 17 |
| REQ-10 Tests | 13, 14, 16 |

## Definition of Done

- [ ] New translation versions store `glossary_revision`.
- [ ] New translation versions store `glossary_hash` when available.
- [ ] Translation cache keys include glossary identity.
- [ ] Stale detection works for active, historical, and legacy versions.
- [ ] Admin APIs expose glossary freshness fields.
- [ ] Admin can retranslate stale chapters using current glossary.
- [ ] Fresh retranslations create new versions.
- [ ] Active version behavior is preserved.
- [ ] Existing glossary gate and prompt injection still work.
- [ ] Focused backend and UI tests pass.

