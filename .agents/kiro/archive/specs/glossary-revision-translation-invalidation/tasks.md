# Tasks: Glossary Revision Translation Invalidation

## Overview

Implement glossary revision translation invalidation by making glossary freshness visible and actionable for translation versions, queued translation jobs, admin APIs, and admin UI.

This work assumes glossary-first onboarding, glossary review gating, prompt glossary injection, revision counters, and cache invalidation may already exist. Do not rebuild those systems. Verify them, patch missing paths only where necessary, and focus on stale translated-version detection, queued job invalidation, and admin retranslation choices.

Scope boundaries:

- Do not redesign glossary review workflows.
- Do not rebuild glossary revision counters if they already exist.
- Do not rebuild glossary cache invalidation if already complete.
- Do not change public reader behavior.
- Do not automatically deactivate stale active versions.
- Do not delete old translation versions.
- Do not delete old cache entries.
- Do not implement glossary-aware manual editor linting here.

## Task List

- [x] 1. Preflight Glossary, Translation, and Job Flow
  - [x] 1.1 Inspect glossary models and identify the canonical `glossary_revision` owner.
  - [x] 1.2 Inspect glossary create/update/delete/approval flows and record where revision increments already happen.
  - [x] 1.3 Inspect glossary prompt injection and identify any existing glossary revision/hash metadata.
  - [x] 1.4 Inspect `TranslateStage` or equivalent translation stage for glossary metadata in translation context.
  - [x] 1.5 Inspect translation cache-key generation.
  - [x] 1.6 Inspect translation version save/load/list helpers in `storage/translations.py`.
  - [x] 1.7 Inspect active-version selection behavior.
  - [x] 1.8 Inspect translation activity/job scheduler and queued job metadata.
  - [x] 1.9 Inspect admin/editor translation version APIs and response models.
  - [x] 1.10 Inspect existing retranslation endpoints or activities.
  - [x] 1.11 Inspect admin frontend translation/version UI.
  - [x] 1.12 Inspect existing glossary, translation storage, cache, scheduler, and admin UI tests.

- [x] 2. Define Current Glossary Snapshot Access
  - [x] 2.1 Add or reuse a `GlossarySnapshot` helper with `revision`, `hash`, and `approved_term_count`.
  - [x] 2.2 Resolve the snapshot from existing glossary services or model fields.
  - [x] 2.3 Ensure the snapshot reflects the approved glossary content used by prompt injection.
  - [x] 2.4 Do not introduce a second glossary revision system.
  - [x] 2.5 If no stable hash exists, keep `hash=None` and proceed with revision-based freshness.
  - [x] 2.6 If hash computation exists, verify it is deterministic.
  - [x] 2.7 If hash computation is added or patched, exclude volatile timestamp-only fields.
  - [x] 2.8 Add unit tests for deterministic hash ordering only if hash logic is changed.

- [x] 3. Verify Glossary Revision Increment Paths
  - [x] 3.1 Confirm approved term creation increments the glossary revision.
  - [x] 3.2 Confirm approved translation changes increment the glossary revision.
  - [x] 3.3 Confirm approved term deletion or deactivation increments the glossary revision.
  - [x] 3.4 Confirm enforcement-level changes increment the glossary revision.
  - [x] 3.5 Confirm aliases used by prompt injection increment the glossary revision when changed.
  - [x] 3.6 Confirm status changes into or out of approved/enforced state increment the glossary revision.
  - [x] 3.7 If a path is already correct, leave it unchanged.
  - [x] 3.8 Patch only missing revision-increment paths.
  - [x] 3.9 Add targeted tests only for paths that were missing or untested.

- [x] 4. Store Glossary Snapshot on New Translation Versions
  - [x] 4.1 Pass the current glossary snapshot into the translation result/version save path.
  - [x] 4.2 Prefer passing glossary metadata from translation context if `TranslateStage` already has it.
  - [x] 4.3 Store `glossary_revision` on new translation versions when available.
  - [x] 4.4 Store `glossary_hash` when available.
  - [x] 4.5 Store `glossary_term_count` when available.
  - [x] 4.6 Treat newly created versions using the current snapshot as fresh.
  - [x] 4.7 Do not require persisted `glossary_stale`; computed freshness is the source of truth.
  - [x] 4.8 Preserve all existing translation version fields.
  - [x] 4.9 Ensure loaders tolerate missing glossary fields on legacy versions.
  - [x] 4.10 Do not rewrite old version files.

- [x] 5. Verify Glossary-Aware Cache Identity
  - [x] 5.1 Locate the translation cache key builder.
  - [x] 5.2 Confirm cache keys include `glossary_revision` when available.
  - [x] 5.3 Confirm cache keys include `glossary_hash` when available and stable.
  - [x] 5.4 Confirm existing dimensions remain intact: provider, model, source language, target language, prompt settings, source text identity, and chunk identity.
  - [x] 5.5 Confirm cache entries generated with older glossary state are not reused after glossary revision changes.
  - [x] 5.6 Confirm legacy cache entries without glossary identity are not reused for non-zero current glossary revision.
  - [x] 5.7 If cache identity is already complete, add regression tests only.
  - [x] 5.8 Do not delete old cache entries.

- [x] 6. Add Translation Freshness Helpers
  - [x] 6.1 Add or centralize helper logic for comparing translation version glossary metadata with the current glossary snapshot.
  - [x] 6.2 Return `fresh` when version revision/hash matches current snapshot.
  - [x] 6.3 Return `stale` when version revision is lower than current revision.
  - [x] 6.4 Return `stale` when both hashes exist and differ.
  - [x] 6.5 Return `legacy_unknown` when version glossary metadata is missing.
  - [x] 6.6 Return `unknown` when the current glossary snapshot cannot be resolved.
  - [x] 6.7 Include boolean `glossary_stale` for UI convenience.
  - [x] 6.8 Include `glossary_stale_reason`.
  - [x] 6.9 Include `current_glossary_revision` where available.
  - [x] 6.10 Include `current_glossary_hash` where available.
  - [x] 6.11 Ensure the helper never changes active-version selection.

- [x] 7. Define Stale Reason Semantics
  - [x] 7.1 Support `fresh`.
  - [x] 7.2 Support `legacy_missing_revision`.
  - [x] 7.3 Support `revision_mismatch`.
  - [x] 7.4 Support `hash_mismatch`.
  - [x] 7.5 Support `current_snapshot_unavailable`.
  - [x] 7.6 Ensure stale reasons are deterministic and easy to test.
  - [x] 7.7 Ensure missing legacy metadata does not break loading.
  - [x] 7.8 Ensure hash mismatch is only used when both current and stored hashes exist.

- [x] 8. Compute Freshness on Storage Read/List
  - [x] 8.1 Update admin-facing active translation loading to compute freshness.
  - [x] 8.2 Update `list_translated_chapter_versions` or admin-specific version list helper to compute freshness for each version.
  - [x] 8.3 Ensure historical versions are evaluated independently.
  - [x] 8.4 Keep freshness computation dynamic and non-mutating.
  - [x] 8.5 Treat persisted stale flags, if present, as cached convenience values only.
  - [x] 8.6 Keep response fields additive.
  - [x] 8.7 Avoid exposing admin-only freshness fields through public reader routes.

- [x] 9. Add Active Translation Stale Counts
  - [x] 9.1 Add helper logic to count active translations by freshness state.
  - [x] 9.2 Count `fresh_active_translation_count`.
  - [x] 9.3 Count `stale_active_translation_count`.
  - [x] 9.4 Count `legacy_unknown_translation_count`.
  - [x] 9.5 Include `current_glossary_revision` in summary data where available.
  - [x] 9.6 Use existing translated chapter listing helpers.
  - [x] 9.7 Avoid expensive full text reads when metadata is sufficient.
  - [x] 9.8 Keep aggregate counts optional if first-pass performance or API shape makes them unsafe.

- [x] 10. Track Glossary Snapshot on Queued Translation Jobs
  - [x] 10.1 Add `scheduled_glossary_revision` to queued translation job metadata when available.
  - [x] 10.2 Add `scheduled_glossary_hash` when available.
  - [x] 10.3 Record the scheduled snapshot when the translation job is created.
  - [x] 10.4 Before execution starts, resolve the current glossary snapshot.
  - [x] 10.5 Compare scheduled snapshot with current snapshot.
  - [x] 10.6 If the job is already running, let it continue with the execution snapshot.
  - [x] 10.7 Ensure saved versions record the glossary snapshot actually used.
  - [x] 10.8 Preserve activity tracking, request IDs, and checkpoint/resume metadata where they already exist.

- [x] 11. Implement Queued Job Invalidation Behavior
  - [x] 11.1 Define the default stale-before-run behavior.
  - [x] 11.2 Prefer `cancel_and_reschedule` unless the existing scheduler has a better native pattern.
  - [x] 11.3 Support or document allowed behaviors: `cancel_and_reschedule`, `run_with_current_glossary`, `run_with_scheduled_glossary`, and `fail_requires_admin`.
  - [x] 11.4 Mark stale queued jobs with a clear status or metadata field.
  - [x] 11.5 Avoid producing new translations with known-stale glossary state by default.
  - [x] 11.6 Integrate with existing checkpoint/resume semantics.
  - [x] 11.7 Do not create a parallel scheduler state machine.
  - [x] 11.8 Ensure completed jobs are not retroactively changed.

- [x] 12. Expose Freshness in Admin APIs
  - [x] 12.1 Add glossary metadata fields to version list responses.
  - [x] 12.2 Add computed freshness fields to version list responses.
  - [x] 12.3 Add freshness fields to version detail responses.
  - [x] 12.4 Add active-version freshness to chapter translation detail responses.
  - [x] 12.5 Add stale/fresh/legacy counts to novel/admin summary responses when implemented.
  - [x] 12.6 Update strict response models if they would drop new fields.
  - [x] 12.7 Keep all admin response changes additive.
  - [x] 12.8 Do not change public reader response shape.

- [x] 13. Add or Extend Retranslate-Stale Operation
  - [x] 13.1 Inspect existing retranslation endpoint/activity and prefer extending it with `stale_only=true`.
  - [x] 13.2 If no suitable endpoint exists, add a focused admin retranslate-stale operation.
  - [x] 13.3 Support a single chapter.
  - [x] 13.4 Support a selected list of chapter IDs.
  - [x] 13.5 Support all stale active translations in a novel.
  - [x] 13.6 Optionally include `legacy_unknown` translations.
  - [x] 13.7 Use current glossary revision/hash.
  - [x] 13.8 Reuse existing translation orchestration.
  - [x] 13.9 Reuse existing translation locks.
  - [x] 13.10 Reuse existing activity/job tracking.
  - [x] 13.11 Return scheduled count, stale count, legacy count, activity ID, and activation behavior.

- [x] 14. Preserve Version History During Retranslation
  - [x] 14.1 Save retranslations as new translation versions.
  - [x] 14.2 Do not overwrite stale versions.
  - [x] 14.3 Do not delete stale versions.
  - [x] 14.4 Ensure new versions store current glossary metadata.
  - [x] 14.5 Ensure new versions compute as `fresh`.
  - [x] 14.6 Keep stale versions available for admin comparison.
  - [x] 14.7 Do not mutate historical version text.

- [x] 15. Preserve Active-Version Semantics
  - [x] 15.1 Confirm stale detection does not deactivate active versions.
  - [x] 15.2 Confirm stale detection does not activate historical versions.
  - [x] 15.3 Retranslation must not activate new versions by default unless existing behavior already does or `activate=true` is explicitly requested.
  - [x] 15.4 Support `activate: true` where compatible with existing version controls.
  - [x] 15.5 If `activate: false`, leave fresh versions available for admin review.
  - [x] 15.6 Confirm public reader continues using active-version selection.
  - [x] 15.7 Do not add public reader stale warnings.

- [x] 16. Update Admin UI
  - [x] 16.1 Show stale glossary badge in translation/version lists.
  - [x] 16.2 Show freshness state in version detail.
  - [x] 16.3 Show version glossary revision versus current glossary revision.
  - [x] 16.4 Show stale reason where available.
  - [x] 16.5 Show stale active translation count in novel translation overview when API provides it.
  - [x] 16.6 Show legacy/unknown count when API provides it.
  - [x] 16.7 Add retranslate-stale action.
  - [x] 16.8 Add option to include or exclude legacy/unknown versions where supported.
  - [x] 16.9 Add option to activate fresh retranslations automatically where supported.
  - [x] 16.10 Keep stale warnings out of public reader UI.

- [x] 17. Add Backend Tests
  - [x] 17.1 Create `backend/tests/test_glossary_revision_translation_invalidation.py`.
  - [x] 17.2 Test new translation versions store `glossary_revision`.
  - [x] 17.3 Test new translation versions store `glossary_hash` when available.
  - [x] 17.4 Test new translation versions store `glossary_term_count` when available.
  - [x] 17.5 Test active version becomes visibly stale after glossary revision increments.
  - [x] 17.6 Test historical versions compute freshness independently.
  - [x] 17.7 Test legacy versions without glossary metadata load as `legacy_unknown`.
  - [x] 17.8 Test unknown current snapshot returns `unknown` without breaking load.
  - [x] 17.9 Test stale detection does not deactivate active versions.
  - [x] 17.10 Test admin version responses include freshness fields.
  - [x] 17.11 Test admin summary responses include stale/fresh/legacy counts when implemented.
  - [x] 17.12 Test retranslate-stale creates a new fresh version.
  - [x] 17.13 Test retranslate-stale does not overwrite old versions.
  - [x] 17.14 Test retranslate-stale does not activate by default unless requested.
  - [x] 17.15 Test retranslate-stale can activate when explicitly requested.
  - [x] 17.16 Ensure tests do not call live translation providers.

- [x] 18. Add Cache and Queue Tests
  - [x] 18.1 Test cache keys include `glossary_revision`.
  - [x] 18.2 Test cache keys include `glossary_hash` when available.
  - [x] 18.3 Test legacy cache entries are not reused for non-zero current glossary revision.
  - [x] 18.4 Test queued translation jobs record scheduled glossary snapshot.
  - [x] 18.5 Test queued jobs detect glossary changes before execution.
  - [x] 18.6 Test stale queued jobs follow the documented invalidation behavior.
  - [x] 18.7 Test running jobs save versions with the execution glossary snapshot.
  - [x] 18.8 Test request IDs and activity tracking survive queued-job invalidation.

- [x] 19. Add Frontend Tests If UI Changes
  - [x] 19.1 Test stale badge rendering.
  - [x] 19.2 Test stale reason tooltip or detail display.
  - [x] 19.3 Test stale active translation count rendering.
  - [x] 19.4 Test legacy/unknown count rendering.
  - [x] 19.5 Test retranslate-stale action calls the correct API.
  - [x] 19.6 Test include-legacy option is respected.
  - [x] 19.7 Test activate-on-completion option is respected.
  - [x] 19.8 Test fresh status appears after data refresh.

- [x] 20. Backward Compatibility Checks
  - [x] 20.1 Confirm translation versions without glossary metadata still load.
  - [x] 20.2 Confirm existing active-version selection still works.
  - [x] 20.3 Confirm existing glossary gate behavior remains intact.
  - [x] 20.4 Confirm existing prompt glossary injection remains intact.
  - [x] 20.5 Confirm existing cache entries may remain on disk.
  - [x] 20.6 Confirm old cache entries are not reused incorrectly.
  - [x] 20.7 Confirm no DB migration is needed if glossary revision data is already accessible.
  - [x] 20.8 Confirm storage changes are additive fields only.
  - [x] 20.9 Confirm public reader behavior is unchanged.

- [x] 21. Run Verification
  - [x] 21.1 Run focused glossary revision invalidation tests.
  - [x] 21.2 Run existing glossary tests.
  - [x] 21.3 Run existing translation storage tests.
  - [x] 21.4 Run existing translation cache tests.
  - [x] 21.5 Run existing translation scheduler/job tests.
  - [x] 21.6 Run admin API tests.
  - [x] 21.7 Run frontend/admin tests if UI changed.
  - [x] 21.8 Run `ruff check` on changed backend source and test files.
  - [x] 21.9 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 21.10 Fix test, lint, and type failures caused by this work.

- [x] 22. Final Acceptance Review
  - [x] 22.1 Verify new translation versions store glossary revision metadata.
  - [x] 22.2 Verify new translation versions store glossary hash when available.
  - [x] 22.3 Verify active and historical versions classify as `fresh`, `stale`, `legacy_unknown`, or `unknown`.
  - [x] 22.4 Verify glossary changes make older translations visibly stale without deactivating them.
  - [x] 22.5 Verify queued translation jobs detect stale scheduled glossary snapshots before execution.
  - [x] 22.6 Verify stale queued jobs follow the documented invalidation behavior.
  - [x] 22.7 Verify admin APIs expose glossary freshness fields additively.
  - [x] 22.8 Verify admin summaries expose stale and legacy/unknown counts when implemented.
  - [x] 22.9 Verify admins can retranslate stale chapters and produce new fresh versions.
  - [x] 22.10 Verify retranslation does not overwrite old versions.
  - [x] 22.11 Verify retranslation does not activate new versions by default unless requested.
  - [x] 22.12 Verify legacy versions without glossary metadata remain loadable.
  - [x] 22.13 Verify existing glossary gate, prompt injection, cache identity, and active-version behavior remain intact.
  - [x] 22.14 Verify public reader behavior is unchanged.
  - [x] 22.15 Verify focused backend and admin UI tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Store Glossary Snapshot on New Translation Versions | 1, 4, 17, 20, 22 |
| REQ-2 Resolve Current Glossary Snapshot | 1, 2, 6, 17 |
| REQ-3 Verify Glossary Revision Behavior | 1, 3, 17, 20 |
| REQ-4 Preserve Glossary-Aware Cache Identity | 5, 18, 20, 22 |
| REQ-5 Compute Translation Freshness | 6, 8, 17, 22 |
| REQ-6 Expose Stale Reasons | 6, 7, 12, 17 |
| REQ-7 Compute Freshness Dynamically on Read/List | 8, 12, 17, 20 |
| REQ-8 Track Glossary Snapshot on Queued Jobs | 10, 18, 22 |
| REQ-9 Handle Queued Job Invalidation | 11, 18, 22 |
| REQ-10 Expose Freshness in Admin APIs | 9, 12, 17, 22 |
| REQ-11 Provide Admin Retranslation Choices | 13, 17, 22 |
| REQ-12 Preserve Version History During Retranslation | 14, 17, 22 |
| REQ-13 Preserve Active-Version Semantics | 15, 17, 20, 22 |
| REQ-14 Admin UI Visibility | 16, 19, 22 |
| REQ-15 Backward Compatibility | 20, 21, 22 |
| REQ-16 Tests | 17, 18, 19, 21 |

## Definition of Done

- [x] New translation versions store glossary revision metadata.
- [x] New translation versions store glossary hash when available.
- [x] Current glossary snapshot is resolved from existing glossary state.
- [x] Glossary revision increment paths are verified and only missing paths are patched.
- [x] Cache identity remains glossary-aware.
- [x] Active and historical versions compute freshness dynamically.
- [x] Freshness states include `fresh`, `stale`, `legacy_unknown`, and `unknown`.
- [x] Stale reasons are exposed for admin diagnosis.
- [x] Queued translation jobs record scheduled glossary snapshots.
- [x] Queued jobs detect stale glossary snapshots before execution.
- [x] Admin APIs expose freshness fields additively.
- [x] Admin UI shows stale badges, stale counts, stale reasons, and retranslation controls.
- [x] Retranslate-stale creates new fresh versions without overwriting old versions.
- [x] Stale detection does not deactivate active versions.
- [x] Public reader behavior is unchanged.
- [x] Legacy translation versions without glossary metadata remain loadable.
- [x] Existing glossary gate, prompt injection, cache identity, provider routing, and active-version behavior remain intact.
- [x] Focused backend, queue, cache, admin API, and admin UI tests pass.