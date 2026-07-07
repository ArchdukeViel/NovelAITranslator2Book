# Tasks: Translation Scheduler Observability

## Task List

- [ ] 1. Preflight Scheduler Review
  - [ ] 1.1 Inspect `TranslationScheduler` model selection flow.
  - [ ] 1.2 Inspect provider/model config objects and available fields.
  - [ ] 1.3 Inspect runtime scheduler state fields such as RPM/RPD counters, cooldown, exhausted, failed, status, and last error code.
  - [ ] 1.4 Inspect translation service/orchestration path where selected provider/model is attached to translation metadata.
  - [ ] 1.5 Inspect translation activity metadata aggregation path.
  - [ ] 1.6 Inspect admin translation/activity APIs and response models.
  - [ ] 1.7 Inspect frontend admin translation/activity UI.
  - [ ] 1.8 Inspect existing scheduler tests.

- [ ] 2. Define Decision Record Types
  - [ ] 2.1 Add `SchedulerDecision` dataclass or equivalent serializable dict. (REQ-1)
  - [ ] 2.2 Add `SchedulerCandidateDecision` dataclass or equivalent serializable dict.
  - [ ] 2.3 Include selected provider/model. (REQ-1.1)
  - [ ] 2.4 Include scheduler policy. (REQ-1.2)
  - [ ] 2.5 Include bounded candidates list. (REQ-1.3, REQ-8.1)
  - [ ] 2.6 Include fallback flag. (REQ-1.5)
  - [ ] 2.7 Include selection timestamp. (REQ-1.6)
  - [ ] 2.8 Exclude secrets. (REQ-1.7, REQ-8.3)

- [ ] 3. Define Skip Reason Codes
  - [ ] 3.1 Add stable skip reason constants. (REQ-2)
  - [ ] 3.2 Add `cooldown_active`. (REQ-2.1)
  - [ ] 3.3 Add `quota_exhausted`. (REQ-2.2)
  - [ ] 3.4 Add `rpm_limited`. (REQ-2.3)
  - [ ] 3.5 Add `rpd_limited`. (REQ-2.4)
  - [ ] 3.6 Add `disabled`. (REQ-2.5)
  - [ ] 3.7 Add `previously_attempted`. (REQ-2.6)
  - [ ] 3.8 Add `unhealthy`. (REQ-2.7)
  - [ ] 3.9 Add `no_capacity`. (REQ-2.8)
  - [ ] 3.10 Add `unknown`. (REQ-2.9)

- [ ] 4. Instrument Scheduler Candidate Evaluation
  - [ ] 4.1 Record candidate provider/model in evaluation order. (REQ-1.3)
  - [ ] 4.2 Record selected candidate with `selected=true`.
  - [ ] 4.3 Record skipped candidates with `selected=false` and skip reason. (REQ-1.4)
  - [ ] 4.4 Record cooldown timestamps when available.
  - [ ] 4.5 Record exhausted timestamps when available.
  - [ ] 4.6 Record failed timestamps and safe last error code when available.
  - [ ] 4.7 Bound candidate list and record truncation metadata if needed. (REQ-8.1)
  - [ ] 4.8 Preserve existing selection order and behavior. (REQ-9.1)

- [ ] 5. Record No-Capacity Decisions
  - [ ] 5.1 When no model is available, create decision with `selected=null`. (REQ-7.1)
  - [ ] 5.2 Set failure reason to `no_capacity`. (REQ-7.1)
  - [ ] 5.3 Include skipped candidate summary where available.
  - [ ] 5.4 Ensure existing translation error behavior is preserved. (REQ-7.5)

- [ ] 6. Attach Decision to Translation Metadata
  - [ ] 6.1 Pass scheduler decision from scheduler to translation orchestration. (REQ-3.1)
  - [ ] 6.2 Store decision in per-chapter translation metadata or version metadata. (REQ-3.1)
  - [ ] 6.3 Keep metadata bounded. (REQ-3.3)
  - [ ] 6.4 Ensure metadata is additive. (REQ-3.4)
  - [ ] 6.5 Ensure records without scheduler metadata still load. (REQ-3.5, REQ-9.2)

- [ ] 7. Add Activity Scheduler Summary
  - [ ] 7.1 Define `scheduler_summary` activity metadata shape. (REQ-3.2)
  - [ ] 7.2 Count chapters with decisions.
  - [ ] 7.3 Count fallback selections. (REQ-5.1, REQ-5.3)
  - [ ] 7.4 Count no-capacity failures.
  - [ ] 7.5 Aggregate skip reason counts. (REQ-5.3)
  - [ ] 7.6 Aggregate selected model counts.
  - [ ] 7.7 Persist summary in translation activity metadata. (REQ-3.2)

- [ ] 8. Add Scheduler Health Admin API
  - [ ] 8.1 Decide whether to extend an existing admin route or add a narrow scheduler-health route. (REQ-4.1)
  - [ ] 8.2 Expose provider and model. (REQ-4.2)
  - [ ] 8.3 Expose runtime status. (REQ-4.2)
  - [ ] 8.4 Expose RPM/RPD limits and counters. (REQ-4.2)
  - [ ] 8.5 Expose cooldown/exhausted timestamps. (REQ-4.2)
  - [ ] 8.6 Expose failed timestamp and safe last error code. (REQ-4.2)
  - [ ] 8.7 Redact provider secrets. (REQ-4.3, REQ-8.3)
  - [ ] 8.8 Update strict response models if needed. (REQ-4.4)
  - [ ] 8.9 Confirm public APIs do not expose scheduler health. (REQ-4.5)

- [ ] 9. Expose Decisions in Admin Translation APIs
  - [ ] 9.1 Add scheduler summary to translation activity detail response. (REQ-5.1)
  - [ ] 9.2 Add selected provider/model to chapter/version metadata responses. (REQ-5.2)
  - [ ] 9.3 Add fallback and skipped candidate summary to chapter/version metadata responses. (REQ-5.2)
  - [ ] 9.4 Add aggregate counts to novel translation summary if practical. (REQ-5.3)
  - [ ] 9.5 Keep response changes additive. (REQ-5.4)
  - [ ] 9.6 Ensure legacy records show not available instead of failing. (REQ-5.5)

- [ ] 10. Update Admin UI
  - [ ] 10.1 Show selected provider/model summary in translation activity UI. (REQ-6.1)
  - [ ] 10.2 Show fallback count. (REQ-6.2)
  - [ ] 10.3 Show skip reason counts. (REQ-6.3)
  - [ ] 10.4 Show selected provider/model in chapter/version UI. (REQ-6.4)
  - [ ] 10.5 Show provider/model health states. (REQ-6.5)
  - [ ] 10.6 Confirm no secrets appear in UI. (REQ-6.6)

- [ ] 11. Safety and Size Review
  - [ ] 11.1 Bound candidate decision list. (REQ-8.1)
  - [ ] 11.2 Use reason codes instead of long raw errors. (REQ-8.2)
  - [ ] 11.3 Redact secrets and account identifiers. (REQ-8.3)
  - [ ] 11.4 Confirm prompts and translated content are not stored in scheduler metadata. (REQ-8.4)
  - [ ] 11.5 Store safe last error code only. (REQ-8.5)

- [ ] 12. Add Backend Tests
  - [ ] 12.1 Create `backend/tests/test_translation_scheduler_observability.py`. (REQ-10)
  - [ ] 12.2 Test selected model decision is recorded. (REQ-10.1)
  - [ ] 12.3 Test cooldown skip reason is recorded. (REQ-10.2)
  - [ ] 12.4 Test RPM and RPD skip reasons are recorded. (REQ-10.3)
  - [ ] 12.5 Test quota/exhausted skip reason is recorded. (REQ-10.4)
  - [ ] 12.6 Test fallback selection records skipped candidates. (REQ-10.5)
  - [ ] 12.7 Test no-capacity failure records `selected=null` and `no_capacity`. (REQ-10.6)
  - [ ] 12.8 Test activity metadata includes scheduler summary. (REQ-10.7)
  - [ ] 12.9 Test scheduler health API excludes secrets. (REQ-10.8)
  - [ ] 12.10 Test legacy translations without scheduler metadata still load. (REQ-10.9)

- [ ] 13. Add Frontend Tests If UI Is Changed
  - [ ] 13.1 Test activity summary renders fallback and skip counts. (REQ-10.10)
  - [ ] 13.2 Test chapter/version shows selected model. (REQ-10.10)
  - [ ] 13.3 Test health view renders cooldown/exhausted/failed states.
  - [ ] 13.4 Test secrets are not rendered.

- [ ] 14. Backward Compatibility Checks
  - [ ] 14.1 Confirm scheduler selection order did not change. (REQ-9.1)
  - [ ] 14.2 Confirm existing translation flows work without observability metadata. (REQ-9.2)
  - [ ] 14.3 Confirm old activity records remain loadable. (REQ-9.3)
  - [ ] 14.4 Confirm provider/model config formats remain supported. (REQ-9.4)
  - [ ] 14.5 Confirm public reader behavior is unchanged. (REQ-9.5)

- [ ] 15. Run Verification
  - [ ] 15.1 Run focused scheduler observability tests.
  - [ ] 15.2 Run existing scheduler tests.
  - [ ] 15.3 Run existing translation orchestration tests.
  - [ ] 15.4 Run existing activity metadata tests.
  - [ ] 15.5 Run admin frontend tests if UI changed.
  - [ ] 15.6 Run `ruff check` on changed backend files and tests.
  - [ ] 15.7 Run configured backend type checker if present.
  - [ ] 15.8 Fix test, lint, and type failures caused by this work.

- [ ] 16. Final Acceptance Review
  - [ ] 16.1 Verify scheduler selection produces compact decision records.
  - [ ] 16.2 Verify skipped candidates use stable reason codes.
  - [ ] 16.3 Verify per-chapter translation metadata includes scheduler decision when available.
  - [ ] 16.4 Verify translation activity metadata includes aggregate scheduler summary.
  - [ ] 16.5 Verify admin API exposes provider/model scheduler health without secrets.
  - [ ] 16.6 Verify admin UI shows fallback, skip reason, and health information.
  - [ ] 16.7 Verify scheduler policy and provider routing behavior are unchanged except instrumentation.
  - [ ] 16.8 Verify legacy translations and activities remain compatible.
  - [ ] 16.9 Verify focused tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Record Scheduler Decisions | 2, 4, 6, 12, 16 |
| REQ-2 Standardize Skip Reasons | 3, 4, 5, 12 |
| REQ-3 Persist Decision Records | 6, 7, 12, 16 |
| REQ-4 Scheduler Health Admin APIs | 8, 12, 16 |
| REQ-5 Admin Activity/Translation APIs | 7, 9, 12, 16 |
| REQ-6 Admin UI Visibility | 10, 13, 16 |
| REQ-7 Failure and Fallback Visibility | 4, 5, 7, 9, 12 |
| REQ-8 Bounded and Safe Metadata | 2, 4, 6, 11 |
| REQ-9 Backward Compatibility | 6, 9, 14, 16 |
| REQ-10 Tests | 12, 13, 15 |

## Definition of Done

- [ ] Scheduler emits compact decision records.
- [ ] Skip/fallback reasons use stable codes.
- [ ] Per-chapter translation metadata stores scheduler decision when available.
- [ ] Activity metadata stores aggregate scheduler summary.
- [ ] Admin API exposes scheduler health without secrets.
- [ ] Admin UI shows selected model, fallback, skip reasons, and health states.
- [ ] No scheduling policy behavior changes except instrumentation.
- [ ] Legacy records remain compatible.
- [ ] Focused backend and frontend tests pass.

