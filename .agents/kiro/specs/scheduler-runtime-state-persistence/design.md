# design.md

# Design: Scheduler Runtime State Persistence

## Overview

`scheduler-runtime-state-persistence` persists scheduler runtime state so scheduler health reflects real behavior instead of only static configuration.

The scheduler currently risks reporting “healthy” or “configured” even when a source, job type, adapter, or scheduler loop is actually stuck in cooldown, exhausted, repeatedly failing, or stale. This spec adds durable runtime state records for scheduler decisions and failure transitions.

The persisted state should power scheduler health APIs, admin diagnostics, and future operations work such as alerts, metrics, maintenance cleanup, and notification routing.

## Goals

* Persist live scheduler runtime states.
* Track cooldown, exhausted, failed, running, disabled, and recovered states.
* Track next eligible run time for cooldown/exhausted sources or jobs.
* Track last attempt, last success, last failure, and consecutive failure counts.
* Track safe error category and message.
* Update scheduler health API to use persisted runtime state.
* Make scheduler state survive process restarts.
* Add cleanup/expiry for old runtime records.
* Add tests for state transitions, persistence, health output, and stale detection.

## Non-goals

* No rewrite of scheduler job selection logic.
* No new scheduler UI unless an admin scheduler page already exists.
* No full metrics dashboard.
* No alert delivery system.
* No retry algorithm redesign unless needed to persist state.
* No duplicate source-health system if one already exists.
* No change to crawl/translate job behavior except state recording.

## Runtime state concepts

The scheduler should persist runtime state for the units it schedules.

Possible runtime scopes:

```text id="c26q2f"
global scheduler
job type
source adapter
source key
novel
chapter batch
queue worker
```

Recommended V1 scopes:

```text id="l6qk0y"
scheduler
job_type
source
```

Example states:

```text id="9ts41t"
idle
running
cooldown
exhausted
failed
disabled
stale
recovered
```

Recommended meaning:

```text id="pqq2ox"
idle: scheduler/scope is available and not currently blocked
running: a scheduler run or scoped job is currently executing
cooldown: scope is temporarily paused until a known time
exhausted: scheduler has no eligible work or source has exhausted available work
failed: last run failed and failure state is still active
disabled: scope is intentionally disabled by config
stale: runtime state has not been updated within expected interval
recovered: previous failure/cooldown has been cleared by a later success
```

## Data model

Recommended table/model: `scheduler_runtime_states`

Recommended fields:

```text id="dpolzz"
id
scheduler_key
scope_type
scope_key
state
reason
error_category
error_message
failure_count
consecutive_failures
last_attempt_at
last_success_at
last_failure_at
last_started_at
last_finished_at
cooldown_until
exhausted_until
next_eligible_at
heartbeat_at
locked_by
metadata_json
created_at
updated_at
expires_at
```

Recommended unique key:

```text id="uu908c"
scheduler_key + scope_type + scope_key
```

Example records:

```json id="rvykf6"
{
  "scheduler_key": "crawl_scheduler",
  "scope_type": "source",
  "scope_key": "syosetu",
  "state": "cooldown",
  "reason": "rate limit detected",
  "error_category": "rate_limited",
  "consecutive_failures": 2,
  "last_attempt_at": "2026-07-10T01:00:00Z",
  "last_failure_at": "2026-07-10T01:00:05Z",
  "cooldown_until": "2026-07-10T01:15:00Z",
  "next_eligible_at": "2026-07-10T01:15:00Z"
}
```

```json id="97a9dp"
{
  "scheduler_key": "translation_scheduler",
  "scope_type": "job_type",
  "scope_key": "translate",
  "state": "failed",
  "reason": "provider unavailable",
  "error_category": "provider_error",
  "consecutive_failures": 5,
  "last_attempt_at": "2026-07-10T01:10:00Z",
  "last_failure_at": "2026-07-10T01:10:30Z",
  "next_eligible_at": "2026-07-10T01:20:00Z"
}
```

## State transition model

Recommended transitions:

```text id="7h0sju"
idle -> running
running -> idle
running -> failed
running -> cooldown
running -> exhausted
failed -> running
failed -> recovered
cooldown -> running
cooldown -> idle
cooldown -> failed
exhausted -> idle
exhausted -> running
disabled -> idle
any active state -> stale
```

### On scheduler start

When a scheduler loop starts:

```text id="fkd6qc"
set state = running
set last_started_at
set heartbeat_at
clear stale marker if present
```

### On successful scheduler pass

When a scheduler pass completes successfully:

```text id="h08dnd"
set last_success_at
set last_finished_at
reset consecutive_failures to 0
clear error_category/error_message if appropriate
set state = idle or exhausted depending on work availability
```

### On failure

When a scheduler pass fails:

```text id="4coc57"
set state = failed
set last_failure_at
set last_finished_at
increment failure_count
increment consecutive_failures
set error_category
set safe error_message
set next_eligible_at if retry/cooldown applies
```

### On cooldown

When the scheduler intentionally backs off:

```text id="9i34l2"
set state = cooldown
set cooldown_until
set next_eligible_at = cooldown_until
set reason
set error_category if cooldown is caused by an error
```

### On exhausted

When no work is eligible or a source has no more work:

```text id="dx48lv"
set state = exhausted
set exhausted_until if known
set next_eligible_at if known
set reason
```

### On recovery

When a previously failed/cooldown scope succeeds:

```text id="04smjx"
set state = recovered or idle
set last_success_at
reset consecutive_failures
clear active error fields
clear cooldown_until when no longer active
```

V1 may skip the explicit `recovered` state and transition directly to `idle`, as long as recovery is visible through `last_success_at` and reset failure counters.

## Scheduler health integration

Existing scheduler health should be changed from static configuration-only output to runtime-aware output.

Recommended endpoint:

```http id="etp3nl"
GET /admin/scheduler/health
```

If an endpoint already exists, update it rather than adding a duplicate.

Recommended response:

```json id="bh6y11"
{
  "status": "degraded",
  "timestamp": "2026-07-10T01:30:00Z",
  "schedulers": [
    {
      "scheduler_key": "crawl_scheduler",
      "state": "degraded",
      "last_success_at": "2026-07-10T01:00:00Z",
      "last_failure_at": "2026-07-10T01:20:00Z",
      "stale": false,
      "active_cooldowns": 1,
      "active_failures": 1,
      "exhausted_scopes": 0
    }
  ],
  "runtime_states": [
    {
      "scheduler_key": "crawl_scheduler",
      "scope_type": "source",
      "scope_key": "syosetu",
      "state": "cooldown",
      "reason": "rate limit detected",
      "error_category": "rate_limited",
      "next_eligible_at": "2026-07-10T01:45:00Z",
      "consecutive_failures": 2,
      "last_attempt_at": "2026-07-10T01:20:00Z"
    }
  ]
}
```

Public health endpoints should not expose detailed scheduler runtime state. Deep health can consume summarized scheduler status later.

## Health status calculation

Recommended scheduler health status:

```text id="eai9ix"
healthy
degraded
unhealthy
unknown
```

Suggested rules:

```text id="1xwegg"
healthy: scheduler heartbeat is fresh and no required scope has active failure
degraded: cooldowns, exhausted scopes, or non-critical failures exist but scheduler can continue
unhealthy: scheduler heartbeat is stale, required job type is failed, or all work is blocked
unknown: no runtime state exists yet
```

A source in cooldown should usually be degraded, not unhealthy, unless all configured sources are blocked or the cooldown is long/stale.

A source exhausted state should usually be healthy or degraded depending on whether exhaustion is expected.

A failed required job type should be unhealthy.

## Heartbeat and stale detection

Schedulers should update heartbeat periodically.

Recommended config:

```text id="d8x3lh"
SCHEDULER_HEARTBEAT_INTERVAL_SECONDS=30
SCHEDULER_STALE_AFTER_SECONDS=120
SCHEDULER_RUNTIME_STATE_TTL_DAYS=14
```

Behavior:

* Scheduler loop updates `heartbeat_at`.
* Health marks scheduler stale when `heartbeat_at` is older than threshold.
* Stale state should be derived in health calculation or persisted by cleanup/maintenance job.
* Scheduler restart should recover from stale state by updating heartbeat and state.

## Error categories

Reuse existing structured error categories if available.

Recommended categories:

```text id="a8qxxb"
rate_limited
not_found
timeout
server_error
fetch_error
provider_error
storage_error
database_error
queue_error
configuration_error
no_work_available
exhausted
lock_unavailable
unknown
```

Error messages must be safe:

* No provider API keys.
* No raw tokens.
* No full credentials.
* No stack traces in API responses.
* No large exception bodies.

## Persistence strategy

State updates should be small and safe.

Recommended repository methods:

```text id="8yv4tn"
upsert_runtime_state()
mark_started()
mark_success()
mark_failure()
mark_cooldown()
mark_exhausted()
mark_disabled()
update_heartbeat()
clear_state()
list_runtime_states()
get_scheduler_health_summary()
delete_expired_states()
```

State writes should be best-effort only where failure should not crash user-facing jobs, but scheduler health must record critical failures where possible.

For state transitions that are part of scheduler decisions, persist before acting when needed. For final success/failure, persist after completion.

## Concurrency and locking

If multiple scheduler workers can run, state updates must be safe.

Recommended:

```text id="himk6f"
unique key per scheduler/scope
atomic upsert
compare-and-set where lock ownership matters
database transaction around state transition when tied to job claiming
```

Do not allow one scheduler instance to overwrite another active run incorrectly. Include `locked_by` or `run_id` if existing scheduler uses run IDs.

## Cleanup and expiry

Runtime state should not grow forever.

Recommended behavior:

```text id="ep2j1d"
active states do not expire
old recovered/idle states expire after TTL
old disabled/configured states remain if still configured
old unknown source states expire after TTL
```

This can be integrated with the later `maintenance-cron` spec. For this spec, provide the deletion method and optionally call it from scheduler startup or existing cleanup.

## Admin UI

A full operations UI is optional. If an admin scheduler page exists, add runtime state display.

Recommended display:

```text id="7cst96"
overall scheduler health
heartbeat age
active cooldowns
active failures
exhausted scopes
last success/failure
next eligible time
safe failure reason
```

## Observability

This spec should produce structured logs for state transitions:

```text id="915yx4"
scheduler_key
scope_type
scope_key
previous_state
new_state
reason
error_category
next_eligible_at
run_id
```

Metrics are not required here, but this should be compatible with future metrics:

```text id="fbo607"
scheduler_runtime_state_total
scheduler_cooldown_active_total
scheduler_failure_active_total
scheduler_stale_total
scheduler_consecutive_failures
```

## Security

Admin scheduler health should be admin-only.

Rules:

```text id="9so9ob"
do not expose runtime details publicly
redact secrets from errors
do not expose raw provider credentials
do not expose full stack traces
do not expose user private content in scheduler metadata
```

## Testing strategy

Backend tests should cover:

```text id="2dtprp"
state upsert
started transition
success transition
failure transition
cooldown transition
exhausted transition
recovery transition
heartbeat update
stale detection
health aggregation
admin-only access
redaction
cleanup of expired states
process restart simulation using persisted state
```

## Rollout plan

1. Inspect existing scheduler state and health output.
2. Add runtime state model and migration.
3. Add scheduler runtime state repository/service.
4. Add state transition helpers.
5. Wire scheduler loop and job selection to update state.
6. Wire cooldown/exhausted/failure decisions to persisted state.
7. Update scheduler health API to use persisted state.
8. Add stale detection.
9. Add cleanup method for expired runtime state.
10. Add tests.
11. Verify:

    * cooldown survives restart.
    * failed state survives restart.
    * scheduler health shows live runtime state.
    * stale scheduler is detected.
    * recovery clears active failure/cooldown state.
