# Requirements: Glossary-Aware Editor QA

## Introduction

Manual editing can currently save translated chapter text without checking whether approved glossary terms are preserved. This creates a consistency gap: translation prompts may know the glossary, but editor changes can remove required names, replace approved terminology, or introduce forbidden variants without warning.

This spec adds deterministic glossary QA to the editor workflow. It merges the earlier `editor-glossary-enforcement` idea into `glossary-aware-editor-qa`, so there is one complete spec covering preview linting, save-time QA, override handling, edit metadata, and an admin shortcut for approving intentional terminology changes.

## Scope

In scope:

- A reusable backend QA/lint service for translated chapter edits.
- A preview lint endpoint for editor UI checks before saving.
- Save-time glossary QA on manual translation edits.
- Configurable severity handling: advisory, warning, blocking, and override.
- Persisted QA metadata on edited translation versions or edit history.
- Editor UI surfacing for glossary issues and override rationale.
- Admin shortcut to approve a changed term translation when the edit is intentionally better than the existing glossary.
- Unit and API tests for the QA service, editor endpoints, override path, and admin update path.

Out of scope:

- AI-based semantic validation of term usage.
- Full-text batch lint for every chapter in a novel.
- Public reader glossary annotations.
- Translation prompt glossary injection.
- Glossary revision invalidation for queued or completed machine translations.

## Requirements

### Requirement 1: Deterministic glossary QA service

**User Story:** As a maintainer, I want manual edits checked against approved glossary entries, so that editor changes do not silently break term consistency.

#### Acceptance Criteria

1. WHEN editor QA is requested THEN the system SHALL call a reusable service named `GlossaryEditorQAService` or an equivalent local name such as `GlossaryLintService`.
2. WHEN the service runs THEN it SHALL load approved glossary entries for the novel through the existing glossary repository.
3. WHEN source text is available THEN the service SHALL only require terms that are detected in the source text.
4. WHEN source text is not available THEN the service SHALL run in advisory mode against a capped set of approved terms and mark the result with a source-context note.
5. WHEN an approved source term is detected but its approved translation is absent from the edited text THEN the service SHALL emit a glossary issue.
6. WHEN an approved entry has forbidden variants and a forbidden variant appears in the edited text THEN the service SHALL emit a glossary issue.
7. WHEN a term is owner-locked or has a strict/required/blocking enforcement level THEN the issue SHALL be eligible to block save unless an authorized override is submitted.
8. WHEN no approved entries exist THEN the service SHALL return a passing result with zero issues.
9. WHEN too many entries are eligible for checking THEN the service SHALL cap checks at a configured limit and include the cap metadata in the result.

### Requirement 2: Preview lint endpoint

**User Story:** As an editor, I want to check glossary issues before saving, so that I can fix terminology without losing my current edit.

#### Acceptance Criteria

1. WHEN an owner calls `POST /{novel_id}/chapters/{chapter_id}/translated/lint` with edited text THEN the backend SHALL return glossary QA results without saving the text.
2. WHEN the route receives a slug `novel_id` but the glossary repository requires the integer platform novel id THEN the backend SHALL resolve the slug through the `Novel` row before running QA.
3. WHEN the novel cannot be resolved to a glossary-enabled DB row THEN the endpoint SHALL return HTTP 200 with an empty advisory result and a note such as `Glossary not available for this novel.`
4. WHEN linting succeeds THEN the endpoint SHALL return HTTP 200 with `glossary_qa`, including status, checked term count, glossary revision, issues, and notes.
5. WHEN the user is not authorized to edit the novel THEN the endpoint SHALL return the same authorization error style as existing editor endpoints.
6. WHEN source text is provided in the request THEN the service SHALL use it for relevant-term detection.
7. WHEN source text is omitted THEN the service SHALL still return an advisory result rather than failing the request.

### Requirement 3: Save-time QA

**User Story:** As a novel owner, I want glossary QA to run when edited translations are saved, so that inconsistent terminology cannot enter the stored edited version unnoticed.

#### Acceptance Criteria

1. WHEN `PUT /{novel_id}/chapters/{chapter_id}/translated` is called with QA enabled THEN the backend SHALL run glossary QA before committing the edited translation as active content.
2. WHEN the request sets `lint=true` or equivalent THEN the response SHALL include `glossary_qa`.
3. WHEN the request does not request lint output THEN the backend MAY still enforce blocking issues, but it SHALL preserve the existing response shape unless an issue blocks the save.
4. WHEN QA returns only advisory or warning issues THEN the save SHALL succeed and the response SHALL include the issues if lint output was requested.
5. WHEN QA returns blocking issues and no valid override is provided THEN the save SHALL fail with HTTP 409 and a response body containing `glossary_qa`.
6. WHEN QA returns blocking issues and a valid override is provided by an authorized owner/admin THEN the save SHALL succeed and persist the override reason.
7. WHEN the glossary system is unavailable for the novel THEN editor save SHALL not fail solely because of glossary QA; the response SHALL include an advisory note when lint output is requested.
8. WHEN existing clients omit the new QA fields THEN their current edit save behavior SHALL remain backward compatible.

### Requirement 4: Override workflow

**User Story:** As a reviewer, I need to override glossary QA in rare cases, so that intentional prose improvements are possible without disabling glossary protection globally.

#### Acceptance Criteria

1. WHEN a blocking issue is returned THEN the editor UI SHALL show which glossary terms caused the block.
2. WHEN the user chooses to override THEN the UI SHALL require an override reason.
3. WHEN the override is submitted THEN the request SHALL include a structured override object with reason and affected issue ids or term ids.
4. WHEN the backend accepts an override THEN the saved edit metadata SHALL include override author, timestamp, reason, glossary revision, and affected issues.
5. WHEN the user lacks override permission THEN the backend SHALL reject the override request.
6. WHEN an override succeeds THEN the response SHALL mark `glossary_qa.status` as `overridden`.

### Requirement 5: Persist QA metadata

**User Story:** As an administrator, I want to audit glossary QA decisions on edited translations, so that terminology drift can be traced later.

#### Acceptance Criteria

1. WHEN an edited translation is saved after QA THEN the system SHALL persist the QA result or a compact immutable summary with the edited translation version.
2. WHEN an edit is saved with override THEN the system SHALL persist the override metadata.
3. WHEN the edited translation version is fetched for admin/editor display THEN the backend SHALL be able to expose the latest QA status.
4. WHEN only legacy edited files exist THEN readers and editors SHALL continue to load them without requiring QA metadata.
5. WHEN QA metadata is stored in JSON files THEN it SHALL follow the storage contract and atomic write rules defined by storage specs.

### Requirement 6: Admin shortcut for approving changed terminology

**User Story:** As a glossary owner, I want to approve a better term translation directly from an editor QA issue, so that intentional terminology improvements update the glossary instead of becoming repeated overrides.

#### Acceptance Criteria

1. WHEN an owner/admin calls `POST /{novel_id}/glossary/entries/{entry_id}/approve-translation-change` with a new translation THEN the backend SHALL update the glossary entry approved translation.
2. WHEN the approval request includes a rationale THEN the backend SHALL persist it as a glossary decision event.
3. WHEN the entry is not part of the requested novel or inherited global glossary scope THEN the backend SHALL reject the request.
4. WHEN the entry is owner-locked THEN only a user with owner/admin permission SHALL approve the translation change.
5. WHEN the update succeeds THEN the endpoint SHALL return entry id, canonical term, approved translation, glossary revision, and updated timestamp.
6. WHEN the glossary revision changes THEN downstream specs for revision invalidation SHALL handle invalidating affected translations.

### Requirement 7: Editor UI surfacing

**User Story:** As an editor, I want glossary issues displayed near the edited text, so that I can quickly understand and fix them.

#### Acceptance Criteria

1. WHEN the editor opens a translated chapter THEN the UI SHALL provide a glossary QA action or automatically run preview lint after edits debounce.
2. WHEN QA finds issues THEN the UI SHALL show issue severity, source term, expected translation, actual matched variant if present, and a short fix hint.
3. WHEN QA returns blocking issues THEN the primary save action SHALL communicate that saving requires fixing issues or submitting an override.
4. WHEN a term translation should be changed globally THEN the UI SHALL provide an owner/admin action that calls the approve translation change endpoint.
5. WHEN the backend returns only advisory notes THEN the UI SHALL not present them as save failures.
6. WHEN the backend is unavailable or QA fails unexpectedly THEN the UI SHALL allow existing save behavior and show a non-blocking QA unavailable message.

### Requirement 8: Observability and diagnostics

**User Story:** As an operator, I want visibility into editor QA outcomes, so that I can diagnose noisy rules and terminology drift.

#### Acceptance Criteria

1. WHEN QA runs THEN the backend SHALL log novel id, chapter id, glossary revision, checked term count, issue count, status, and elapsed time.
2. WHEN QA blocks a save THEN the backend SHALL log a structured warning without logging full chapter text.
3. WHEN an override is accepted THEN the backend SHALL log the override metadata without leaking full chapter text.
4. WHEN the admin diagnostics spec is implemented THEN editor QA results SHOULD be eligible for aggregation there.

### Requirement 9: Tests

**User Story:** As a developer, I want tests covering glossary-aware editing, so that the editor does not regress into silent glossary drift.

#### Acceptance Criteria

1. WHEN an approved term is present in source text but the approved translation is missing from edited text THEN a unit test SHALL assert a missing required term issue.
2. WHEN an owner-locked or strict term is violated THEN a unit test SHALL assert blocking severity.
3. WHEN all required translations are present THEN a unit test SHALL assert passing QA.
4. WHEN no glossary entries exist THEN a unit test SHALL assert passing QA with zero issues.
5. WHEN the preview lint endpoint is called THEN an API test SHALL assert HTTP 200 and the expected issue payload.
6. WHEN the preview lint endpoint cannot resolve a DB novel row THEN an API test SHALL assert HTTP 200 with an empty advisory result and note.
7. WHEN save-time QA finds a blocking issue without override THEN an API test SHALL assert HTTP 409.
8. WHEN save-time QA finds a blocking issue with valid override THEN an API test SHALL assert successful save and persisted override metadata.
9. WHEN `lint=true` is passed to save THEN an API test SHALL assert the response includes `glossary_qa`.
10. WHEN approve translation change is called by an authorized owner/admin THEN an API test SHALL assert the glossary entry and decision event are updated.
11. WHEN an unauthorized user calls editor QA or approval endpoints THEN API tests SHALL assert access is denied.

