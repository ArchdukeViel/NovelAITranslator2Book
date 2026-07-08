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

- [ ] 1. Preflight Editor, Glossary, and Storage Paths
  - [ ] 1.1 Locate the translated chapter save route.
  - [ ] 1.2 Inspect the translated edit request and response schemas.
  - [ ] 1.3 Inspect edited translation storage or edit history metadata format.
  - [ ] 1.4 Locate glossary repository methods for approved novel entries.
  - [ ] 1.5 Locate glossary repository support for inherited/global entries, if any.
  - [ ] 1.6 Confirm how string `novel_id` slugs map to integer platform novel IDs.
  - [ ] 1.7 Identify existing owner/admin/editor permission helpers.
  - [ ] 1.8 Identify existing glossary decision event logging.
  - [ ] 1.9 Inspect storage contract and atomic JSON write helpers.
  - [ ] 1.10 Inspect existing editor, glossary, storage, and frontend tests.

- [ ] 2. Define QA Data Contracts
  - [ ] 2.1 Add `GlossaryQAIssue`.
  - [ ] 2.2 Include `issue_id`.
  - [ ] 2.3 Include `entry_id`.
  - [ ] 2.4 Include `canonical_term`.
  - [ ] 2.5 Include `approved_translation`.
  - [ ] 2.6 Include `matched_variant`.
  - [ ] 2.7 Include `severity`.
  - [ ] 2.8 Include `code`.
  - [ ] 2.9 Include `owner_locked`.
  - [ ] 2.10 Include `context_hint`.
  - [ ] 2.11 Add `GlossaryQAResult`.
  - [ ] 2.12 Include `status`.
  - [ ] 2.13 Include novel identifiers, `chapter_id`, and `glossary_revision`.
  - [ ] 2.14 Include `checked_terms`, `issue_count`, `has_errors`, and `has_warnings`.
  - [ ] 2.15 Include `source_context`, `notes`, `issues`, and cap/truncation metadata.
  - [ ] 2.16 Keep schemas stable for API responses and persisted summaries.

- [ ] 3. Define Request and Response Schemas
  - [ ] 3.1 Add `GlossaryEditorQARequest` or `GlossaryLintRequest`.
  - [ ] 3.2 Include `text`.
  - [ ] 3.3 Include optional `source_text`.
  - [ ] 3.4 Include optional `max_terms`.
  - [ ] 3.5 Add `GlossaryOverrideRequest`.
  - [ ] 3.6 Include override `reason`.
  - [ ] 3.7 Include affected `issue_ids` or term IDs.
  - [ ] 3.8 Extend translated edit request schema with optional `lint`.
  - [ ] 3.9 Extend translated edit request schema with optional `source_text`.
  - [ ] 3.10 Extend translated edit request schema with optional `glossary_override`.
  - [ ] 3.11 Add approve-translation-change request schema.
  - [ ] 3.12 Add approve-translation-change response schema.
  - [ ] 3.13 Ensure new request fields are optional and backward compatible.

- [ ] 4. Implement `GlossaryEditorQAService`
  - [ ] 4.1 Create `backend/src/novelai/services/glossary_editor_qa_service.py`, or use the existing `GlossaryLintService` name if already present.
  - [ ] 4.2 Keep the service independent of HTTP/router concerns.
  - [ ] 4.3 Inject or construct `GlossaryRepository` using existing dependency patterns.
  - [ ] 4.4 Load approved glossary entries for the novel.
  - [ ] 4.5 Include inherited/global entries only if the repository already supports them.
  - [ ] 4.6 Use the same approved-term source of truth as prompt glossary injection.
  - [ ] 4.7 Include glossary revision in the result when available.
  - [ ] 4.8 Return passing result with zero issues when no approved entries exist.
  - [ ] 4.9 Do not mutate glossary entries during QA.

- [ ] 5. Implement Deterministic Matching and Relevance
  - [ ] 5.1 Normalize text for comparison without changing stored edited text.
  - [ ] 5.2 Apply Unicode normalization where appropriate.
  - [ ] 5.3 Compare English translations case-insensitively.
  - [ ] 5.4 Trim surrounding whitespace for matching.
  - [ ] 5.5 Collapse repeated internal whitespace for matching.
  - [ ] 5.6 When `source_text` is available, require only entries whose `canonical_term` or aliases appear in source text.
  - [ ] 5.7 When `source_text` is unavailable, run in advisory/no-source mode.
  - [ ] 5.8 Add `legacy_no_source_context` note when source text is unavailable.
  - [ ] 5.9 Do not enforce pending, rejected, disabled, archived, or inactive entries.
  - [ ] 5.10 Cap checked terms at `max_terms`.
  - [ ] 5.11 Include cap/truncation metadata when the cap is reached.

- [ ] 6. Implement Issue Detection
  - [ ] 6.1 Detect missing approved translations.
  - [ ] 6.2 Emit `missing_approved_translation` for non-blocking approved-term omissions.
  - [ ] 6.3 Emit `missing_required_term` for owner-locked or strict/required/blocking omissions.
  - [ ] 6.4 Detect forbidden variants.
  - [ ] 6.5 Emit `forbidden_variant`.
  - [ ] 6.6 Detect known non-approved variants when approved translation is absent.
  - [ ] 6.7 Emit `non_approved_translation`.
  - [ ] 6.8 Emit `ambiguous_match` as advisory or warning when substring collision is likely.
  - [ ] 6.9 Generate deterministic issue IDs.
  - [ ] 6.10 Include short fix hints without storing full source or edited text.

- [ ] 7. Implement Severity and Status Mapping
  - [ ] 7.1 Map `owner_locked=true` violations to `error`.
  - [ ] 7.2 Map `enforcement_level in strict|required|blocking` to `error`.
  - [ ] 7.3 Map `enforcement_level=warning` to `warning`.
  - [ ] 7.4 Map `enforcement_level in advisory|soft` to `advisory`.
  - [ ] 7.5 Treat unknown enforcement levels as `warning`.
  - [ ] 7.6 If `enforcement_level` does not exist, derive severity from `owner_locked` first and treat other approved terms as warnings.
  - [ ] 7.7 Return `passed` when QA runs and finds no issues.
  - [ ] 7.8 Return `advisory` for notes-only or glossary-unavailable results.
  - [ ] 7.9 Return `warning` for non-blocking warnings.
  - [ ] 7.10 Return `blocked` for blocking issues without accepted override.
  - [ ] 7.11 Return `overridden` when blocking issues are accepted through authorized override.

- [ ] 8. Add Preview Lint Endpoint
  - [ ] 8.1 Add `POST /{novel_id}/chapters/{chapter_id}/translated/lint`.
  - [ ] 8.2 Reuse existing translated-chapter edit authorization.
  - [ ] 8.3 Accept edited text without saving it.
  - [ ] 8.4 Accept optional `source_text`.
  - [ ] 8.5 Accept optional `max_terms`.
  - [ ] 8.6 Resolve slug `novel_id` to platform novel ID when required by glossary repository.
  - [ ] 8.7 Return HTTP 200 with empty advisory result when glossary data is unavailable for the novel.
  - [ ] 8.8 Return HTTP 200 with `glossary_qa` on successful QA.
  - [ ] 8.9 Ensure source-text omission returns advisory behavior instead of failure.
  - [ ] 8.10 Confirm the endpoint never saves edited text.

- [ ] 9. Integrate QA Into Translated Edit Save
  - [ ] 9.1 Update `PUT /{novel_id}/chapters/{chapter_id}/translated`.
  - [ ] 9.2 Run QA before committing edited content when `lint=true`.
  - [ ] 9.3 Run QA before committing edited content when novel/editor policy requires enforcement.
  - [ ] 9.4 Preserve existing save behavior for clients that omit QA fields when no blocking issue applies.
  - [ ] 9.5 Include `glossary_qa` in the response when `lint=true`.
  - [ ] 9.6 Allow advisory and warning issues to save.
  - [ ] 9.7 Return HTTP 409 with `glossary_qa` for blocking issues without valid override.
  - [ ] 9.8 Accept authorized override payloads with required reason.
  - [ ] 9.9 Mark accepted override results as `overridden`.
  - [ ] 9.10 Ensure glossary-unavailable advisory results do not fail saves by themselves.
  - [ ] 9.11 Ensure failed or blocked saves do not partially write edited content.

- [ ] 10. Implement Override Validation and Authorization
  - [ ] 10.1 Validate override payload shape.
  - [ ] 10.2 Require non-empty override reason.
  - [ ] 10.3 Require affected issue IDs or term IDs.
  - [ ] 10.4 Reject invalid override payloads with HTTP 400.
  - [ ] 10.5 Require owner/admin or explicit glossary override permission.
  - [ ] 10.6 Reject unauthorized override attempts using existing auth error style.
  - [ ] 10.7 Attach override author, timestamp, reason, glossary revision, and affected issues to QA metadata.
  - [ ] 10.8 Ensure override metadata is auditable from admin/editor history.

- [ ] 11. Persist QA and Override Metadata
  - [ ] 11.1 Choose existing edited translation version or edit history location for QA metadata.
  - [ ] 11.2 Persist compact `glossary_qa` summary.
  - [ ] 11.3 Persist status, glossary revision, checked term count, issue count, and issue summaries.
  - [ ] 11.4 Persist override metadata when override is accepted.
  - [ ] 11.5 Do not persist full source text in QA metadata.
  - [ ] 11.6 Do not persist full edited text inside QA metadata.
  - [ ] 11.7 Store only short sanitized snippets if context is needed.
  - [ ] 11.8 Follow storage contract and atomic write rules for JSON-backed metadata.
  - [ ] 11.9 Keep legacy edited translation records readable when QA metadata is absent.
  - [ ] 11.10 Expose latest QA status in admin/editor version detail where existing patterns support it.

- [ ] 12. Add Approve Translation Change Endpoint
  - [ ] 12.1 Add `POST /{novel_id}/glossary/entries/{entry_id}/approve-translation-change`.
  - [ ] 12.2 Add route to admin glossary router or nearest existing glossary admin router.
  - [ ] 12.3 Require owner/admin permission.
  - [ ] 12.4 Validate that the entry belongs to the novel or allowed inherited/global scope.
  - [ ] 12.5 Reject invalid scope requests.
  - [ ] 12.6 Update `approved_translation` through existing glossary repository methods.
  - [ ] 12.7 Persist rationale as a glossary decision event.
  - [ ] 12.8 Use `event_type="approve"` or nearest existing event type.
  - [ ] 12.9 Rely on existing glossary revision behavior to increment revision.
  - [ ] 12.10 Return entry ID, canonical term, approved translation, glossary revision, and updated timestamp.
  - [ ] 12.11 Do not silently approve pending or rejected terms outside existing glossary rules.

- [ ] 13. Add Editor Frontend QA Flow
  - [ ] 13.1 Add glossary QA action or debounced preview lint call in translated chapter editor.
  - [ ] 13.2 Render issue severity.
  - [ ] 13.3 Render source/canonical term.
  - [ ] 13.4 Render approved translation.
  - [ ] 13.5 Render matched variant when available.
  - [ ] 13.6 Render short fix hint.
  - [ ] 13.7 Show advisory notes separately from warnings and blocking errors.
  - [ ] 13.8 On blocking save response, show fix or override options.
  - [ ] 13.9 Add override UI with required reason for authorized users.
  - [ ] 13.10 Add owner/admin action to approve a changed translation from a QA issue.
  - [ ] 13.11 Show QA unavailable messages as non-blocking.
  - [ ] 13.12 Keep QA UI admin/editor-only.
  - [ ] 13.13 Confirm public reader UI is unchanged.

- [ ] 14. Add Observability
  - [ ] 14.1 Log structured QA run events.
  - [ ] 14.2 Include novel ID, chapter ID, platform novel ID when available, glossary revision, checked term count, issue count, status, and elapsed time.
  - [ ] 14.3 Log blocking save events as structured warnings.
  - [ ] 14.4 Log accepted override events.
  - [ ] 14.5 Do not log full source text.
  - [ ] 14.6 Do not log full translated or edited text.
  - [ ] 14.7 Do not log private notes beyond the required audit-safe override reason.
  - [ ] 14.8 Add counters/metrics only if the project already has a metrics pattern.
  - [ ] 14.9 Make QA results eligible for future glossary diagnostics aggregation where applicable.

- [ ] 15. Add Backend Unit Tests
  - [ ] 15.1 Test approved source term present but approved translation missing.
  - [ ] 15.2 Test forbidden variant detection.
  - [ ] 15.3 Test non-approved variant detection.
  - [ ] 15.4 Test owner-locked term maps to blocking severity.
  - [ ] 15.5 Test strict/required/blocking enforcement maps to blocking severity.
  - [ ] 15.6 Test warning/advisory enforcement mapping.
  - [ ] 15.7 Test passing result when approved translation is present.
  - [ ] 15.8 Test empty glossary returns passing result.
  - [ ] 15.9 Test missing source text returns advisory source-context note.
  - [ ] 15.10 Test pending terms are not enforced as approved.
  - [ ] 15.11 Test inactive/rejected/archived terms do not create blocking issues.
  - [ ] 15.12 Test alias relevance matching.
  - [ ] 15.13 Test max term cap metadata.
  - [ ] 15.14 Test deterministic issue IDs.
  - [ ] 15.15 Test normalization does not alter saved edited text.

- [ ] 16. Add API Tests
  - [ ] 16.1 Test preview lint returns HTTP 200 with expected issue payload.
  - [ ] 16.2 Test preview lint with unresolved DB novel returns HTTP 200 and empty advisory note.
  - [ ] 16.3 Test preview lint without source text returns advisory behavior.
  - [ ] 16.4 Test unauthorized preview lint is denied.
  - [ ] 16.5 Test save with `lint=true` includes `glossary_qa`.
  - [ ] 16.6 Test save with warning issues succeeds.
  - [ ] 16.7 Test save with blocking issue and no override returns HTTP 409.
  - [ ] 16.8 Test save with valid authorized override succeeds.
  - [ ] 16.9 Test save with valid authorized override persists override metadata.
  - [ ] 16.10 Test invalid override returns HTTP 400.
  - [ ] 16.11 Test unauthorized override is denied.
  - [ ] 16.12 Test glossary-unavailable save does not fail solely due to QA.
  - [ ] 16.13 Test approve translation change updates glossary entry.
  - [ ] 16.14 Test approve translation change records a decision event.
  - [ ] 16.15 Test approve translation change returns glossary revision and timestamp.
  - [ ] 16.16 Test unauthorized approve translation change is denied.
  - [ ] 16.17 Test approve translation change rejects entries outside novel or allowed inherited/global scope.

- [ ] 17. Add Storage Tests
  - [ ] 17.1 Test persisted QA metadata appears on edited version or edit history.
  - [ ] 17.2 Test override metadata is persisted.
  - [ ] 17.3 Test glossary revision is persisted when available.
  - [ ] 17.4 Test full source text is not persisted inside QA metadata.
  - [ ] 17.5 Test full edited text is not duplicated inside QA metadata.
  - [ ] 17.6 Test legacy edited versions without QA metadata remain loadable.
  - [ ] 17.7 Test JSON-backed QA metadata follows storage contract and atomic write behavior where applicable.

- [ ] 18. Add Frontend Tests
  - [ ] 18.1 Test issue list renders advisory, warning, blocked, and overridden states.
  - [ ] 18.2 Test preview lint action or debounce calls backend.
  - [ ] 18.3 Test returned issues render severity, source term, approved translation, matched variant, and fix hint.
  - [ ] 18.4 Test blocking save response displays fix or override options.
  - [ ] 18.5 Test override requires reason before submit.
  - [ ] 18.6 Test authorized override submits structured override payload.
  - [ ] 18.7 Test approve translation change action calls admin endpoint.
  - [ ] 18.8 Test advisory notes are non-blocking.
  - [ ] 18.9 Test QA unavailable message does not block normal editing.
  - [ ] 18.10 Test QA metadata is not shown in public reader UI.

- [ ] 19. Backward Compatibility Checks
  - [ ] 19.1 Confirm existing edited translations remain loadable.
  - [ ] 19.2 Confirm existing editor save clients can omit new QA fields.
  - [ ] 19.3 Confirm glossary-unavailable results do not break legacy saves.
  - [ ] 19.4 Confirm prompt-time glossary injection is unchanged.
  - [ ] 19.5 Confirm glossary approval workflows remain the source of truth.
  - [ ] 19.6 Confirm active-version selection is unchanged.
  - [ ] 19.7 Confirm public reader output is unchanged.
  - [ ] 19.8 Confirm full glossary revision invalidation remains separate.

- [ ] 20. Documentation and Rollout
  - [ ] 20.1 Document the `glossary_qa` response contract.
  - [ ] 20.2 Document issue codes and severity mapping.
  - [ ] 20.3 Document when QA blocks saves.
  - [ ] 20.4 Document who can override blocking issues.
  - [ ] 20.5 Document override metadata and audit behavior.
  - [ ] 20.6 Document approve-translation-change behavior.
  - [ ] 20.7 Roll out preview lint first.
  - [ ] 20.8 Enable blocking enforcement only for owner-locked, strict, required, or blocking terms.
  - [ ] 20.9 Confirm this spec replaces the partial `editor-glossary-enforcement` spec.

- [ ] 21. Run Verification
  - [ ] 21.1 Run focused backend unit tests for glossary editor QA.
  - [ ] 21.2 Run editor API tests.
  - [ ] 21.3 Run glossary API tests.
  - [ ] 21.4 Run edited translation storage tests.
  - [ ] 21.5 Run frontend editor tests.
  - [ ] 21.6 Run existing glossary tests.
  - [ ] 21.7 Run existing editor save tests.
  - [ ] 21.8 Run existing public reader tests to confirm no reader regression.
  - [ ] 21.9 Run `ruff check` on changed backend files and tests.
  - [ ] 21.10 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 21.11 Fix test, lint, and type failures caused by this work.

- [ ] 22. Final Acceptance Review
  - [ ] 22.1 Verify preview lint returns deterministic `glossary_qa` results.
  - [ ] 22.2 Verify save-time QA blocks strict, required, blocking, or owner-locked violations unless authorized override is provided.
  - [ ] 22.3 Verify warning and advisory issues save successfully and persist QA metadata.
  - [ ] 22.4 Verify override reason, author, timestamp, glossary revision, and affected issues are persisted.
  - [ ] 22.5 Verify admins can approve edited terminology as a new glossary translation.
  - [ ] 22.6 Verify approve-translation-change records a decision event.
  - [ ] 22.7 Verify glossary revision metadata is included in QA results and persisted summaries when available.
  - [ ] 22.8 Verify missing glossary data does not break legacy editor saves.
  - [ ] 22.9 Verify public reader output remains unchanged.
  - [ ] 22.10 Verify unit, API, storage, and frontend tests pass.

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

- [ ] `GlossaryEditorQAService` or equivalent deterministic QA service exists.
- [ ] QA service loads approved glossary entries through existing repository patterns.
- [ ] QA service detects missing approved translations, required term violations, forbidden variants, and non-approved variants.
- [ ] QA service supports source-context relevance and advisory no-source mode.
- [ ] Preview lint endpoint returns `glossary_qa` without saving text.
- [ ] Save-time QA blocks only blocking issues unless authorized override is provided.
- [ ] Authorized override requires reason and persists audit metadata.
- [ ] Edited translation saves persist compact QA summaries.
- [ ] Approve-translation-change endpoint updates glossary entries through existing glossary methods.
- [ ] Editor UI displays QA issues, advisory notes, blocking states, override controls, and approve-change action.
- [ ] Structured QA logs are emitted without full chapter text.
- [ ] Legacy edited translations remain loadable.
- [ ] Prompt-time glossary injection, glossary review workflows, active-version selection, and public reader output are unchanged.
- [ ] Unit, API, storage, frontend, lint, and type checks pass.