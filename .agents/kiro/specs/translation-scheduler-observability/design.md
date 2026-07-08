# Design: Translation Scheduler Observability

## Overview

This design adds observability around translation scheduling, provider/model selection, quota state, cooldown state, and job execution health.

The scheduler already makes provider/model decisions using model configuration, runtime state, checkpoint/resume state, chapter parallelization, request IDs, and memory safeguards. This spec does not change those systems. It records the scheduler’s existing decisions as compact metadata, exposes aggregate health in admin APIs, and gives the admin UI enough information to explain fallback, skip, quota, cooldown, and no-capacity behavior.

The design is instrumentation-first:

- Do not change scheduling policy.
- Do not change model priority/order.
- Do not change quota or cooldown behavior.
- Do not change retry behavior.
- Do not change translation output.
- Do not introduce a parallel job state machine.
- Reuse existing checkpoint/resume, request IDs, chapter parallelization, and memory tracking.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| Translation scheduler module, such as `backend/src/novelai/translation/scheduler.py` | Emit compact provider/model selection decision records |
| Translation orchestration/service code | Attach scheduler decision metadata to per-chapter translation results |
| Translation activity/job worker | Aggregate scheduler summary into activity/job metadata |
| Translation checkpoint/resume module | Preserve scheduler metadata across resume/retry where applicable |
| Translation runtime-state or memory module | Reuse exact memory/request state for observability fields |
| Admin operations/translation API router | Expose scheduler health and activity/job dashboard metadata |
| Admin API response models, if strict | Add additive observability fields |
| Admin frontend activity/job/provider UI | Show selected model, fallback counts, skip reasons, quota/cooldown state, request IDs, and memory state |
| `backend/tests/test_translation_scheduler_observability.py` | Add focused tests |

### Files Not Touched

- Prompt templates.
- Glossary review and prompt injection.
- Public reader APIs.
- Provider credential loading.
- Translation storage format, except additive metadata where translation versions already store provider/model metadata.
- Scheduler policy/order/quota behavior.
- Chapter parallelization behavior.
- Checkpoint/resume semantics.

## Decision Record Contract

Each scheduler selection should produce a compact decision record.

```json
{
  "request_id": "req-123",
  "activity_id": "activity-456",
  "job_id": "job-789",
  "chapter_id": "12",
  "checkpoint_id": "checkpoint-abc",
  "selected": {
    "provider": "openai",
    "model": "gpt-example"
  },
  "policy": "priority",
  "fallback_used": true,
  "selected_at": "2026-07-07T00:00:00Z",
  "parallel_slot": 3,
  "memory": {
    "exact_memory_bytes": 524288000,
    "memory_limit_bytes": 1073741824,
    "memory_pressure": false
  },
  "candidates": [
    {
      "provider": "primary",
      "model": "model-a",
      "status": "cooldown",
      "selected": false,
      "skip_reason": "cooldown_active",
      "cooldown_until": "2026-07-07T00:01:00Z",
      "last_error_code": "rate_limited"
    },
    {
      "provider": "fallback",
      "model": "model-b",
      "status": "available",
      "selected": true,
      "skip_reason": null
    }
  ],
  "candidate_count_total": 2,
  "candidate_count_recorded": 2,
  "candidate_list_truncated": false
}
```

When no model is available:

```json
{
  "request_id": "req-123",
  "activity_id": "activity-456",
  "job_id": "job-789",
  "chapter_id": "12",
  "selected": null,
  "policy": "priority",
  "fallback_used": false,
  "selected_at": "2026-07-07T00:00:00Z",
  "failure_reason": "no_capacity",
  "candidates": [],
  "candidate_count_total": 0,
  "candidate_count_recorded": 0,
  "candidate_list_truncated": false
}
```

## Skip and Failure Reason Codes

Use stable reason codes instead of raw exception messages.

| Code | Meaning |
|---|---|
| `cooldown_active` | Candidate is cooling down |
| `quota_exhausted` | Provider or model quota is exhausted |
| `rpm_limited` | Requests-per-minute limit prevents selection |
| `rpd_limited` | Requests-per-day limit prevents selection |
| `memory_pressure` | Existing exact memory guard prevents safe selection/execution |
| `parallelism_limit` | Chapter parallelization limit prevents immediate execution |
| `disabled` | Candidate disabled by config |
| `previously_attempted` | Candidate skipped because it was already attempted for this unit of work |
| `unhealthy` | Runtime health marks candidate unavailable |
| `checkpoint_blocked` | Existing checkpoint/resume state prevents selection or execution |
| `no_capacity` | No candidates are available |
| `unknown` | Unexpected skip reason |

## Scheduler Integration

Add a decision recorder around the existing model-selection flow.

Preferred structure:

```python
@dataclass
class SchedulerDecision:
    request_id: str | None
    activity_id: str | None
    job_id: str | None
    chapter_id: str | None
    checkpoint_id: str | None
    selected_provider: str | None
    selected_model: str | None
    policy: str
    fallback_used: bool
    selected_at: str
    candidates: list[SchedulerCandidateDecision]
    failure_reason: str | None = None
    parallel_slot: int | None = None
    exact_memory_bytes: int | None = None
    memory_limit_bytes: int | None = None
    memory_pressure: bool | None = None
    candidate_count_total: int = 0
    candidate_count_recorded: int = 0
    candidate_list_truncated: bool = False


@dataclass
class SchedulerCandidateDecision:
    provider: str
    model: str
    status: str | None
    selected: bool
    skip_reason: str | None
    cooldown_until: str | None = None
    exhausted_until: str | None = None
    failed_at: str | None = None
    last_error_code: str | None = None
```

If changing the scheduler return type is too invasive, keep `select_model(...)` unchanged and use a side-channel recorder:

```python
recorder = SchedulerDecisionRecorder(
    request_id=request_id,
    activity_id=activity_id,
    job_id=job_id,
    chapter_id=chapter_id,
)

model = scheduler.select_model(..., decision_recorder=recorder)
decision = recorder.last_decision
```

The recorder must observe decisions only. It must not influence selection.

## Candidate Evaluation Recording

During candidate evaluation, record a bounded summary:

- provider key/name,
- model name,
- runtime status,
- selected true/false,
- skip reason,
- cooldown timestamp,
- quota exhaustion timestamp,
- failed timestamp,
- last safe error code,
- request counters where already available.

Do not record:

- API keys,
- account identifiers,
- full exception traces,
- prompts,
- source text,
- translated text,
- glossary contents,
- provider raw response bodies.

Recommended bound:

```python
MAX_SCHEDULER_DECISION_CANDIDATES = 20
```

If more candidates exist, keep the first 20 in evaluation order and set:

```json
{
  "candidate_count_total": 34,
  "candidate_count_recorded": 20,
  "candidate_list_truncated": true
}
```

## Checkpoint and Resume Integration

Scheduler observability must align with existing checkpoint/resume behavior.

Rules:

- A resumed chapter must preserve prior scheduler decisions if they were already recorded.
- A new provider/model selection after resume must create a new decision record.
- Decision records should include `checkpoint_id` or equivalent checkpoint reference when available.
- Activity summaries must distinguish resumed work from newly scheduled work when existing metadata supports it.
- Observability must not change resume eligibility or checkpoint write timing.

Optional summary fields:

```json
{
  "checkpoint_summary": {
    "resumed_chapter_count": 8,
    "new_selection_after_resume_count": 2,
    "checkpoint_blocked_count": 1
  }
}
```

## Chapter Parallelization Integration

Scheduler observability must work with parallel chapter translation.

Rules:

- Each decision record must be tied to a stable `chapter_id`.
- Each decision record should include `job_id`, `request_id`, and `parallel_slot` where available.
- Parallel workers must not overwrite each other’s decision metadata.
- Activity aggregation must be concurrency-safe.
- Duplicate chapter attempts must be aggregated by attempt/request ID, not by lossy chapter-only keys.

Optional per-decision fields:

```json
{
  "chapter_id": "12",
  "attempt": 2,
  "parallel_slot": 3,
  "request_id": "req-123"
}
```

## Exact Memory Integration

If the project already tracks exact memory, scheduler observability should surface it additively.

Per-decision memory shape:

```json
{
  "memory": {
    "exact_memory_bytes": 524288000,
    "memory_limit_bytes": 1073741824,
    "memory_pressure": false
  }
}
```

Activity summary shape:

```json
{
  "memory_summary": {
    "peak_exact_memory_bytes": 812646400,
    "memory_pressure_count": 2,
    "memory_blocked_count": 1
  }
}
```

Rules:

- Reuse existing exact memory tracking.
- Do not add a second memory accounting system.
- Do not store memory data if no reliable existing source exists.
- Do not change memory guard behavior.

## Persistence

### Per-Chapter Metadata

Attach scheduler decisions to the translation context/result and persist them where provider/model metadata is already stored.

Recommended translation version metadata:

```json
{
  "provider": "openai",
  "model": "gpt-example",
  "scheduler_decision": {
    "request_id": "req-123",
    "job_id": "job-789",
    "chapter_id": "12",
    "selected": {
      "provider": "openai",
      "model": "gpt-example"
    },
    "fallback_used": true,
    "failure_reason": null,
    "candidates": []
  }
}
```

Rules:

- Persist only compact metadata.
- Do not store source text, prompt text, or translated text inside scheduler metadata.
- Legacy translation versions without scheduler metadata remain valid.

### Activity Metadata Summary

Aggregate scheduler decisions into activity metadata.

```json
{
  "scheduler_summary": {
    "chapters_with_decisions": 42,
    "fallback_count": 5,
    "no_capacity_count": 1,
    "checkpoint_blocked_count": 1,
    "memory_pressure_count": 2,
    "skip_reason_counts": {
      "cooldown_active": 4,
      "rpm_limited": 2,
      "quota_exhausted": 1,
      "memory_pressure": 2
    },
    "selected_model_counts": {
      "openai:gpt-example": 37,
      "fallback:model-b": 5
    },
    "provider_counts": {
      "openai": 37,
      "fallback": 5
    }
  }
}
```

Aggregation must be safe under chapter parallelization.

## Scheduler Health API

Expose provider/model health through an existing admin operations route if one exists. Add a new admin-only route only if no suitable operations route exists.

Possible route:

```http
GET /admin/translation/scheduler-health
```

Response:

```json
{
  "models": [
    {
      "provider": "openai",
      "model": "gpt-example",
      "status": "available",
      "rpm_limit": 60,
      "rpd_limit": 1000,
      "requests_this_minute": 12,
      "requests_today": 250,
      "cooldown_until": null,
      "exhausted_until": null,
      "failed_at": null,
      "last_error_code": null
    }
  ],
  "summary": {
    "available_count": 4,
    "cooldown_count": 1,
    "quota_exhausted_count": 1,
    "unhealthy_count": 0
  }
}
```

Rules:

- Admin-only.
- No secrets.
- No raw provider credentials.
- No raw prompts or request bodies.
- Redact account identifiers.
- Use safe reason/error codes.

## Admin API Integration

Expose scheduler observability additively in:

- translation activity detail,
- translation activity/job dashboard summary,
- chapter translation version detail,
- scheduler/provider health route,
- operation runtime-state route if one already exists.

Legacy records without scheduler metadata should return `null`, omit the field, or show `"not_available"` according to existing API style.

## Admin UI Design

### Translation Activity Dashboard

Show:

- selected model counts,
- provider counts,
- fallback count,
- no-capacity count,
- cooldown skip count,
- quota skip count,
- memory pressure count,
- checkpoint blocked/resumed counts where available,
- link/button to scheduler health.

### Chapter/Version Review

Show:

- selected provider/model,
- request ID,
- job ID,
- fallback used,
- failure reason if no model was selected,
- compact skipped candidate list,
- skip reason badges,
- cooldown/quota timestamps where available.

### Scheduler Health View

Show:

- provider/model status,
- cooldown until,
- quota exhausted until,
- requests this minute,
- requests today,
- last safe error code,
- redacted health details.

No secrets should appear in UI.

## Safety and Size Controls

- Bound candidate list length.
- Redact secrets and account identifiers.
- Store stable reason codes instead of full raw errors.
- Do not store prompt text.
- Do not store source text.
- Do not store translated text inside scheduler metadata.
- Keep activity summary compact.
- Keep per-chapter decision records small enough for existing metadata storage.
- Prefer aggregate dashboard metrics over storing large candidate histories.

## Migration and Backward Compatibility

- Existing scheduler behavior is unchanged.
- Existing checkpoint/resume behavior is unchanged.
- Existing chapter parallelization behavior is unchanged.
- Existing memory guard behavior is unchanged.
- Existing translation versions remain loadable.
- Existing activity records remain loadable.
- New metadata fields are additive.
- Public reader behavior is unchanged.
- Provider credentials/config loading is unchanged except for redacted health output.

## Test Design

Create `backend/tests/test_translation_scheduler_observability.py`.

Core backend tests:

- `test_scheduler_records_selected_model_decision`
- `test_scheduler_records_cooldown_skip_reason`
- `test_scheduler_records_rpm_and_rpd_skip_reasons`
- `test_scheduler_records_quota_exhausted_skip_reason`
- `test_scheduler_records_memory_pressure_skip_reason`
- `test_scheduler_records_checkpoint_blocked_skip_reason`
- `test_scheduler_records_fallback_selection`
- `test_scheduler_records_no_capacity_failure`
- `test_scheduler_decision_includes_request_id_job_id_and_chapter_id`
- `test_scheduler_decision_candidate_list_is_bounded`
- `test_parallel_chapter_decisions_do_not_overwrite_each_other`
- `test_resumed_translation_preserves_or_records_scheduler_decision`
- `test_translation_activity_metadata_includes_scheduler_summary`
- `test_scheduler_summary_counts_selected_models`
- `test_scheduler_summary_counts_skip_reasons`
- `test_scheduler_health_response_redacts_secrets`
- `test_legacy_translation_without_scheduler_metadata_loads`

Frontend tests if UI is changed:

- activity dashboard renders fallback and skip counts,
- activity dashboard renders quota/cooldown counts,
- chapter/version review shows selected provider/model,
- chapter/version review shows request ID,
- scheduler health view redacts secrets,
- memory pressure and checkpoint-blocked badges render when present.

No tests should call live translation providers.

## Acceptance Criteria

1. Scheduler selection produces a compact decision record.
2. Decision records include request/job/chapter identity where available.
3. Skipped candidates use stable reason codes.
4. Quota, cooldown, no-capacity, memory-pressure, and checkpoint-blocked states are visible.
5. Per-chapter translation metadata includes scheduler decision when available.
6. Translation activity metadata includes aggregate scheduler summary.
7. Aggregation is safe under chapter parallelization.
8. Checkpoint/resume behavior remains unchanged and observable.
9. Admin API exposes provider/model scheduler health without secrets.
10. Admin UI shows fallback, skip reason, quota, cooldown, request ID, and health information.
11. No scheduling policy, provider routing, quota behavior, memory behavior, or translation output changes.
12. Existing translations and activities without scheduler metadata remain compatible.
13. Focused backend and frontend tests pass.