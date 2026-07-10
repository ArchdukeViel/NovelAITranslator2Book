# design.md

# Design: Metrics Dashboard Baseline

## Overview

`metrics-dashboard-baseline` adds a baseline operational metrics layer and an admin dashboard/API for observing production health.

The system needs visibility into:

```text id="r4y5ku"
request latency
error rate
queue depth
translation throughput
crawl failures
cache hit rate
public reader performance
worker/scheduler behavior
export performance
storage/object-storage errors
```

This is a should-have operations spec. It is not a V1 launch blocker, but it becomes important before scale and before public traffic grows.

## Goals

* Add baseline application metrics instrumentation.
* Track request latency and error rates.
* Track queue depth and worker throughput.
* Track translation throughput and failures.
* Track crawl success/failure counts and error categories.
* Track cache hit/miss rate.
* Track public reader latency, fallback, and error rates.
* Add admin-only metrics summary endpoint.
* Add optional admin metrics dashboard page.
* Keep metrics privacy-friendly and low-cardinality.
* Add tests for instrumentation and endpoint authorization.

## Non-goals

* No full product analytics. That belongs to `analytics-baseline`.
* No alert delivery system. That belongs to `notification-system`.
* No external vendor requirement.
* No complex distributed tracing requirement.
* No per-user behavioral tracking.
* No billing/reporting analytics.
* No final SLO/SLA program.
* No advanced Prometheus/Grafana deployment requirement, though the design should be compatible.

## Metrics architecture

Recommended components:

```text id="t8gg56"
MetricsRecorder
MetricsRegistry
MetricsMiddleware
MetricsSnapshotService
AdminMetricsRouter
Optional AdminMetricsDashboard
```

Recommended flow:

```text id="uwggj5"
1. Request middleware records HTTP metrics.
2. Pipeline services record crawl/translation/export metrics.
3. Queue/worker services record queue and throughput metrics.
4. Cache layer records hit/miss metrics.
5. Public reader records latency/fallback/error metrics.
6. MetricsSnapshotService aggregates recent values.
7. Admin metrics endpoint returns privacy-safe summaries.
8. Optional dashboard renders summary cards and charts.
```

## Backend metric types

Recommended metric types:

```text id="og6sbh"
counter
gauge
histogram/timer
rate summary
```

Examples:

```text id="q7arc6"
counter: http_requests_total
gauge: queue_depth
histogram: http_request_duration_ms
timer: public_reader_response_duration_ms
```

If an existing metrics library exists, use it. If not, implement a lightweight in-process rolling metrics collector first.

## Storage model

Two acceptable V1 approaches:

### Option A: In-memory rolling metrics

Good for single-node or early V1.

Pros:

```text id="ln9b8v"
simple
fast
no migration
low implementation cost
```

Cons:

```text id="e6060v"
resets on restart
per-instance only
not durable
```

### Option B: Durable metrics snapshots

Good if multi-node or persistent admin history is needed.

Recommended table/model: `metrics_snapshots`

Fields:

```text id="fc1rx5"
id
window_start
window_end
metric_key
dimensions_json
count
sum
min
max
p50
p95
p99
value
created_at
```

For this baseline spec, in-memory metrics are acceptable if the admin endpoint clearly reports that values are since process start or within a rolling window.

## Recommended time windows

Admin summaries should support short operational windows.

Recommended windows:

```text id="jln1dt"
5m
15m
1h
24h
```

If full time-window storage is not available, support:

```text id="jkv8hg"
current rolling window
since process start
```

## HTTP request metrics

Instrument all backend requests.

Recommended metrics:

```text id="loyv4j"
http_requests_total
http_request_errors_total
http_request_duration_ms
http_requests_in_flight
```

Recommended dimensions:

```text id="9wc8i4"
method
route_template
status_class
```

Avoid high-cardinality dimensions:

```text id="v9r7gw"
raw URL
query string
user ID
email
novel title
chapter title
full IP address
```

Route template example:

```text id="nxhpah"
/api/novels/{novel_id}/chapters/{chapter_id}
```

Not:

```text id="a8r6k2"
/api/novels/123/chapters/456?token=...
```

## Queue and worker metrics

Track background processing health.

Recommended metrics:

```text id="vcq8w6"
queue_depth
queue_oldest_job_age_seconds
jobs_started_total
jobs_completed_total
jobs_failed_total
job_duration_ms
worker_heartbeat_age_seconds
active_workers
```

Recommended dimensions:

```text id="02r2o9"
queue_name
job_type
status
```

Avoid:

```text id="vko4id"
job ID
user ID
raw payload
provider API key
```

## Translation metrics

Track translation pipeline throughput and failures.

Recommended metrics:

```text id="dx893z"
translation_jobs_started_total
translation_jobs_completed_total
translation_jobs_failed_total
translation_chapters_completed_total
translation_tokens_input_total
translation_tokens_output_total
translation_duration_ms
translation_provider_errors_total
translation_quality_warnings_total
```

Recommended dimensions:

```text id="3ykvio"
provider
model_family
language_pair
status
error_category
```

Avoid raw model prompts, full provider model names if they expose private config, API keys, raw text, or user IDs.

## Crawl metrics

Track crawling/fetching/scraping reliability.

Recommended metrics:

```text id="m15we0"
crawl_jobs_started_total
crawl_jobs_completed_total
crawl_jobs_failed_total
crawl_chapters_discovered_total
crawl_chapters_succeeded_total
crawl_chapters_failed_total
crawl_duration_ms
crawl_fetch_errors_total
crawl_image_download_failures_total
```

Recommended dimensions:

```text id="gksjai"
source_key
status
error_category
```

This should integrate with persisted crawl diagnostics if `crawl-fetch-observability` exists.

## Cache metrics

Track cache effectiveness.

Recommended metrics:

```text id="58au7s"
cache_requests_total
cache_hits_total
cache_misses_total
cache_hit_rate
cache_evictions_total
cache_errors_total
```

Recommended dimensions:

```text id="oxkr6o"
cache_name
operation
```

Cache hit rate should be computed from hits and total requests.

## Public reader metrics

Track user-facing reader performance.

Recommended metrics:

```text id="i4a4l4"
public_reader_requests_total
public_reader_errors_total
public_reader_duration_ms
public_reader_fallback_served_total
public_reader_degraded_total
public_reader_unavailable_total
public_reader_snapshot_age_seconds
public_reader_annotation_failures_total
```

Recommended dimensions:

```text id="18dth8"
endpoint_type
status_class
degradation_state
```

Avoid novel/chapter title and raw user identifiers.

## Export metrics

Track export usage and failures.

Recommended metrics:

```text id="uyig8z"
export_requests_total
export_completed_total
export_failed_total
export_duration_ms
export_artifact_size_bytes
```

Recommended dimensions:

```text id="i3qx2u"
format
status
error_category
```

## Storage/object storage metrics

Track storage reliability.

Recommended metrics:

```text id="g4a9g9"
storage_operations_total
storage_errors_total
storage_operation_duration_ms
object_storage_errors_total
```

Recommended dimensions:

```text id="jqch31"
backend
operation
status
error_category
```

Do not expose bucket names or credentials in public/admin metrics unless explicitly safe.

## Admin metrics API

Recommended endpoint:

```http id="1x4aqu"
GET /admin/metrics/summary
```

Query params:

```text id="pma966"
window=5m|15m|1h|24h
```

Recommended response:

```json id="6ceakz"
{
  "window": "15m",
  "generated_at": "2026-07-10T00:00:00Z",
  "http": {
    "requests_total": 1200,
    "error_rate": 0.012,
    "p50_ms": 48,
    "p95_ms": 220,
    "p99_ms": 700
  },
  "queue": {
    "depth": 42,
    "oldest_job_age_seconds": 180,
    "jobs_completed": 300,
    "jobs_failed": 4
  },
  "translation": {
    "chapters_completed": 180,
    "jobs_failed": 2,
    "avg_duration_ms": 35000
  },
  "crawl": {
    "jobs_completed": 20,
    "jobs_failed": 1,
    "chapter_failures": 5
  },
  "cache": {
    "hit_rate": 0.83,
    "hits": 830,
    "misses": 170
  },
  "public_reader": {
    "requests_total": 800,
    "error_rate": 0.005,
    "p95_ms": 180,
    "fallback_served": 3,
    "unavailable": 1
  }
}
```

Optional endpoint:

```http id="3ea1y6"
GET /admin/metrics/timeseries
```

This is optional and can be deferred if the dashboard only needs current summaries.

## Optional Prometheus endpoint

If the project uses Prometheus or wants compatibility, add:

```http id="ntnz1i"
/metrics
```

This endpoint should be protected or deployment-restricted unless the deployment network already protects it.

Do not expose sensitive labels.

For V1 baseline, admin JSON summary is enough.

## Admin dashboard

Optional route:

```text id="nkn1bx"
/admin/metrics
```

Recommended dashboard cards:

```text id="xzs44e"
HTTP requests and error rate
HTTP p95 latency
queue depth and oldest job age
translation throughput and failures
crawl failures by category
cache hit rate
public reader p95 latency and fallback count
export failures
```

Charts are optional. A summary-card dashboard is enough for baseline.

## Privacy and cardinality rules

Metrics must be privacy-friendly.

Never use these as metric labels:

```text id="pi62gb"
user ID
email
IP address
full URL
query string
chapter title
novel title
raw source text
raw translated text
prompt text
provider API key
session ID
request token
```

Allowed low-cardinality labels:

```text id="sb7xd0"
route_template
method
status_class
job_type
queue_name
source_key
error_category
format
cache_name
degradation_state
```

## Error categories

Use existing structured error categories where possible.

Recommended categories:

```text id="eas50e"
timeout
validation_error
auth_error
permission_denied
not_found
rate_limited
provider_error
database_error
storage_error
queue_error
cache_error
crawl_error
translation_error
export_error
unknown
```

## Performance

Instrumentation should be low overhead.

Rules:

```text id="4ubf79"
metrics recording must not block main request paths significantly
metrics failures must not fail user requests
avoid synchronous durable writes per request
aggregate in memory before snapshotting if durable storage is used
bound metric label cardinality
```

## Security

Admin metrics APIs must be admin-only.

Rules:

```text id="0pjfu8"
non-admin -> 403
unauthenticated -> 401
disabled admin -> rejected according to existing auth
no secrets in responses
no raw stack traces
no per-user tracking
```

## Testing strategy

Tests should cover:

```text id="au9qtw"
HTTP middleware records request count
HTTP middleware records latency
HTTP middleware records error status
queue metrics record depth/job completion/failure
translation metrics record completion/failure
crawl metrics record success/failure/error category
cache metrics record hits/misses
public reader metrics record latency/fallback/unavailable
admin metrics summary authorization
admin metrics response shape
privacy/cardinality guardrails
metrics recorder failure does not fail request
```

## Rollout plan

1. Inspect existing logging/metrics libraries.
2. Add metrics recorder abstraction.
3. Add HTTP metrics middleware.
4. Instrument queue/worker.
5. Instrument translation pipeline.
6. Instrument crawl pipeline.
7. Instrument cache layer.
8. Instrument public reader.
9. Instrument export/storage where practical.
10. Add admin metrics summary endpoint.
11. Add optional admin dashboard.
12. Add tests.
13. Verify:

    * metrics are recorded.
    * admin summary shows key operational data.
    * metrics do not include user/private labels.
    * instrumentation failures do not break app behavior.
