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

- [ ] 1. Preflight Glossary, Translation, and Job Flow
  - [ ] 1.1 Inspect glossary models and identify the canonical `glossary_revision` owner.
  - [ ] 1.2 Inspect glossary create/update/delete/approval flows and record where revision increments already happen.
  - [ ] 1.3 Inspect glossary prompt injection and identify any existing glossary revision/hash metadata.
  - [ ] 1.4 Inspect `TranslateStage` or equivalent translation stage for glossary metadata in translation context.
  - [ ] 1.5 Inspect translation cache-key generation.
  - [ ] 1.6 Inspect translation version save/load/list helpers in `storage/translations.py`.
  - [ ] 1.7 Inspect active-version selection behavior.
  - [ ] 1.8 Inspect translation activity/job scheduler and queued job metadata.
  - [ ] 1.9 Inspect admin/editor translation version APIs and response models.
  - [ ] 1.10 Inspect existing retranslation endpoints or activities.
  - [ ] 1.11 Inspect admin frontend translation/version UI.
  - [ ] 1.12 Inspect existing glossary, translation storage, cache, scheduler, and admin UI tests.

- [ ] 2. Define Current Glossary Snapshot Access
  - [ ] 2.1 Add or reuse a `GlossarySnapshot` helper with `revision`, `hash`, and `approved_term_count`.
  - [ ] 2.2 Resolve the snapshot from existing glossary services or model fields.
  - [ ] 2.3 Ensure the snapshot reflects the approved glossary content used by prompt injection.
  - [ ] 2.4 Do not introduce a second glossary revision system.
  - [ ] 2.5 If no stable hash exists, keep `hash=None` and proceed with revision-based freshness.
  - [ ] 2.6 If hash computation exists, verify it is deterministic.
  - [ ] 2.7 If hash computation is added or patched, exclude volatile timestamp-only fields.
  - [ ] 2.8 Add unit tests for deterministic hash ordering only if hash logic is changed.

- [ ] 3. Verify Glossary Revision Increment Paths
  - [ ] 3.1 Confirm approved term creation increments the glossary revision.
  - [ ] 3.2 Confirm approved translation changes increment the glossary revision.
  - [ ] 3.3 Confirm approved term deletion or deactivation increments the glossary revision.
  - [ ] 3.4 Confirm enforcement-level changes increment the glossary revision.
  - [ ] 3.5 Confirm aliases used by prompt injection increment the glossary revision when changed.
  - [ ] 3.6 Confirm status changes into or out of approved/enforced state increment the glossary revision.
  - [ ] 3.7 If a path is already correct, leave it unchanged.
  - [ ] 3.8 Patch only missing revision-increment paths.
  - [ ] 3.9 Add targeted tests only for paths that were missing or untested.

- [ ] 4. Store Glossary Snapshot on New Translation Versions
  - [ ] 4.1 Pass the current glossary snapshot into the translation result/version save path.
  - [ ] 4.2 Prefer passing glossary metadata from translation context if `TranslateStage` already has it.
  - [ ] 4.3 Store `glossary_revision` on new translation versions when available.
  - [ ] 4.4 Store `glossary_hash` when available.
  - [ ] 4.5 Store `glossary_term_count` when available.
  - [ ] 4.6 Treat newly created versions using the current snapshot as fresh.
  - [ ] 4.7 Do not require persisted `glossary_stale`; computed freshness is the source of truth.
  - [ ] 4.8 Preserve all existing translation version fields.
  - [ ] 4.9 Ensure loaders tolerate missing glossary fields on legacy versions.
  - [ ] 4.10 Do not rewrite old version files.

- [ ] 5. Verify Glossary-Aware Cache Identity
  - [ ] 5.1 Locate the translation cache key builder.
  - [ ] 5.2 Confirm cache keys include `glossary_revision` when available.
  - [ ] 5.3 Confirm cache keys include `glossary_hash` when available and stable.
  - [ ] 5.4 Confirm existing dimensions remain intact: provider, model, source language, target language, prompt settings, source text identity, and chunk identity.
  - [ ] 5.5 Confirm cache entries generated with older glossary state are not reused after glossary revision changes.
  - [ ] 5.6 Confirm legacy cache entries without glossary identity are not reused for non-zero current glossary revision.
  - [ ] 5.7 If cache identity is already complete, add regression tests only.
  - [ ] 5.8 Do not delete old cache entries.

- [ ] 6. Add Translation Freshness Helpers
  - [ ] 6.1 Add or centralize helper logic for comparing translation version glossary metadata with the current glossary snapshot.
  - [ ] 6.2 Return `fresh` when version revision/hash matches current snapshot.
  - [ ] 6.3 Return `stale` when version revision is lower than current revision.
  - [ ] 6.4 Return `stale` when both hashes exist and differ.
  - [ ] 6.5 Return `legacy_unknown` when version glossary metadata is missing.
  - [ ] 6.6 Return `unknown` when the current glossary snapshot cannot be resolved.
  - [ ] 6.7 Include boolean `glossary_stale` for UI convenience.
  - [ ] 6.8 Include `glossary_stale_reason`.
  - [ ] 6.9 Include `current_glossary_revision` where available.
  - [ ] 6.10 Include `current_glossary_hash` where available.
  - [ ] 6.11 Ensure the helper never changes active-version selection.

- [ ] 7. Define Stale Reason Semantics
  - [ ] 7.1 Support `fresh`.
  - [ ] 7.2 Support `legacy_missing_revision`.
  - [ ] 7.3 Support `revision_mismatch`.
  - [ ] 7.4 Support `hash_mismatch`.
  - [ ] 7.5 Support `current_snapshot_unavailable`.
  - [ ] 7.6 Ensure stale reasons are deterministic and easy to test.
  - [ ] 7.7 Ensure missing legacy metadata does not break loading.
  - [ ] 7.8 Ensure hash mismatch is only used when both current and stored hashes exist.

- [ ] 8. Compute Freshness on Storage Read/List
  - [ ] 8.1 Update admin-facing active translation loading to compute freshness.
  - [ ] 8.2 Update `list_translated_chapter_versions` or admin-specific version list helper to compute freshness for each version.
  - [ ] 8.3 Ensure historical versions are evaluated independently.
  - [ ] 8.4 Keep freshness computation dynamic and non-mutating.
  - [ ] 8.5 Treat persisted stale flags, if present, as cached convenience values only.
  - [ ] 8.6 Keep response fields additive.
  - [ ] 8.7 Avoid exposing admin-only freshness fields through public reader routes.

- [ ] 9. Add Active Translation Stale Counts
  - [ ] 9.1 Add helper logic to count active translations by freshness state.
  - [ ] 9.2 Count `fresh_active_translation_count`.
  - [ ] 9.3 Count `stale_active_translation_count`.
  - [ ] 9.4 Count `legacy_unknown_translation_count`.
  - [ ] 9.5 Include `current_glossary_revision` in summary data where available.
  - [ ] 9.6 Use existing translated chapter listing helpers.
  - [ ] 9.7 Avoid expensive full text reads when metadata is sufficient.
  - [ ] 9.8 Keep aggregate counts optional if first-pass performance or API shape makes them unsafe.

- [ ] 10. Track Glossary Snapshot on Queued Translation Jobs
  - [ ] 10.1 Add `scheduled_glossary_revision` to queued translation job metadata when available.
  - [ ] 10.2 Add `scheduled_glossary_hash` when available.
  - [ ] 10.3 Record the scheduled snapshot when the translation job is created.
  - [ ] 10.4 Before execution starts, resolve the current glossary snapshot.
  - [ ] 10.5 Compare scheduled snapshot with current snapshot.
  - [ ] 10.6 If the job is already running, let it continue with the execution snapshot.
  - [ ] 10.7 Ensure saved versions record the glossary snapshot actually used.
  - [ ] 10.8 Preserve activity tracking, request IDs, and checkpoint/resume metadata where they already exist.

- [ ] 11. Implement Queued Job Invalidation Behavior
  - [ ] 11.1 Define the default stale-before-run behavior.
  - [ ] 11.2 Prefer `cancel_and_reschedule` unless the existing scheduler has a better native pattern.
  - [ ] 11.3 Support or document allowed behaviors: `cancel_and_reschedule`, `run_with_current_glossary`, `run_with_scheduled_glossary`, and `fail_requires_admin`.
  - [ ] 11.4 Mark stale queued jobs with a clear status or metadata field.
  - [ ] 11.5 Avoid producing new translations with known-stale glossary state by default.
  - [ ] 11.6 Integrate with existing checkpoint/resume semantics.
  - [ ] 11.7 Do not create a parallel scheduler state machine.
  - [ ] 11.8 Ensure completed jobs are not retroactively changed.

- [ ] 12. Expose Freshness in Admin APIs
  - [ ] 12.1 Add glossary metadata fields to version list responses.
  - [ ] 12.2 Add computed freshness fields to version list responses.
  - [ ] 12.3 Add freshness fields to version detail responses.
  - [ ] 12.4 Add active-version freshness to chapter translation detail responses.
  - [ ] 12.5 Add stale/fresh/legacy counts to novel/admin summary responses when implemented.
  - [ ] 12.6 Update strict response models if they would drop new fields.
  - [ ] 12.7 Keep all admin response changes additive.
  - [ ] 12.8 Do not change public reader response shape.

- [ ] 13. Add or Extend Retranslate-Stale Operation
  - [ ] 13.1 Inspect existing retranslation endpoint/activity and prefer extending it with `stale_only=true`.
  - [ ] 13.2 If no suitable endpoint exists, add a focused admin retranslate-stale operation.
  - [ ] 13.3 Support a single chapter.
  - [ ] 13.4 Support a selected list of chapter IDs.
  - [ ] 13.5 Support all stale active translations in a novel.
  - [ ] 13.6 Optionally include `legacy_unknown` translations.
  - [ ] 13.7 Use current glossary revision/hash.
  - [ ] 13.8 Reuse existing translation orchestration.
  - [ ] 13.9 Reuse existing translation locks.
  - [ ] 13.10 Reuse existing activity/job tracking.
  - [ ] 13.11 Return scheduled count, stale count, legacy count, activity ID, and activation behavior.

- [ ] 14. Preserve Version History During Retranslation
  - [ ] 14.1 Save retranslations as new translation versions.
  - [ ] 14.2 Do not overwrite stale versions.
  - [ ] 14.3 Do not delete stale versions.
  - [ ] 14.4 Ensure new versions store current glossary metadata.
  - [ ] 14.5 Ensure new versions compute as `fresh`.
  - [ ] 14.6 Keep stale versions available for admin comparison.
  - [ ] 14.7 Do not mutate historical version text.

- [ ] 15. Preserve Active-Version Semantics
  - [ ] 15.1 Confirm stale detection does not deactivate active versions.
  - [ ] 15.2 Confirm stale detection does not activate historical versions.
  - [ ] 15.3 Retranslation must not activate new versions by default unless existing behavior already does or `activate=true` is explicitly requested.
  - [ ] 15.4 Support `activate: true` where compatible with existing version controls.
  - [ ] 15.5 If `activate: false`, leave fresh versions available for admin review.
  - [ ] 15.6 Confirm public reader continues using active-version selection.
  - [ ] 15.7 Do not add public reader stale warnings.

- [ ] 16. Update Admin UI
  - [ ] 16.1 Show stale glossary badge in translation/version lists.
  - [ ] 16.2 Show freshness state in version detail.
  - [ ] 16.3 Show version glossary revision versus current glossary revision.
  - [ ] 16.4 Show stale reason where available.
  - [ ] 16.5 Show stale active translation count in novel translation overview when API provides it.
  - [ ] 16.6 Show legacy/unknown count when API provides it.
  - [ ] 16.7 Add retranslate-stale action.
  - [ ] 16.8 Add option to include or exclude legacy/unknown versions where supported.
  - [ ] 16.9 Add option to activate fresh retranslations automatically where supported.
  - [ ] 16.10 Keep stale warnings out of public reader UI.

- [ ] 17. Add Backend Tests
  - [ ] 17.1 Create `backend/tests/test_glossary_revision_translation_invalidation.py`.
  - [ ] 17.2 Test new translation versions store `glossary_revision`.
  - [ ] 17.3 Test new translation versions store `glossary_hash` when available.
  - [ ] 17.4 Test new translation versions store `glossary_term_count` when available.
  - [ ] 17.5 Test active version becomes visibly stale after glossary revision increments.
  - [ ] 17.6 Test historical versions compute freshness independently.
  - [ ] 17.7 Test legacy versions without glossary metadata load as `legacy_unknown`.
  - [ ] 17.8 Test unknown current snapshot returns `unknown` without breaking load.
  - [ ] 17.9 Test stale detection does not deactivate active versions.
  - [ ] 17.10 Test admin version responses include freshness fields.
  - [ ] 17.11 Test admin summary responses include stale/fresh/legacy counts when implemented.
  - [ ] 17.12 Test retranslate-stale creates a new fresh version.
  - [ ] 17.13 Test retranslate-stale does not overwrite old versions.
  - [ ] 17.14 Test retranslate-stale does not activate by default unless requested.
  - [ ] 17.15 Test retranslate-stale can activate when explicitly requested.
  - [ ] 17.16 Ensure tests do not call live translation providers.

- [ ] 18. Add Cache and Queue Tests
  - [ ] 18.1 Test cache keys include `glossary_revision`.
  - [ ] 18.2 Test cache keys include `glossary_hash` when available.
  - [ ] 18.3 Test legacy cache entries are not reused for non-zero current glossary revision.
  - [ ] 18.4 Test queued translation jobs record scheduled glossary snapshot.
  - [ ] 18.5 Test queued jobs detect glossary changes before execution.
  - [ ] 18.6 Test stale queued jobs follow the documented invalidation behavior.
  - [ ] 18.7 Test running jobs save versions with the execution glossary snapshot.
  - [ ] 18.8 Test request IDs and activity tracking survive queued-job invalidation.

- [ ] 19. Add Frontend Tests If UI Changes
  - [ ] 19.1 Test stale badge rendering.
  - [ ] 19.2 Test stale reason tooltip or detail display.
  - [ ] 19.3 Test stale active translation count rendering.
  - [ ] 19.4 Test legacy/unknown count rendering.
  - [ ] 19.5 Test retranslate-stale action calls the correct API.
  - [ ] 19.6 Test include-legacy option is respected.
  - [ ] 19.7 Test activate-on-completion option is respected.
  - [ ] 19.8 Test fresh status appears after data refresh.

- [ ] 20. Backward Compatibility Checks
  - [ ] 20.1 Confirm translation versions without glossary metadata still load.
  - [ ] 20.2 Confirm existing active-version selection still works.
  - [ ] 20.3 Confirm existing glossary gate behavior remains intact.
  - [ ] 20.4 Confirm existing prompt glossary injection remains intact.
  - [ ] 20.5 Confirm existing cache entries may remain on disk.
  - [ ] 20.6 Confirm old cache entries are not reused incorrectly.
  - [ ] 20.7 Confirm no DB migration is needed if glossary revision data is already accessible.
  - [ ] 20.8 Confirm storage changes are additive fields only.
  - [ ] 20.9 Confirm public reader behavior is unchanged.

- [ ] 21. Run Verification
  - [ ] 21.1 Run focused glossary revision invalidation tests.
  - [ ] 21.2 Run existing glossary tests.
  - [ ] 21.3 Run existing translation storage tests.
  - [ ] 21.4 Run existing translation cache tests.
  - [ ] 21.5 Run existing translation scheduler/job tests.
  - [ ] 21.6 Run admin API tests.
  - [ ] 21.7 Run frontend/admin tests if UI changed.
  - [ ] 21.8 Run `ruff check` on changed backend source and test files.
  - [ ] 21.9 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 21.10 Fix test, lint, and type failures caused by this work.

- [ ] 22. Final Acceptance Review
  - [ ] 22.1 Verify new translation versions store glossary revision metadata.
  - [ ] 22.2 Verify new translation versions store glossary hash when available.
  - [ ] 22.3 Verify active and historical versions classify as `fresh`, `stale`, `legacy_unknown`, or `unknown`.
  - [ ] 22.4 Verify glossary changes make older translations visibly stale without deactivating them.
  - [ ] 22.5 Verify queued translation jobs detect stale scheduled glossary snapshots before execution.
  - [ ] 22.6 Verify stale queued jobs follow the documented invalidation behavior.
  - [ ] 22.7 Verify admin APIs expose glossary freshness fields additively.
  - [ ] 22.8 Verify admin summaries expose stale and legacy/unknown counts when implemented.
  - [ ] 22.9 Verify admins can retranslate stale chapters and produce new fresh versions.
  - [ ] 22.10 Verify retranslation does not overwrite old versions.
  - [ ] 22.11 Verify retranslation does not activate new versions by default unless requested.
  - [ ] 22.12 Verify legacy versions without glossary metadata remain loadable.
  - [ ] 22.13 Verify existing glossary gate, prompt injection, cache identity, and active-version behavior remain intact.
  - [ ] 22.14 Verify public reader behavior is unchanged.
  - [ ] 22.15 Verify focused backend and admin UI tests pass.

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

- [ ] New translation versions store glossary revision metadata.
- [ ] New translation versions store glossary hash when available.
- [ ] Current glossary snapshot is resolved from existing glossary state.
- [ ] Glossary revision increment paths are verified and only missing paths are patched.
- [ ] Cache identity remains glossary-aware.
- [ ] Active and historical versions compute freshness dynamically.
- [ ] Freshness states include `fresh`, `stale`, `legacy_unknown`, and `unknown`.
- [ ] Stale reasons are exposed for admin diagnosis.
- [ ] Queued translation jobs record scheduled glossary snapshots.
- [ ] Queued jobs detect stale glossary snapshots before execution.
- [ ] Admin APIs expose freshness fields additively.
- [ ] Admin UI shows stale badges, stale counts, stale reasons, and retranslation controls.
- [ ] Retranslate-stale creates new fresh versions without overwriting old versions.
- [ ] Stale detection does not deactivate active versions.
- [ ] Public reader behavior is unchanged.
- [ ] Legacy translation versions without glossary metadata remain loadable.
- [ ] Existing glossary gate, prompt injection, cache identity, provider routing, and active-version behavior remain intact.
- [ ] Focused backend, queue, cache, admin API, and admin UI tests pass.