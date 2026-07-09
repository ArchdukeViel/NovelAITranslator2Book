# Requirements: Glossary Diagnostics Admin Surfacing

## Introduction

The translation pipeline already uses glossary data during prompt generation. During that process, the backend can know whether approved terms were available, how many terms were injected, whether the glossary prompt block was truncated, whether conflicts or warnings were detected, and which glossary revision/hash was used.

The remaining gap is admin visibility. These diagnostics are not consistently persisted, aggregated, exposed in admin APIs, or shown in translation review screens.

This spec makes glossary prompt-injection diagnostics visible to admins and reviewers. It is diagnostic-only and additive. It must not change glossary injection rules, prompt construction, glossary review workflows, scheduler behavior, translation output, active-version selection, or public reader behavior.

## Scope

In scope:

- Normalize glossary prompt-injection diagnostics into a compact stable shape.
- Persist per-version glossary diagnostics for new translations.
- Aggregate diagnostics into translation activity metadata.
- Expose diagnostics in admin activity, chapter, version, and summary APIs.
- Show glossary diagnostics in admin/editor UI.
- Support lightweight admin filtering or summary counts for glossary issues.
- Enforce safety controls so diagnostics do not leak prompt/source/translation text.
- Preserve compatibility with legacy translations and activities.

Out of scope:

- Changing which glossary terms are injected.
- Changing prompt templates or prompt policy.
- Changing glossary approval/edit workflows.
- Implementing glossary revision invalidation.
- Implementing glossary-aware editor QA enforcement.
- Adding public reader glossary annotations.
- Exposing diagnostics publicly.
- Storing full prompts by default.

## Requirements

### REQ-1: Normalize Glossary Diagnostics

Glossary diagnostics must use a stable, compact, documented shape.

- REQ-1.1: Add a normalizer/helper that converts raw translation context metadata into compact glossary diagnostics.
- REQ-1.2: The normalizer must accept raw `TranslationContext.metadata`, glossary prompt-injection metadata, or already-normalized diagnostics.
- REQ-1.3: The normalizer must handle missing fields without raising.
- REQ-1.4: The normalized diagnostics must include `diagnostics_available`.
- REQ-1.5: The normalized diagnostics must include `term_count_available`.
- REQ-1.6: The normalized diagnostics must include `term_count_injected`.
- REQ-1.7: The normalized diagnostics must include `prompt_block_truncated`.
- REQ-1.8: The normalized diagnostics must include `conflict_count`.
- REQ-1.9: The normalized diagnostics must include `warning_count`.
- REQ-1.10: The normalized diagnostics must include `glossary_revision` when available.
- REQ-1.11: The normalized diagnostics must include `glossary_hash` when available.
- REQ-1.12: Missing numeric counts must default to `0`.
- REQ-1.13: Missing booleans must default to `false`.
- REQ-1.14: Missing diagnostics must produce an explicit unavailable state rather than failing.

### REQ-2: Bound Warning and Conflict Details

Diagnostics may include warning and conflict details, but they must remain compact and safe.

- REQ-2.1: Diagnostics may include a bounded `warnings` list.
- REQ-2.2: Diagnostics may include a bounded `conflicts` list.
- REQ-2.3: Warning and conflict entries must use stable machine-readable codes.
- REQ-2.4: Warning and conflict entries may include glossary terms only when those terms are already admin-visible glossary entries.
- REQ-2.5: Warning and conflict lists must be bounded by a constant such as `MAX_GLOSSARY_DIAGNOSTIC_ITEMS`.
- REQ-2.6: Stored term values must be bounded by a constant such as `MAX_GLOSSARY_DIAGNOSTIC_TERM_LENGTH`.
- REQ-2.7: Long terms must be truncated or omitted safely.
- REQ-2.8: Free-form messages must be omitted unless already safe, bounded, and admin-appropriate.

### REQ-3: Persist Per-Version Glossary Diagnostics

Glossary diagnostics produced during translation must survive beyond logs.

- REQ-3.1: Persist per-chapter glossary diagnostics when a chapter translation completes.
- REQ-3.2: Persist diagnostics on translation version metadata where provider/model/glossary metadata is already stored.
- REQ-3.3: Diagnostics must be persisted under a stable key such as `glossary_diagnostics`.
- REQ-3.4: Persisted diagnostics must use the normalized compact shape.
- REQ-3.5: Persisted diagnostics must include glossary revision/hash when available.
- REQ-3.6: Persisted diagnostics must include injected and available term counts.
- REQ-3.7: Persisted diagnostics must include prompt block truncation status.
- REQ-3.8: Persisted diagnostics must include warning and conflict counts.
- REQ-3.9: New fields must be additive to existing translation version metadata.
- REQ-3.10: Existing translation version fields must be preserved.

### REQ-4: Reuse Existing Glossary Revision and Hash Metadata

Diagnostics must not create a competing glossary identity system.

- REQ-4.1: If glossary revision/hash metadata is already available from glossary revision invalidation, diagnostics must reuse it.
- REQ-4.2: Diagnostics must not introduce a second glossary revision counter.
- REQ-4.3: Diagnostics must not compute a different glossary hash from the invalidation system when one already exists.
- REQ-4.4: If glossary revision/hash are unavailable, diagnostics must still persist available counts and warning/conflict data.
- REQ-4.5: Top-level `glossary_revision`, `glossary_hash`, and `glossary_term_count` fields may be included only as additive convenience fields.

### REQ-5: Aggregate Diagnostics in Activity Metadata

Translation activities must expose compact glossary diagnostics summaries.

- REQ-5.1: Activity metadata should include `glossary_diagnostics_summary` when translated chapters have diagnostics.
- REQ-5.2: Summary must include `chapters_with_diagnostics`.
- REQ-5.3: Summary must include `chapters_missing_diagnostics`.
- REQ-5.4: Summary must include `chapters_with_conflicts`.
- REQ-5.5: Summary must include `chapters_with_warnings`.
- REQ-5.6: Summary must include `chapters_with_truncated_blocks`.
- REQ-5.7: Summary must include `chapters_with_zero_injected_terms`.
- REQ-5.8: Summary must include `total_terms_available`.
- REQ-5.9: Summary must include `total_terms_injected`.
- REQ-5.10: Summary must include total `warning_count`.
- REQ-5.11: Summary must include total `conflict_count`.
- REQ-5.12: Aggregates must be computed from compact diagnostics, not full prompt text.
- REQ-5.13: Activity summary updates must not overwrite crawl/fetch, scheduler, editor QA, or other observability metadata.
- REQ-5.14: Aggregation must be safe under parallel chapter translation.

### REQ-6: Preserve Activity Metadata Merge Safety

Glossary diagnostics must coexist with other observability specs.

- REQ-6.1: Activity metadata updates must use existing safe merge/update helpers.
- REQ-6.2: Diagnostics aggregation must preserve existing activity metadata keys.
- REQ-6.3: Diagnostics must not remove or replace crawl/fetch progress metadata.
- REQ-6.4: Diagnostics must not remove or replace scheduler summary metadata.
- REQ-6.5: Diagnostics must not remove or replace glossary editor QA metadata.
- REQ-6.6: If activity completion recomputes summaries from saved versions, the recomputation must preserve unrelated metadata.

### REQ-7: Expose Diagnostics in Admin APIs

Admin APIs must expose glossary diagnostics additively.

- REQ-7.1: Translation activity detail responses must include `glossary_diagnostics_summary` when available.
- REQ-7.2: Translation activity metadata responses must preserve diagnostics summary fields.
- REQ-7.3: Chapter translation detail responses must include active-version glossary diagnostics when available.
- REQ-7.4: Chapter version list responses should include compact glossary diagnostics fields.
- REQ-7.5: Chapter version detail responses must include glossary diagnostics when available.
- REQ-7.6: Novel translation summary responses should include aggregate glossary warning/conflict/truncation counts when practical.
- REQ-7.7: Admin operations/runtime-state or diagnostics routes may include glossary diagnostics summary when an appropriate route already exists.
- REQ-7.8: Response changes must be additive.
- REQ-7.9: Strict response models must be updated if they would otherwise drop diagnostics fields.
- REQ-7.10: Legacy records without diagnostics must return `null`, omitted fields, or `not_available` according to existing API style.

### REQ-8: Exclude Diagnostics from Public Reader APIs

Glossary diagnostics are admin-only.

- REQ-8.1: Public reader chapter responses must not expose `glossary_diagnostics`.
- REQ-8.2: Public reader chapter list responses must not expose glossary diagnostic counts.
- REQ-8.3: Public reader version responses, if any, must not expose admin-only diagnostics.
- REQ-8.4: Public reader responses must not expose warning/conflict codes.
- REQ-8.5: Public reader behavior and response shape must remain unchanged except for unrelated already-approved public reader availability fields.

### REQ-9: Admin UI Visibility

Admin UI must make glossary diagnostics visible and actionable.

- REQ-9.1: Translation activity detail UI must show a glossary diagnostics summary panel when summary data is available.
- REQ-9.2: Activity UI must show chapters with diagnostics.
- REQ-9.3: Activity UI must show missing diagnostics count.
- REQ-9.4: Activity UI must show glossary conflict count.
- REQ-9.5: Activity UI must show glossary warning count.
- REQ-9.6: Activity UI must show truncated glossary block count.
- REQ-9.7: Activity UI must show zero-injected-term chapter count.
- REQ-9.8: Chapter/version UI must show whether glossary diagnostics are available.
- REQ-9.9: Chapter/version UI must show glossary revision/hash when available.
- REQ-9.10: Chapter/version UI must show injected/available term counts.
- REQ-9.11: Chapter/version UI must show a warning when the glossary prompt block was truncated.
- REQ-9.12: Chapter/version UI must show warning/conflict counts.
- REQ-9.13: Chapter/version UI may show bounded warning/conflict code lists.
- REQ-9.14: UI should link to glossary management/review screens when diagnostics indicate conflicts or truncation.
- REQ-9.15: UI must show a clear legacy/unavailable state for older versions.

### REQ-10: Support Lightweight Filtering and Review Workflow

Admins should be able to find translations with glossary-related issues.

- REQ-10.1: Admin filtering or summary fields should support `has_glossary_conflicts`.
- REQ-10.2: Admin filtering or summary fields should support `has_glossary_warnings`.
- REQ-10.3: Admin filtering or summary fields should support `has_truncated_glossary_block`.
- REQ-10.4: Admin filtering or summary fields should support `zero_injected_glossary_terms`.
- REQ-10.5: Admin filtering or summary fields should support `missing_glossary_diagnostics`.
- REQ-10.6: Filters should use saved version metadata where practical.
- REQ-10.7: Filters must not require loading full chapter text.
- REQ-10.8: Filters must not require frontend-only scans of full prompt/chapter content.
- REQ-10.9: If efficient filtering is unsafe for the first implementation, aggregate counts may ship first and deep filtering may be documented as follow-up.

### REQ-11: Enforce Security and Size Controls

Diagnostics must not leak sensitive or oversized data.

- REQ-11.1: Do not persist full provider prompts by default.
- REQ-11.2: Do not persist full glossary prompt blocks by default.
- REQ-11.3: Do not persist raw source chapter text inside diagnostics.
- REQ-11.4: Do not persist translated chapter text inside diagnostics.
- REQ-11.5: Do not persist provider request bodies.
- REQ-11.6: Do not persist provider response bodies.
- REQ-11.7: Do not persist provider API keys.
- REQ-11.8: Do not persist account identifiers.
- REQ-11.9: Do not persist hidden model configuration.
- REQ-11.10: Warning/conflict lists must be bounded.
- REQ-11.11: Prefer safe codes over free-form messages.
- REQ-11.12: Admin API and UI must not render full prompt text unless an explicit existing admin-debug mode already allows it.

### REQ-12: Preserve Backward Compatibility

Existing translations, activities, and readers must continue to work.

- REQ-12.1: Translation versions without glossary diagnostics must still load.
- REQ-12.2: Activity records without glossary diagnostics must still load.
- REQ-12.3: Admin UI must gracefully show "not available" for older translations.
- REQ-12.4: Existing glossary prompt injection behavior must remain unchanged.
- REQ-12.5: Existing translation version schema changes must be additive only.
- REQ-12.6: Existing activity metadata must remain compatible.
- REQ-12.7: Existing public reader behavior must remain unchanged.
- REQ-12.8: Existing crawl/fetch, scheduler, editor QA, and storage metadata must remain intact.

### REQ-13: Tests

Focused tests must prove diagnostics are normalized, persisted, exposed, safe, and backward compatible.

- REQ-13.1: Test diagnostics normalizer handles full raw metadata.
- REQ-13.2: Test diagnostics normalizer handles missing fields.
- REQ-13.3: Test diagnostics normalizer returns explicit unavailable state.
- REQ-13.4: Test diagnostics normalizer bounds warning lists.
- REQ-13.5: Test diagnostics normalizer bounds conflict lists.
- REQ-13.6: Test diagnostics normalizer truncates or omits overlong terms.
- REQ-13.7: Test translation completion persists per-version glossary diagnostics.
- REQ-13.8: Test glossary revision/hash fields are reused when already available.
- REQ-13.9: Test translation activity metadata includes aggregate diagnostics.
- REQ-13.10: Test activity diagnostics summary does not overwrite other observability metadata.
- REQ-13.11: Test admin version/detail API includes diagnostics fields.
- REQ-13.12: Test admin activity/detail API includes diagnostics summary.
- REQ-13.13: Test novel/admin summary includes aggregate counts when implemented.
- REQ-13.14: Test public reader API does not expose diagnostics.
- REQ-13.15: Test warning/conflict lists are bounded and safe.
- REQ-13.16: Test legacy translation versions without diagnostics still load.
- REQ-13.17: Test legacy activity records without diagnostics still load.
- REQ-13.18: Test admin UI displays activity summary when frontend is changed.
- REQ-13.19: Test admin UI displays conflict, warning, truncation, zero-injection, and unavailable states when frontend is changed.
- REQ-13.20: Tests must not call live providers.

## Non-Goals

- This spec does not change glossary prompt injection rules.
- This spec does not change glossary review workflows.
- This spec does not change prompt templates.
- This spec does not change translation output.
- This spec does not change scheduler behavior.
- This spec does not change cache identity.
- This spec does not change active-version selection.
- This spec does not implement glossary revision invalidation; that belongs to `glossary-revision-translation-invalidation`.
- This spec does not implement glossary-aware manual editor linting; that belongs to `glossary-aware-editor-qa`.
- This spec does not add public reader glossary annotations.
- This spec does not expose diagnostics in public reader APIs.
- This spec does not store full prompts by default.