# Implementation Plan: Glossary-Aware Editor QA

- [ ] 1. Inspect current editor, glossary, and edited translation paths
  - [ ] 1.1 Locate the translated chapter save route and request/response schemas.
  - [ ] 1.2 Locate the glossary repository methods for approved novel and global entries.
  - [ ] 1.3 Locate edited translation storage or edit history metadata format.
  - [ ] 1.4 Confirm how string `novel_id` slugs map to integer platform novel ids.
  - [ ] 1.5 Identify existing owner/admin permission helpers used by editor and glossary routes.

- [ ] 2. Add glossary editor QA schemas
  - [ ] 2.1 Add `GlossaryQAIssue` schema with entry id, canonical term, approved translation, matched variant, severity, code, owner locked flag, and context hint.
  - [ ] 2.2 Add `GlossaryQAResult` schema with status, novel ids, chapter id, glossary revision, checked term count, issue count, source context, notes, and issues.
  - [ ] 2.3 Add `GlossaryLintRequest` or `GlossaryEditorQARequest` with `text`, optional `source_text`, and optional `max_terms`.
  - [ ] 2.4 Extend translated edit request schema with optional `lint` and optional `glossary_override`.
  - [ ] 2.5 Add approve translation change request/response schemas.

- [ ] 3. Implement `GlossaryEditorQAService`
  - [ ] 3.1 Create the service under the existing services package.
  - [ ] 3.2 Inject or construct `GlossaryRepository` using existing dependency patterns.
  - [ ] 3.3 Load approved glossary entries for the novel and inherited global scope when available.
  - [ ] 3.4 Resolve relevant entries from source text using canonical terms and aliases.
  - [ ] 3.5 Fall back to advisory checking when source text is absent.
  - [ ] 3.6 Detect missing approved translations in edited text.
  - [ ] 3.7 Detect forbidden variants and known non-approved variants in edited text.
  - [ ] 3.8 Map `owner_locked` and `enforcement_level` values to advisory, warning, or error severity.
  - [ ] 3.9 Cap checked entries at the configured max term count and include cap metadata.
  - [ ] 3.10 Return stable `passed`, `advisory`, `warning`, or `blocked` status.

- [ ] 4. Add preview lint endpoint
  - [ ] 4.1 Add `POST /{novel_id}/chapters/{chapter_id}/translated/lint` to the editor router.
  - [ ] 4.2 Reuse existing editor authorization checks.
  - [ ] 4.3 Resolve slug `novel_id` to platform novel id when required by the glossary repository.
  - [ ] 4.4 Return HTTP 200 with empty advisory result when glossary data is unavailable for the novel.
  - [ ] 4.5 Return HTTP 200 with `glossary_qa` on successful QA.
  - [ ] 4.6 Avoid saving text from the preview lint endpoint.

- [ ] 5. Integrate QA into translated edit save
  - [ ] 5.1 Run QA before saving when `lint=true` or novel/editor policy requires enforcement.
  - [ ] 5.2 Preserve existing save behavior for clients that omit QA fields when no blocking issue applies.
  - [ ] 5.3 Return `glossary_qa` in the save response when `lint=true`.
  - [ ] 5.4 Return HTTP 409 with `glossary_qa` when blocking issues exist and no valid override is supplied.
  - [ ] 5.5 Accept authorized override payloads with required reason.
  - [ ] 5.6 Mark accepted override results as `overridden`.
  - [ ] 5.7 Ensure glossary-unavailable advisory results do not fail saves by themselves.

- [ ] 6. Persist QA and override metadata
  - [ ] 6.1 Choose the existing edited translation version or edit history location for QA metadata.
  - [ ] 6.2 Store a compact `glossary_qa` summary with status, revision, issue count, checked term count, and issue summaries.
  - [ ] 6.3 Store override user id, timestamp, reason, and affected issue ids when override is accepted.
  - [ ] 6.4 Avoid persisting full source text in QA metadata.
  - [ ] 6.5 Keep legacy edited translation records readable when QA metadata is absent.

- [ ] 7. Add approve translation change endpoint
  - [ ] 7.1 Add `POST /{novel_id}/glossary/entries/{entry_id}/approve-translation-change` to the admin glossary router.
  - [ ] 7.2 Validate owner/admin permission.
  - [ ] 7.3 Validate that the entry belongs to the novel or an allowed inherited/global scope.
  - [ ] 7.4 Update the entry `approved_translation`.
  - [ ] 7.5 Record a glossary decision event with rationale.
  - [ ] 7.6 Return entry id, canonical term, approved translation, glossary revision, and updated timestamp.

- [ ] 8. Add editor frontend QA flow
  - [ ] 8.1 Add a glossary QA action or debounced preview lint call in the translated chapter editor.
  - [ ] 8.2 Render issue severity, canonical term, approved translation, matched variant, and fix hint.
  - [ ] 8.3 Show advisory notes separately from warnings and blocking errors.
  - [ ] 8.4 Disable or intercept save when backend returns blocking issues.
  - [ ] 8.5 Add override UI with required reason for authorized users.
  - [ ] 8.6 Add owner/admin action to approve a changed translation from a QA issue.
  - [ ] 8.7 Show QA unavailable messages as non-blocking.

- [ ] 9. Add observability
  - [ ] 9.1 Log structured QA run events with novel id, chapter id, glossary revision, checked terms, issue count, status, and elapsed time.
  - [ ] 9.2 Log blocking save events without full chapter text.
  - [ ] 9.3 Log accepted override events without full chapter text.
  - [ ] 9.4 Add counters or metrics if the project already has a metrics pattern.

- [ ] 10. Add backend unit tests
  - [ ] 10.1 Test missing approved translation when source contains the canonical term.
  - [ ] 10.2 Test owner-locked or strict term maps to blocking severity.
  - [ ] 10.3 Test forbidden variant detection.
  - [ ] 10.4 Test passing result when approved translation is present.
  - [ ] 10.5 Test empty glossary returns passing result.
  - [ ] 10.6 Test missing source text returns advisory source-context note.
  - [ ] 10.7 Test max term cap metadata.

- [ ] 11. Add API tests
  - [ ] 11.1 Test preview lint returns HTTP 200 with expected issue payload.
  - [ ] 11.2 Test preview lint with unresolved DB novel returns HTTP 200 and empty advisory note.
  - [ ] 11.3 Test unauthorized preview lint is denied.
  - [ ] 11.4 Test save with `lint=true` includes `glossary_qa`.
  - [ ] 11.5 Test save with warning issues succeeds.
  - [ ] 11.6 Test save with blocking issue and no override returns HTTP 409.
  - [ ] 11.7 Test save with valid override succeeds and persists override metadata.
  - [ ] 11.8 Test approve translation change updates the glossary entry and records a decision event.
  - [ ] 11.9 Test unauthorized approve translation change is denied.

- [ ] 12. Add frontend tests
  - [ ] 12.1 Test issue list rendering by severity.
  - [ ] 12.2 Test preview lint call from editor action or debounce.
  - [ ] 12.3 Test blocking save response displays fix or override options.
  - [ ] 12.4 Test override requires a reason before submit.
  - [ ] 12.5 Test approve translation change action calls the admin endpoint.
  - [ ] 12.6 Test QA unavailable message does not block normal editing.

- [ ] 13. Documentation and rollout
  - [ ] 13.1 Document the editor QA response contract.
  - [ ] 13.2 Document when QA blocks saves and who can override.
  - [ ] 13.3 Document the approve translation change shortcut.
  - [ ] 13.4 Roll out with preview lint first, then enable blocking enforcement only for locked or strict terms.
  - [ ] 13.5 Confirm this spec replaces the partial `editor-glossary-enforcement` spec.

