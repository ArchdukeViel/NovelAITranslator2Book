# Requirements: Glossary-Aware Editor QA

## Introduction

Manual editing can currently save translated chapter text without verifying that approved glossary terminology is preserved. This creates a consistency gap: machine translation prompts may receive approved glossary terms, but manual edits can later remove required names, replace approved terminology, or introduce forbidden variants without warning.

This spec adds deterministic glossary QA to the manual editor workflow. It merges the earlier `editor-glossary-enforcement` idea into `glossary-aware-editor-qa`, so preview linting, save-time QA, blocking behavior, overrides, persisted QA metadata, and glossary update shortcuts are handled in one complete workflow.

This spec must reuse the existing glossary repository, approved-term resolution, editor auth patterns, storage contract, and glossary revision metadata where available. It must not replace prompt-time glossary injection or implement glossary revision invalidation for completed translations.

## Scope

In scope:

- Reusable backend QA/lint service for edited translated chapters.
- Preview lint endpoint for editor UI checks before saving.
- Save-time glossary QA on manual translation edits.
- Deterministic matching against approved glossary terms.
- Severity handling for advisory, warning, blocking, and overridden results.
- Override workflow with required reason and audit metadata.
- Persisted QA summaries on edited translation versions or edit history.
- Admin shortcut to approve a changed term translation when an edit is intentionally better than the current glossary.
- Editor UI surfacing for glossary issues, fix hints, override rationale, and approval shortcut.
- Unit, API, storage, and frontend tests.

Out of scope:

- LLM-based semantic validation.
- Full-text batch linting for every chapter in a novel.
- Public reader glossary annotations.
- Public reader glossary warnings.
- Translation prompt glossary injection.
- Glossary revision invalidation for queued or completed machine translations.
- Automatic retranslation after glossary edits.
- Changing active-version selection.

## Requirements

### REQ-1: Provide a Deterministic Glossary Editor QA Service

The backend must provide a reusable deterministic service for checking edited translated text against approved glossary entries.

- REQ-1.1: The service must be named `GlossaryEditorQAService` or use an existing equivalent local name such as `GlossaryLintService`.
- REQ-1.2: The service must be independent of HTTP/router concerns.
- REQ-1.3: The service must load approved glossary entries for the novel through the existing glossary repository.
- REQ-1.4: The service must use the same approved-term source of truth used by prompt glossary injection.
- REQ-1.5: The service must include inherited/global glossary entries only if the existing glossary repository already supports that behavior.
- REQ-1.6: The service must not mutate glossary entries during QA checks.
- REQ-1.7: The service must return a stable structured result suitable for API responses and persisted summaries.
- REQ-1.8: The service must include the glossary revision used for checking when available.
- REQ-1.9: When no approved glossary entries exist, the service must return a passing result with zero issues.
- REQ-1.10: When too many entries are eligible for checking, the service must cap checks at a configured limit and include cap/truncation metadata in the result.

### REQ-2: Resolve Relevant Approved Terms

The QA service must determine which approved terms are relevant to the edited chapter.

- REQ-2.1: When `source_text` is available, only approved entries whose `canonical_term` or aliases appear in the source text should be required.
- REQ-2.2: When `source_text` is unavailable, the service must run in advisory mode against a capped set of approved terms.
- REQ-2.3: When source text is unavailable, the result must include a note or code such as `legacy_no_source_context`.
- REQ-2.4: Missing source text must not create blocking issues by itself.
- REQ-2.5: Pending glossary entries must not be enforced as approved terms.
- REQ-2.6: Rejected, disabled, archived, or inactive entries must not create blocking issues.
- REQ-2.7: Aliases must be considered relevant-term matches when those aliases are used by prompt injection.
- REQ-2.8: Approved-term casing, spelling, and configured translation form must be preserved in checks where the glossary defines them.

### REQ-3: Detect Glossary QA Issues

The QA service must emit deterministic issues for glossary violations.

- REQ-3.1: When an approved source term is relevant and its `approved_translation` is absent from edited text, the service must emit `missing_approved_translation`.
- REQ-3.2: When a relevant term is owner-locked or strict/required/blocking and its approved translation is absent, the service must emit `missing_required_term`.
- REQ-3.3: When an approved entry has forbidden variants and a forbidden variant appears in edited text, the service must emit `forbidden_variant`.
- REQ-3.4: When a known non-approved variant appears while the approved translation is absent, the service must emit `non_approved_translation`.
- REQ-3.5: When substring matching cannot confidently distinguish the approved translation from a collision, the service should emit `ambiguous_match` as advisory or warning.
- REQ-3.6: Matching must be deterministic and must not call an LLM.
- REQ-3.7: Initial matching may use normalized case-insensitive substring checks.
- REQ-3.8: Future tokenizer, word-boundary, fuzzy, or script-aware matching improvements must remain deterministic and covered by tests.

### REQ-4: Normalize Text Safely

The QA service must normalize text for matching without changing stored edited content.

- REQ-4.1: Matching should apply Unicode normalization where appropriate.
- REQ-4.2: Matching should compare English translations case-insensitively.
- REQ-4.3: Matching should trim surrounding whitespace.
- REQ-4.4: Matching should collapse repeated internal whitespace for comparison.
- REQ-4.5: Normalization must not alter the edited text saved by the editor.
- REQ-4.6: Normalization must not change term meaning.

### REQ-5: Map Issues to Severity and Result Status

QA results must use stable severity and status values.

- REQ-5.1: Owner-locked terms must produce `error` severity when violated.
- REQ-5.2: Terms with `enforcement_level` in `strict`, `required`, or `blocking` must produce `error` severity when violated.
- REQ-5.3: Terms with `enforcement_level = warning` must produce `warning` severity.
- REQ-5.4: Terms with `enforcement_level` in `advisory` or `soft` must produce `advisory` severity.
- REQ-5.5: Unknown enforcement levels must default to `warning`.
- REQ-5.6: If `enforcement_level` does not exist in the schema, severity must derive from `owner_locked` first and treat other approved terms as warnings.
- REQ-5.7: Result status must be `passed` when QA runs and finds no issues.
- REQ-5.8: Result status must be `advisory` when QA has only advisory notes or glossary data is unavailable.
- REQ-5.9: Result status must be `warning` when non-blocking warning issues exist.
- REQ-5.10: Result status must be `blocked` when blocking issues exist and no valid override is accepted.
- REQ-5.11: Result status must be `overridden` when blocking issues exist but an authorized override allows save.

### REQ-6: Add Preview Lint Endpoint

Editors must be able to check glossary QA before saving.

- REQ-6.1: Add or expose `POST /{novel_id}/chapters/{chapter_id}/translated/lint`.
- REQ-6.2: The endpoint must accept edited translated text without saving it.
- REQ-6.3: The endpoint should accept optional `source_text`.
- REQ-6.4: The endpoint should accept optional `max_terms`.
- REQ-6.5: When the route receives a slug `novel_id` but the glossary repository requires an integer platform novel ID, the backend must resolve the slug through the `Novel` row before running QA.
- REQ-6.6: When the novel cannot be resolved to a glossary-enabled DB row, the endpoint must return HTTP 200 with an empty advisory result and a note such as `Glossary not available for this novel.`
- REQ-6.7: When linting succeeds, the endpoint must return HTTP 200 with `glossary_qa`.
- REQ-6.8: The `glossary_qa` response must include status, checked term count, issue count, glossary revision when available, issues, and notes.
- REQ-6.9: When source text is omitted, the endpoint must still return an advisory result instead of failing.
- REQ-6.10: The endpoint must use the same authorization style as existing editor endpoints.

### REQ-7: Run Save-Time QA

Manual translation saves must run glossary QA when enabled or required.

- REQ-7.1: Extend `PUT /{novel_id}/chapters/{chapter_id}/translated` with optional QA fields.
- REQ-7.2: The request may include `lint: true`.
- REQ-7.3: The request may include optional `source_text`.
- REQ-7.4: The request may include optional `glossary_override`.
- REQ-7.5: When QA is enabled or enforcement is configured for the novel, the backend must run QA before committing edited content.
- REQ-7.6: When `lint=true`, the response must include `glossary_qa`.
- REQ-7.7: When `lint` output is not requested, the backend may still enforce blocking issues but must preserve the existing response shape unless save is blocked.
- REQ-7.8: When QA returns only advisory or warning issues, save must succeed.
- REQ-7.9: When QA returns blocking issues and no valid override is provided, save must fail with HTTP 409 and include `glossary_qa`.
- REQ-7.10: When QA returns blocking issues and a valid authorized override is provided, save must succeed and mark QA status as `overridden`.
- REQ-7.11: Glossary data being unavailable must not fail editor save by itself unless an existing editor policy explicitly requires hard failure.
- REQ-7.12: Existing clients that omit new QA fields must remain backward compatible.

### REQ-8: Support Authorized Override Workflow

Reviewers must be able to override blocking QA issues in audited cases.

- REQ-8.1: Blocking issues must identify which glossary terms caused the block.
- REQ-8.2: The editor UI must require an override reason before submitting an override.
- REQ-8.3: Override requests must include a structured object with reason and affected issue IDs or term IDs.
- REQ-8.4: The backend must validate override payload shape.
- REQ-8.5: Invalid override payloads must return HTTP 400.
- REQ-8.6: Users without override permission must be rejected using the existing auth error style.
- REQ-8.7: Accepted overrides must persist override author, timestamp, reason, glossary revision, and affected issues.
- REQ-8.8: Accepted overrides must mark `glossary_qa.status` as `overridden`.
- REQ-8.9: Override metadata must be auditable from admin/editor history.

### REQ-9: Persist QA Metadata

Saved edited translations must retain compact QA metadata.

- REQ-9.1: When an edited translation is saved after QA, persist the QA result or a compact immutable QA summary.
- REQ-9.2: QA metadata must be stored with the edited translation version or edit history record according to existing storage patterns.
- REQ-9.3: When an edit is saved with override, persist override metadata.
- REQ-9.4: Admin/editor version detail must be able to expose the latest QA status.
- REQ-9.5: Legacy edited versions without QA metadata must remain loadable.
- REQ-9.6: If QA metadata is stored in JSON files, writes must follow the storage contract and atomic write rules.
- REQ-9.7: QA metadata must include glossary revision when available.
- REQ-9.8: QA metadata must not store full source text.
- REQ-9.9: QA metadata must not store full edited text inside the QA summary.
- REQ-9.10: If context is needed for display, store only short sanitized snippets or recompute QA on demand.

### REQ-10: Add Admin Shortcut for Approving Changed Terminology

Owners/admins must be able to approve an intentional terminology improvement from an editor QA issue.

- REQ-10.1: Add or expose `POST /{novel_id}/glossary/entries/{entry_id}/approve-translation-change`.
- REQ-10.2: The endpoint must accept a new approved translation.
- REQ-10.3: The endpoint should accept a rationale.
- REQ-10.4: The endpoint must update the glossary entry approved translation through existing glossary repository methods.
- REQ-10.5: The endpoint must reject requests where the entry is not part of the requested novel or inherited global glossary scope.
- REQ-10.6: Owner-locked entries must require owner/admin permission.
- REQ-10.7: Successful updates must return entry ID, canonical term, approved translation, glossary revision, and updated timestamp.
- REQ-10.8: Successful updates must record a glossary decision event with `event_type = "approve"` or the nearest existing event type.
- REQ-10.9: Glossary revision changes caused by this endpoint must rely on existing glossary revision behavior.
- REQ-10.10: Downstream glossary revision invalidation remains the responsibility of the separate invalidation spec.

### REQ-11: Surface QA in the Editor UI

The editor UI must make glossary issues understandable and actionable.

- REQ-11.1: The editor must provide a glossary QA action or automatically run preview lint after edit debounce.
- REQ-11.2: The UI must show issue severity.
- REQ-11.3: The UI must show source term.
- REQ-11.4: The UI must show expected approved translation.
- REQ-11.5: The UI must show actual matched variant when available.
- REQ-11.6: The UI must show a short fix hint.
- REQ-11.7: When QA returns blocking issues, the primary save action must explain that saving requires fixing issues or submitting an override.
- REQ-11.8: When the user has permission, the UI must allow override with a required reason.
- REQ-11.9: When the user has permission, the UI should provide an action to approve a changed term globally.
- REQ-11.10: Advisory notes must not be presented as save failures.
- REQ-11.11: Glossary-unavailable results must be shown as non-blocking.
- REQ-11.12: QA UI and metadata must remain admin/editor-only and must not appear in the public reader.

### REQ-12: Authorization

Glossary QA actions must follow existing editor and glossary permission patterns.

- REQ-12.1: Preview lint must require the same permission as editing translated chapters.
- REQ-12.2: Saving with non-blocking QA must require the same permission as editing translated chapters.
- REQ-12.3: Saving with a blocking override must require owner/admin or explicit glossary override permission.
- REQ-12.4: Approving a translation change must require owner/admin permission for the novel or glossary scope.
- REQ-12.5: Unauthorized requests must return the existing project auth error style.
- REQ-12.6: Authorization behavior must be covered by API tests.

### REQ-13: Observability and Diagnostics

Editor QA must emit safe operational diagnostics.

- REQ-13.1: When QA runs, the backend must log a structured QA event.
- REQ-13.2: The QA event must include novel ID, chapter ID, platform novel ID when available, glossary revision, checked term count, issue count, status, and elapsed time.
- REQ-13.3: When QA blocks a save, the backend must log a structured warning.
- REQ-13.4: When an override is accepted, the backend must log override metadata.
- REQ-13.5: Logs must not include full source chapter text.
- REQ-13.6: Logs must not include full translated or edited chapter text.
- REQ-13.7: Logs must not include private override notes beyond the required audit-safe reason.
- REQ-13.8: When glossary diagnostics/admin surfacing is implemented, editor QA results should be eligible for aggregation there.

### REQ-14: Failure Handling

Failure behavior must be predictable and compatible with existing editor saves.

- REQ-14.1: If the glossary novel row is missing, preview lint must return an advisory empty result.
- REQ-14.2: If the glossary novel row is missing, save must continue unless another error exists.
- REQ-14.3: If the glossary repository fails during direct preview lint, the endpoint may return a service error using existing API error style.
- REQ-14.4: If the glossary repository fails during save, save may treat QA as unavailable only if existing editor policy allows soft QA failure.
- REQ-14.5: Missing source text must not fail lint or save.
- REQ-14.6: Blocking issue without override must return HTTP 409 with `glossary_qa`.
- REQ-14.7: Invalid override payload must return HTTP 400.
- REQ-14.8: Unknown enforcement level must be treated as warning.
- REQ-14.9: Excessive glossary term count must respect `max_terms` and include cap metadata.

### REQ-15: Backward Compatibility

Existing editor and reader behavior must remain compatible.

- REQ-15.1: Existing edited translations must remain loadable.
- REQ-15.2: Existing editor save behavior must remain compatible when glossary data is unavailable.
- REQ-15.3: Existing prompt-time glossary injection must remain unchanged.
- REQ-15.4: Existing glossary approval workflows remain the source of truth.
- REQ-15.5: New request fields must be optional.
- REQ-15.6: New response fields must be additive.
- REQ-15.7: Public reader output must remain unchanged.
- REQ-15.8: Full glossary revision invalidation must remain in the separate invalidation spec.

### REQ-16: Tests

The implementation must include unit, API, storage, and frontend tests.

- REQ-16.1: Unit test approved source term present but approved translation missing.
- REQ-16.2: Unit test forbidden variant detection.
- REQ-16.3: Unit test non-approved variant detection.
- REQ-16.4: Unit test owner-locked term produces blocking severity.
- REQ-16.5: Unit test strict/required/blocking enforcement produces blocking severity.
- REQ-16.6: Unit test warning/advisory enforcement mapping.
- REQ-16.7: Unit test passing QA when all required translations are present.
- REQ-16.8: Unit test passing QA when no glossary entries exist.
- REQ-16.9: Unit test no-source-context advisory behavior.
- REQ-16.10: Unit test term cap behavior and cap metadata.
- REQ-16.11: Unit test deterministic issue IDs.
- REQ-16.12: API test preview lint returns HTTP 200 and expected issue payload.
- REQ-16.13: API test preview lint cannot resolve DB novel row and returns HTTP 200 with empty advisory result.
- REQ-16.14: API test preview lint requires edit permission.
- REQ-16.15: API test save with warnings succeeds and persists QA metadata.
- REQ-16.16: API test save with blocking issue and no override returns HTTP 409.
- REQ-16.17: API test save with valid authorized override succeeds.
- REQ-16.18: API test save with invalid override returns HTTP 400.
- REQ-16.19: API test save with unauthorized override returns auth error.
- REQ-16.20: API test `lint=true` response includes `glossary_qa`.
- REQ-16.21: API test approve translation change updates glossary entry.
- REQ-16.22: API test approve translation change increments glossary revision through existing behavior.
- REQ-16.23: API test approve translation change records a decision event.
- REQ-16.24: API test unauthorized approval is denied.
- REQ-16.25: Storage test persisted QA metadata appears on edited version or edit history.
- REQ-16.26: Storage test override metadata is persisted.
- REQ-16.27: Storage test full source text is not persisted inside QA metadata.
- REQ-16.28: Storage test legacy edited versions without QA metadata remain loadable.
- REQ-16.29: Frontend test QA issue panel renders advisory, warning, blocked, and overridden states.
- REQ-16.30: Frontend test preview lint action displays returned issues.
- REQ-16.31: Frontend test blocked save flow requires fix or override.
- REQ-16.32: Frontend test override requires reason.
- REQ-16.33: Frontend test approve translation change action calls API.
- REQ-16.34: Frontend test glossary-unavailable result is non-blocking.

## Non-Goals

- This spec does not implement LLM-based QA.
- This spec does not perform semantic translation review.
- This spec does not batch-lint every chapter in a novel.
- This spec does not replace prompt-time glossary injection.
- This spec does not redesign glossary review workflows.
- This spec does not implement glossary revision invalidation for completed translations.
- This spec does not schedule retranslations.
- This spec does not add public reader glossary annotations.
- This spec does not add public reader warnings.
- This spec does not change active-version selection.