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

- [x] 1. Preflight Scheduler and Job Flow
  - [x] 1.1 Inspect `TranslationScheduler` or equivalent provider/model selection flow.
  - [x] 1.2 Inspect provider/model config objects and available safe fields.
  - [x] 1.3 Inspect runtime scheduler state fields: RPM/RPD counters, cooldown, exhausted state, failed timestamp, status, and last error code.
  - [x] 1.4 Inspect quota and cooldown update paths.
  - [x] 1.5 Inspect request ID propagation through translation jobs.
  - [x] 1.6 Inspect checkpoint/resume metadata and execution flow.
  - [x] 1.7 Inspect chapter parallelization worker flow and per-chapter attempt handling.
  - [x] 1.8 Inspect exact memory tracking and memory guard state.
  - [x] 1.9 Inspect translation orchestration path where selected provider/model is attached to translation metadata.
  - [x] 1.10 Inspect translation activity/job metadata aggregation.
  - [x] 1.11 Inspect admin translation/activity/job dashboard APIs and response models.
  - [x] 1.12 Inspect admin frontend translation/activity/provider health UI.
  - [x] 1.13 Inspect existing scheduler, translation orchestration, activity, checkpoint, and frontend tests.

- [x] 2. Define Scheduler Decision Record Shape
  - [x] 2.1 Add `SchedulerDecision` dataclass or equivalent serializable structure.
  - [x] 2.2 Add `SchedulerCandidateDecision` dataclass or equivalent serializable structure.
  - [x] 2.3 Include selected provider/model.
  - [x] 2.4 Include `selected: null` support for no-capacity decisions.
  - [x] 2.5 Include scheduler policy.
  - [x] 2.6 Include fallback flag.
  - [x] 2.7 Include selection timestamp.
  - [x] 2.8 Include bounded candidate list.
  - [x] 2.9 Include candidate count total.
  - [x] 2.10 Include candidate count recorded.
  - [x] 2.11 Include candidate list truncated flag.
  - [x] 2.12 Ensure the structure is JSON-serializable.
  - [x] 2.13 Exclude secrets, prompts, source text, translated text, and raw provider responses.

- [x] 3. Add Identity Fields to Decision Records
  - [x] 3.1 Include `request_id` when available.
  - [x] 3.2 Include `activity_id` when available.
  - [x] 3.3 Include `job_id` when available.
  - [x] 3.4 Include `chapter_id` when available.
  - [x] 3.5 Include attempt number when available.
  - [x] 3.6 Include checkpoint ID or checkpoint reference when available.
  - [x] 3.7 Include parallel slot when available.
  - [x] 3.8 Ensure missing identity fields do not break translation execution.
  - [x] 3.9 Reuse existing request ID propagation instead of creating a separate correlation system.

- [x] 4. Define Skip and Failure Reason Codes
  - [x] 4.1 Add stable reason constants or enum values.
  - [x] 4.2 Add `cooldown_active`.
  - [x] 4.3 Add `quota_exhausted`.
  - [x] 4.4 Add `rpm_limited`.
  - [x] 4.5 Add `rpd_limited`.
  - [x] 4.6 Add `memory_pressure`.
  - [x] 4.7 Add `parallelism_limit`.
  - [x] 4.8 Add `disabled`.
  - [x] 4.9 Add `previously_attempted`.
  - [x] 4.10 Add `unhealthy`.
  - [x] 4.11 Add `checkpoint_blocked`.
  - [x] 4.12 Add `no_capacity`.
  - [x] 4.13 Add `unknown`.
  - [x] 4.14 Ensure reason codes are machine-readable and do not contain raw exception text.

- [x] 5. Add Scheduler Decision Recorder
  - [x] 5.1 Add a decision recorder around the existing selection flow.
  - [x] 5.2 Prefer a side-channel recorder if changing scheduler return type is invasive.
  - [x] 5.3 Ensure the recorder observes only and never influences selection.
  - [x] 5.4 Record the selected candidate.
  - [x] 5.5 Record skipped candidates.
  - [x] 5.6 Record no-capacity decisions.
  - [x] 5.7 Preserve existing selection order exactly.
  - [x] 5.8 Preserve existing scheduler errors exactly.

- [x] 6. Instrument Candidate Evaluation
  - [x] 6.1 Record candidate provider and model in evaluation order.
  - [x] 6.2 Record candidate runtime status when available.
  - [x] 6.3 Record `selected=true` for the chosen candidate.
  - [x] 6.4 Record `selected=false` for skipped candidates.
  - [x] 6.5 Record skip reason for skipped candidates.
  - [x] 6.6 Record `cooldown_until` when available.
  - [x] 6.7 Record `exhausted_until` when available.
  - [x] 6.8 Record `failed_at` when available.
  - [x] 6.9 Record safe `last_error_code` when available.
  - [x] 6.10 Record request counters where already available.
  - [x] 6.11 Bound candidate list with `MAX_SCHEDULER_DECISION_CANDIDATES`.
  - [x] 6.12 Record truncation metadata when candidates exceed the bound.

- [x] 7. Record No-Capacity Decisions
  - [x] 7.1 When no model is available, create a decision with `selected=null`.
  - [x] 7.2 Set `failure_reason="no_capacity"`.
  - [x] 7.3 Include skipped candidate summary when available.
  - [x] 7.4 Preserve existing no-capacity error behavior.
  - [x] 7.5 Ensure no-capacity observability does not trigger independent retry or rerouting.

- [x] 8. Integrate Checkpoint and Resume Observability
  - [x] 8.1 Include checkpoint reference in decision records when available.
  - [x] 8.2 Preserve prior scheduler decision metadata when a resumed chapter already has it.
  - [x] 8.3 Create a new decision record when resume triggers a new provider/model selection.
  - [x] 8.4 Count resumed work in activity summary when existing metadata supports it.
  - [x] 8.5 Count checkpoint-blocked states with `checkpoint_blocked`.
  - [x] 8.6 Ensure observability does not change checkpoint write timing.
  - [x] 8.7 Ensure observability does not change resume eligibility.

- [x] 9. Integrate Chapter Parallelization Safely
  - [x] 9.1 Tie every decision record to a stable chapter ID when available.
  - [x] 9.2 Include attempt number, request ID, or job ID to distinguish duplicate chapter attempts.
  - [x] 9.3 Ensure parallel workers do not overwrite each other’s scheduler metadata.
  - [x] 9.4 Ensure activity summary aggregation is concurrency-safe.
  - [x] 9.5 Aggregate by decision/attempt rather than lossy chapter-only keys where retries/resumes exist.
  - [x] 9.6 Preserve existing chapter parallelization limits and behavior.

- [x] 10. Integrate Exact Memory Observability
  - [x] 10.1 Reuse existing exact memory tracking if available.
  - [x] 10.2 Add `exact_memory_bytes` to decision metadata when available.
  - [x] 10.3 Add `memory_limit_bytes` when available.
  - [x] 10.4 Add `memory_pressure` when available.
  - [x] 10.5 Count memory pressure events in activity summary.
  - [x] 10.6 Count memory-blocked events in activity summary when available.
  - [x] 10.7 Track peak exact memory in activity summary when available.
  - [x] 10.8 Do not add a second memory accounting system.
  - [x] 10.9 Do not change memory guard behavior.

- [x] 11. Attach Decision to Per-Chapter Translation Metadata
  - [x] 11.1 Pass scheduler decision from scheduler to translation orchestration.
  - [x] 11.2 Store decision in per-chapter translation result metadata.
  - [x] 11.3 Store decision in translation version metadata where provider/model metadata is already stored.
  - [x] 11.4 Keep scheduler metadata compact.
  - [x] 11.5 Ensure metadata is additive.
  - [x] 11.6 Ensure translation versions without scheduler metadata still load.
  - [x] 11.7 Ensure scheduler metadata does not duplicate prompt, source, or translated text.

- [x] 12. Add Activity Scheduler Summary
  - [x] 12.1 Define `scheduler_summary` activity metadata shape.
  - [x] 12.2 Count `chapters_with_decisions`.
  - [x] 12.3 Count fallback selections.
  - [x] 12.4 Count no-capacity decisions.
  - [x] 12.5 Aggregate skip reason counts.
  - [x] 12.6 Aggregate selected model counts.
  - [x] 12.7 Aggregate provider counts.
  - [x] 12.8 Aggregate quota/cooldown counts.
  - [x] 12.9 Aggregate checkpoint/resume counts when available.
  - [x] 12.10 Aggregate memory pressure and memory blocked counts when available.
  - [x] 12.11 Persist summary in translation activity metadata.
  - [x] 12.12 Ensure summary updates are safe under parallel chapter execution.

- [x] 13. Add Scheduler Health Admin API
  - [x] 13.1 Prefer extending an existing admin operations/runtime-state route.
  - [x] 13.2 Add a narrow admin-only scheduler-health route only if no suitable route exists.
  - [x] 13.3 Expose provider and model.
  - [x] 13.4 Expose runtime status.
  - [x] 13.5 Expose RPM limit and requests this minute when available.
  - [x] 13.6 Expose RPD limit and requests today when available.
  - [x] 13.7 Expose cooldown timestamp when available.
  - [x] 13.8 Expose exhausted timestamp when available.
  - [x] 13.9 Expose failed timestamp when available.
  - [x] 13.10 Expose safe last error code when available.
  - [x] 13.11 Include aggregate health summary counts.
  - [x] 13.12 Redact provider secrets and account identifiers.
  - [x] 13.13 Update strict response models if needed.
  - [x] 13.14 Confirm public APIs do not expose scheduler health.

- [x] 14. Expose Decisions in Admin Translation APIs
  - [x] 14.1 Add scheduler summary to translation activity detail response.
  - [x] 14.2 Add scheduler summary to job dashboard response where applicable.
  - [x] 14.3 Add selected provider/model to chapter/version detail response.
  - [x] 14.4 Add fallback state to chapter/version detail response.
  - [x] 14.5 Add compact skipped candidate summary to chapter/version detail response.
  - [x] 14.6 Add request ID/job ID/checkpoint ID where useful.
  - [x] 14.7 Add aggregate fallback, cooldown, quota, memory, checkpoint, and no-capacity counts to novel translation summary when practical.
  - [x] 14.8 Keep response changes additive.
  - [x] 14.9 Update strict response models if they would drop new fields.
  - [x] 14.10 Show legacy records as `null`, omitted, or `not_available` according to existing API style.

- [x] 15. Update Admin UI
  - [x] 15.1 Show selected model counts in translation activity dashboard.
  - [x] 15.2 Show provider counts.
  - [x] 15.3 Show fallback count.
  - [x] 15.4 Show no-capacity count.
  - [x] 15.5 Show skip reason counts.
  - [x] 15.6 Show cooldown and quota counts.
  - [x] 15.7 Show memory pressure and memory blocked counts when available.
  - [x] 15.8 Show checkpoint/resume counts when available.
  - [x] 15.9 Show selected provider/model in chapter/version UI.
  - [x] 15.10 Show fallback state and skipped candidate reasons in chapter/version UI.
  - [x] 15.11 Show request ID/job ID/checkpoint ID where useful.
  - [x] 15.12 Show provider/model health states.
  - [x] 15.13 Confirm secrets and account identifiers are not rendered.

- [x] 16. Safety and Size Review
  - [x] 16.1 Confirm candidate decision list is bounded.
  - [x] 16.2 Confirm truncation metadata is present when needed.
  - [x] 16.3 Confirm reason codes are used instead of long raw errors.
  - [x] 16.4 Confirm provider secrets are redacted.
  - [x] 16.5 Confirm account identifiers are redacted.
  - [x] 16.6 Confirm prompts are not stored.
  - [x] 16.7 Confirm source text is not stored.
  - [x] 16.8 Confirm translated text is not stored inside scheduler metadata.
  - [x] 16.9 Confirm raw provider responses are not stored.
  - [x] 16.10 Confirm activity summaries remain compact.

- [x] 17. Add Backend Tests
  - [x] 17.1 Create `backend/tests/test_translation_scheduler_observability.py`.
  - [x] 17.2 Test selected model decision is recorded.
  - [x] 17.3 Test decision includes request ID, job ID, and chapter ID when available.
  - [x] 17.4 Test checkpoint ID is recorded when available.
  - [x] 17.5 Test cooldown skip reason is recorded.
  - [x] 17.6 Test RPM skip reason is recorded.
  - [x] 17.7 Test RPD skip reason is recorded.
  - [x] 17.8 Test quota/exhausted skip reason is recorded.
  - [x] 17.9 Test memory pressure skip reason is recorded when memory guard state exists.
  - [x] 17.10 Test checkpoint blocked skip reason is recorded when checkpoint state blocks execution.
  - [x] 17.11 Test fallback selection records skipped candidates.
  - [x] 17.12 Test no-capacity failure records `selected=null` and `failure_reason="no_capacity"`.
  - [x] 17.13 Test candidate list is bounded.
  - [x] 17.14 Test truncation metadata is recorded.
  - [x] 17.15 Test per-chapter translation metadata includes scheduler decision.
  - [x] 17.16 Test legacy translations without scheduler metadata still load.
  - [x] 17.17 Ensure tests do not call live translation providers.

- [x] 18. Add Activity, Parallelism, and Resume Tests
  - [x] 18.1 Test activity metadata includes scheduler summary.
  - [x] 18.2 Test scheduler summary counts selected models.
  - [x] 18.3 Test scheduler summary counts providers.
  - [x] 18.4 Test scheduler summary counts skip reasons.
  - [x] 18.5 Test scheduler summary counts fallback selections.
  - [x] 18.6 Test scheduler summary counts no-capacity decisions.
  - [x] 18.7 Test scheduler summary counts memory pressure when available.
  - [x] 18.8 Test scheduler summary counts checkpoint-blocked states when available.
  - [x] 18.9 Test parallel chapter decisions do not overwrite each other.
  - [x] 18.10 Test duplicate attempts remain distinguishable by request ID, job ID, or attempt number.
  - [x] 18.11 Test resumed translation preserves or records scheduler decision metadata.
  - [x] 18.12 Test request IDs survive activity aggregation.

- [x] 19. Add Admin API Tests
  - [x] 19.1 Test scheduler health API returns provider/model status.
  - [x] 19.2 Test scheduler health API returns quota and cooldown fields when available.
  - [x] 19.3 Test scheduler health API excludes secrets.
  - [x] 19.4 Test scheduler health API excludes account identifiers.
  - [x] 19.5 Test translation activity detail exposes scheduler summary.
  - [x] 19.6 Test chapter/version detail exposes selected provider/model.
  - [x] 19.7 Test chapter/version detail exposes fallback and skip summary.
  - [x] 19.8 Test legacy records without scheduler metadata return `null`, omitted, or `not_available` according to existing API style.
  - [x] 19.9 Confirm public APIs do not expose scheduler health.

- [x] 20. Add Frontend Tests If UI Changes
  - [x] 20.1 Test activity dashboard renders selected model counts.
  - [x] 20.2 Test activity dashboard renders fallback and skip counts.
  - [x] 20.3 Test activity dashboard renders quota/cooldown counts.
  - [x] 20.4 Test activity dashboard renders memory/checkpoint counts when present.
  - [x] 20.5 Test chapter/version UI shows selected provider/model.
  - [x] 20.6 Test chapter/version UI shows request ID/job ID where present.
  - [x] 20.7 Test scheduler health view renders cooldown/exhausted/failed states.
  - [x] 20.8 Test secrets and account identifiers are not rendered.

- [x] 21. Backward Compatibility Checks
  - [x] 21.1 Confirm scheduler selection order did not change.
  - [x] 21.2 Confirm provider routing policy did not change.
  - [x] 21.3 Confirm quota behavior did not change.
  - [x] 21.4 Confirm cooldown behavior did not change.
  - [x] 21.5 Confirm checkpoint/resume behavior did not change.
  - [x] 21.6 Confirm chapter parallelization behavior did not change.
  - [x] 21.7 Confirm memory guard behavior did not change.
  - [x] 21.8 Confirm existing translation flows work without observability metadata.
  - [x] 21.9 Confirm old activity records remain loadable.
  - [x] 21.10 Confirm old translation versions remain loadable.
  - [x] 21.11 Confirm provider/model config formats remain supported.
  - [x] 21.12 Confirm public reader behavior is unchanged.

- [x] 22. Run Verification
  - [x] 22.1 Run focused scheduler observability tests.
  - [x] 22.2 Run existing scheduler tests.
  - [x] 22.3 Run existing translation orchestration tests.
  - [x] 22.4 Run existing checkpoint/resume tests.
  - [x] 22.5 Run existing chapter parallelization tests.
  - [x] 22.6 Run existing activity metadata tests.
  - [x] 22.7 Run admin API tests.
  - [x] 22.8 Run admin frontend tests if UI changed.
  - [x] 22.9 Run `ruff check` on changed backend source and test files.
  - [x] 22.10 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 22.11 Fix test, lint, and type failures caused by this work.

- [x] 23. Final Acceptance Review
  - [x] 23.1 Verify scheduler selection produces compact decision records.
  - [x] 23.2 Verify decision records include request/job/chapter identity where available.
  - [x] 23.3 Verify skipped candidates use stable reason codes.
  - [x] 23.4 Verify quota, cooldown, no-capacity, memory-pressure, and checkpoint-blocked states are visible.
  - [x] 23.5 Verify per-chapter translation metadata includes scheduler decision when available.
  - [x] 23.6 Verify activity metadata includes aggregate scheduler summary.
  - [x] 23.7 Verify aggregation is safe under chapter parallelization.
  - [x] 23.8 Verify checkpoint/resume behavior remains unchanged and observable.
  - [x] 23.9 Verify admin API exposes provider/model scheduler health without secrets.
  - [x] 23.10 Verify admin UI shows fallback, skip reason, quota, cooldown, request ID, and health information.
  - [x] 23.11 Verify scheduler policy, provider routing, quota behavior, memory behavior, and translation output are unchanged.
  - [x] 23.12 Verify legacy translations and activities remain compatible.
  - [x] 23.13 Verify focused backend and frontend tests pass.

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

- [x] Scheduler emits compact decision records.
- [x] Decision records include request/job/chapter/checkpoint identity where available.
- [x] Skip and failure reasons use stable codes.
- [x] Candidate records include safe runtime state.
- [x] Candidate lists are bounded and truncation is explicit.
- [x] Per-chapter translation metadata stores scheduler decision when available.
- [x] Activity metadata stores aggregate scheduler summary.
- [x] Activity aggregation is safe under chapter parallelization.
- [x] Checkpoint/resume behavior is unchanged and observable.
- [x] Exact memory state is surfaced where existing tracking supports it.
- [x] Admin API exposes scheduler health without secrets.
- [x] Admin translation APIs expose scheduler summaries and per-version decisions.
- [x] Admin UI shows selected model, fallback, skip reasons, quota, cooldown, memory, checkpoint, request ID, and health states.
- [x] No scheduling policy, provider routing, quota, cooldown, checkpoint/resume, parallelization, memory guard, or translation output behavior changes.
- [x] Legacy translations and activities remain compatible.
- [x] Focused backend, admin API, and frontend tests pass.