# Requirements Document

## Introduction

The glossary-first onboarding feature integrates glossary bootstrapping into
the novel onboarding flow so that every newly crawled or imported novel goes
through a structured glossary readiness gate before translation is permitted.

Currently the glossary subsystem — term extraction, translation, review, and
prompt injection — is fully functional but entirely decoupled from onboarding.
Nothing forces or even encourages an operator to build a glossary before
running translation, so terminology consistency is left to chance.

This feature adds a per-novel `glossary_status` field with three states
(`glossary_pending`, `glossary_ready`, `glossary_skipped`), an automatic
glossary bootstrap step after metadata is saved during preliminary crawl or
scrape, a translation guard that blocks jobs when the status is
`glossary_pending` unless the request carries an explicit override flag, an
owner-facing control surface in the novel-add flow ("Extract terms / Approve /
Skip"), a readiness badge on the admin novel-detail page, and a translation
prompt audit field that records which glossary revision was active when each
chapter was translated.

---

## Glossary

- **Novel**: A web novel entry identified by `novel_id` (slug). Heavy content
  lives in `storage/novel_library/`; catalog metadata lives in the `novels`
  relational table.
- **Glossary_Status**: A per-novel readiness state persisted in the `novels`
  table. Valid values are `glossary_pending`, `glossary_ready`, and
  `glossary_skipped`.
- **Glossary_Bootstrap**: The automatic stage, executed by the
  `Onboarding_Orchestrator` immediately after metadata is saved, that extracts
  candidate glossary terms from available source chapters and marks the novel
  `glossary_pending`.
- **Glossary_Revision**: An integer counter incremented every time the set of
  approved glossary entries for a novel changes. Stored on the `novels` table
  as `glossary_revision`.
- **Onboarding_Orchestrator**: The backend service responsible for executing
  the preliminary-crawl and scrape-metadata pipeline steps, located at
  `services/orchestration/crawler.py` and orchestrated by
  `NovelOrchestrationService`.
- **Translation_Guard**: The pre-flight check inside `_preflight_translation`
  that inspects `Glossary_Status` and blocks translation when the status is
  `glossary_pending` and no override flag is provided.
- **Override_Flag**: A boolean request field (`skip_glossary_gate`) on the
  translate API endpoint that allows an authenticated owner to bypass the
  `Translation_Guard` for a single translation job.
- **Readiness_Badge**: A UI element on the admin novel-detail page that
  displays the current `Glossary_Status` and provides direct links to the
  glossary review workflow.
- **Prompt_Audit_Metadata**: Per-chapter metadata saved alongside each
  translation output recording the `Glossary_Revision` number and the count
  of approved glossary terms that were injected into the prompt at the time of
  translation.
- **GlossaryRepository**: The SQLAlchemy-backed data-access object at
  `services/glossary_repository.py` that manages glossary entry records.
- **GlossaryPromptInjectionService**: The service at
  `services/glossary_prompt_injection.py` that builds the glossary block
  included in translation prompts.
- **TranslateStage**: The translation pipeline stage at
  `translation/pipeline/stages/translate.py` that calls
  `GlossaryPromptInjectionService` and emits per-chunk translation outputs.

---

## Requirements

### Requirement 1: Per-Novel Glossary Status Field

**User Story:** As the platform owner, I want every novel to carry an explicit
glossary readiness state, so that I can see at a glance whether a novel is
ready to translate with a vetted glossary or still needs review.

#### Acceptance Criteria

1. THE `novels` table SHALL include a `glossary_status` column of type
   `VARCHAR(32)` with a default value of `glossary_pending`.
2. THE `novels` table SHALL include a `glossary_revision` column of type
   `INTEGER` with a default value of `0`.
3. WHEN the `glossary_status` column is read, THE `Novel_Model` SHALL only
   accept one of the three values `glossary_pending`, `glossary_ready`, or
   `glossary_skipped`.
4. IF an attempt is made to write an unrecognised value to `glossary_status`,
   THEN THE `Novel_Model` SHALL reject the write with a `ValueError`.
5. THE `Catalog_Projection` SHALL include `glossary_status` and
   `glossary_revision` so that admin list views can filter and sort without
   additional queries.

---

### Requirement 2: Automatic Glossary Bootstrap After Metadata Save

**User Story:** As the platform owner, I want candidate glossary terms to be
extracted automatically when I add a new novel, so that I arrive at the review
step with a pre-populated list rather than starting from scratch.

#### Acceptance Criteria

1. WHEN `scrape_metadata` completes successfully for a novel whose
   `glossary_status` is not `glossary_ready`, THE `Onboarding_Orchestrator`
   SHALL invoke `extract_glossary_terms` using available source chapter texts
   or, when no chapters are stored yet, metadata fields (title, synopsis).
2. WHEN `Glossary_Bootstrap` succeeds and produces at least one candidate
   term, THE `Onboarding_Orchestrator` SHALL set `glossary_status` to
   `glossary_pending` and persist the candidates via `GlossaryRepository`.
3. WHEN `Glossary_Bootstrap` produces zero candidate terms, THE
   `Onboarding_Orchestrator` SHALL leave `glossary_status` as
   `glossary_pending` and record a warning in the activity log explaining
   that no terms were found.
4. IF `Glossary_Bootstrap` raises an exception, THEN THE
   `Onboarding_Orchestrator` SHALL log the error, leave `glossary_status`
   unchanged, and allow the rest of the metadata-save pipeline to complete
   without surfacing the bootstrap failure as a fatal error.
5. WHILE `glossary_status` is `glossary_ready`, THE `Onboarding_Orchestrator`
   SHALL skip `Glossary_Bootstrap` so that an already-approved glossary is
   not overwritten by re-crawling the novel.

---

### Requirement 3: Translation Guard

**User Story:** As the platform owner, I want translation to be blocked for
novels that still need glossary review, so that I never accidentally produce
an inconsistently translated output.

#### Acceptance Criteria

1. WHEN a translate request is received for a novel whose `glossary_status` is
   `glossary_pending` and the request does not include `skip_glossary_gate:
   true`, THE `Translation_Guard` SHALL reject the job with HTTP 422 and a
   machine-readable error code `glossary_gate_pending`.
2. WHEN a translate request is received with `skip_glossary_gate: true`, THE
   `Translation_Guard` SHALL allow translation to proceed regardless of
   `glossary_status` and SHALL record the override in the activity log.
3. WHILE `glossary_status` is `glossary_ready` or `glossary_skipped`, THE
   `Translation_Guard` SHALL not impose any additional restriction beyond the
   existing pre-flight checks.
4. THE `TranslateRequest` schema SHALL include an optional boolean field
   `skip_glossary_gate` with a default value of `false`.
5. IF the `Translation_Guard` rejects a job, THEN THE `Translation_Guard`
   SHALL include in the error response body: the current `glossary_status`,
   the count of `glossary_pending` candidate entries awaiting review, and a
   URL path to the glossary review page for that novel.

---

### Requirement 4: Owner Glossary Control During Novel Add

**User Story:** As the platform owner, I want to choose "Extract and review
terms", "Approve all candidates", or "Skip glossary this time" immediately
after adding a novel, so that I have full control over the glossary gate
without navigating away to a separate admin section.

#### Acceptance Criteria

1. WHEN a preliminary crawl or scrape completes and `Glossary_Bootstrap` has
   produced at least one candidate, THE `Admin_Novel_Add_Flow` SHALL present
   three actions: "Review glossary before translating",
   "Approve all candidates and set ready", and "Skip glossary for now".
2. WHEN the owner selects "Approve all candidates and set ready", THE
   `Admin_Novel_Add_Flow` SHALL call the glossary batch-approve endpoint, set
   `glossary_status` to `glossary_ready`, and increment `glossary_revision`
   by 1.
3. WHEN the owner selects "Skip glossary for now", THE `Admin_Novel_Add_Flow`
   SHALL set `glossary_status` to `glossary_skipped` so that translation is
   not blocked.
4. WHEN the owner selects "Review glossary before translating", THE
   `Admin_Novel_Add_Flow` SHALL navigate to the existing glossary review page
   and leave `glossary_status` as `glossary_pending`.
5. WHEN `Glossary_Bootstrap` produces zero candidates, THE
   `Admin_Novel_Add_Flow` SHALL present only the "Skip glossary for now"
   action and a notice explaining that no terms were detected.
6. THE `Glossary_Status` transition endpoint SHALL be authenticated and
   restricted to the `owner` role.

---

### Requirement 5: Glossary Readiness Badge on Admin Novel Detail

**User Story:** As the platform owner, I want a visible readiness badge on the
novel detail page, so that I can immediately see whether the glossary gate is
blocking translation without opening the glossary management section.

#### Acceptance Criteria

1. THE `Admin_Novel_Detail_Page` SHALL display a `Readiness_Badge` that
   reflects the current `glossary_status` using distinct visual treatments:
   amber for `glossary_pending`, green for `glossary_ready`, and grey for
   `glossary_skipped`.
2. WHEN `glossary_status` is `glossary_pending`, THE `Readiness_Badge` SHALL
   include a link to the glossary review workflow and display the count of
   candidate entries awaiting review.
3. WHEN `glossary_status` is `glossary_ready`, THE `Readiness_Badge` SHALL
   display the current `glossary_revision` number.
4. WHEN the owner clicks the badge action link, THE `Admin_Novel_Detail_Page`
   SHALL navigate to the correct glossary management view without a full page
   reload.
5. THE `Admin_Novel_Detail_API` SHALL return `glossary_status`,
   `glossary_revision`, and `glossary_pending_count` in the novel detail
   response payload so that the frontend can render the badge without a
   separate API call.

---

### Requirement 6: Glossary Status Transition API

**User Story:** As the platform owner, I want a dedicated API endpoint to
change a novel's glossary status, so that status transitions are auditable and
cannot be performed by anonymous or non-owner actors.

#### Acceptance Criteria

1. THE `Glossary_Status_Transition_API` SHALL expose a `PATCH
   /api/novels/{novel_id}/glossary-status` endpoint that accepts a
   `target_status` field from the set `{glossary_ready, glossary_skipped,
   glossary_pending}`.
2. WHEN the endpoint is called with `target_status: glossary_ready`, THE
   `Glossary_Status_Transition_API` SHALL also increment `glossary_revision`
   by 1.
3. WHEN the endpoint is called with `target_status: glossary_skipped`, THE
   `Glossary_Status_Transition_API` SHALL set the status without changing
   `glossary_revision`.
4. IF the `novel_id` does not correspond to an existing novel, THEN THE
   `Glossary_Status_Transition_API` SHALL return HTTP 404.
5. IF the caller does not hold the `owner` role, THEN THE
   `Glossary_Status_Transition_API` SHALL return HTTP 403.
6. THE `Glossary_Status_Transition_API` SHALL write a
   `NovelGlossaryDecisionEvent` record for every successful status change,
   capturing the actor user ID, old status, new status, and an ISO 8601
   timestamp.

---

### Requirement 7: Prompt Audit Metadata

**User Story:** As the platform owner, I want each translated chapter to
record which glossary revision was active at translation time, so that I can
detect chapters that were translated before a glossary was approved and
re-translate them if needed.

#### Acceptance Criteria

1. WHEN `TranslateStage` resolves the glossary block for a chapter, THE
   `TranslateStage` SHALL record in the translation output metadata:
   `glossary_revision` (the integer revision at the time of translation) and
   `glossary_injected_term_count` (the count of approved terms included in
   the prompt).
2. WHEN no approved glossary entries exist for a novel, THE `TranslateStage`
   SHALL record `glossary_revision: 0` and `glossary_injected_term_count: 0`
   in the translation output metadata.
3. THE `Prompt_Audit_Metadata` fields SHALL be persisted alongside the
   existing translation output record in storage so that they survive
   re-translation operations without overwriting previous audit values.
4. WHEN the admin translation output detail API returns a chapter's translation
   record, THE response SHALL include `glossary_revision` and
   `glossary_injected_term_count` from the stored `Prompt_Audit_Metadata`.
5. THE `glossary_revision` value written by `TranslateStage` SHALL be read
   from the `novels.glossary_revision` column at the moment translation
   starts, not inferred from entry counts.

---

### Requirement 8: Glossary Revision Increment on Approved-Entry Change

**User Story:** As the platform owner, I want `glossary_revision` to
automatically increment whenever approved glossary entries change, so that the
prompt audit trail stays accurate without requiring manual version bumps.

#### Acceptance Criteria

1. WHEN a glossary entry's status is changed to `approved` via
   `GlossaryRepository`, THE `GlossaryRepository` SHALL increment
   `novels.glossary_revision` for the affected novel within the same database
   transaction.
2. WHEN an `approved` glossary entry is updated (translation, enforcement
   level, or matching policy), THE `GlossaryRepository` SHALL increment
   `novels.glossary_revision` for the affected novel within the same database
   transaction.
3. WHEN an `approved` glossary entry is deprecated or rejected, THE
   `GlossaryRepository` SHALL increment `novels.glossary_revision` for the
   affected novel within the same database transaction.
4. WHEN a glossary entry whose status is `candidate` or `recommended` is
   updated but not transitioned to `approved`, THE `GlossaryRepository` SHALL
   NOT increment `glossary_revision`.
5. IF the `novels.glossary_revision` increment fails due to a database error,
   THEN THE `GlossaryRepository` SHALL roll back the entire transaction and
   propagate the error.
