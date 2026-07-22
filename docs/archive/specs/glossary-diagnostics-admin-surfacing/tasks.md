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

- [x] 1. Preflight Diagnostics Review
  - [x] 1.1 Inspect `TranslateStage` or equivalent translation stage for glossary-related context metadata.
  - [x] 1.2 Inspect `GlossaryPromptInjectionService` output metadata.
  - [x] 1.3 Identify existing glossary revision/hash fields from glossary revision invalidation work, if implemented.
  - [x] 1.4 Inspect translation version save/load/list helpers.
  - [x] 1.5 Inspect translation activity worker/queue metadata update paths.
  - [x] 1.6 Inspect existing safe activity metadata merge/update helpers.
  - [x] 1.7 Inspect admin activity detail APIs and response models.
  - [x] 1.8 Inspect admin/editor chapter translation detail APIs.
  - [x] 1.9 Inspect chapter version list/detail APIs and response models.
  - [x] 1.10 Inspect novel/admin translation summary APIs.
  - [x] 1.11 Inspect operations/runtime-state or diagnostics routes that could surface aggregate data.
  - [x] 1.12 Inspect public reader chapter and chapter-list APIs to confirm admin metadata is excluded.
  - [x] 1.13 Inspect frontend admin activity and chapter/version review components.
  - [x] 1.14 Inspect existing glossary, translation storage, activity, public reader, and frontend tests.

- [x] 2. Define Compact Diagnostics Contract
  - [x] 2.1 Define the `glossary_diagnostics` metadata shape.
  - [x] 2.2 Include `diagnostics_available`.
  - [x] 2.3 Include `glossary_revision` when available.
  - [x] 2.4 Include `glossary_hash` when available.
  - [x] 2.5 Include `term_count_available`.
  - [x] 2.6 Include `term_count_injected`.
  - [x] 2.7 Include `prompt_block_truncated`.
  - [x] 2.8 Include `conflict_count`.
  - [x] 2.9 Include `warning_count`.
  - [x] 2.10 Include bounded safe `warnings` list.
  - [x] 2.11 Include bounded safe `conflicts` list.
  - [x] 2.12 Define unavailable-state defaults.
  - [x] 2.13 Document that full prompt text is not stored.
  - [x] 2.14 Document that source and translated chapter text are not stored.
  - [x] 2.15 Document admin-only exposure.

- [x] 3. Add Diagnostics Normalizer
  - [x] 3.1 Create `backend/src/novelai/services/glossary_diagnostics.py` or nearest existing metadata helper module.
  - [x] 3.2 Add `normalize_glossary_diagnostics(metadata)`.
  - [x] 3.3 Accept raw `TranslationContext.metadata`.
  - [x] 3.4 Accept glossary prompt-injection metadata.
  - [x] 3.5 Accept already-normalized diagnostics.
  - [x] 3.6 Handle missing fields without raising.
  - [x] 3.7 Return explicit unavailable state when diagnostics cannot be derived.
  - [x] 3.8 Default missing numeric counts to `0`.
  - [x] 3.9 Default missing booleans to `false`.
  - [x] 3.10 Convert raw injected-term metadata to compact counts.
  - [x] 3.11 Convert raw conflict metadata to compact count and bounded safe list.
  - [x] 3.12 Convert raw warning metadata to compact count and bounded safe list.
  - [x] 3.13 Detect prompt block truncation.
  - [x] 3.14 Redact or omit unsafe free-form messages.
  - [x] 3.15 Add `MAX_GLOSSARY_DIAGNOSTIC_ITEMS`.
  - [x] 3.16 Add `MAX_GLOSSARY_DIAGNOSTIC_TERM_LENGTH`.
  - [x] 3.17 Truncate or omit overlong term values safely.

- [x] 4. Reuse Existing Glossary Revision and Hash Metadata
  - [x] 4.1 Identify existing glossary revision source.
  - [x] 4.2 Identify existing glossary hash source.
  - [x] 4.3 Reuse existing revision/hash values when available.
  - [x] 4.4 Do not add a second glossary revision counter.
  - [x] 4.5 Do not compute a competing glossary hash if glossary invalidation already provides one.
  - [x] 4.6 Allow diagnostics to persist counts and warning/conflict data when revision/hash are unavailable.
  - [x] 4.7 Add top-level `glossary_revision`, `glossary_hash`, or `glossary_term_count` only as additive convenience fields.

- [x] 5. Persist Per-Version Diagnostics
  - [x] 5.1 Invoke the normalizer during translation completion or immediately before saving a translation version.
  - [x] 5.2 Store normalized diagnostics under `glossary_diagnostics`.
  - [x] 5.3 Store diagnostics in translation version metadata where provider/model/glossary metadata already lives.
  - [x] 5.4 Preserve all existing translation version fields.
  - [x] 5.5 Preserve existing glossary revision/hash fields.
  - [x] 5.6 Ensure legacy versions without diagnostics still load.
  - [x] 5.7 Ensure diagnostics writes follow existing translation storage contract.
  - [x] 5.8 Ensure JSON-backed metadata uses existing atomic write behavior.

- [x] 6. Add Activity Diagnostics Aggregation
  - [x] 6.1 Define `glossary_diagnostics_summary` activity metadata shape.
  - [x] 6.2 Add `aggregate_glossary_diagnostics(...)` helper.
  - [x] 6.3 Count `chapters_with_diagnostics`.
  - [x] 6.4 Count `chapters_missing_diagnostics`.
  - [x] 6.5 Count `chapters_with_conflicts`.
  - [x] 6.6 Count `chapters_with_warnings`.
  - [x] 6.7 Count `chapters_with_truncated_blocks`.
  - [x] 6.8 Count `chapters_with_zero_injected_terms`.
  - [x] 6.9 Sum `total_terms_available`.
  - [x] 6.10 Sum `total_terms_injected`.
  - [x] 6.11 Sum total `warning_count`.
  - [x] 6.12 Sum total `conflict_count`.
  - [x] 6.13 Compute aggregates from compact diagnostics only.
  - [x] 6.14 Persist summary in translation activity metadata.
  - [x] 6.15 If per-chapter result objects are not available in memory, compute summary from saved versions at activity completion.
  - [x] 6.16 Ensure aggregation is safe under parallel chapter translation.

- [x] 7. Preserve Activity Metadata Merge Safety
  - [x] 7.1 Use existing safe activity metadata merge/update helpers.
  - [x] 7.2 Preserve existing activity metadata keys.
  - [x] 7.3 Do not overwrite crawl/fetch progress or crawl result metadata.
  - [x] 7.4 Do not overwrite scheduler summary metadata.
  - [x] 7.5 Do not overwrite glossary editor QA metadata.
  - [x] 7.6 Do not overwrite other existing observability metadata.
  - [x] 7.7 Ensure legacy activity records without diagnostics still load.
  - [x] 7.8 Ensure activity completion recomputation preserves unrelated metadata.

- [x] 8. Expose Diagnostics in Admin APIs
  - [x] 8.1 Add `glossary_diagnostics_summary` to translation activity detail responses when available.
  - [x] 8.2 Preserve diagnostics summary in activity metadata responses.
  - [x] 8.3 Add active-version glossary diagnostics to chapter translation detail responses when available.
  - [x] 8.4 Add compact diagnostics fields to chapter version list responses where practical.
  - [x] 8.5 Add full compact diagnostics to chapter version detail responses.
  - [x] 8.6 Add aggregate glossary warning/conflict/truncation counts to novel translation summary when practical.
  - [x] 8.7 Add diagnostics summary to operations/runtime-state or diagnostics route only if a suitable route already exists.
  - [x] 8.8 Update strict response models if they would drop diagnostics fields.
  - [x] 8.9 Keep all response changes additive.
  - [x] 8.10 Represent legacy records as `null`, omitted fields, or `not_available` according to existing API style.

- [x] 9. Confirm Public Reader Exclusion
  - [x] 9.1 Confirm public reader chapter responses do not expose `glossary_diagnostics`.
  - [x] 9.2 Confirm public reader chapter list responses do not expose diagnostics counts.
  - [x] 9.3 Confirm public version responses, if any, do not expose admin-only diagnostics.
  - [x] 9.4 Confirm public responses do not expose warning/conflict codes.
  - [x] 9.5 Confirm public reader response shape remains unchanged except for unrelated approved availability fields.

- [x] 10. Add Filtering or Summary Support
  - [x] 10.1 Add backend filter or summary support for `has_glossary_conflicts` when efficient.
  - [x] 10.2 Add backend filter or summary support for `has_glossary_warnings` when efficient.
  - [x] 10.3 Add backend filter or summary support for `has_truncated_glossary_block` when efficient.
  - [x] 10.4 Add backend filter or summary support for `zero_injected_glossary_terms` when efficient.
  - [x] 10.5 Add backend filter or summary support for `missing_glossary_diagnostics` when efficient.
  - [x] 10.6 Prefer filtering from saved version metadata.
  - [x] 10.7 Avoid loading full chapter text for filtering.
  - [x] 10.8 Avoid frontend-only filtering that scans full prompt or chapter content.
  - [x] 10.9 If efficient filtering is unsafe for first implementation, expose aggregate fields first and document deep filtering as follow-up.

- [x] 11. Update Admin Activity UI
  - [x] 11.1 Add glossary diagnostics summary panel to translation activity detail.
  - [x] 11.2 Show chapters with diagnostics.
  - [x] 11.3 Show missing diagnostics count.
  - [x] 11.4 Show glossary conflict count.
  - [x] 11.5 Show glossary warning count.
  - [x] 11.6 Show truncated glossary block count.
  - [x] 11.7 Show zero-injected-term chapter count.
  - [x] 11.8 Link to glossary management/review when conflicts or truncation are present.
  - [x] 11.9 Show "diagnostics not available" for legacy activities.

- [x] 12. Update Admin Chapter and Version UI
  - [x] 12.1 Show glossary diagnostics availability state.
  - [x] 12.2 Show glossary injected badge or count.
  - [x] 12.3 Show glossary revision/hash when available.
  - [x] 12.4 Show injected/available term count.
  - [x] 12.5 Show prompt block truncation warning.
  - [x] 12.6 Show warning count.
  - [x] 12.7 Show conflict count.
  - [x] 12.8 Show bounded warning/conflict code list.
  - [x] 12.9 Show "diagnostics not available" for legacy versions.
  - [x] 12.10 Avoid rendering full prompt text.
  - [x] 12.11 Keep diagnostics UI admin/editor-only.

- [x] 13. Security and Size Review
  - [x] 13.1 Confirm diagnostics do not persist full provider prompts.
  - [x] 13.2 Confirm diagnostics do not persist full glossary prompt blocks.
  - [x] 13.3 Confirm diagnostics do not persist raw source chapter text.
  - [x] 13.4 Confirm diagnostics do not persist translated chapter text.
  - [x] 13.5 Confirm diagnostics do not persist provider request bodies.
  - [x] 13.6 Confirm diagnostics do not persist provider response bodies.
  - [x] 13.7 Confirm diagnostics do not persist provider API keys.
  - [x] 13.8 Confirm diagnostics do not persist account identifiers.
  - [x] 13.9 Confirm diagnostics do not persist hidden model configuration.
  - [x] 13.10 Confirm warning/conflict lists are bounded.
  - [x] 13.11 Confirm safe codes are preferred over free-form messages.
  - [x] 13.12 Confirm admin UI does not render full prompt text unless an explicit existing admin-debug mode already allows it.

- [x] 14. Add Backend Tests
  - [x] 14.1 Create `backend/tests/test_glossary_diagnostics_admin_surfacing.py`.
  - [x] 14.2 Test normalizer handles full raw metadata.
  - [x] 14.3 Test normalizer handles missing fields.
  - [x] 14.4 Test normalizer returns explicit unavailable state.
  - [x] 14.5 Test normalizer bounds warning lists.
  - [x] 14.6 Test normalizer bounds conflict lists.
  - [x] 14.7 Test normalizer truncates or omits overlong terms.
  - [x] 14.8 Test translation completion persists per-version diagnostics.
  - [x] 14.9 Test glossary revision/hash fields are reused when already available.
  - [x] 14.10 Test translation activity metadata includes aggregate diagnostics.
  - [x] 14.11 Test activity diagnostics summary does not overwrite crawl/fetch metadata.
  - [x] 14.12 Test activity diagnostics summary does not overwrite scheduler metadata.
  - [x] 14.13 Test activity diagnostics summary does not overwrite editor QA metadata.
  - [x] 14.14 Test admin version/detail API includes diagnostics fields.
  - [x] 14.15 Test admin activity/detail API includes diagnostics summary.
  - [x] 14.16 Test novel/admin summary includes aggregate counts when implemented.
  - [x] 14.17 Test public reader API does not expose diagnostics.
  - [x] 14.18 Test warning/conflict lists are bounded and safe.
  - [x] 14.19 Test legacy translation versions without diagnostics still load.
  - [x] 14.20 Test legacy activity records without diagnostics still load.
  - [x] 14.21 Ensure tests do not call live providers.

- [x] 15. Add Frontend Tests If UI Changes
  - [x] 15.1 Test activity diagnostics summary panel renders.
  - [x] 15.2 Test conflict count renders.
  - [x] 15.3 Test warning count renders.
  - [x] 15.4 Test truncation warning renders.
  - [x] 15.5 Test zero-injection state renders.
  - [x] 15.6 Test glossary revision/hash renders when available.
  - [x] 15.7 Test bounded warning/conflict list renders.
  - [x] 15.8 Test legacy "diagnostics not available" state renders.
  - [x] 15.9 Test diagnostics are not shown in public reader UI.

- [x] 16. Backward Compatibility Checks
  - [x] 16.1 Confirm translation versions without diagnostics load.
  - [x] 16.2 Confirm activity records without diagnostics load.
  - [x] 16.3 Confirm admin UI gracefully handles missing diagnostics.
  - [x] 16.4 Confirm glossary prompt injection behavior remains unchanged.
  - [x] 16.5 Confirm prompt templates are unchanged except metadata pass-through if needed.
  - [x] 16.6 Confirm translation version metadata changes are additive only.
  - [x] 16.7 Confirm activity metadata remains compatible.
  - [x] 16.8 Confirm crawl/fetch, scheduler, editor QA, and storage metadata remain intact.
  - [x] 16.9 Confirm public reader behavior is unchanged.
  - [x] 16.10 Confirm active-version selection is unchanged.
  - [x] 16.11 Confirm cache identity is unchanged.

- [x] 17. Run Verification
  - [x] 17.1 Run focused glossary diagnostics backend tests.
  - [x] 17.2 Run existing glossary prompt injection tests.
  - [x] 17.3 Run existing translation version/storage tests.
  - [x] 17.4 Run existing activity metadata tests.
  - [x] 17.5 Run existing public reader tests.
  - [x] 17.6 Run existing crawl/fetch observability tests if present.
  - [x] 17.7 Run existing scheduler observability tests if present.
  - [x] 17.8 Run existing editor QA tests if present.
  - [x] 17.9 Run admin frontend tests if UI changed.
  - [x] 17.10 Run `ruff check` on changed backend source and test files.
  - [x] 17.11 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 17.12 Fix test, lint, and type failures caused by this work.

- [x] 18. Final Acceptance Review
  - [x] 18.1 Verify per-version glossary diagnostics persist for new translations.
  - [x] 18.2 Verify activity-level glossary diagnostics summary is available after translation activity completion.
  - [x] 18.3 Verify admin activity APIs expose diagnostics additively.
  - [x] 18.4 Verify admin chapter/version APIs expose diagnostics additively.
  - [x] 18.5 Verify admin UI shows injection counts, truncation warnings, conflicts, warnings, and unavailable states.
  - [x] 18.6 Verify diagnostics are bounded.
  - [x] 18.7 Verify diagnostics do not store full prompt, source, or translated text.
  - [x] 18.8 Verify diagnostics reuse existing glossary revision/hash metadata when available.
  - [x] 18.9 Verify public reader APIs do not expose admin diagnostics.
  - [x] 18.10 Verify legacy translations and activities remain compatible.
  - [x] 18.11 Verify crawl/fetch, scheduler, editor QA, and activity metadata remain intact.
  - [x] 18.12 Verify focused backend and frontend tests pass.

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

- [x] Compact `glossary_diagnostics` contract is defined.
- [x] Diagnostics normalizer is implemented and tested.
- [x] Missing diagnostics produce an explicit unavailable state.
- [x] New translation versions persist per-version diagnostics.
- [x] Existing glossary revision/hash metadata is reused when available.
- [x] Translation activities expose aggregate glossary diagnostics summary.
- [x] Activity metadata updates preserve crawl/fetch, scheduler, editor QA, and other observability metadata.
- [x] Admin APIs expose diagnostics additively.
- [x] Public reader APIs do not expose diagnostics.
- [x] Admin UI shows glossary injection counts, conflicts, warnings, truncation, zero-injection, and unavailable states.
- [x] Filtering or aggregate review support exists for glossary conflicts, warnings, truncation, zero injection, and missing diagnostics.
- [x] Diagnostics are bounded and do not store full prompts, source text, translated text, provider payloads, secrets, or account identifiers.
- [x] Legacy translations and activities remain compatible.
- [x] Glossary prompt injection behavior, prompt templates, scheduler behavior, cache identity, active-version selection, and public reader behavior are unchanged.
- [x] Focused backend, admin API, and frontend tests pass.