# Design: Translation Scheduler Observability

## Overview

This design adds observability around translation provider/model selection. The scheduler already makes decisions based on model configuration and runtime state. This feature captures those decisions as compact metadata, exposes provider/model health in admin APIs, and shows fallback/skip reasons in admin UI.

The design is instrumentation-first. It should not change scheduling policy, model order, quota behavior, or translation output.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| Translation scheduler module, such as `backend/src/novelai/translation/scheduler.py` | Emit selection decision records |
| Translation orchestration/service code | Persist per-chapter decision metadata and activity summary |
| Activity queue/worker code | Store aggregate scheduler summary in activity metadata |
| Admin API router/model for translation or operations | Expose decision metadata and scheduler health |
| Admin frontend translation/activity/provider UI | Show selected model, fallback, skip counts, and health state |
| `backend/tests/test_translation_scheduler_observability.py` | New focused tests |

### Files Not Touched

- Prompt templates.
- Glossary review/prompt injection.
- Public reader APIs.
- Provider credentials/config loading, except redaction for health output.

## Decision Record Contract

Add a compact selection decision shape:

```json
{
  "selected": {
    "provider": "openai",
    "model": "gpt-example"
  },
  "policy": "priority",
  "fallback_used": true,
  "selected_at": "2026-07-07T00:00:00Z",
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
  ]
}
```

When no model is available:

```json
{
  "selected": null,
  "policy": "priority",
  "fallback_used": false,
  "selected_at": "2026-07-07T00:00:00Z",
  "failure_reason": "no_capacity",
  "candidates": []
}
```

### Skip Reason Codes

Supported reason codes:

| Code | Meaning |
|---|---|
| `cooldown_active` | Candidate is cooling down |
| `quota_exhausted` | Provider or model quota is exhausted |
| `rpm_limited` | Requests-per-minute limit prevents selection |
| `rpd_limited` | Requests-per-day limit prevents selection |
| `disabled` | Candidate disabled by config |
| `previously_attempted` | Candidate skipped due to attempted model history |
| `unhealthy` | Runtime status marks candidate unavailable |
| `no_capacity` | No candidates available |
| `unknown` | Unexpected skip reason |

## Scheduler Integration

Add a decision recorder around the existing `select_model` flow.

Preferred API:

```python
@dataclass
class SchedulerDecision:
    selected_provider: str | None
    selected_model: str | None
    policy: str
    fallback_used: bool
    selected_at: str
    candidates: list[SchedulerCandidateDecision]
    failure_reason: str | None = None

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

If changing return type is too invasive, keep `select_model(...)` return value unchanged and store the latest decision in a side-channel result object or callback:

```python
model = scheduler.select_model(..., decision_recorder=recorder)
decision = recorder.last_decision
```

Do not change ordering or availability decisions.

## Candidate Evaluation

During candidate evaluation, collect a bounded summary:

- provider key/name,
- model name,
- runtime status,
- selected true/false,
- skip reason,
- cooldown/exhausted/failed timestamps,
- last safe error code.

Do not include:

- API keys,
- account identifiers,
- full exception stack traces,
- prompts,
- source or translated text.

Recommended bound:

```python
MAX_SCHEDULER_DECISION_CANDIDATES = 20
```

If more candidates exist, include the first 20 in evaluation order and add:

```json
{
  "candidate_count_total": 34,
  "candidate_count_recorded": 20,
  "candidate_list_truncated": true
}
```

## Persistence

### Per-Chapter Translation Metadata

Attach scheduler decision to translation context/result:

```json
{
  "scheduler_decision": {
    "selected": {"provider": "openai", "model": "gpt-example"},
    "fallback_used": true,
    "candidates": [...]
  }
}
```

Store this in translation version metadata or chapter translation result metadata where existing patterns already store provider/model metadata.

### Activity Summary

Aggregate per-chapter decisions into activity metadata:

```json
{
  "scheduler_summary": {
    "chapters_with_decisions": 42,
    "fallback_count": 5,
    "no_capacity_count": 1,
    "skip_reason_counts": {
      "cooldown_active": 4,
      "rpm_limited": 2,
      "quota_exhausted": 1
    },
    "selected_model_counts": {
      "openai:gpt-example": 37,
      "fallback:model-b": 5
    }
  }
}
```

This lets admins understand broad routing behavior without opening every chapter version.

## Scheduler Health API

Expose provider/model health through an admin-only route or existing operations/admin route.

Example:

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
  ]
}
```

If an admin route already exposes operations/provider health, extend that route instead of adding a new one.

## Admin API Integration

Expose scheduler data additively in:

- translation activity detail,
- chapter translation version detail,
- translation activity summary,
- scheduler health endpoint/route.

Legacy records without scheduler metadata should return `null`, omit the field, or show "not available" depending on existing API style.

## Admin UI Design

### Translation Activity

Show:

- selected model counts,
- fallback count,
- no-capacity count,
- skip reason counts,
- link/button to provider health.

### Chapter/Version Review

Show:

- selected provider/model,
- whether fallback was used,
- compact skipped candidate list,
- skip reason badges.

### Scheduler Health

Show:

- provider/model status,
- cooldown until,
- exhausted until,
- request counters,
- last error code.

No secrets should appear in UI.

## Safety and Size Controls

- Bound candidate decision list.
- Redact secrets.
- Use reason codes, not full raw errors.
- Do not store prompt/chapter text.
- Keep activity summary compact.

## Migration and Backward Compatibility

- Existing scheduler behavior is unchanged.
- Existing translation versions remain loadable.
- Existing activity records remain loadable.
- New metadata fields are additive.
- Public reader behavior is unchanged.

## Test Design

Create `backend/tests/test_translation_scheduler_observability.py`.

Core tests:

- `test_scheduler_records_selected_model_decision`
- `test_scheduler_records_cooldown_skip_reason`
- `test_scheduler_records_rpm_and_rpd_skip_reasons`
- `test_scheduler_records_quota_exhausted_skip_reason`
- `test_scheduler_records_fallback_selection`
- `test_scheduler_records_no_capacity_failure`
- `test_translation_activity_metadata_includes_scheduler_summary`
- `test_scheduler_health_response_redacts_secrets`
- `test_legacy_translation_without_scheduler_metadata_loads`

Frontend tests if UI is changed:

- activity summary renders fallback and skip counts,
- chapter/version shows selected model,
- health view redacts secrets.

## Acceptance Criteria

1. Scheduler selection produces a compact decision record.
2. Skipped candidates use stable reason codes.
3. Per-chapter translation metadata includes scheduler decision when available.
4. Translation activity metadata includes aggregate scheduler summary.
5. Admin API exposes provider/model scheduler health without secrets.
6. Admin UI shows fallback, skip reason, and health information.
7. No scheduling policy or provider routing behavior changes except instrumentation.
8. Existing translations and activities without scheduler metadata remain compatible.
9. Focused tests pass.

