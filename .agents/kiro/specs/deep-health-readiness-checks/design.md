# design.md

# Design: Deep Health and Readiness Checks

## Overview

`deep-health-readiness-checks` replaces shallow health checks with production-ready liveness, readiness, and admin diagnostics.

The current shallow health endpoint is not enough for V1 launch because it can report success while critical dependencies are broken. The application needs distinct endpoints for process liveness, traffic readiness, and admin-only deep dependency inspection.

This spec adds:

```text id="srcduz"
/health/live
/health/ready
/admin/health
```

The system should check core runtime dependencies:

```text id="3clzjg"
application process
database
Redis or worker backend
storage
database migrations
disk space
object storage
backup freshness signal when available
```

## Goals

* Add a lightweight liveness endpoint.
* Add a readiness endpoint that confirms the app can safely receive traffic.
* Add an admin-only deep health endpoint with detailed dependency probes.
* Add structured probe results with status, latency, message, and safe metadata.
* Add timeouts so health checks cannot hang.
* Add degraded/unhealthy classification.
* Integrate migration status checks.
* Integrate storage and object-storage checks.
* Integrate worker/queue availability checks.
* Add tests for healthy, degraded, unhealthy, timeout, and auth behavior.

## Non-goals

* No full metrics dashboard. That belongs to `metrics-dashboard-baseline`.
* No complete alert notification system. That belongs to `notification-system`.
* No backup implementation. That belongs to `scheduled-backups-and-restore-drills`.
* No public exposure of sensitive infrastructure details.
* No auto-repair of failed services.
* No deployment-specific Kubernetes/Render/Fly/Railway configuration beyond endpoint compatibility.

## Endpoint model

### Liveness endpoint

```http id="83qpos"
GET /health/live
```

Purpose:

* Confirms the application process is alive.
* Should be fast and shallow.
* Should not depend on database, Redis, S3, or external services.
* Suitable for container liveness probes.

Expected response when process is alive:

```json id="wsqcln"
{
  "status": "ok",
  "service": "novelai",
  "timestamp": "2026-07-10T00:00:00Z"
}
```

If the process cannot serve this endpoint, the infrastructure will naturally treat the service as dead.

### Readiness endpoint

```http id="vyov5n"
GET /health/ready
```

Purpose:

* Confirms the app is ready to serve normal traffic.
* Checks required dependencies.
* Should return non-2xx when traffic should not be routed to this instance.
* Suitable for container readiness probes and load balancer health checks.

Recommended response:

```json id="w3q6zj"
{
  "status": "ready",
  "timestamp": "2026-07-10T00:00:00Z",
  "checks": {
    "database": "healthy",
    "migrations": "healthy",
    "storage": "healthy",
    "worker": "healthy"
  }
}
```

The public readiness endpoint should be safe and concise. It should not expose hostnames, credentials, bucket names, filesystem paths, stack traces, SQL errors, or internal exception details.

### Admin health endpoint

```http id="1vz1zy"
GET /admin/health
```

Purpose:

* Gives admins/operators detailed dependency health.
* Requires admin authentication.
* Includes detailed probe result objects.
* Supports launch verification and incident debugging.

Recommended response:

```json id="50cw4v"
{
  "status": "healthy",
  "timestamp": "2026-07-10T00:00:00Z",
  "duration_ms": 42,
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 8,
      "message": "Database query succeeded"
    },
    "migrations": {
      "status": "healthy",
      "latency_ms": 5,
      "message": "Database schema is up to date",
      "metadata": {
        "current_revision": "abc123",
        "expected_revision": "abc123"
      }
    },
    "worker": {
      "status": "healthy",
      "latency_ms": 10,
      "message": "Queue backend reachable",
      "metadata": {
        "queue_depth": 3
      }
    },
    "storage": {
      "status": "healthy",
      "latency_ms": 6,
      "message": "Storage read/write probe succeeded"
    },
    "disk": {
      "status": "healthy",
      "latency_ms": 1,
      "message": "Disk has sufficient free space",
      "metadata": {
        "free_percent": 72
      }
    },
    "object_storage": {
      "status": "healthy",
      "latency_ms": 12,
      "message": "Object storage reachable"
    }
  }
}
```

## Status model

Use three internal health states:

```text id="x72ijz"
healthy
degraded
unhealthy
```

Public endpoint mapping:

```text id="4sbb57"
healthy   -> HTTP 200
degraded  -> HTTP 200 or 503 depending on whether normal traffic is safe
unhealthy -> HTTP 503
```

Recommended readiness behavior:

* `healthy`: return `200`.
* `degraded`: return `200` only if the app can still safely serve normal user traffic.
* `unhealthy`: return `503`.

For V1, if a required dependency is degraded enough that user requests may fail, readiness should return `503`.

## Probe result contract

All deep probes should return a consistent shape.

Recommended internal object:

```text id="qa6kr8"
name
status
latency_ms
message
metadata
error_category
checked_at
```

Recommended JSON shape:

```json id="jvjcqe"
{
  "status": "healthy",
  "latency_ms": 8,
  "message": "Database query succeeded",
  "metadata": {},
  "error_category": null,
  "checked_at": "2026-07-10T00:00:00Z"
}
```

For public readiness responses, return only summarized check states.

For admin responses, return detailed but safe probe results.

## Required probes

### Process probe

Used by `/health/live`.

The process probe should verify:

```text id="b07k7z"
server can execute request handler
clock/timestamp generation works
```

It should not check external dependencies.

### Database probe

The database probe should verify:

```text id="708nsb"
database connection can be acquired
simple query succeeds
query completes within timeout
```

Recommended query:

```sql id="mmx2ax"
SELECT 1
```

The probe should not perform expensive table scans.

### Migration probe

The migration probe should verify:

```text id="9b6hsd"
current database revision is known
expected/latest migration revision is known
database is not behind expected revision
```

Possible statuses:

```text id="3vku2a"
healthy: current revision equals expected revision
degraded: revision cannot be determined but database is reachable
unhealthy: database is behind required migration or migration table is missing unexpectedly
```

During development, missing migration metadata may be configurable. In production, it should be unhealthy.

### Redis/queue/worker probe

The worker probe should verify the configured queue backend.

Depending on existing architecture, check one or more:

```text id="utmgox"
Redis ping succeeds
queue backend can report depth
worker heartbeat exists
recent worker heartbeat is fresh
scheduler heartbeat is fresh
```

Recommended V1 behavior:

* If background translation/crawl jobs require Redis/workers, missing Redis or stale workers should make readiness unhealthy.
* If workers are optional in the current deployment mode, status may be degraded instead.

### Storage probe

The storage probe should verify local or configured application storage.

Check:

```text id="balv8h"
storage root exists
storage root is readable
storage root is writable
small temporary probe file can be written and deleted
```

The probe file should use a safe health-check path, such as:

```text id="p6xpth"
.healthcheck/
```

The probe must not modify user content.

### Disk probe

The disk probe should verify available disk capacity.

Recommended thresholds:

```text id="5b6vwc"
healthy: free space above warning threshold
degraded: free space below warning threshold
unhealthy: free space below critical threshold
```

Recommended config:

```text id="8de2x9"
HEALTH_DISK_WARNING_FREE_PERCENT=15
HEALTH_DISK_CRITICAL_FREE_PERCENT=5
HEALTH_DISK_MIN_FREE_BYTES=
```

Use both percentage and absolute byte thresholds if practical.

### Object storage probe

If object storage is configured, the probe should verify:

```text id="fu4a3v"
credentials/config are present
bucket/container is reachable
small read/write/delete probe succeeds when allowed
```

If write probes are too expensive or not permitted, use a safe list/head operation.

The endpoint should not expose object storage credentials, raw bucket secrets, signed URLs, or full provider error details.

### Backup freshness probe

If `scheduled-backups-and-restore-drills` is implemented, deep health should consume its backup status service.

Check:

```text id="8omuti"
latest successful backup exists
latest successful backup is not stale
latest restore verification status is acceptable
```

If backup status service is not implemented yet, this probe can be omitted or return `degraded` with a clear admin-only message.

## Dependency criticality

Each probe should have a criticality level.

Recommended levels:

```text id="yrxvua"
required
optional
informational
```

Readiness should fail when a `required` probe is unhealthy.

Default criticality:

```text id="jji3pe"
process: required
database: required
migrations: required
storage: required
disk: required
worker: required if background jobs are required for normal operation
object_storage: required if configured as primary storage
backup_freshness: required for admin health, degraded for readiness unless release policy says otherwise
```

## Timeout behavior

Every deep probe must have a timeout.

Recommended config:

```text id="e7knj7"
HEALTH_PROBE_TIMEOUT_MS=1000
HEALTH_TOTAL_TIMEOUT_MS=3000
```

Behavior:

* A timed-out required probe is unhealthy.
* A timed-out optional probe is degraded.
* Timeout errors should be categorized as `timeout`.
* Health endpoint should return quickly even when dependencies hang.

## Caching behavior

Health checks can be called frequently by load balancers. Avoid expensive repeated checks.

Recommended caching:

```text id="75bdt7"
liveness: no cache needed
readiness: cache for 1-5 seconds
admin health: optional cache for 1-5 seconds, with force refresh query if desired
```

Optional query:

```http id="j34dwz"
GET /admin/health?refresh=true
```

If caching is implemented, responses should include:

```text id="giq8b2"
checked_at
cache_age_ms
```

## Error categories

Recommended error categories:

```text id="xgzmef"
timeout
connection_failed
authentication_failed
permission_denied
migration_pending
migration_unknown
read_failed
write_failed
delete_failed
disk_low
disk_full
worker_unreachable
worker_stale
queue_unreachable
object_storage_unreachable
backup_stale
backup_failed
configuration_error
unknown
```

## Security and redaction

Public health endpoints must not leak internal details.

Public endpoints may expose:

```text id="6v9lz7"
overall status
timestamp
simple dependency names
simple dependency states
```

Public endpoints must not expose:

```text id="v84kel"
database URLs
hostnames
ports
user emails
bucket names if considered sensitive
filesystem paths
stack traces
raw exception messages
credentials
tokens
full SQL errors
signed URLs
```

Admin health may expose more operational detail, but still must redact secrets.

## Frontend/admin UI

A full dashboard belongs to `metrics-dashboard-baseline`, but this spec may add a simple admin health page if an admin frontend already exists.

Recommended route:

```text id="ky4o5j"
/admin/health
```

Display:

```text id="4h9itv"
overall status
dependency cards
latency
last checked time
safe messages
degraded/unhealthy reasons
```

This UI is optional for this spec if the admin JSON endpoint is implemented.

## Integration with deployment

The endpoints are designed for common deployment systems.

Recommended use:

```text id="guyjxi"
liveness probe: /health/live
readiness probe: /health/ready
operator diagnostics: /admin/health
```

`/health/live` should almost never fail unless the process is broken.

`/health/ready` should fail when the instance should be removed from traffic.

`/admin/health` should help explain why readiness is failing.

## Testing strategy

Backend tests should cover:

```text id="h2zkyn"
liveness always succeeds while app is running
readiness healthy path
database failure
migration pending
storage write failure
disk low/degraded
disk critical/unhealthy
Redis/queue failure
worker heartbeat stale
object storage failure
backup stale if backup service is available
probe timeout
public response redaction
admin-only detailed health access
```

## Rollout plan

1. Add health settings.
2. Add health result/status models.
3. Add probe runner with timeout and redaction.
4. Add liveness endpoint.
5. Add database probe.
6. Add migration probe.
7. Add storage probe.
8. Add disk probe.
9. Add Redis/queue/worker probe.
10. Add object storage probe if configured.
11. Add backup freshness integration when available.
12. Add readiness endpoint.
13. Add admin health endpoint.
14. Add tests.
15. Update deployment docs to use `/health/live` and `/health/ready`.
16. Verify V1 launch checklist:

    * Liveness returns `200`.
    * Readiness returns `200` only when required dependencies are healthy.
    * Admin health shows dependency detail.
    * Failed dependency changes readiness state.
    * Public responses do not leak secrets.
