# Tasks: Translation Scheduler Observability

## Overview

Implement translation scheduler observability by recording compact provider/model selection decisions, exposing quota/cooldown/job health in admin APIs, and rendering scheduler state in admin dashboards.

This work is instrumentation-only. It must reuse existing checkpoint/resume, request IDs, chapter parallelization, exact memory tracking, quota/cooldown state, and activity/job metadata patterns.

Scope boundaries:

- Do not change scheduler policy.
- Do not change model priority/order.
- Do not change provider routing.
- Do not change quota or cooldown behavior.
- Do not change retry behavior.
- Do not change checkpoint/resume semantics.
- Do not change chapter parallelization behavior.
- Do not change memory guard behavior.
- Do not change translation output.
- Do not expose scheduler health publicly.
- Do not store prompts, source text, translated text, secrets, or raw provider responses in scheduler metadata.

## Task List

- [ ] 1. Preflight Scheduler and Job Flow
  - [ ] 1.1 Inspect `TranslationScheduler` or equivalent provider/model selection flow.
  - [ ] 1.2 Inspect provider/model config objects and available safe fields.
  - [ ] 1.3 Inspect runtime scheduler state fields: RPM/RPD counters, cooldown, exhausted state, failed timestamp, status, and last error code.
  - [ ] 1.4 Inspect quota and cooldown update paths.
  - [ ] 1.5 Inspect request ID propagation through translation jobs.
  - [ ] 1.6 Inspect checkpoint/resume metadata and execution flow.
  - [ ] 1.7 Inspect chapter parallelization worker flow and per-chapter attempt handling.
  - [ ] 1.8 Inspect exact memory tracking and memory guard state.
  - [ ] 1.9 Inspect translation orchestration path where selected provider/model is attached to translation metadata.
  - [ ] 1.10 Inspect translation activity/job metadata aggregation.
  - [ ] 1.11 Inspect admin translation/activity/job dashboard APIs and response models.
  - [ ] 1.12 Inspect admin frontend translation/activity/provider health UI.
  - [ ] 1.13 Inspect existing scheduler, translation orchestration, activity, checkpoint, and frontend tests.

- [ ] 2. Define Scheduler Decision Record Shape
  - [ ] 2.1 Add `SchedulerDecision` dataclass or equivalent serializable structure.
  - [ ] 2.2 Add `SchedulerCandidateDecision` dataclass or equivalent serializable structure.
  - [ ] 2.3 Include selected provider/model.
  - [ ] 2.4 Include `selected: null` support for no-capacity decisions.
  - [ ] 2.5 Include scheduler policy.
  - [ ] 2.6 Include fallback flag.
  - [ ] 2.7 Include selection timestamp.
  - [ ] 2.8 Include bounded candidate list.
  - [ ] 2.9 Include candidate count total.
  - [ ] 2.10 Include candidate count recorded.
  - [ ] 2.11 Include candidate list truncated flag.
  - [ ] 2.12 Ensure the structure is JSON-serializable.
  - [ ] 2.13 Exclude secrets, prompts, source text, translated text, and raw provider responses.

- [ ] 3. Add Identity Fields to Decision Records
  - [ ] 3.1 Include `request_id` when available.
  - [ ] 3.2 Include `activity_id` when available.
  - [ ] 3.3 Include `job_id` when available.
  - [ ] 3.4 Include `chapter_id` when available.
  - [ ] 3.5 Include attempt number when available.
  - [ ] 3.6 Include checkpoint ID or checkpoint reference when available.
  - [ ] 3.7 Include parallel slot when available.
  - [ ] 3.8 Ensure missing identity fields do not break translation execution.
  - [ ] 3.9 Reuse existing request ID propagation instead of creating a separate correlation system.

- [ ] 4. Define Skip and Failure Reason Codes
  - [ ] 4.1 Add stable reason constants or enum values.
  - [ ] 4.2 Add `cooldown_active`.
  - [ ] 4.3 Add `quota_exhausted`.
  - [ ] 4.4 Add `rpm_limited`.
  - [ ] 4.5 Add `rpd_limited`.
  - [ ] 4.6 Add `memory_pressure`.
  - [ ] 4.7 Add `parallelism_limit`.
  - [ ] 4.8 Add `disabled`.
  - [ ] 4.9 Add `previously_attempted`.
  - [ ] 4.10 Add `unhealthy`.
  - [ ] 4.11 Add `checkpoint_blocked`.
  - [ ] 4.12 Add `no_capacity`.
  - [ ] 4.13 Add `unknown`.
  - [ ] 4.14 Ensure reason codes are machine-readable and do not contain raw exception text.

- [ ] 5. Add Scheduler Decision Recorder
  - [ ] 5.1 Add a decision recorder around the existing selection flow.
  - [ ] 5.2 Prefer a side-channel recorder if changing scheduler return type is invasive.
  - [ ] 5.3 Ensure the recorder observes only and never influences selection.
  - [ ] 5.4 Record the selected candidate.
  - [ ] 5.5 Record skipped candidates.
  - [ ] 5.6 Record no-capacity decisions.
  - [ ] 5.7 Preserve existing selection order exactly.
  - [ ] 5.8 Preserve existing scheduler errors exactly.

- [ ] 6. Instrument Candidate Evaluation
  - [ ] 6.1 Record candidate provider and model in evaluation order.
  - [ ] 6.2 Record candidate runtime status when available.
  - [ ] 6.3 Record `selected=true` for the chosen candidate.
  - [ ] 6.4 Record `selected=false` for skipped candidates.
  - [ ] 6.5 Record skip reason for skipped candidates.
  - [ ] 6.6 Record `cooldown_until` when available.
  - [ ] 6.7 Record `exhausted_until` when available.
  - [ ] 6.8 Record `failed_at` when available.
  - [ ] 6.9 Record safe `last_error_code` when available.
  - [ ] 6.10 Record request counters where already available.
  - [ ] 6.11 Bound candidate list with `MAX_SCHEDULER_DECISION_CANDIDATES`.
  - [ ] 6.12 Record truncation metadata when candidates exceed the bound.

- [ ] 7. Record No-Capacity Decisions
  - [ ] 7.1 When no model is available, create a decision with `selected=null`.
  - [ ] 7.2 Set `failure_reason="no_capacity"`.
  - [ ] 7.3 Include skipped candidate summary when available.
  - [ ] 7.4 Preserve existing no-capacity error behavior.
  - [ ] 7.5 Ensure no-capacity observability does not trigger independent retry or rerouting.

- [ ] 8. Integrate Checkpoint and Resume Observability
  - [ ] 8.1 Include checkpoint reference in decision records when available.
  - [ ] 8.2 Preserve prior scheduler decision metadata when a resumed chapter already has it.
  - [ ] 8.3 Create a new decision record when resume triggers a new provider/model selection.
  - [ ] 8.4 Count resumed work in activity summary when existing metadata supports it.
  - [ ] 8.5 Count checkpoint-blocked states with `checkpoint_blocked`.
  - [ ] 8.6 Ensure observability does not change checkpoint write timing.
  - [ ] 8.7 Ensure observability does not change resume eligibility.

- [ ] 9. Integrate Chapter Parallelization Safely
  - [ ] 9.1 Tie every decision record to a stable chapter ID when available.
  - [ ] 9.2 Include attempt number, request ID, or job ID to distinguish duplicate chapter attempts.
  - [ ] 9.3 Ensure parallel workers do not overwrite each other’s scheduler metadata.
  - [ ] 9.4 Ensure activity summary aggregation is concurrency-safe.
  - [ ] 9.5 Aggregate by decision/attempt rather than lossy chapter-only keys where retries/resumes exist.
  - [ ] 9.6 Preserve existing chapter parallelization limits and behavior.

- [ ] 10. Integrate Exact Memory Observability
  - [ ] 10.1 Reuse existing exact memory tracking if available.
  - [ ] 10.2 Add `exact_memory_bytes` to decision metadata when available.
  - [ ] 10.3 Add `memory_limit_bytes` when available.
  - [ ] 10.4 Add `memory_pressure` when available.
  - [ ] 10.5 Count memory pressure events in activity summary.
  - [ ] 10.6 Count memory-blocked events in activity summary when available.
  - [ ] 10.7 Track peak exact memory in activity summary when available.
  - [ ] 10.8 Do not add a second memory accounting system.
  - [ ] 10.9 Do not change memory guard behavior.

- [ ] 11. Attach Decision to Per-Chapter Translation Metadata
  - [ ] 11.1 Pass scheduler decision from scheduler to translation orchestration.
  - [ ] 11.2 Store decision in per-chapter translation result metadata.
  - [ ] 11.3 Store decision in translation version metadata where provider/model metadata is already stored.
  - [ ] 11.4 Keep scheduler metadata compact.
  - [ ] 11.5 Ensure metadata is additive.
  - [ ] 11.6 Ensure translation versions without scheduler metadata still load.
  - [ ] 11.7 Ensure scheduler metadata does not duplicate prompt, source, or translated text.

- [ ] 12. Add Activity Scheduler Summary
  - [ ] 12.1 Define `scheduler_summary` activity metadata shape.
  - [ ] 12.2 Count `chapters_with_decisions`.
  - [ ] 12.3 Count fallback selections.
  - [ ] 12.4 Count no-capacity decisions.
  - [ ] 12.5 Aggregate skip reason counts.
  - [ ] 12.6 Aggregate selected model counts.
  - [ ] 12.7 Aggregate provider counts.
  - [ ] 12.8 Aggregate quota/cooldown counts.
  - [ ] 12.9 Aggregate checkpoint/resume counts when available.
  - [ ] 12.10 Aggregate memory pressure and memory blocked counts when available.
  - [ ] 12.11 Persist summary in translation activity metadata.
  - [ ] 12.12 Ensure summary updates are safe under parallel chapter execution.

- [ ] 13. Add Scheduler Health Admin API
  - [ ] 13.1 Prefer extending an existing admin operations/runtime-state route.
  - [ ] 13.2 Add a narrow admin-only scheduler-health route only if no suitable route exists.
  - [ ] 13.3 Expose provider and model.
  - [ ] 13.4 Expose runtime status.
  - [ ] 13.5 Expose RPM limit and requests this minute when available.
  - [ ] 13.6 Expose RPD limit and requests today when available.
  - [ ] 13.7 Expose cooldown timestamp when available.
  - [ ] 13.8 Expose exhausted timestamp when available.
  - [ ] 13.9 Expose failed timestamp when available.
  - [ ] 13.10 Expose safe last error code when available.
  - [ ] 13.11 Include aggregate health summary counts.
  - [ ] 13.12 Redact provider secrets and account identifiers.
  - [ ] 13.13 Update strict response models if needed.
  - [ ] 13.14 Confirm public APIs do not expose scheduler health.

- [ ] 14. Expose Decisions in Admin Translation APIs
  - [ ] 14.1 Add scheduler summary to translation activity detail response.
  - [ ] 14.2 Add scheduler summary to job dashboard response where applicable.
  - [ ] 14.3 Add selected provider/model to chapter/version detail response.
  - [ ] 14.4 Add fallback state to chapter/version detail response.
  - [ ] 14.5 Add compact skipped candidate summary to chapter/version detail response.
  - [ ] 14.6 Add request ID/job ID/checkpoint ID where useful.
  - [ ] 14.7 Add aggregate fallback, cooldown, quota, memory, checkpoint, and no-capacity counts to novel translation summary when practical.
  - [ ] 14.8 Keep response changes additive.
  - [ ] 14.9 Update strict response models if they would drop new fields.
  - [ ] 14.10 Show legacy records as `null`, omitted, or `not_available` according to existing API style.

- [ ] 15. Update Admin UI
  - [ ] 15.1 Show selected model counts in translation activity dashboard.
  - [ ] 15.2 Show provider counts.
  - [ ] 15.3 Show fallback count.
  - [ ] 15.4 Show no-capacity count.
  - [ ] 15.5 Show skip reason counts.
  - [ ] 15.6 Show cooldown and quota counts.
  - [ ] 15.7 Show memory pressure and memory blocked counts when available.
  - [ ] 15.8 Show checkpoint/resume counts when available.
  - [ ] 15.9 Show selected provider/model in chapter/version UI.
  - [ ] 15.10 Show fallback state and skipped candidate reasons in chapter/version UI.
  - [ ] 15.11 Show request ID/job ID/checkpoint ID where useful.
  - [ ] 15.12 Show provider/model health states.
  - [ ] 15.13 Confirm secrets and account identifiers are not rendered.

- [ ] 16. Safety and Size Review
  - [ ] 16.1 Confirm candidate decision list is bounded.
  - [ ] 16.2 Confirm truncation metadata is present when needed.
  - [ ] 16.3 Confirm reason codes are used instead of long raw errors.
  - [ ] 16.4 Confirm provider secrets are redacted.
  - [ ] 16.5 Confirm account identifiers are redacted.
  - [ ] 16.6 Confirm prompts are not stored.
  - [ ] 16.7 Confirm source text is not stored.
  - [ ] 16.8 Confirm translated text is not stored inside scheduler metadata.
  - [ ] 16.9 Confirm raw provider responses are not stored.
  - [ ] 16.10 Confirm activity summaries remain compact.

- [ ] 17. Add Backend Tests
  - [ ] 17.1 Create `backend/tests/test_translation_scheduler_observability.py`.
  - [ ] 17.2 Test selected model decision is recorded.
  - [ ] 17.3 Test decision includes request ID, job ID, and chapter ID when available.
  - [ ] 17.4 Test checkpoint ID is recorded when available.
  - [ ] 17.5 Test cooldown skip reason is recorded.
  - [ ] 17.6 Test RPM skip reason is recorded.
  - [ ] 17.7 Test RPD skip reason is recorded.
  - [ ] 17.8 Test quota/exhausted skip reason is recorded.
  - [ ] 17.9 Test memory pressure skip reason is recorded when memory guard state exists.
  - [ ] 17.10 Test checkpoint blocked skip reason is recorded when checkpoint state blocks execution.
  - [ ] 17.11 Test fallback selection records skipped candidates.
  - [ ] 17.12 Test no-capacity failure records `selected=null` and `failure_reason="no_capacity"`.
  - [ ] 17.13 Test candidate list is bounded.
  - [ ] 17.14 Test truncation metadata is recorded.
  - [ ] 17.15 Test per-chapter translation metadata includes scheduler decision.
  - [ ] 17.16 Test legacy translations without scheduler metadata still load.
  - [ ] 17.17 Ensure tests do not call live translation providers.

- [ ] 18. Add Activity, Parallelism, and Resume Tests
  - [ ] 18.1 Test activity metadata includes scheduler summary.
  - [ ] 18.2 Test scheduler summary counts selected models.
  - [ ] 18.3 Test scheduler summary counts providers.
  - [ ] 18.4 Test scheduler summary counts skip reasons.
  - [ ] 18.5 Test scheduler summary counts fallback selections.
  - [ ] 18.6 Test scheduler summary counts no-capacity decisions.
  - [ ] 18.7 Test scheduler summary counts memory pressure when available.
  - [ ] 18.8 Test scheduler summary counts checkpoint-blocked states when available.
  - [ ] 18.9 Test parallel chapter decisions do not overwrite each other.
  - [ ] 18.10 Test duplicate attempts remain distinguishable by request ID, job ID, or attempt number.
  - [ ] 18.11 Test resumed translation preserves or records scheduler decision metadata.
  - [ ] 18.12 Test request IDs survive activity aggregation.

- [ ] 19. Add Admin API Tests
  - [ ] 19.1 Test scheduler health API returns provider/model status.
  - [ ] 19.2 Test scheduler health API returns quota and cooldown fields when available.
  - [ ] 19.3 Test scheduler health API excludes secrets.
  - [ ] 19.4 Test scheduler health API excludes account identifiers.
  - [ ] 19.5 Test translation activity detail exposes scheduler summary.
  - [ ] 19.6 Test chapter/version detail exposes selected provider/model.
  - [ ] 19.7 Test chapter/version detail exposes fallback and skip summary.
  - [ ] 19.8 Test legacy records without scheduler metadata return `null`, omitted, or `not_available` according to existing API style.
  - [ ] 19.9 Confirm public APIs do not expose scheduler health.

- [ ] 20. Add Frontend Tests If UI Changes
  - [ ] 20.1 Test activity dashboard renders selected model counts.
  - [ ] 20.2 Test activity dashboard renders fallback and skip counts.
  - [ ] 20.3 Test activity dashboard renders quota/cooldown counts.
  - [ ] 20.4 Test activity dashboard renders memory/checkpoint counts when present.
  - [ ] 20.5 Test chapter/version UI shows selected provider/model.
  - [ ] 20.6 Test chapter/version UI shows request ID/job ID where present.
  - [ ] 20.7 Test scheduler health view renders cooldown/exhausted/failed states.
  - [ ] 20.8 Test secrets and account identifiers are not rendered.

- [ ] 21. Backward Compatibility Checks
  - [ ] 21.1 Confirm scheduler selection order did not change.
  - [ ] 21.2 Confirm provider routing policy did not change.
  - [ ] 21.3 Confirm quota behavior did not change.
  - [ ] 21.4 Confirm cooldown behavior did not change.
  - [ ] 21.5 Confirm checkpoint/resume behavior did not change.
  - [ ] 21.6 Confirm chapter parallelization behavior did not change.
  - [ ] 21.7 Confirm memory guard behavior did not change.
  - [ ] 21.8 Confirm existing translation flows work without observability metadata.
  - [ ] 21.9 Confirm old activity records remain loadable.
  - [ ] 21.10 Confirm old translation versions remain loadable.
  - [ ] 21.11 Confirm provider/model config formats remain supported.
  - [ ] 21.12 Confirm public reader behavior is unchanged.

- [ ] 22. Run Verification
  - [ ] 22.1 Run focused scheduler observability tests.
  - [ ] 22.2 Run existing scheduler tests.
  - [ ] 22.3 Run existing translation orchestration tests.
  - [ ] 22.4 Run existing checkpoint/resume tests.
  - [ ] 22.5 Run existing chapter parallelization tests.
  - [ ] 22.6 Run existing activity metadata tests.
  - [ ] 22.7 Run admin API tests.
  - [ ] 22.8 Run admin frontend tests if UI changed.
  - [ ] 22.9 Run `ruff check` on changed backend source and test files.
  - [ ] 22.10 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 22.11 Fix test, lint, and type failures caused by this work.

- [ ] 23. Final Acceptance Review
  - [ ] 23.1 Verify scheduler selection produces compact decision records.
  - [ ] 23.2 Verify decision records include request/job/chapter identity where available.
  - [ ] 23.3 Verify skipped candidates use stable reason codes.
  - [ ] 23.4 Verify quota, cooldown, no-capacity, memory-pressure, and checkpoint-blocked states are visible.
  - [ ] 23.5 Verify per-chapter translation metadata includes scheduler decision when available.
  - [ ] 23.6 Verify activity metadata includes aggregate scheduler summary.
  - [ ] 23.7 Verify aggregation is safe under chapter parallelization.
  - [ ] 23.8 Verify checkpoint/resume behavior remains unchanged and observable.
  - [ ] 23.9 Verify admin API exposes provider/model scheduler health without secrets.
  - [ ] 23.10 Verify admin UI shows fallback, skip reason, quota, cooldown, request ID, and health information.
  - [ ] 23.11 Verify scheduler policy, provider routing, quota behavior, memory behavior, and translation output are unchanged.
  - [ ] 23.12 Verify legacy translations and activities remain compatible.
  - [ ] 23.13 Verify focused backend and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Record Scheduler Selection Decisions | 2, 5, 6, 7, 17, 23 |
| REQ-2 Include Request, Job, Chapter, and Checkpoint Identity | 3, 8, 9, 17, 18, 23 |
| REQ-3 Standardize Skip and Failure Reason Codes | 4, 6, 7, 17, 18, 23 |
| REQ-4 Record Candidate Runtime State Safely | 6, 13, 16, 17, 19 |
| REQ-5 Persist Per-Chapter Scheduler Metadata | 11, 17, 19, 23 |
| REQ-6 Aggregate Scheduler Summary in Activity Metadata | 12, 18, 23 |
| REQ-7 Preserve Checkpoint and Resume Semantics | 8, 18, 21, 23 |
| REQ-8 Support Chapter Parallelization Safely | 9, 18, 21, 23 |
| REQ-9 Surface Exact Memory State When Available | 10, 18, 21, 23 |
| REQ-10 Expose Scheduler Health in Admin APIs | 13, 19, 23 |
| REQ-11 Expose Scheduler Metadata in Admin Translation APIs | 14, 19, 23 |
| REQ-12 Admin UI Visibility | 15, 20, 23 |
| REQ-13 Failure and Fallback Visibility | 7, 12, 14, 17, 18, 23 |
| REQ-14 Bounded and Safe Metadata | 2, 6, 11, 16, 19 |
| REQ-15 Backward Compatibility | 21, 22, 23 |
| REQ-16 Tests | 17, 18, 19, 20, 22 |

## Definition of Done

- [ ] Scheduler emits compact decision records.
- [ ] Decision records include request/job/chapter/checkpoint identity where available.
- [ ] Skip and failure reasons use stable codes.
- [ ] Candidate records include safe runtime state.
- [ ] Candidate lists are bounded and truncation is explicit.
- [ ] Per-chapter translation metadata stores scheduler decision when available.
- [ ] Activity metadata stores aggregate scheduler summary.
- [ ] Activity aggregation is safe under chapter parallelization.
- [ ] Checkpoint/resume behavior is unchanged and observable.
- [ ] Exact memory state is surfaced where existing tracking supports it.
- [ ] Admin API exposes scheduler health without secrets.
- [ ] Admin translation APIs expose scheduler summaries and per-version decisions.
- [ ] Admin UI shows selected model, fallback, skip reasons, quota, cooldown, memory, checkpoint, request ID, and health states.
- [ ] No scheduling policy, provider routing, quota, cooldown, checkpoint/resume, parallelization, memory guard, or translation output behavior changes.
- [ ] Legacy translations and activities remain compatible.
- [ ] Focused backend, admin API, and frontend tests pass.