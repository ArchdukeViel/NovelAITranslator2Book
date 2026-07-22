# Requirements: Glossary Revision Translation Invalidation

## Introduction

The glossary system is already part of the translation pipeline: glossary candidates are bootstrapped during onboarding, glossary review gates translation readiness, approved terms are injected into prompts, and glossary revision/cache behavior may already exist.

The remaining reliability gap is what happens after glossary changes. Existing translation versions may have been produced with older approved terminology, queued translation jobs may have been scheduled with a stale glossary snapshot, and admins need a clear way to identify and retranslate affected chapters.

This spec makes glossary freshness visible and actionable without redesigning glossary revision counters, prompt injection, cache invalidation, or active-version selection.

## Requirements

### REQ-1: Store Glossary Snapshot on New Translation Versions

Every newly saved translation version must record the glossary state used to produce it.

* REQ-1.1: New translation version metadata must include `glossary_revision: int` when available.
* REQ-1.2: New translation version metadata must include `glossary_hash: str | null` when a stable hash is available.
* REQ-1.3: New translation version metadata should include `glossary_term_count: int | null` when available.
* REQ-1.4: New translation versions produced with the current glossary must be considered fresh at creation time.
* REQ-1.5: `glossary_stale` may be persisted as a convenience field, but computed freshness must remain the source of truth.
* REQ-1.6: Existing translation versions without glossary metadata must remain loadable.
* REQ-1.7: Storage changes must be additive and must not delete, rewrite, or corrupt existing version text.

### REQ-2: Resolve Current Glossary Snapshot

The system must expose the current glossary state used by translation.

* REQ-2.1: A current glossary snapshot must include:

  * `revision`
  * `hash`
  * `approved_term_count`
* REQ-2.2: The snapshot must come from existing glossary services or model fields where possible.
* REQ-2.3: Do not introduce a second glossary revision system if one already exists.
* REQ-2.4: The snapshot must reflect the same approved glossary content used for prompt injection.
* REQ-2.5: If a glossary hash is computed, it must be stable for semantically meaningful approved glossary content.
* REQ-2.6: Hash computation must not include volatile metadata such as `updated_at` unless the project intentionally treats timestamp-only edits as translation-invalidating.

### REQ-3: Verify Glossary Revision Behavior Without Redesigning It

Glossary revision increments must be verified, not reimplemented wholesale.

* REQ-3.1: Meaningful approved glossary changes must increment the current glossary revision.
* REQ-3.2: Meaningful changes include approved term creation, deletion, deactivation, approved translation changes, enforcement-level changes, alias changes used by prompt injection, and status changes into or out of approved/enforced state.
* REQ-3.3: If revision increments already work, this spec must not duplicate that logic.
* REQ-3.4: If a specific write path fails to increment revision, patch only that missing path.
* REQ-3.5: Glossary review workflow behavior must remain unchanged.

### REQ-4: Preserve Glossary-Aware Cache Identity

Translation cache identity must remain glossary-aware.

* REQ-4.1: Cache keys must include `glossary_revision` when available.
* REQ-4.2: Cache keys should include `glossary_hash` when available and stable.
* REQ-4.3: Cache keys must continue including existing dimensions such as provider, model, source language, target language, prompt settings, source text identity, and chunk identity.
* REQ-4.4: Cached translations generated with older glossary state must not be reused for newer glossary revisions.
* REQ-4.5: Legacy cache entries without glossary identity must not be used when current glossary revision is non-zero.
* REQ-4.6: If glossary-aware cache identity is already complete, add regression tests instead of reimplementing it.
* REQ-4.7: This spec must not delete old cache entries.

### REQ-5: Compute Translation Freshness

The system must classify active and historical translation versions against the current glossary snapshot.

* REQ-5.1: Add or centralize helper logic to compare version glossary metadata with the current glossary snapshot.
* REQ-5.2: Freshness states must include:

  * `fresh`
  * `stale`
  * `legacy_unknown`
  * `unknown`
* REQ-5.3: A version is `fresh` when its glossary revision/hash matches the current glossary snapshot.
* REQ-5.4: A version is `stale` when its `glossary_revision` is lower than the current revision.
* REQ-5.5: A version is `stale` when both current and stored glossary hashes exist and differ.
* REQ-5.6: A version is `legacy_unknown` when it lacks glossary metadata.
* REQ-5.7: A version is `unknown` when the current glossary snapshot cannot be resolved.
* REQ-5.8: Stale detection must apply to active and historical versions.
* REQ-5.9: Stale detection must not automatically deactivate, replace, delete, or republish versions.

### REQ-6: Expose Stale Reasons

Freshness responses must explain why a version is stale or unknown.

* REQ-6.1: Version freshness metadata must include `glossary_freshness`.
* REQ-6.2: Version freshness metadata must include `glossary_stale: bool` for UI convenience.
* REQ-6.3: Version freshness metadata must include `glossary_stale_reason`.
* REQ-6.4: Supported stale reasons must include:

  * `fresh`
  * `legacy_missing_revision`
  * `revision_mismatch`
  * `hash_mismatch`
  * `current_snapshot_unavailable`
* REQ-6.5: Freshness metadata should include `current_glossary_revision`.
* REQ-6.6: Freshness metadata should include `current_glossary_hash` when available.
* REQ-6.7: Response changes must be additive.

### REQ-7: Compute Freshness Dynamically on Read/List

Freshness must be visible without rewriting every translation file after each glossary edit.

* REQ-7.1: Loading active translation details must compute glossary freshness where admin metadata is exposed.
* REQ-7.2: Listing historical translation versions must compute glossary freshness.
* REQ-7.3: Admin chapter translation detail responses must expose active-version freshness.
* REQ-7.4: Dynamic freshness computation must not mutate stored translation version files.
* REQ-7.5: Persisted stale flags, if used, must be treated as cached convenience values only.
* REQ-7.6: Persisted stale flag updates must be best-effort and must not corrupt translation version files.

### REQ-8: Track Glossary Snapshot on Queued Translation Jobs

Queued translation jobs must know which glossary snapshot they were scheduled with.

* REQ-8.1: A queued translation job must store `scheduled_glossary_revision` when available.
* REQ-8.2: A queued translation job should store `scheduled_glossary_hash` when available.
* REQ-8.3: The scheduled snapshot must be recorded when the translation job is created.
* REQ-8.4: Before execution starts, the worker must compare the scheduled snapshot with the current glossary snapshot.
* REQ-8.5: If a job is already running, it must save produced versions with the glossary snapshot actually used for execution.
* REQ-8.6: Completed jobs must not be retroactively changed; their versions become stale through normal stale detection.

### REQ-9: Handle Queued Job Invalidation

Queued jobs that become stale before execution must be handled deterministically.

* REQ-9.1: If the scheduled glossary snapshot still matches current glossary state, the job must run normally.
* REQ-9.2: If the scheduled snapshot is stale before execution, the job must be marked as stale-before-run or handled through an equivalent scheduler state.
* REQ-9.3: The default behavior should avoid producing new translations with known-stale glossary state.
* REQ-9.4: Supported behavior may include:

  * `cancel_and_reschedule`
  * `run_with_current_glossary`
  * `run_with_scheduled_glossary`
  * `fail_requires_admin`
* REQ-9.5: The chosen behavior must be documented.
* REQ-9.6: If checkpoint/resume semantics already exist, queued glossary invalidation must integrate with them instead of creating a parallel scheduler system.
* REQ-9.7: Queued job invalidation must preserve activity tracking and request IDs where already supported.

### REQ-10: Expose Glossary Freshness in Admin APIs

Admin-facing APIs must expose glossary freshness information.

* REQ-10.1: Version list responses must include glossary revision metadata.
* REQ-10.2: Version list responses must include computed freshness state.
* REQ-10.3: Version detail responses must include current glossary revision where available.
* REQ-10.4: Chapter translation detail responses must expose whether the active version is stale.
* REQ-10.5: Novel/admin summary responses should expose:

  * `stale_active_translation_count`
  * `legacy_unknown_translation_count`
  * `fresh_active_translation_count`
  * `current_glossary_revision`
* REQ-10.6: Strict response models must be updated if they would otherwise drop the new fields.
* REQ-10.7: Admin response changes must be additive.

### REQ-11: Provide Admin Retranslation Choices

Admins must be able to retranslate stale chapters using current glossary state.

* REQ-11.1: Add or extend an admin operation for stale-only retranslation.
* REQ-11.2: If an existing retranslation endpoint exists, prefer extending it with `stale_only=true`.
* REQ-11.3: If no suitable endpoint exists, add a focused retranslate-stale admin operation.
* REQ-11.4: The operation must support a single chapter.
* REQ-11.5: The operation must support a selected list of chapter IDs.
* REQ-11.6: The operation should support all stale active translations in a novel.
* REQ-11.7: The operation should optionally include `legacy_unknown` versions.
* REQ-11.8: The operation must use current glossary revision/hash.
* REQ-11.9: The operation must create normal translation activity/jobs through existing orchestration.
* REQ-11.10: Existing translation locks and activity tracking must be reused.

### REQ-12: Preserve Version History During Retranslation

Retranslating stale chapters must be non-destructive.

* REQ-12.1: Retranslation must save a new translation version.
* REQ-12.2: Retranslation must not overwrite old versions.
* REQ-12.3: Retranslation must not delete old versions.
* REQ-12.4: The new version must store current glossary revision metadata.
* REQ-12.5: The new version must be classified as `fresh` if saved with current glossary state.
* REQ-12.6: Old stale versions must remain available for admin comparison.

### REQ-13: Preserve Active-Version Semantics

Glossary staleness must not unexpectedly publish or unpublish content.

* REQ-13.1: Detecting that an active version is stale must not deactivate it automatically.
* REQ-13.2: Retranslation must not activate a new version by default unless existing behavior or an explicit request says so.
* REQ-13.3: The retranslation operation may support `activate: true`.
* REQ-13.4: If `activate: false`, admins must be able to review and activate the fresh version through existing version controls.
* REQ-13.5: Public reader output must continue using active-version selection.
* REQ-13.6: This spec must not add public reader stale warnings.

### REQ-14: Admin UI Visibility

Admin UI must make stale glossary translations visible and actionable.

* REQ-14.1: Translation/chapter version UI must show a stale glossary badge for stale versions.
* REQ-14.2: Version detail UI must show version glossary revision and current glossary revision when available.
* REQ-14.3: Version detail UI should show the stale reason.
* REQ-14.4: Novel translation overview should show stale active translation count when available.
* REQ-14.5: Novel translation overview should show legacy/unknown count when available.
* REQ-14.6: UI must provide a retranslate-stale action for stale active versions.
* REQ-14.7: UI should let admins choose whether to include legacy/unknown versions.
* REQ-14.8: UI should let admins choose whether fresh retranslations are activated automatically.
* REQ-14.9: Public reader UI must remain unchanged.

### REQ-15: Backward Compatibility

Existing translations and deployments must continue to work.

* REQ-15.1: Translation versions without glossary metadata must still load.
* REQ-15.2: Existing active-version selection must still work.
* REQ-15.3: Existing glossary gate behavior must remain intact.
* REQ-15.4: Existing prompt glossary injection must remain intact.
* REQ-15.5: Existing translation cache entries may remain on disk.
* REQ-15.6: Legacy cache entries must not be reused incorrectly for newer glossary revisions.
* REQ-15.7: No database migration is required if current glossary revision data is already accessible.
* REQ-15.8: Storage changes must be additive fields on translation version payloads.
* REQ-15.9: Public reader behavior must remain unchanged.

### REQ-16: Tests

Create `backend/tests/test_glossary_revision_translation_invalidation.py`.

* REQ-16.1: Test new translation versions store `glossary_revision`.
* REQ-16.2: Test new translation versions store `glossary_hash` when available.
* REQ-16.3: Test new translation versions store `glossary_term_count` when available.
* REQ-16.4: Test cache keys include `glossary_revision`.
* REQ-16.5: Test cache keys include `glossary_hash` when available.
* REQ-16.6: Test legacy cache entries are not reused for non-zero current glossary revision.
* REQ-16.7: Test active version becomes visibly stale after glossary revision increments.
* REQ-16.8: Test historical versions compute staleness independently.
* REQ-16.9: Test legacy versions without glossary metadata load as `legacy_unknown`.
* REQ-16.10: Test stale detection does not deactivate active versions.
* REQ-16.11: Test admin API version responses include freshness fields.
* REQ-16.12: Test admin summary responses include stale and legacy/unknown counts when implemented.
* REQ-16.13: Test queued translation jobs record scheduled glossary snapshot.
* REQ-16.14: Test queued jobs detect glossary changes before execution.
* REQ-16.15: Test stale queued jobs follow the documented invalidation behavior.
* REQ-16.16: Test retranslate-stale creates a new fresh version.
* REQ-16.17: Test retranslate-stale does not overwrite old versions.
* REQ-16.18: Test retranslate-stale does not activate by default unless requested.
* REQ-16.19: Test retranslate-stale can activate when explicitly requested.
* REQ-16.20: Add frontend tests for stale badges and actions if admin UI changes.
* REQ-16.21: Tests must not call live translation providers.

## Non-Goals

* This spec does not redesign glossary review workflows.
* This spec does not rebuild glossary revision counters.
* This spec does not rebuild glossary cache invalidation.
* This spec does not change glossary prompt injection rules except to record or pass through revision/hash metadata.
* This spec does not force automatic retranslation immediately after every glossary edit.
* This spec does not automatically deactivate stale active versions.
* This spec does not change public reader behavior.
* This spec does not delete old translation versions.
* This spec does not delete old cache entries.
* This spec does not implement glossary-aware manual editor linting; that belongs to `glossary-aware-editor-qa`.
