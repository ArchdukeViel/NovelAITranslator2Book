# Requirements: Novel Onboarding State Machine

## Introduction

Adding a new novel is a two-phase workflow. The admin crawler page first runs a preliminary crawl that can persist `metadata.json`, refresh the catalog projection, and bootstrap glossary candidates. Only after the operator reviews discovered chapters does the system create and run the full chapter scrape activity. If the operator closes the page, abandons the modal, or the full scrape fails, the repository can be left with metadata and glossary state but no fetched chapter bodies.

This spec makes onboarding state explicit and recoverable. The goal is to distinguish metadata-only novels, pending body scrape, failed onboarding, and ready-for-translation novels across backend APIs, storage metadata, DB projection, and admin UI.

## Requirements

### REQ-1: Explicit Onboarding State

The system must track novel onboarding as an explicit state machine.

- REQ-1.1: Add an onboarding status field to the novel's storage metadata under `onboarding_status`.
- REQ-1.2: Allowed values must include `not_started`, `metadata_discovered`, `glossary_pending`, `chapters_pending`, `scraping_chapters`, `ready_for_translation`, `failed`, and `cancelled`.
- REQ-1.3: Existing novels without `onboarding_status` must be treated as backward-compatible. If they have fetched chapters, infer `ready_for_translation`; otherwise infer `metadata_discovered` or `chapters_pending` based on available metadata.
- REQ-1.4: The status must be updated by backend workflow code, not only by frontend state.
- REQ-1.5: The status must be visible in admin/library responses used to list novels.

### REQ-2: Preliminary Crawl State

Preliminary crawl must mark that metadata has been discovered but chapter bodies may not exist yet.

- REQ-2.1: When `preliminary_crawl_novel` successfully saves metadata, set `onboarding_status` to `metadata_discovered`.
- REQ-2.2: If glossary candidates are bootstrapped and review is required, set or expose glossary status as `glossary_pending` without losing the onboarding status.
- REQ-2.3: If the preliminary crawl discovers selectable chapters, set `chapters_pending` after metadata save and glossary bootstrap are complete.
- REQ-2.4: The preliminary crawl response must include onboarding status and whether body scrape is required.
- REQ-2.5: Preliminary crawl failure must not create `ready_for_translation` state.

### REQ-3: Full Chapter Scrape State

The full chapter scrape activity must update onboarding status throughout the scrape lifecycle.

- REQ-3.1: When full chapter scrape starts for a novel that is not ready, set `onboarding_status` to `scraping_chapters`.
- REQ-3.2: When full chapter scrape completes with at least one usable raw chapter and no blocking failure, set `onboarding_status` to `ready_for_translation`.
- REQ-3.3: When full chapter scrape completes with partial failures but at least one usable raw chapter, the status may become `ready_for_translation` only if the existing translation flow supports partial chapter sets.
- REQ-3.4: When full chapter scrape fails fatally before any usable raw chapter is saved, set `onboarding_status` to `failed`.
- REQ-3.5: Failure status must include a short machine-readable `onboarding_error_code` and safe human-readable `onboarding_error_message` in metadata.
- REQ-3.6: Retrying a failed or pending full scrape must clear stale onboarding error fields when the retry starts.

### REQ-4: Resume Onboarding

Admins must be able to resume an interrupted or incomplete onboarding flow.

- REQ-4.1: The admin API or existing activity creation flow must allow resuming full chapter scrape for novels in `metadata_discovered`, `glossary_pending`, `chapters_pending`, or `failed` state.
- REQ-4.2: Resume must reuse existing metadata and discovered chapter list when available.
- REQ-4.3: Resume must not rerun preliminary crawl unless the admin explicitly refreshes metadata.
- REQ-4.4: Resume must create or run the normal crawl activity so existing crawl observability still applies.
- REQ-4.5: Resume must be idempotent enough that repeated clicks do not create conflicting concurrent scrapes.

### REQ-5: Cancel or Remove Incomplete Onboarding

Admins must be able to cancel incomplete onboarding state.

- REQ-5.1: Add a backend operation to mark onboarding as `cancelled` for metadata-only or failed onboarding novels.
- REQ-5.2: Cancel must not delete files by default.
- REQ-5.3: If the project already has a delete/remove novel operation, the UI may guide users to that operation for destructive cleanup.
- REQ-5.4: Cancelled novels must not appear as ready for translation.
- REQ-5.5: Cancelled novels may remain visible in admin library with a cancelled badge/filter.
- REQ-5.6: Public reader routes must not expose cancelled onboarding novels unless they are explicitly published by existing publish controls.

### REQ-6: Translation Readiness Gate

Translation should not start for novels that are not ready for translation.

- REQ-6.1: `translate_novel` or its orchestration preflight must check onboarding status before starting translation.
- REQ-6.2: Novels in `metadata_discovered`, `glossary_pending`, `chapters_pending`, `scraping_chapters`, `failed`, or `cancelled` must produce a clear preflight issue or HTTP error instead of starting translation.
- REQ-6.3: Existing glossary gate behavior must remain intact.
- REQ-6.4: `ready_for_translation` does not bypass glossary review; both onboarding readiness and glossary readiness must pass unless an existing override explicitly bypasses glossary.
- REQ-6.5: Existing novels without status must use inferred readiness to avoid breaking current deployments.

### REQ-7: Admin UI Visibility

Admin screens must make incomplete onboarding visible and actionable.

- REQ-7.1: Novel list/library admin UI must show onboarding status badges.
- REQ-7.2: Metadata-only or chapter-pending novels must show an action to resume chapter scrape.
- REQ-7.3: Failed onboarding novels must show the last onboarding error message.
- REQ-7.4: Failed onboarding novels must show retry/resume action.
- REQ-7.5: Cancelled novels must be visually distinct and not grouped with ready novels.
- REQ-7.6: Existing ready novels must not be visually regressed.

### REQ-8: API Response Shape

Backend responses must expose onboarding state additively.

- REQ-8.1: Preliminary crawl response must include `onboarding_status`.
- REQ-8.2: Admin novel list/detail responses must include `onboarding_status`.
- REQ-8.3: Activity-related responses for crawl completion should include final onboarding status where convenient through existing metadata or novel summary fields.
- REQ-8.4: New response fields must be additive and must not remove existing fields.
- REQ-8.5: If strict response models are used, they must be updated so the new fields are not dropped.

### REQ-9: Backward Compatibility

The state machine must work with existing novels and existing storage.

- REQ-9.1: Existing `metadata.json` files without onboarding fields must load successfully.
- REQ-9.2: Existing DB rows without onboarding-specific columns must continue to work if no DB migration is chosen.
- REQ-9.3: If a DB projection field is added, a migration/backfill plan must be included.
- REQ-9.4: Existing crawler and translation APIs must keep their route paths unless an additional route is necessary.
- REQ-9.5: Existing public reader behavior must remain controlled by publish/reader availability logic, not onboarding status alone.

### REQ-10: Tests

The implementation must include focused tests for state transitions and compatibility.

- REQ-10.1: Test preliminary crawl success sets metadata/discovered or chapters-pending status.
- REQ-10.2: Test glossary bootstrap can coexist with onboarding status.
- REQ-10.3: Test full scrape start sets `scraping_chapters`.
- REQ-10.4: Test full scrape completion sets `ready_for_translation`.
- REQ-10.5: Test fatal scrape failure sets `failed` and records safe error metadata.
- REQ-10.6: Test resume from pending/failed state creates or runs crawl activity.
- REQ-10.7: Test cancel sets `cancelled` and blocks translation readiness.
- REQ-10.8: Test translation preflight blocks non-ready onboarding states.
- REQ-10.9: Test existing metadata without onboarding fields infers compatible status.
- REQ-10.10: Test admin/API responses include onboarding status.

## Non-Goals

- This spec does not redesign source adapters.
- This spec does not change crawl parsing logic.
- This spec does not replace activity queue semantics.
- This spec does not delete files for cancelled onboarding by default.
- This spec does not change glossary review rules except to display them alongside onboarding state.
- This spec does not change public reader availability policy.

