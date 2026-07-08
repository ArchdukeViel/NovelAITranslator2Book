# Tasks: Glossary Diagnostics Admin Surfacing

## Overview

Implement compact admin-only glossary diagnostics for translations.

This work surfaces glossary prompt-injection diagnostics that already exist or can be derived from translation context metadata. It must reuse existing activity metadata, admin API, storage, glossary revision/hash, and observability patterns. It must not change prompt construction, glossary injection rules, glossary approval workflows, translation output, scheduler behavior, cache identity, active-version selection, or public reader behavior.

Scope boundaries:

- No public reader diagnostics exposure.
- No full prompt storage.
- No source or translated chapter text inside diagnostics.
- No glossary rule changes.
- No new glossary revision/hash source of truth.
- No editor QA enforcement changes.
- No scheduler or cache behavior changes.
- New fields must be additive and backward compatible.

## Task List

- [ ] 1. Preflight Diagnostics Review
  - [ ] 1.1 Inspect `TranslateStage` or equivalent translation stage for glossary-related context metadata.
  - [ ] 1.2 Inspect `GlossaryPromptInjectionService` output metadata.
  - [ ] 1.3 Identify existing glossary revision/hash fields from glossary revision invalidation work, if implemented.
  - [ ] 1.4 Inspect translation version save/load/list helpers.
  - [ ] 1.5 Inspect translation activity worker/queue metadata update paths.
  - [ ] 1.6 Inspect existing safe activity metadata merge/update helpers.
  - [ ] 1.7 Inspect admin activity detail APIs and response models.
  - [ ] 1.8 Inspect admin/editor chapter translation detail APIs.
  - [ ] 1.9 Inspect chapter version list/detail APIs and response models.
  - [ ] 1.10 Inspect novel/admin translation summary APIs.
  - [ ] 1.11 Inspect operations/runtime-state or diagnostics routes that could surface aggregate data.
  - [ ] 1.12 Inspect public reader chapter and chapter-list APIs to confirm admin metadata is excluded.
  - [ ] 1.13 Inspect frontend admin activity and chapter/version review components.
  - [ ] 1.14 Inspect existing glossary, translation storage, activity, public reader, and frontend tests.

- [ ] 2. Define Compact Diagnostics Contract
  - [ ] 2.1 Define the `glossary_diagnostics` metadata shape.
  - [ ] 2.2 Include `diagnostics_available`.
  - [ ] 2.3 Include `glossary_revision` when available.
  - [ ] 2.4 Include `glossary_hash` when available.
  - [ ] 2.5 Include `term_count_available`.
  - [ ] 2.6 Include `term_count_injected`.
  - [ ] 2.7 Include `prompt_block_truncated`.
  - [ ] 2.8 Include `conflict_count`.
  - [ ] 2.9 Include `warning_count`.
  - [ ] 2.10 Include bounded safe `warnings` list.
  - [ ] 2.11 Include bounded safe `conflicts` list.
  - [ ] 2.12 Define unavailable-state defaults.
  - [ ] 2.13 Document that full prompt text is not stored.
  - [ ] 2.14 Document that source and translated chapter text are not stored.
  - [ ] 2.15 Document admin-only exposure.

- [ ] 3. Add Diagnostics Normalizer
  - [ ] 3.1 Create `backend/src/novelai/services/glossary_diagnostics.py` or nearest existing metadata helper module.
  - [ ] 3.2 Add `normalize_glossary_diagnostics(metadata)`.
  - [ ] 3.3 Accept raw `TranslationContext.metadata`.
  - [ ] 3.4 Accept glossary prompt-injection metadata.
  - [ ] 3.5 Accept already-normalized diagnostics.
  - [ ] 3.6 Handle missing fields without raising.
  - [ ] 3.7 Return explicit unavailable state when diagnostics cannot be derived.
  - [ ] 3.8 Default missing numeric counts to `0`.
  - [ ] 3.9 Default missing booleans to `false`.
  - [ ] 3.10 Convert raw injected-term metadata to compact counts.
  - [ ] 3.11 Convert raw conflict metadata to compact count and bounded safe list.
  - [ ] 3.12 Convert raw warning metadata to compact count and bounded safe list.
  - [ ] 3.13 Detect prompt block truncation.
  - [ ] 3.14 Redact or omit unsafe free-form messages.
  - [ ] 3.15 Add `MAX_GLOSSARY_DIAGNOSTIC_ITEMS`.
  - [ ] 3.16 Add `MAX_GLOSSARY_DIAGNOSTIC_TERM_LENGTH`.
  - [ ] 3.17 Truncate or omit overlong term values safely.

- [ ] 4. Reuse Existing Glossary Revision and Hash Metadata
  - [ ] 4.1 Identify existing glossary revision source.
  - [ ] 4.2 Identify existing glossary hash source.
  - [ ] 4.3 Reuse existing revision/hash values when available.
  - [ ] 4.4 Do not add a second glossary revision counter.
  - [ ] 4.5 Do not compute a competing glossary hash if glossary invalidation already provides one.
  - [ ] 4.6 Allow diagnostics to persist counts and warning/conflict data when revision/hash are unavailable.
  - [ ] 4.7 Add top-level `glossary_revision`, `glossary_hash`, or `glossary_term_count` only as additive convenience fields.

- [ ] 5. Persist Per-Version Diagnostics
  - [ ] 5.1 Invoke the normalizer during translation completion or immediately before saving a translation version.
  - [ ] 5.2 Store normalized diagnostics under `glossary_diagnostics`.
  - [ ] 5.3 Store diagnostics in translation version metadata where provider/model/glossary metadata already lives.
  - [ ] 5.4 Preserve all existing translation version fields.
  - [ ] 5.5 Preserve existing glossary revision/hash fields.
  - [ ] 5.6 Ensure legacy versions without diagnostics still load.
  - [ ] 5.7 Ensure diagnostics writes follow existing translation storage contract.
  - [ ] 5.8 Ensure JSON-backed metadata uses existing atomic write behavior.

- [ ] 6. Add Activity Diagnostics Aggregation
  - [ ] 6.1 Define `glossary_diagnostics_summary` activity metadata shape.
  - [ ] 6.2 Add `aggregate_glossary_diagnostics(...)` helper.
  - [ ] 6.3 Count `chapters_with_diagnostics`.
  - [ ] 6.4 Count `chapters_missing_diagnostics`.
  - [ ] 6.5 Count `chapters_with_conflicts`.
  - [ ] 6.6 Count `chapters_with_warnings`.
  - [ ] 6.7 Count `chapters_with_truncated_blocks`.
  - [ ] 6.8 Count `chapters_with_zero_injected_terms`.
  - [ ] 6.9 Sum `total_terms_available`.
  - [ ] 6.10 Sum `total_terms_injected`.
  - [ ] 6.11 Sum total `warning_count`.
  - [ ] 6.12 Sum total `conflict_count`.
  - [ ] 6.13 Compute aggregates from compact diagnostics only.
  - [ ] 6.14 Persist summary in translation activity metadata.
  - [ ] 6.15 If per-chapter result objects are not available in memory, compute summary from saved versions at activity completion.
  - [ ] 6.16 Ensure aggregation is safe under parallel chapter translation.

- [ ] 7. Preserve Activity Metadata Merge Safety
  - [ ] 7.1 Use existing safe activity metadata merge/update helpers.
  - [ ] 7.2 Preserve existing activity metadata keys.
  - [ ] 7.3 Do not overwrite crawl/fetch progress or crawl result metadata.
  - [ ] 7.4 Do not overwrite scheduler summary metadata.
  - [ ] 7.5 Do not overwrite glossary editor QA metadata.
  - [ ] 7.6 Do not overwrite other existing observability metadata.
  - [ ] 7.7 Ensure legacy activity records without diagnostics still load.
  - [ ] 7.8 Ensure activity completion recomputation preserves unrelated metadata.

- [ ] 8. Expose Diagnostics in Admin APIs
  - [ ] 8.1 Add `glossary_diagnostics_summary` to translation activity detail responses when available.
  - [ ] 8.2 Preserve diagnostics summary in activity metadata responses.
  - [ ] 8.3 Add active-version glossary diagnostics to chapter translation detail responses when available.
  - [ ] 8.4 Add compact diagnostics fields to chapter version list responses where practical.
  - [ ] 8.5 Add full compact diagnostics to chapter version detail responses.
  - [ ] 8.6 Add aggregate glossary warning/conflict/truncation counts to novel translation summary when practical.
  - [ ] 8.7 Add diagnostics summary to operations/runtime-state or diagnostics route only if a suitable route already exists.
  - [ ] 8.8 Update strict response models if they would drop diagnostics fields.
  - [ ] 8.9 Keep all response changes additive.
  - [ ] 8.10 Represent legacy records as `null`, omitted fields, or `not_available` according to existing API style.

- [ ] 9. Confirm Public Reader Exclusion
  - [ ] 9.1 Confirm public reader chapter responses do not expose `glossary_diagnostics`.
  - [ ] 9.2 Confirm public reader chapter list responses do not expose diagnostics counts.
  - [ ] 9.3 Confirm public version responses, if any, do not expose admin-only diagnostics.
  - [ ] 9.4 Confirm public responses do not expose warning/conflict codes.
  - [ ] 9.5 Confirm public reader response shape remains unchanged except for unrelated approved availability fields.

- [ ] 10. Add Filtering or Summary Support
  - [ ] 10.1 Add backend filter or summary support for `has_glossary_conflicts` when efficient.
  - [ ] 10.2 Add backend filter or summary support for `has_glossary_warnings` when efficient.
  - [ ] 10.3 Add backend filter or summary support for `has_truncated_glossary_block` when efficient.
  - [ ] 10.4 Add backend filter or summary support for `zero_injected_glossary_terms` when efficient.
  - [ ] 10.5 Add backend filter or summary support for `missing_glossary_diagnostics` when efficient.
  - [ ] 10.6 Prefer filtering from saved version metadata.
  - [ ] 10.7 Avoid loading full chapter text for filtering.
  - [ ] 10.8 Avoid frontend-only filtering that scans full prompt or chapter content.
  - [ ] 10.9 If efficient filtering is unsafe for first implementation, expose aggregate fields first and document deep filtering as follow-up.

- [ ] 11. Update Admin Activity UI
  - [ ] 11.1 Add glossary diagnostics summary panel to translation activity detail.
  - [ ] 11.2 Show chapters with diagnostics.
  - [ ] 11.3 Show missing diagnostics count.
  - [ ] 11.4 Show glossary conflict count.
  - [ ] 11.5 Show glossary warning count.
  - [ ] 11.6 Show truncated glossary block count.
  - [ ] 11.7 Show zero-injected-term chapter count.
  - [ ] 11.8 Link to glossary management/review when conflicts or truncation are present.
  - [ ] 11.9 Show "diagnostics not available" for legacy activities.

- [ ] 12. Update Admin Chapter and Version UI
  - [ ] 12.1 Show glossary diagnostics availability state.
  - [ ] 12.2 Show glossary injected badge or count.
  - [ ] 12.3 Show glossary revision/hash when available.
  - [ ] 12.4 Show injected/available term count.
  - [ ] 12.5 Show prompt block truncation warning.
  - [ ] 12.6 Show warning count.
  - [ ] 12.7 Show conflict count.
  - [ ] 12.8 Show bounded warning/conflict code list.
  - [ ] 12.9 Show "diagnostics not available" for legacy versions.
  - [ ] 12.10 Avoid rendering full prompt text.
  - [ ] 12.11 Keep diagnostics UI admin/editor-only.

- [ ] 13. Security and Size Review
  - [ ] 13.1 Confirm diagnostics do not persist full provider prompts.
  - [ ] 13.2 Confirm diagnostics do not persist full glossary prompt blocks.
  - [ ] 13.3 Confirm diagnostics do not persist raw source chapter text.
  - [ ] 13.4 Confirm diagnostics do not persist translated chapter text.
  - [ ] 13.5 Confirm diagnostics do not persist provider request bodies.
  - [ ] 13.6 Confirm diagnostics do not persist provider response bodies.
  - [ ] 13.7 Confirm diagnostics do not persist provider API keys.
  - [ ] 13.8 Confirm diagnostics do not persist account identifiers.
  - [ ] 13.9 Confirm diagnostics do not persist hidden model configuration.
  - [ ] 13.10 Confirm warning/conflict lists are bounded.
  - [ ] 13.11 Confirm safe codes are preferred over free-form messages.
  - [ ] 13.12 Confirm admin UI does not render full prompt text unless an explicit existing admin-debug mode already allows it.

- [ ] 14. Add Backend Tests
  - [ ] 14.1 Create `backend/tests/test_glossary_diagnostics_admin_surfacing.py`.
  - [ ] 14.2 Test normalizer handles full raw metadata.
  - [ ] 14.3 Test normalizer handles missing fields.
  - [ ] 14.4 Test normalizer returns explicit unavailable state.
  - [ ] 14.5 Test normalizer bounds warning lists.
  - [ ] 14.6 Test normalizer bounds conflict lists.
  - [ ] 14.7 Test normalizer truncates or omits overlong terms.
  - [ ] 14.8 Test translation completion persists per-version diagnostics.
  - [ ] 14.9 Test glossary revision/hash fields are reused when already available.
  - [ ] 14.10 Test translation activity metadata includes aggregate diagnostics.
  - [ ] 14.11 Test activity diagnostics summary does not overwrite crawl/fetch metadata.
  - [ ] 14.12 Test activity diagnostics summary does not overwrite scheduler metadata.
  - [ ] 14.13 Test activity diagnostics summary does not overwrite editor QA metadata.
  - [ ] 14.14 Test admin version/detail API includes diagnostics fields.
  - [ ] 14.15 Test admin activity/detail API includes diagnostics summary.
  - [ ] 14.16 Test novel/admin summary includes aggregate counts when implemented.
  - [ ] 14.17 Test public reader API does not expose diagnostics.
  - [ ] 14.18 Test warning/conflict lists are bounded and safe.
  - [ ] 14.19 Test legacy translation versions without diagnostics still load.
  - [ ] 14.20 Test legacy activity records without diagnostics still load.
  - [ ] 14.21 Ensure tests do not call live providers.

- [ ] 15. Add Frontend Tests If UI Changes
  - [ ] 15.1 Test activity diagnostics summary panel renders.
  - [ ] 15.2 Test conflict count renders.
  - [ ] 15.3 Test warning count renders.
  - [ ] 15.4 Test truncation warning renders.
  - [ ] 15.5 Test zero-injection state renders.
  - [ ] 15.6 Test glossary revision/hash renders when available.
  - [ ] 15.7 Test bounded warning/conflict list renders.
  - [ ] 15.8 Test legacy "diagnostics not available" state renders.
  - [ ] 15.9 Test diagnostics are not shown in public reader UI.

- [ ] 16. Backward Compatibility Checks
  - [ ] 16.1 Confirm translation versions without diagnostics load.
  - [ ] 16.2 Confirm activity records without diagnostics load.
  - [ ] 16.3 Confirm admin UI gracefully handles missing diagnostics.
  - [ ] 16.4 Confirm glossary prompt injection behavior remains unchanged.
  - [ ] 16.5 Confirm prompt templates are unchanged except metadata pass-through if needed.
  - [ ] 16.6 Confirm translation version metadata changes are additive only.
  - [ ] 16.7 Confirm activity metadata remains compatible.
  - [ ] 16.8 Confirm crawl/fetch, scheduler, editor QA, and storage metadata remain intact.
  - [ ] 16.9 Confirm public reader behavior is unchanged.
  - [ ] 16.10 Confirm active-version selection is unchanged.
  - [ ] 16.11 Confirm cache identity is unchanged.

- [ ] 17. Run Verification
  - [ ] 17.1 Run focused glossary diagnostics backend tests.
  - [ ] 17.2 Run existing glossary prompt injection tests.
  - [ ] 17.3 Run existing translation version/storage tests.
  - [ ] 17.4 Run existing activity metadata tests.
  - [ ] 17.5 Run existing public reader tests.
  - [ ] 17.6 Run existing crawl/fetch observability tests if present.
  - [ ] 17.7 Run existing scheduler observability tests if present.
  - [ ] 17.8 Run existing editor QA tests if present.
  - [ ] 17.9 Run admin frontend tests if UI changed.
  - [ ] 17.10 Run `ruff check` on changed backend source and test files.
  - [ ] 17.11 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 17.12 Fix test, lint, and type failures caused by this work.

- [ ] 18. Final Acceptance Review
  - [ ] 18.1 Verify per-version glossary diagnostics persist for new translations.
  - [ ] 18.2 Verify activity-level glossary diagnostics summary is available after translation activity completion.
  - [ ] 18.3 Verify admin activity APIs expose diagnostics additively.
  - [ ] 18.4 Verify admin chapter/version APIs expose diagnostics additively.
  - [ ] 18.5 Verify admin UI shows injection counts, truncation warnings, conflicts, warnings, and unavailable states.
  - [ ] 18.6 Verify diagnostics are bounded.
  - [ ] 18.7 Verify diagnostics do not store full prompt, source, or translated text.
  - [ ] 18.8 Verify diagnostics reuse existing glossary revision/hash metadata when available.
  - [ ] 18.9 Verify public reader APIs do not expose admin diagnostics.
  - [ ] 18.10 Verify legacy translations and activities remain compatible.
  - [ ] 18.11 Verify crawl/fetch, scheduler, editor QA, and activity metadata remain intact.
  - [ ] 18.12 Verify focused backend and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Normalize Glossary Diagnostics | 2, 3, 14, 18 |
| REQ-2 Bound Warning and Conflict Details | 2, 3, 13, 14, 18 |
| REQ-3 Persist Per-Version Glossary Diagnostics | 4, 5, 14, 16, 18 |
| REQ-4 Reuse Existing Glossary Revision and Hash Metadata | 1, 4, 5, 14, 18 |
| REQ-5 Aggregate Diagnostics in Activity Metadata | 6, 14, 18 |
| REQ-6 Preserve Activity Metadata Merge Safety | 7, 14, 16, 18 |
| REQ-7 Expose Diagnostics in Admin APIs | 8, 14, 18 |
| REQ-8 Exclude Diagnostics from Public Reader APIs | 9, 13, 14, 16, 18 |
| REQ-9 Admin UI Visibility | 11, 12, 15, 18 |
| REQ-10 Lightweight Filtering and Review Workflow | 10, 11, 12, 18 |
| REQ-11 Security and Size Controls | 2, 3, 9, 13, 14, 18 |
| REQ-12 Backward Compatibility | 5, 7, 8, 9, 16, 17, 18 |
| REQ-13 Tests | 14, 15, 17 |

## Definition of Done

- [ ] Compact `glossary_diagnostics` contract is defined.
- [ ] Diagnostics normalizer is implemented and tested.
- [ ] Missing diagnostics produce an explicit unavailable state.
- [ ] New translation versions persist per-version diagnostics.
- [ ] Existing glossary revision/hash metadata is reused when available.
- [ ] Translation activities expose aggregate glossary diagnostics summary.
- [ ] Activity metadata updates preserve crawl/fetch, scheduler, editor QA, and other observability metadata.
- [ ] Admin APIs expose diagnostics additively.
- [ ] Public reader APIs do not expose diagnostics.
- [ ] Admin UI shows glossary injection counts, conflicts, warnings, truncation, zero-injection, and unavailable states.
- [ ] Filtering or aggregate review support exists for glossary conflicts, warnings, truncation, zero injection, and missing diagnostics.
- [ ] Diagnostics are bounded and do not store full prompts, source text, translated text, provider payloads, secrets, or account identifiers.
- [ ] Legacy translations and activities remain compatible.
- [ ] Glossary prompt injection behavior, prompt templates, scheduler behavior, cache identity, active-version selection, and public reader behavior are unchanged.
- [ ] Focused backend, admin API, and frontend tests pass.