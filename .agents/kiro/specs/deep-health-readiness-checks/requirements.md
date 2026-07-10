# requirements.md

# Requirements: Deep Health and Readiness Checks

## Introduction

The application needs production-grade health checks before V1 launch. The current shallow health behavior can report success even when critical dependencies are broken. The system must provide separate liveness, readiness, and admin diagnostic endpoints.

## Requirement 1: Liveness endpoint

### User story

As an operator, I want a lightweight liveness endpoint so that infrastructure can detect when the application process is alive.

### Acceptance criteria

1. WHEN `GET /health/live` is called and the application process is running THEN the system SHALL return `200 OK`.
2. WHEN `GET /health/live` is called THEN the system SHALL NOT require authentication.
3. WHEN `GET /health/live` is called THEN the system SHALL NOT check database, Redis, object storage, worker, or external dependencies.
4. WHEN `GET /health/live` returns successfully THEN the response SHALL include a simple status and timestamp.
5. WHEN dependencies are unavailable but the process can still serve requests THEN `/health/live` SHALL still return success.
6. WHEN the process cannot serve `/health/live` THEN the deployment platform MAY restart or replace the instance.

## Requirement 2: Readiness endpoint

### User story

As an operator, I want a readiness endpoint so that traffic is routed only to instances that can safely serve normal requests.

### Acceptance criteria

1. WHEN `GET /health/ready` is called and all required dependencies are healthy THEN the system SHALL return `200 OK`.
2. WHEN a required dependency is unhealthy THEN `/health/ready` SHALL return `503 Service Unavailable`.
3. WHEN a required dependency times out THEN `/health/ready` SHALL return `503 Service Unavailable`.
4. WHEN only optional dependencies are degraded THEN `/health/ready` MAY return `200 OK` with degraded status.
5. WHEN `/health/ready` is called THEN the response SHALL be safe for public/load-balancer consumption.
6. WHEN `/health/ready` returns dependency states THEN it SHALL NOT expose credentials, hostnames, filesystem paths, stack traces, or raw exception details.
7. WHEN `/health/ready` is called THEN it SHALL complete within the configured total health timeout.
8. WHEN the app is not ready to receive traffic THEN readiness SHALL fail even if liveness succeeds.

## Requirement 3: Admin health endpoint

### User story

As an admin, I want detailed health diagnostics so that I can understand which dependency is failing.

### Acceptance criteria

1. WHEN an admin calls `GET /admin/health` THEN the system SHALL return detailed health probe results.
2. WHEN an unauthenticated user calls `GET /admin/health` THEN the system SHALL return `401 Unauthorized`.
3. WHEN a non-admin authenticated user calls `GET /admin/health` THEN the system SHALL return `403 Forbidden`.
4. WHEN a disabled admin calls `GET /admin/health` THEN the system SHALL reject the request.
5. WHEN admin health returns probe details THEN each probe SHALL include status, latency, message, checked time, and safe metadata where available.
6. WHEN admin health includes errors THEN error details SHALL be safe and redacted.
7. WHEN admin health is called THEN the response SHALL include overall status.
8. WHEN admin health is called THEN the response SHALL complete within the configured total health timeout.

## Requirement 4: Health status model

### User story

As a developer, I want consistent health statuses so that endpoints and tests classify failures predictably.

### Acceptance criteria

1. WHEN a probe succeeds THEN it SHALL return `healthy`.
2. WHEN a probe has a non-critical problem THEN it SHALL return `degraded`.
3. WHEN a required probe fails THEN it SHALL return `unhealthy`.
4. WHEN a required probe times out THEN it SHALL return `unhealthy`.
5. WHEN an optional probe times out THEN it SHALL return `degraded` unless configured otherwise.
6. WHEN overall health is computed THEN required probe failures SHALL make the overall status unhealthy.
7. WHEN only optional probes are degraded THEN the overall status SHALL be degraded.
8. WHEN all probes are healthy THEN the overall status SHALL be healthy.

## Requirement 5: Probe timeout and isolation

### User story

As an operator, I want health checks to be bounded and isolated so that a hung dependency does not hang the health endpoint.

### Acceptance criteria

1. WHEN any probe runs THEN it SHALL use a configured timeout.
2. WHEN any probe exceeds its timeout THEN the system SHALL stop waiting for it and mark it as timed out.
3. WHEN one probe fails THEN other probes SHALL still be attempted where practical.
4. WHEN total health check execution exceeds the configured total timeout THEN the system SHALL return a safe timeout response.
5. WHEN a probe raises an exception THEN the system SHALL convert it into a structured failed probe result.
6. WHEN a probe fails THEN raw exception details SHALL not be exposed in public readiness responses.
7. WHEN admin health includes probe errors THEN secrets SHALL be redacted.

## Requirement 6: Database probe

### User story

As an operator, I want the health system to verify database connectivity so that readiness fails when core data access is unavailable.

### Acceptance criteria

1. WHEN database connectivity is healthy THEN the database probe SHALL return `healthy`.
2. WHEN the database connection cannot be acquired THEN the database probe SHALL return `unhealthy`.
3. WHEN a simple database query fails THEN the database probe SHALL return `unhealthy`.
4. WHEN a database query times out THEN the database probe SHALL return `unhealthy`.
5. WHEN the database probe succeeds THEN it SHALL record latency.
6. WHEN the database probe fails THEN it SHALL record a safe error category.
7. WHEN `/health/ready` depends on the database THEN database failure SHALL make readiness return `503`.

## Requirement 7: Migration probe

### User story

As an operator, I want readiness to detect missing or pending migrations so that incompatible application/schema versions do not receive traffic.

### Acceptance criteria

1. WHEN the database schema is at the expected migration revision THEN the migration probe SHALL return `healthy`.
2. WHEN the database schema is behind the expected migration revision THEN the migration probe SHALL return `unhealthy`.
3. WHEN the migration metadata table is missing in a production-like environment THEN the migration probe SHALL return `unhealthy`.
4. WHEN migration state cannot be determined but the database is reachable THEN the probe SHALL return `degraded` or `unhealthy` according to configuration.
5. WHEN migration state is returned in admin health THEN it MAY include safe current and expected revision identifiers.
6. WHEN migration state is returned publicly THEN it SHALL not expose unsafe internal details.
7. WHEN required migrations are pending THEN `/health/ready` SHALL return `503`.

## Requirement 8: Redis, queue, scheduler, and worker probe

### User story

As an operator, I want readiness to detect broken background job infrastructure so that crawl and translation processing failures are visible.

### Acceptance criteria

1. WHEN Redis or the configured queue backend is reachable THEN the queue probe SHALL return `healthy`.
2. WHEN Redis or the configured queue backend is unreachable and required THEN the queue probe SHALL return `unhealthy`.
3. WHEN worker heartbeat tracking exists and a recent heartbeat is available THEN the worker probe SHALL return `healthy`.
4. WHEN worker heartbeat tracking exists and the heartbeat is stale THEN the worker probe SHALL return `unhealthy` or `degraded` according to criticality.
5. WHEN scheduler heartbeat tracking exists and the scheduler heartbeat is stale THEN the scheduler probe SHALL return `unhealthy` or `degraded` according to criticality.
6. WHEN queue depth can be read safely THEN admin health SHOULD include queue depth.
7. WHEN queue infrastructure is required for normal operation and fails THEN `/health/ready` SHALL return `503`.
8. WHEN queue infrastructure is optional in the current deployment mode THEN failure MAY produce degraded status instead.

## Requirement 9: Storage probe

### User story

As an operator, I want health checks to verify persistent storage so that the app does not accept traffic when it cannot read or write required files.

### Acceptance criteria

1. WHEN configured storage root exists and is readable THEN the storage probe SHALL continue to write validation.
2. WHEN configured storage root is missing and required THEN the storage probe SHALL return `unhealthy`.
3. WHEN configured storage root is not readable THEN the storage probe SHALL return `unhealthy`.
4. WHEN configured storage root is not writable THEN the storage probe SHALL return `unhealthy`.
5. WHEN write probing is enabled THEN the storage probe SHALL create and delete a small temporary health-check file.
6. WHEN health-check file deletion fails THEN the probe SHALL return `degraded` or `unhealthy` according to cleanup risk.
7. WHEN storage probe succeeds THEN it SHALL not leave health-check files behind.
8. WHEN storage is required and unhealthy THEN `/health/ready` SHALL return `503`.

## Requirement 10: Disk space probe

### User story

As an operator, I want health checks to detect low disk space so that the system can be drained before writes fail.

### Acceptance criteria

1. WHEN free disk space is above warning threshold THEN disk probe SHALL return `healthy`.
2. WHEN free disk space is below warning threshold but above critical threshold THEN disk probe SHALL return `degraded`.
3. WHEN free disk space is below critical threshold THEN disk probe SHALL return `unhealthy`.
4. WHEN absolute minimum free bytes is configured and free bytes are below that value THEN disk probe SHALL return `unhealthy`.
5. WHEN disk probe returns admin metadata THEN it SHALL include safe free-space summary.
6. WHEN disk space is critical and storage is required THEN `/health/ready` SHALL return `503`.
7. WHEN disk probe cannot inspect the configured path THEN it SHALL return `unhealthy`.

## Requirement 11: Object storage probe

### User story

As an operator, I want health checks to verify object storage so that missing bucket access or broken credentials are detected.

### Acceptance criteria

1. WHEN object storage is configured and reachable THEN the object storage probe SHALL return `healthy`.
2. WHEN object storage is configured but credentials are missing THEN the probe SHALL return `unhealthy`.
3. WHEN object storage is configured but the bucket/container is unreachable THEN the probe SHALL return `unhealthy`.
4. WHEN object storage write probing is enabled THEN the probe SHALL perform a safe write/read/delete check.
5. WHEN object storage write probing is disabled THEN the probe SHALL perform a safe read/list/head check where possible.
6. WHEN object storage fails and is required for normal operation THEN `/health/ready` SHALL return `503`.
7. WHEN object storage fails but is optional THEN overall health MAY be degraded.
8. WHEN object storage errors are returned THEN credentials, signed URLs, and raw provider secrets SHALL be redacted.

## Requirement 12: Backup freshness health integration

### User story

As an operator, I want health diagnostics to show backup freshness so that recovery risk is visible in launch and operations checks.

### Acceptance criteria

1. WHEN backup status service exists THEN admin health SHALL include backup freshness status.
2. WHEN latest successful backup is fresh THEN the backup probe SHALL return `healthy`.
3. WHEN no successful backup exists THEN the backup probe SHALL return `unhealthy` or `degraded` according to environment configuration.
4. WHEN latest successful backup is stale THEN the backup probe SHALL return `unhealthy` or `degraded` according to launch policy.
5. WHEN latest restore verification failed THEN the backup probe SHALL return `unhealthy` or `degraded` according to launch policy.
6. WHEN backup service is not implemented yet THEN the probe SHALL be omitted or marked as degraded with a safe admin-only message.
7. WHEN readiness includes backup status THEN it SHALL not expose backup artifact paths or credentials.

## Requirement 13: Health response caching

### User story

As an operator, I want frequent health checks to avoid overloading dependencies while still reflecting current state.

### Acceptance criteria

1. WHEN readiness is called repeatedly within the configured cache TTL THEN the system MAY return cached probe results.
2. WHEN cached results are returned THEN admin health SHOULD include cache age or checked timestamp.
3. WHEN cache TTL expires THEN the next health call SHALL refresh probe results.
4. WHEN `refresh=true` is supported for admin health THEN the system SHALL bypass the cache for admin requests.
5. WHEN liveness is called THEN it SHALL not require expensive cached dependency results.
6. WHEN cache is used THEN stale cache SHALL not persist beyond the configured TTL.

## Requirement 14: Security and redaction

### User story

As a security-conscious operator, I want health checks to be useful without leaking infrastructure secrets.

### Acceptance criteria

1. WHEN public health endpoints return responses THEN they SHALL not include credentials, tokens, database URLs, raw hostnames, filesystem paths, stack traces, or raw exception messages.
2. WHEN admin health returns responses THEN it SHALL still redact credentials, tokens, signed URLs, and secrets.
3. WHEN probe failures are logged THEN logs SHALL redact secrets.
4. WHEN object storage config is invalid THEN returned messages SHALL not expose access keys or secret keys.
5. WHEN database errors occur THEN public readiness SHALL not expose raw SQL errors.
6. WHEN filesystem errors occur THEN public readiness SHALL not expose sensitive absolute paths.
7. WHEN health metadata is included THEN it SHALL be limited to operationally safe values.

## Requirement 15: Optional admin health UI

### User story

As an admin, I want a simple health page so that I can quickly inspect dependency status without reading raw JSON.

### Acceptance criteria

1. WHEN the admin frontend exists and this UI is in scope THEN the system SHALL add an admin health page.
2. WHEN an admin opens the health page THEN the page SHALL show overall status.
3. WHEN dependency checks exist THEN the page SHALL show each check status, latency, and safe message.
4. WHEN a check is degraded or unhealthy THEN the page SHALL visually distinguish it.
5. WHEN a non-admin opens the page THEN access SHALL be blocked.
6. WHEN the health endpoint returns an error THEN the page SHALL show a safe error state.

## Requirement 16: Test coverage

### User story

As a maintainer, I want automated tests for health checks so that operational safety does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover liveness success.
2. WHEN tests run THEN they SHALL cover readiness healthy response.
3. WHEN tests run THEN they SHALL cover database failure.
4. WHEN tests run THEN they SHALL cover migration pending failure.
5. WHEN tests run THEN they SHALL cover queue or worker failure when required.
6. WHEN tests run THEN they SHALL cover storage failure.
7. WHEN tests run THEN they SHALL cover disk warning and critical thresholds.
8. WHEN tests run THEN they SHALL cover object storage failure when configured.
9. WHEN tests run THEN they SHALL cover probe timeout behavior.
10. WHEN tests run THEN they SHALL cover public response redaction.
11. WHEN tests run THEN they SHALL cover admin health authorization.
12. WHEN tests run THEN they SHALL cover cache behavior if caching is implemented.
13. WHEN backup integration exists THEN tests SHALL cover fresh and stale backup health states.

## Requirement 17: Launch readiness

### User story

As a deployer, I want health checks verified before V1 so that production traffic only reaches working instances.

### Acceptance criteria

1. WHEN V1 launch verification is performed THEN `/health/live` SHALL return `200`.
2. WHEN V1 launch verification is performed and dependencies are healthy THEN `/health/ready` SHALL return `200`.
3. WHEN a required dependency is deliberately broken in staging THEN `/health/ready` SHALL return `503`.
4. WHEN admin health is opened by an admin THEN it SHALL show detailed dependency status.
5. WHEN admin health is opened by a non-admin THEN it SHALL be blocked.
6. WHEN migrations are pending in staging THEN readiness SHALL fail.
7. WHEN storage is not writable in staging THEN readiness SHALL fail.
8. WHEN public health endpoints are inspected THEN they SHALL not leak secrets.
9. WHEN deployment configuration is updated THEN liveness and readiness probes SHALL point to the new endpoints.
