# tasks.md

# Tasks: Deep Health and Readiness Checks

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing health endpoint implementation and route registration.
  * [ ] 0.2 Inspect existing admin auth guard and admin router conventions.
  * [ ] 0.3 Inspect database connection/session utilities.
  * [ ] 0.4 Inspect migration tooling and how current/latest revisions can be read.
  * [ ] 0.5 Inspect Redis, queue, worker, scheduler, and activity runtime infrastructure.
  * [ ] 0.6 Inspect storage backend abstraction and local/object storage configuration.
  * [ ] 0.7 Inspect deployment config examples for existing health checks.
  * [ ] 0.8 Inspect logging and structured error/redaction conventions.
  * [ ] 0.9 Inspect existing backend and frontend test patterns.

* [ ] 1. Define health configuration

  * [ ] 1.1 Add `HEALTH_PROBE_TIMEOUT_MS`. (REQ-5)
  * [ ] 1.2 Add `HEALTH_TOTAL_TIMEOUT_MS`. (REQ-5)
  * [ ] 1.3 Add `HEALTH_CACHE_TTL_SECONDS`. (REQ-13)
  * [ ] 1.4 Add disk warning threshold config. (REQ-10)
  * [ ] 1.5 Add disk critical threshold config. (REQ-10)
  * [ ] 1.6 Add optional absolute minimum free bytes config. (REQ-10)
  * [ ] 1.7 Add worker heartbeat freshness threshold config if worker heartbeat exists. (REQ-8)
  * [ ] 1.8 Add scheduler heartbeat freshness threshold config if scheduler heartbeat exists. (REQ-8)
  * [ ] 1.9 Add flags for object storage write probe behavior if needed. (REQ-11)
  * [ ] 1.10 Add environment mode behavior for strict migration/backup checks. (REQ-7, REQ-12)

* [ ] 2. Define health models and contracts

  * [ ] 2.1 Define probe statuses: `healthy`, `degraded`, `unhealthy`. (REQ-4)
  * [ ] 2.2 Define overall health status calculation. (REQ-4)
  * [ ] 2.3 Define dependency criticality values: `required`, `optional`, `informational`. (REQ-4)
  * [ ] 2.4 Define internal `HealthProbeResult` model. (REQ-3, REQ-4)
  * [ ] 2.5 Define public readiness response model. (REQ-2, REQ-14)
  * [ ] 2.6 Define admin health response model. (REQ-3, REQ-14)
  * [ ] 2.7 Define stable error categories. (REQ-5, REQ-14)
  * [ ] 2.8 Define redaction helpers for public and admin health responses. (REQ-14)

* [ ] 3. Implement probe runner

  * [ ] 3.1 Add common probe interface. (REQ-4)
  * [ ] 3.2 Add timeout wrapper per probe. (REQ-5)
  * [ ] 3.3 Add total timeout handling for full health check execution. (REQ-5)
  * [ ] 3.4 Convert exceptions into structured probe results. (REQ-5)
  * [ ] 3.5 Ensure one failed probe does not prevent other probes from running where practical. (REQ-5)
  * [ ] 3.6 Add latency measurement for every probe. (REQ-3, REQ-5)
  * [ ] 3.7 Add checked timestamp for every probe. (REQ-3)
  * [ ] 3.8 Add tests for success, exception, timeout, and partial failure behavior. (REQ-5, REQ-16)

* [ ] 4. Implement liveness endpoint

  * [ ] 4.1 Add `GET /health/live`. (REQ-1)
  * [ ] 4.2 Ensure liveness does not require authentication. (REQ-1)
  * [ ] 4.3 Ensure liveness does not call database, Redis, object storage, worker, or external dependencies. (REQ-1)
  * [ ] 4.4 Return simple status, service name, and timestamp. (REQ-1)
  * [ ] 4.5 Add tests proving liveness succeeds even when dependency probes are failing. (REQ-1, REQ-16)

* [ ] 5. Implement database probe

  * [ ] 5.1 Add database connection acquisition check. (REQ-6)
  * [ ] 5.2 Add simple query check such as `SELECT 1`. (REQ-6)
  * [ ] 5.3 Add timeout handling. (REQ-6)
  * [ ] 5.4 Add latency measurement. (REQ-6)
  * [ ] 5.5 Add safe error categorization for connection failure, query failure, and timeout. (REQ-6, REQ-14)
  * [ ] 5.6 Add tests for healthy database, connection failure, query failure, and timeout. (REQ-6, REQ-16)

* [ ] 6. Implement migration probe

  * [ ] 6.1 Identify current migration revision from the database. (REQ-7)
  * [ ] 6.2 Identify expected/latest migration revision from migration tooling. (REQ-7)
  * [ ] 6.3 Compare current and expected revisions. (REQ-7)
  * [ ] 6.4 Return healthy when schema is up to date. (REQ-7)
  * [ ] 6.5 Return unhealthy when required migrations are pending. (REQ-7)
  * [ ] 6.6 Handle missing migration table according to environment/config. (REQ-7)
  * [ ] 6.7 Redact unsafe migration errors from public readiness. (REQ-7, REQ-14)
  * [ ] 6.8 Add tests for up-to-date, pending, missing metadata, and unknown migration states. (REQ-7, REQ-16)

* [ ] 7. Implement Redis/queue probe

  * [ ] 7.1 Detect configured Redis or queue backend. (REQ-8)
  * [ ] 7.2 Add ping or equivalent reachability check. (REQ-8)
  * [ ] 7.3 Add queue depth read if supported safely. (REQ-8)
  * [ ] 7.4 Classify queue backend as required or optional based on configuration. (REQ-8)
  * [ ] 7.5 Return unhealthy when required queue backend is unreachable. (REQ-8)
  * [ ] 7.6 Return degraded when optional queue backend is unreachable. (REQ-8)
  * [ ] 7.7 Add tests for reachable, unreachable required, unreachable optional, and timeout states. (REQ-8, REQ-16)

* [ ] 8. Implement worker and scheduler heartbeat probes

  * [ ] 8.1 Inspect whether worker heartbeat data already exists. (REQ-8)
  * [ ] 8.2 Add worker heartbeat freshness check if heartbeat data exists. (REQ-8)
  * [ ] 8.3 Add scheduler heartbeat freshness check if heartbeat data exists. (REQ-8)
  * [ ] 8.4 If heartbeat data does not exist, return degraded or omit probe according to current architecture. (REQ-8)
  * [ ] 8.5 Add admin metadata such as heartbeat age when safe. (REQ-8, REQ-14)
  * [ ] 8.6 Add tests for fresh heartbeat, stale heartbeat, missing heartbeat, and optional mode. (REQ-8, REQ-16)

* [ ] 9. Implement storage probe

  * [ ] 9.1 Resolve configured storage root. (REQ-9)
  * [ ] 9.2 Check storage root existence. (REQ-9)
  * [ ] 9.3 Check storage root readability. (REQ-9)
  * [ ] 9.4 Check storage root writability. (REQ-9)
  * [ ] 9.5 Write a small temporary health-check file in a safe health-check path. (REQ-9)
  * [ ] 9.6 Read the temporary health-check file if useful. (REQ-9)
  * [ ] 9.7 Delete the temporary health-check file. (REQ-9)
  * [ ] 9.8 Ensure probe does not modify user content. (REQ-9)
  * [ ] 9.9 Add tests for missing root, unreadable root, unwritable root, write failure, delete failure, and success. (REQ-9, REQ-16)

* [ ] 10. Implement disk space probe

  * [ ] 10.1 Resolve disk path to check from storage/config. (REQ-10)
  * [ ] 10.2 Measure free disk percentage and free bytes. (REQ-10)
  * [ ] 10.3 Return healthy above warning threshold. (REQ-10)
  * [ ] 10.4 Return degraded below warning threshold. (REQ-10)
  * [ ] 10.5 Return unhealthy below critical threshold. (REQ-10)
  * [ ] 10.6 Apply absolute minimum free bytes threshold if configured. (REQ-10)
  * [ ] 10.7 Redact sensitive filesystem paths in public response. (REQ-10, REQ-14)
  * [ ] 10.8 Add tests for healthy, warning, critical, absolute minimum, and inspect failure states. (REQ-10, REQ-16)

* [ ] 11. Implement object storage probe

  * [ ] 11.1 Detect whether object storage is configured. (REQ-11)
  * [ ] 11.2 Validate required object storage config without exposing secrets. (REQ-11, REQ-14)
  * [ ] 11.3 Add reachability probe using safe head/list/read operation. (REQ-11)
  * [ ] 11.4 Add optional write/read/delete probe if configured and safe. (REQ-11)
  * [ ] 11.5 Classify object storage as required if it is the primary storage backend. (REQ-11)
  * [ ] 11.6 Return unhealthy when required object storage fails. (REQ-11)
  * [ ] 11.7 Return degraded when optional object storage fails. (REQ-11)
  * [ ] 11.8 Add tests with fake object storage client for success, config failure, auth failure, reachability failure, and write probe failure. (REQ-11, REQ-16)

* [ ] 12. Integrate backup freshness probe

  * [ ] 12.1 Check whether backup status service exists. (REQ-12)
  * [ ] 12.2 Add backup freshness probe when backup status service is available. (REQ-12)
  * [ ] 12.3 Return healthy when latest successful backup is fresh. (REQ-12)
  * [ ] 12.4 Return degraded or unhealthy when no successful backup exists according to environment/config. (REQ-12)
  * [ ] 12.5 Return degraded or unhealthy when latest successful backup is stale. (REQ-12)
  * [ ] 12.6 Return degraded or unhealthy when latest restore verification failed. (REQ-12)
  * [ ] 12.7 Omit or mark degraded when backup status service is not implemented yet. (REQ-12)
  * [ ] 12.8 Add tests for fresh, stale, missing, failed, and unavailable backup service states. (REQ-12, REQ-16)

* [ ] 13. Implement health aggregation service

  * [ ] 13.1 Add service method for liveness response. (REQ-1)
  * [ ] 13.2 Add service method for readiness response. (REQ-2)
  * [ ] 13.3 Add service method for admin health response. (REQ-3)
  * [ ] 13.4 Apply dependency criticality rules. (REQ-4)
  * [ ] 13.5 Map overall status to HTTP status code. (REQ-2, REQ-4)
  * [ ] 13.6 Generate public-safe summarized readiness output. (REQ-2, REQ-14)
  * [ ] 13.7 Generate admin-safe detailed output. (REQ-3, REQ-14)
  * [ ] 13.8 Add tests for aggregation and HTTP status mapping. (REQ-2, REQ-3, REQ-4, REQ-16)

* [ ] 14. Implement health response caching

  * [ ] 14.1 Add short TTL cache for readiness results if needed. (REQ-13)
  * [ ] 14.2 Add optional short TTL cache for admin health results. (REQ-13)
  * [ ] 14.3 Include checked timestamp and cache age in admin health when cached. (REQ-13)
  * [ ] 14.4 Support `refresh=true` for admin health if chosen. (REQ-13)
  * [ ] 14.5 Ensure cache expires after configured TTL. (REQ-13)
  * [ ] 14.6 Add tests for cache hit, cache expiry, and refresh bypass. (REQ-13, REQ-16)

* [ ] 15. Implement readiness endpoint

  * [ ] 15.1 Add `GET /health/ready`. (REQ-2)
  * [ ] 15.2 Ensure readiness does not require authentication. (REQ-2)
  * [ ] 15.3 Run required probes through health aggregation service. (REQ-2)
  * [ ] 15.4 Return `200` when required dependencies are healthy. (REQ-2)
  * [ ] 15.5 Return `503` when required dependencies are unhealthy. (REQ-2)
  * [ ] 15.6 Return public-safe response only. (REQ-2, REQ-14)
  * [ ] 15.7 Add tests for healthy, degraded, unhealthy, timeout, and redacted readiness responses. (REQ-2, REQ-14, REQ-16)

* [ ] 16. Implement admin health endpoint

  * [ ] 16.1 Add `GET /admin/health`. (REQ-3)
  * [ ] 16.2 Protect endpoint with admin auth. (REQ-3)
  * [ ] 16.3 Reject unauthenticated users. (REQ-3)
  * [ ] 16.4 Reject non-admin users. (REQ-3)
  * [ ] 16.5 Reject disabled admins if disabled-user auth handling exists. (REQ-3)
  * [ ] 16.6 Return detailed safe probe results. (REQ-3, REQ-14)
  * [ ] 16.7 Include overall status and total duration. (REQ-3)
  * [ ] 16.8 Add tests for admin, non-admin, unauthenticated, disabled admin, healthy, degraded, and unhealthy responses. (REQ-3, REQ-16)

* [ ] 17. Add optional admin health UI

  * [ ] 17.1 Add `/admin/health` frontend route if admin frontend exists. (REQ-15)
  * [ ] 17.2 Add API client method for admin health endpoint. (REQ-15)
  * [ ] 17.3 Render overall status. (REQ-15)
  * [ ] 17.4 Render dependency status cards/table. (REQ-15)
  * [ ] 17.5 Render latency, checked time, and safe messages. (REQ-15)
  * [ ] 17.6 Add degraded/unhealthy visual states. (REQ-15)
  * [ ] 17.7 Add refresh button if `refresh=true` is supported. (REQ-13, REQ-15)
  * [ ] 17.8 Add frontend tests for admin access, blocked access, healthy display, and failure display. (REQ-15, REQ-16)

* [ ] 18. Add security and redaction hardening

  * [ ] 18.1 Add redaction helper for credentials, URLs, tokens, signed URLs, and secrets. (REQ-14)
  * [ ] 18.2 Ensure public readiness never returns raw exception messages. (REQ-14)
  * [ ] 18.3 Ensure admin health still redacts secrets. (REQ-14)
  * [ ] 18.4 Redact database connection details from errors. (REQ-14)
  * [ ] 18.5 Redact object storage credentials and signed URLs from errors. (REQ-14)
  * [ ] 18.6 Redact sensitive filesystem paths from public output. (REQ-14)
  * [ ] 18.7 Add tests for redaction in public and admin outputs. (REQ-14, REQ-16)

* [ ] 19. Update deployment and operations docs

  * [ ] 19.1 Document `/health/live` usage for liveness probes. (REQ-17)
  * [ ] 19.2 Document `/health/ready` usage for readiness/load balancer probes. (REQ-17)
  * [ ] 19.3 Document `/admin/health` usage for operators. (REQ-17)
  * [ ] 19.4 Document expected healthy/degraded/unhealthy meanings. (REQ-4, REQ-17)
  * [ ] 19.5 Document required environment variables and thresholds. (REQ-17)
  * [ ] 19.6 Update Docker/Kubernetes/deployment examples if present. (REQ-17)
  * [ ] 19.7 Add V1 launch checklist entries for dependency failure verification. (REQ-17)

* [ ] 20. Backend test coverage pass

  * [ ] 20.1 Add liveness tests. (REQ-1, REQ-16)
  * [ ] 20.2 Add readiness healthy/unhealthy tests. (REQ-2, REQ-16)
  * [ ] 20.3 Add admin health authorization tests. (REQ-3, REQ-16)
  * [ ] 20.4 Add status aggregation tests. (REQ-4, REQ-16)
  * [ ] 20.5 Add timeout and exception tests. (REQ-5, REQ-16)
  * [ ] 20.6 Add database probe tests. (REQ-6, REQ-16)
  * [ ] 20.7 Add migration probe tests. (REQ-7, REQ-16)
  * [ ] 20.8 Add Redis/queue/worker probe tests. (REQ-8, REQ-16)
  * [ ] 20.9 Add storage probe tests. (REQ-9, REQ-16)
  * [ ] 20.10 Add disk probe tests. (REQ-10, REQ-16)
  * [ ] 20.11 Add object storage probe tests. (REQ-11, REQ-16)
  * [ ] 20.12 Add backup freshness probe tests if backup integration exists. (REQ-12, REQ-16)
  * [ ] 20.13 Add cache tests if health response caching is implemented. (REQ-13, REQ-16)
  * [ ] 20.14 Add redaction tests. (REQ-14, REQ-16)

* [ ] 21. Release verification

  * [ ] 21.1 Start the app in staging with healthy dependencies. (REQ-17)
  * [ ] 21.2 Verify `GET /health/live` returns `200`. (REQ-1, REQ-17)
  * [ ] 21.3 Verify `GET /health/ready` returns `200`. (REQ-2, REQ-17)
  * [ ] 21.4 Verify admin can access `GET /admin/health`. (REQ-3, REQ-17)
  * [ ] 21.5 Verify non-admin cannot access `GET /admin/health`. (REQ-3, REQ-17)
  * [ ] 21.6 Break database connectivity in staging and verify readiness returns `503`. (REQ-6, REQ-17)
  * [ ] 21.7 Simulate pending migration and verify readiness returns `503`. (REQ-7, REQ-17)
  * [ ] 21.8 Break Redis/queue in staging and verify expected readiness/admin health behavior. (REQ-8, REQ-17)
  * [ ] 21.9 Make storage unwritable in staging and verify readiness returns `503`. (REQ-9, REQ-17)
  * [ ] 21.10 Simulate low disk threshold and verify degraded/unhealthy behavior. (REQ-10, REQ-17)
  * [ ] 21.11 Break object storage config if configured and verify expected behavior. (REQ-11, REQ-17)
  * [ ] 21.12 Verify public health responses do not expose secrets or stack traces. (REQ-14, REQ-17)
  * [ ] 21.13 Update deployment health probe URLs to `/health/live` and `/health/ready`. (REQ-17)
  * [ ] 21.14 Mark `deep-health-readiness-checks` launch blocker complete only after tests and manual staging verification pass.
