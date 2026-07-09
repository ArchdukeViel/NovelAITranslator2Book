# Implementation Plan: Glossary-Aware Editor QA

## Overview

Implement deterministic glossary QA for the manual translated-chapter editor.

This plan merges the earlier partial `editor-glossary-enforcement` work into one complete editor QA workflow covering preview linting, save-time enforcement, override metadata, persisted QA summaries, admin glossary update shortcuts, editor UI surfacing, and tests.

Scope boundaries:

- Do not use an LLM for QA.
- Do not replace prompt-time glossary injection.
- Do not redesign glossary review workflows.
- Do not implement full glossary revision invalidation here.
- Do not add public reader glossary warnings or annotations.
- Do not change active-version selection.
- Keep legacy editor saves compatible when glossary data is unavailable.

## Task List

- [x] 1. Preflight Editor, Glossary, and Storage Paths
  - [x] 1.1 Locate the translated chapter save route.
  - [x] 1.2 Inspect the translated edit request and response schemas.
  - [x] 1.3 Inspect edited translation storage or edit history metadata format.
  - [x] 1.4 Locate glossary repository methods for approved novel entries.
  - [x] 1.5 Locate glossary repository support for inherited/global entries, if any.
  - [x] 1.6 Confirm how string `novel_id` slugs map to integer platform novel IDs.
  - [x] 1.7 Identify existing owner/admin/editor permission helpers.
  - [x] 1.8 Identify existing glossary decision event logging.
  - [x] 1.9 Inspect storage contract and atomic JSON write helpers.
  - [x] 1.10 Inspect existing editor, glossary, storage, and frontend tests.

- [x] 2. Define QA Data Contracts
  - [x] 2.1 Add `GlossaryQAIssue`.
  - [x] 2.2 Include `issue_id`.
  - [x] 2.3 Include `entry_id`.
  - [x] 2.4 Include `canonical_term`.
  - [x] 2.5 Include `approved_translation`.
  - [x] 2.6 Include `matched_variant`.
  - [x] 2.7 Include `severity`.
  - [x] 2.8 Include `code`.
  - [x] 2.9 Include `owner_locked`.
  - [x] 2.10 Include `context_hint`.
  - [x] 2.11 Add `GlossaryQAResult`.
  - [x] 2.12 Include `status`.
  - [x] 2.13 Include novel identifiers, `chapter_id`, and `glossary_revision`.
  - [x] 2.14 Include `checked_terms`, `issue_count`, `has_errors`, and `has_warnings`.
  - [x] 2.15 Include `source_context`, `notes`, `issues`, and cap/truncation metadata.
  - [x] 2.16 Keep schemas stable for API responses and persisted summaries.

- [x] 3. Define Request and Response Schemas
  - [x] 3.1 Add `GlossaryEditorQARequest` or `GlossaryLintRequest`.
  - [x] 3.2 Include `text`.
  - [x] 3.3 Include optional `source_text`.
  - [x] 3.4 Include optional `max_terms`.
  - [x] 3.5 Add `GlossaryOverrideRequest`.
  - [x] 3.6 Include override `reason`.
  - [x] 3.7 Include affected `issue_ids` or term IDs.
  - [x] 3.8 Extend translated edit request schema with optional `lint`.
  - [x] 3.9 Extend translated edit request schema with optional `source_text`.
  - [x] 3.10 Extend translated edit request schema with optional `glossary_override`.
  - [x] 3.11 Add approve-translation-change request schema.
  - [x] 3.12 Add approve-translation-change response schema.
  - [x] 3.13 Ensure new request fields are optional and backward compatible.

- [x] 4. Implement `GlossaryEditorQAService`
  - [x] 4.1 Create `backend/src/novelai/services/glossary_editor_qa_service.py`, or use the existing `GlossaryLintService` name if already present.
  - [x] 4.2 Keep the service independent of HTTP/router concerns.
  - [x] 4.3 Inject or construct `GlossaryRepository` using existing dependency patterns.
  - [x] 4.4 Load approved glossary entries for the novel.
  - [x] 4.5 Include inherited/global entries only if the repository already supports them.
  - [x] 4.6 Use the same approved-term source of truth as prompt glossary injection.
  - [x] 4.7 Include glossary revision in the result when available.
  - [x] 4.8 Return passing result with zero issues when no approved entries exist.
  - [x] 4.9 Do not mutate glossary entries during QA.

- [x] 5. Implement Deterministic Matching and Relevance
  - [x] 5.1 Normalize text for comparison without changing stored edited text.
  - [x] 5.2 Apply Unicode normalization where appropriate.
  - [x] 5.3 Compare English translations case-insensitively.
  - [x] 5.4 Trim surrounding whitespace for matching.
  - [x] 5.5 Collapse repeated internal whitespace for matching.
  - [x] 5.6 When `source_text` is available, require only entries whose `canonical_term` or aliases appear in source text.
  - [x] 5.7 When `source_text` is unavailable, run in advisory/no-source mode.
  - [x] 5.8 Add `legacy_no_source_context` note when source text is unavailable.
  - [x] 5.9 Do not enforce pending, rejected, disabled, archived, or inactive entries.
  - [x] 5.10 Cap checked terms at `max_terms`.
  - [x] 5.11 Include cap/truncation metadata when the cap is reached.

- [x] 6. Implement Issue Detection
  - [x] 6.1 Detect missing approved translations.
  - [x] 6.2 Emit `missing_approved_translation` for non-blocking approved-term omissions.
  - [x] 6.3 Emit `missing_required_term` for owner-locked or strict/required/blocking omissions.
  - [x] 6.4 Detect forbidden variants.
  - [x] 6.5 Emit `forbidden_variant`.
  - [x] 6.6 Detect known non-approved variants when approved translation is absent.
  - [x] 6.7 Emit `non_approved_translation`.
  - [x] 6.8 Emit `ambiguous_match` as advisory or warning when substring collision is likely.
  - [x] 6.9 Generate deterministic issue IDs.
  - [x] 6.10 Include short fix hints without storing full source or edited text.

- [x] 7. Implement Severity and Status Mapping
  - [x] 7.1 Map `owner_locked=true` violations to `error`.
  - [x] 7.2 Map `enforcement_level in strict|required|blocking` to `error`.
  - [x] 7.3 Map `enforcement_level=warning` to `warning`.
  - [x] 7.4 Map `enforcement_level in advisory|soft` to `advisory`.
  - [x] 7.5 Treat unknown enforcement levels as `warning`.
  - [x] 7.6 If `enforcement_level` does not exist, derive severity from `owner_locked` first and treat other approved terms as warnings.
  - [x] 7.7 Return `passed` when QA runs and finds no issues.
  - [x] 7.8 Return `advisory` for notes-only or glossary-unavailable results.
  - [x] 7.9 Return `warning` for non-blocking warnings.
  - [x] 7.10 Return `blocked` for blocking issues without accepted override.
  - [x] 7.11 Return `overridden` when blocking issues are accepted through authorized override.

- [x] 8. Add Preview Lint Endpoint
  - [x] 8.1 Add `POST /{novel_id}/chapters/{chapter_id}/translated/lint`.
  - [x] 8.2 Reuse existing translated-chapter edit authorization.
  - [x] 8.3 Accept edited text without saving it.
  - [x] 8.4 Accept optional `source_text`.
  - [x] 8.5 Accept optional `max_terms`.
  - [x] 8.6 Resolve slug `novel_id` to platform novel ID when required by glossary repository.
  - [x] 8.7 Return HTTP 200 with empty advisory result when glossary data is unavailable for the novel.
  - [x] 8.8 Return HTTP 200 with `glossary_qa` on successful QA.
  - [x] 8.9 Ensure source-text omission returns advisory behavior instead of failure.
  - [x] 8.10 Confirm the endpoint never saves edited text.

- [x] 9. Integrate QA Into Translated Edit Save
  - [x] 9.1 Update `PUT /{novel_id}/chapters/{chapter_id}/translated`.
  - [x] 9.2 Run QA before committing edited content when `lint=true`.
  - [x] 9.3 Run QA before committing edited content when novel/editor policy requires enforcement.
  - [x] 9.4 Preserve existing save behavior for clients that omit QA fields when no blocking issue applies.
  - [x] 9.5 Include `glossary_qa` in the response when `lint=true`.
  - [x] 9.6 Allow advisory and warning issues to save.
  - [x] 9.7 Return HTTP 409 with `glossary_qa` for blocking issues without valid override.
  - [x] 9.8 Accept authorized override payloads with required reason.
  - [x] 9.9 Mark accepted override results as `overridden`.
  - [x] 9.10 Ensure glossary-unavailable advisory results do not fail saves by themselves.
  - [x] 9.11 Ensure failed or blocked saves do not partially write edited content.

- [x] 10. Implement Override Validation and Authorization
  - [x] 10.1 Validate override payload shape.
  - [x] 10.2 Require non-empty override reason.
  - [x] 10.3 Require affected issue IDs or term IDs.
  - [x] 10.4 Reject invalid override payloads with HTTP 400.
  - [x] 10.5 Require owner/admin or explicit glossary override permission.
  - [x] 10.6 Reject unauthorized override attempts using existing auth error style.
  - [x] 10.7 Attach override author, timestamp, reason, glossary revision, and affected issues to QA metadata.
  - [x] 10.8 Ensure override metadata is auditable from admin/editor history.

- [x] 11. Persist QA and Override Metadata
  - [x] 11.1 Choose existing edited translation version or edit history location for QA metadata.
  - [x] 11.2 Persist compact `glossary_qa` summary.
  - [x] 11.3 Persist status, glossary revision, checked term count, issue count, and issue summaries.
  - [x] 11.4 Persist override metadata when override is accepted.
  - [x] 11.5 Do not persist full source text in QA metadata.
  - [x] 11.6 Do not persist full edited text inside QA metadata.
  - [x] 11.7 Store only short sanitized snippets if context is needed.
  - [x] 11.8 Follow storage contract and atomic write rules for JSON-backed metadata.
  - [x] 11.9 Keep legacy edited translation records readable when QA metadata is absent.
  - [x] 11.10 Expose latest QA status in admin/editor version detail where existing patterns support it.

- [x] 12. Add Approve Translation Change Endpoint
  - [x] 12.1 Add `POST /{novel_id}/glossary/entries/{entry_id}/approve-translation-change`.
  - [x] 12.2 Add route to admin glossary router or nearest existing glossary admin router.
  - [x] 12.3 Require owner/admin permission.
  - [x] 12.4 Validate that the entry belongs to the novel or allowed inherited/global scope.
  - [x] 12.5 Reject invalid scope requests.
  - [x] 12.6 Update `approved_translation` through existing glossary repository methods.
  - [x] 12.7 Persist rationale as a glossary decision event.
  - [x] 12.8 Use `event_type="approve"` or nearest existing event type.
  - [x] 12.9 Rely on existing glossary revision behavior to increment revision.
  - [x] 12.10 Return entry ID, canonical term, approved translation, glossary revision, and updated timestamp.
  - [x] 12.11 Do not silently approve pending or rejected terms outside existing glossary rules.

- [x] 13. Add Editor Frontend QA Flow
  - [x] 13.1 Add glossary QA action or debounced preview lint call in translated chapter editor.
  - [x] 13.2 Render issue severity.
  - [x] 13.3 Render source/canonical term.
  - [x] 13.4 Render approved translation.
  - [x] 13.5 Render matched variant when available.
  - [x] 13.6 Render short fix hint.
  - [x] 13.7 Show advisory notes separately from warnings and blocking errors.
  - [x] 13.8 On blocking save response, show fix or override options.
  - [x] 13.9 Add override UI with required reason for authorized users.
  - [x] 13.10 Add owner/admin action to approve a changed translation from a QA issue.
  - [x] 13.11 Show QA unavailable messages as non-blocking.
  - [x] 13.12 Keep QA UI admin/editor-only.
  - [x] 13.13 Confirm public reader UI is unchanged.

- [x] 14. Add Observability
  - [x] 14.1 Log structured QA run events.
  - [x] 14.2 Include novel ID, chapter ID, platform novel ID when available, glossary revision, checked term count, issue count, status, and elapsed time.
  - [x] 14.3 Log blocking save events as structured warnings.
  - [x] 14.4 Log accepted override events.
  - [x] 14.5 Do not log full source text.
  - [x] 14.6 Do not log full translated or edited text.
  - [x] 14.7 Do not log private notes beyond the required audit-safe override reason.
  - [x] 14.8 Add counters/metrics only if the project already has a metrics pattern.
  - [x] 14.9 Make QA results eligible for future glossary diagnostics aggregation where applicable.

- [x] 15. Add Backend Unit Tests
  - [x] 15.1 Test approved source term present but approved translation missing.
  - [x] 15.2 Test forbidden variant detection.
  - [x] 15.3 Test non-approved variant detection.
  - [x] 15.4 Test owner-locked term maps to blocking severity.
  - [x] 15.5 Test strict/required/blocking enforcement maps to blocking severity.
  - [x] 15.6 Test warning/advisory enforcement mapping.
  - [x] 15.7 Test passing result when approved translation is present.
  - [x] 15.8 Test empty glossary returns passing result.
  - [x] 15.9 Test missing source text returns advisory source-context note.
  - [x] 15.10 Test pending terms are not enforced as approved.
  - [x] 15.11 Test inactive/rejected/archived terms do not create blocking issues.
  - [x] 15.12 Test alias relevance matching.
  - [x] 15.13 Test max term cap metadata.
  - [x] 15.14 Test deterministic issue IDs.
  - [x] 15.15 Test normalization does not alter saved edited text.

- [x] 16. Add API Tests
  - [x] 16.1 Test preview lint returns HTTP 200 with expected issue payload.
  - [x] 16.2 Test preview lint with unresolved DB novel returns HTTP 200 and empty advisory note.
  - [x] 16.3 Test preview lint without source text returns advisory behavior.
  - [x] 16.4 Test unauthorized preview lint is denied.
  - [x] 16.5 Test save with `lint=true` includes `glossary_qa`.
  - [x] 16.6 Test save with warning issues succeeds.
  - [x] 16.7 Test save with blocking issue and no override returns HTTP 409.
  - [x] 16.8 Test save with valid authorized override succeeds.
  - [x] 16.9 Test save with valid authorized override persists override metadata.
  - [x] 16.10 Test invalid override returns HTTP 400.
  - [x] 16.11 Test unauthorized override is denied.
  - [x] 16.12 Test glossary-unavailable save does not fail solely due to QA.
  - [x] 16.13 Test approve translation change updates glossary entry.
  - [x] 16.14 Test approve translation change records a decision event.
  - [x] 16.15 Test approve translation change returns glossary revision and timestamp.
  - [x] 16.16 Test unauthorized approve translation change is denied.
  - [x] 16.17 Test approve translation change rejects entries outside novel or allowed inherited/global scope.

- [x] 17. Add Storage Tests
  - [x] 17.1 Test persisted QA metadata appears on edited version or edit history.
  - [x] 17.2 Test override metadata is persisted.
  - [x] 17.3 Test glossary revision is persisted when available.
  - [x] 17.4 Test full source text is not persisted inside QA metadata.
  - [x] 17.5 Test full edited text is not duplicated inside QA metadata.
  - [x] 17.6 Test legacy edited versions without QA metadata remain loadable.
  - [x] 17.7 Test JSON-backed QA metadata follows storage contract and atomic write behavior where applicable.

- [x] 18. Add Frontend Tests
  - [x] 18.1 Test issue list renders advisory, warning, blocked, and overridden states.
  - [x] 18.2 Test preview lint action or debounce calls backend.
  - [x] 18.3 Test returned issues render severity, source term, approved translation, matched variant, and fix hint.
  - [x] 18.4 Test blocking save response displays fix or override options.
  - [x] 18.5 Test override requires reason before submit.
  - [x] 18.6 Test authorized override submits structured override payload.
  - [x] 18.7 Test approve translation change action calls admin endpoint.
  - [x] 18.8 Test advisory notes are non-blocking.
  - [x] 18.9 Test QA unavailable message does not block normal editing.
  - [x] 18.10 Test QA metadata is not shown in public reader UI.

- [x] 19. Backward Compatibility Checks
  - [x] 19.1 Confirm existing edited translations remain loadable.
  - [x] 19.2 Confirm existing editor save clients can omit new QA fields.
  - [x] 19.3 Confirm glossary-unavailable results do not break legacy saves.
  - [x] 19.4 Confirm prompt-time glossary injection is unchanged.
  - [x] 19.5 Confirm glossary approval workflows remain the source of truth.
  - [x] 19.6 Confirm active-version selection is unchanged.
  - [x] 19.7 Confirm public reader output is unchanged.
  - [x] 19.8 Confirm full glossary revision invalidation remains separate.

- [x] 20. Documentation and Rollout
  - [x] 20.1 Document the `glossary_qa` response contract.
  - [x] 20.2 Document issue codes and severity mapping.
  - [x] 20.3 Document when QA blocks saves.
  - [x] 20.4 Document who can override blocking issues.
  - [x] 20.5 Document override metadata and audit behavior.
  - [x] 20.6 Document approve-translation-change behavior.
  - [x] 20.7 Roll out preview lint first.
  - [x] 20.8 Enable blocking enforcement only for owner-locked, strict, required, or blocking terms.
  - [x] 20.9 Confirm this spec replaces the partial `editor-glossary-enforcement` spec.

- [x] 21. Run Verification
  - [x] 21.1 Run focused backend unit tests for glossary editor QA.
  - [x] 21.2 Run editor API tests.
  - [x] 21.3 Run glossary API tests.
  - [x] 21.4 Run edited translation storage tests.
  - [x] 21.5 Run frontend editor tests.
  - [x] 21.6 Run existing glossary tests.
  - [x] 21.7 Run existing editor save tests.
  - [x] 21.8 Run existing public reader tests to confirm no reader regression.
  - [x] 21.9 Run `ruff check` on changed backend files and tests.
  - [x] 21.10 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 21.11 Fix test, lint, and type failures caused by this work.

- [x] 22. Final Acceptance Review
  - [x] 22.1 Verify preview lint returns deterministic `glossary_qa` results.
  - [x] 22.2 Verify save-time QA blocks strict, required, blocking, or owner-locked violations unless authorized override is provided.
  - [x] 22.3 Verify warning and advisory issues save successfully and persist QA metadata.
  - [x] 22.4 Verify override reason, author, timestamp, glossary revision, and affected issues are persisted.
  - [x] 22.5 Verify admins can approve edited terminology as a new glossary translation.
  - [x] 22.6 Verify approve-translation-change records a decision event.
  - [x] 22.7 Verify glossary revision metadata is included in QA results and persisted summaries when available.
  - [x] 22.8 Verify missing glossary data does not break legacy editor saves.
  - [x] 22.9 Verify public reader output remains unchanged.
  - [x] 22.10 Verify unit, API, storage, and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Deterministic Glossary Editor QA Service | 1, 4, 15, 22 |
| REQ-2 Resolve Relevant Approved Terms | 4, 5, 15, 22 |
| REQ-3 Detect Glossary QA Issues | 6, 15, 16, 22 |
| REQ-4 Normalize Text Safely | 5, 15, 17 |
| REQ-5 Severity and Result Status | 7, 15, 16, 18 |
| REQ-6 Preview Lint Endpoint | 3, 8, 16, 18, 22 |
| REQ-7 Save-Time QA | 3, 9, 16, 17, 22 |
| REQ-8 Authorized Override Workflow | 10, 11, 16, 17, 18, 22 |
| REQ-9 Persist QA Metadata | 11, 17, 19, 22 |
| REQ-10 Approve Changed Terminology | 12, 16, 18, 20, 22 |
| REQ-11 Editor UI Surfacing | 13, 18, 22 |
| REQ-12 Authorization | 8, 10, 12, 16 |
| REQ-13 Observability and Diagnostics | 14, 20, 22 |
| REQ-14 Failure Handling | 8, 9, 10, 16, 19 |
| REQ-15 Backward Compatibility | 11, 19, 21, 22 |
| REQ-16 Tests | 15, 16, 17, 18, 21 |

## Definition of Done

- [x] `GlossaryEditorQAService` or equivalent deterministic QA service exists.
- [x] QA service loads approved glossary entries through existing repository patterns.
- [x] QA service detects missing approved translations, required term violations, forbidden variants, and non-approved variants.
- [x] QA service supports source-context relevance and advisory no-source mode.
- [x] Preview lint endpoint returns `glossary_qa` without saving text.
- [x] Save-time QA blocks only blocking issues unless authorized override is provided.
- [x] Authorized override requires reason and persists audit metadata.
- [x] Edited translation saves persist compact QA summaries.
- [x] Approve-translation-change endpoint updates glossary entries through existing glossary methods.
- [x] Editor UI displays QA issues, advisory notes, blocking states, override controls, and approve-change action.
- [x] Structured QA logs are emitted without full chapter text.
- [x] Legacy edited translations remain loadable.
- [x] Prompt-time glossary injection, glossary review workflows, active-version selection, and public reader output are unchanged.
- [x] Unit, API, storage, frontend, lint, and type checks pass.