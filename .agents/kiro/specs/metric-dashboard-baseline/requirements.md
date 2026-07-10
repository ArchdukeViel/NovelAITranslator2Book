# requirements.md

# Requirements: Metrics Dashboard Baseline

## Introduction

The application needs baseline operational metrics before scale. Operators should be able to see request latency, error rate, queue depth, translation throughput, crawl failures, cache hit rate, public reader performance, and export/storage failures through admin-only metrics surfaces.

## Requirement 1: Metrics recorder abstraction

### User story

As a developer, I want a central metrics recorder so services can record operational metrics consistently.

### Acceptance criteria

1. WHEN application code records a counter THEN the metrics recorder SHALL increment the counter safely.
2. WHEN application code records a gauge THEN the metrics recorder SHALL store or publish the gauge value safely.
3. WHEN application code records a duration THEN the metrics recorder SHALL record timing data safely.
4. WHEN metrics recording fails THEN the original application operation SHALL not fail solely because of metrics.
5. WHEN metrics labels are provided THEN the recorder SHALL enforce or support low-cardinality label rules.
6. WHEN no external metrics backend is configured THEN the app SHALL still support baseline in-process metrics or no-op safe recording.
7. WHEN metrics are queried through admin summary THEN values SHALL be aggregated into a JSON-compatible shape.

## Requirement 2: HTTP request metrics

### User story

As an operator, I want request latency and error rate metrics so I can detect API performance and reliability issues.

### Acceptance criteria

1. WHEN an HTTP request completes THEN the system SHALL record request count.
2. WHEN an HTTP request completes THEN the system SHALL record response status class.
3. WHEN an HTTP request completes THEN the system SHALL record request duration.
4. WHEN an HTTP request results in a 4xx or 5xx status THEN the system SHALL include it in error-rate calculations according to chosen policy.
5. WHEN HTTP metrics are labeled THEN labels SHALL use route templates, not raw URLs.
6. WHEN HTTP metrics are labeled THEN labels SHALL not include query strings, tokens, emails, user IDs, or IP addresses.
7. WHEN admin metrics summary is requested THEN it SHALL include request total, error rate, and latency summary.
8. WHEN metrics middleware fails THEN the request SHALL still complete.

## Requirement 3: Queue and worker metrics

### User story

As an operator, I want queue and worker metrics so I can detect backlog and stuck processing.

### Acceptance criteria

1. WHEN queue depth can be read THEN the system SHALL record queue depth.
2. WHEN oldest queued job age can be read THEN the system SHALL record oldest job age.
3. WHEN a job starts THEN the system SHALL record job started count.
4. WHEN a job completes THEN the system SHALL record job completed count.
5. WHEN a job fails THEN the system SHALL record job failed count.
6. WHEN a job completes or fails THEN the system SHALL record job duration where available.
7. WHEN worker heartbeat data exists THEN the system SHALL record worker heartbeat age or active worker count.
8. WHEN admin metrics summary is requested THEN it SHALL include queue depth and job success/failure summary.
9. WHEN queue metrics are unavailable THEN the admin summary SHALL degrade safely instead of failing.

## Requirement 4: Translation throughput metrics

### User story

As an operator, I want translation throughput and failure metrics so I can see whether translation processing is healthy.

### Acceptance criteria

1. WHEN a translation job starts THEN the system SHALL record translation job started count.
2. WHEN a translation job completes THEN the system SHALL record translation job completed count.
3. WHEN a translation job fails THEN the system SHALL record translation job failed count.
4. WHEN a chapter translation completes THEN the system SHALL record translated chapter count.
5. WHEN token counts are available THEN the system SHOULD record input and output token totals.
6. WHEN translation duration is available THEN the system SHALL record duration.
7. WHEN provider errors occur THEN the system SHALL record provider error count with safe error category.
8. WHEN quality/glossary warnings are available THEN the system MAY record warning counts.
9. WHEN admin metrics summary is requested THEN it SHALL include translation throughput and failure summary.
10. WHEN translation metrics are labeled THEN labels SHALL not include raw prompt text, source text, translated text, or user identifiers.

## Requirement 5: Crawl metrics

### User story

As an operator, I want crawl metrics so I can detect source failures and scraping quality issues.

### Acceptance criteria

1. WHEN a crawl job starts THEN the system SHALL record crawl job started count.
2. WHEN a crawl job completes THEN the system SHALL record crawl job completed count.
3. WHEN a crawl job fails THEN the system SHALL record crawl job failed count.
4. WHEN chapters are discovered THEN the system SHALL record discovered chapter count.
5. WHEN chapters are scraped successfully THEN the system SHALL record successful chapter count.
6. WHEN chapter scraping fails THEN the system SHALL record failed chapter count.
7. WHEN crawl errors are categorized THEN the system SHALL record error categories.
8. WHEN image download failures are counted THEN the system SHOULD record image failure count.
9. WHEN admin metrics summary is requested THEN it SHALL include crawl job and chapter failure summary.
10. WHEN crawl metrics are labeled THEN labels SHALL use safe source keys and error categories.

## Requirement 6: Cache metrics

### User story

As an operator, I want cache hit-rate metrics so I can understand whether caches are effective.

### Acceptance criteria

1. WHEN a cache lookup occurs THEN the system SHALL record cache request count.
2. WHEN a cache lookup hits THEN the system SHALL record cache hit count.
3. WHEN a cache lookup misses THEN the system SHALL record cache miss count.
4. WHEN cache errors occur THEN the system SHALL record cache error count.
5. WHEN cache evictions occur and are available THEN the system SHOULD record eviction count.
6. WHEN admin metrics summary is requested THEN it SHALL include cache hit rate.
7. WHEN cache metrics are labeled THEN labels SHALL use cache name and operation only.
8. WHEN cache metrics are unavailable THEN the admin summary SHALL degrade safely.

## Requirement 7: Public reader performance metrics

### User story

As an operator, I want public reader performance metrics so I can detect user-facing reader problems.

### Acceptance criteria

1. WHEN a public reader request completes THEN the system SHALL record request count.
2. WHEN a public reader request completes THEN the system SHALL record duration.
3. WHEN a public reader request fails THEN the system SHALL record error count.
4. WHEN a fallback snapshot is served THEN the system SHALL record fallback served count.
5. WHEN a degraded response is served THEN the system SHALL record degraded count.
6. WHEN the public reader returns unavailable THEN the system SHALL record unavailable count.
7. WHEN annotation lookup fails and is optional THEN the system SHOULD record optional annotation failure count.
8. WHEN admin metrics summary is requested THEN it SHALL include public reader p95 latency, error rate, fallback count, and unavailable count.
9. WHEN public reader metrics are labeled THEN labels SHALL not include chapter titles, novel titles, user IDs, or raw URLs.

## Requirement 8: Export metrics

### User story

As an operator, I want export metrics so I can detect slow or failing exports.

### Acceptance criteria

1. WHEN an export request starts THEN the system SHALL record export request count.
2. WHEN an export completes THEN the system SHALL record export completed count.
3. WHEN an export fails THEN the system SHALL record export failed count.
4. WHEN export duration is available THEN the system SHALL record duration.
5. WHEN export artifact size is available THEN the system SHOULD record artifact size.
6. WHEN export errors are categorized THEN the system SHALL record safe error category.
7. WHEN admin metrics summary is requested THEN it SHOULD include export success/failure summary.
8. WHEN export metrics are labeled THEN labels SHALL use safe format/status/error-category values.

## Requirement 9: Storage and object storage metrics

### User story

As an operator, I want storage metrics so I can detect storage latency and failures.

### Acceptance criteria

1. WHEN a storage operation occurs THEN the system SHOULD record operation count.
2. WHEN a storage operation completes THEN the system SHOULD record operation duration.
3. WHEN a storage operation fails THEN the system SHALL record storage error count.
4. WHEN object storage operation fails THEN the system SHALL record object storage error count.
5. WHEN storage metrics are labeled THEN labels SHALL use safe backend, operation, status, and error category values.
6. WHEN storage metrics are exposed through admin summary THEN they SHALL not reveal credentials, signed URLs, bucket secrets, or unsafe paths.
7. WHEN storage metrics are unavailable THEN the admin summary SHALL degrade safely.

## Requirement 10: Admin metrics summary endpoint

### User story

As an admin, I want a metrics summary endpoint so I can quickly inspect operational health.

### Acceptance criteria

1. WHEN an admin requests `GET /admin/metrics/summary` THEN the system SHALL return a metrics summary.
2. WHEN an unauthenticated user requests metrics summary THEN the system SHALL return `401 Unauthorized`.
3. WHEN a non-admin authenticated user requests metrics summary THEN the system SHALL return `403 Forbidden`.
4. WHEN metrics summary is returned THEN it SHALL include generated timestamp and requested window.
5. WHEN HTTP metrics are available THEN summary SHALL include request count, error rate, and latency summary.
6. WHEN queue metrics are available THEN summary SHALL include queue depth and job summary.
7. WHEN translation metrics are available THEN summary SHALL include translation throughput and failure summary.
8. WHEN crawl metrics are available THEN summary SHALL include crawl success/failure summary.
9. WHEN cache metrics are available THEN summary SHALL include cache hit rate.
10. WHEN public reader metrics are available THEN summary SHALL include reader latency, error rate, fallback count, and unavailable count.
11. WHEN some metric groups are unavailable THEN summary SHALL return available groups and mark unavailable groups safely.
12. WHEN metrics summary is returned THEN it SHALL not include user identifiers or secrets.

## Requirement 11: Optional admin metrics dashboard

### User story

As an admin, I want a simple metrics dashboard so I can view key operational metrics without reading raw JSON.

### Acceptance criteria

1. WHEN the admin dashboard is in scope THEN the system SHALL add an admin metrics page.
2. WHEN an admin opens the metrics page THEN it SHALL show request count, error rate, and latency.
3. WHEN an admin opens the metrics page THEN it SHALL show queue depth and job failures.
4. WHEN an admin opens the metrics page THEN it SHALL show translation throughput and failures.
5. WHEN an admin opens the metrics page THEN it SHALL show crawl failures.
6. WHEN an admin opens the metrics page THEN it SHALL show cache hit rate.
7. WHEN an admin opens the metrics page THEN it SHALL show public reader performance and fallback count.
8. WHEN a non-admin opens the metrics page THEN access SHALL be blocked.
9. WHEN the metrics API returns partial data THEN the dashboard SHALL show a safe partial/unavailable state.

## Requirement 12: Privacy and cardinality guardrails

### User story

As a privacy-conscious operator, I want metrics to avoid collecting user-level behavioral data.

### Acceptance criteria

1. WHEN metrics labels are recorded THEN they SHALL not include user IDs.
2. WHEN metrics labels are recorded THEN they SHALL not include emails.
3. WHEN metrics labels are recorded THEN they SHALL not include full IP addresses.
4. WHEN metrics labels are recorded THEN they SHALL not include raw URLs or query strings.
5. WHEN metrics labels are recorded THEN they SHALL not include novel or chapter titles.
6. WHEN metrics labels are recorded THEN they SHALL not include raw source text or translated text.
7. WHEN metrics labels are recorded THEN they SHALL not include prompt text.
8. WHEN metrics labels are recorded THEN they SHALL not include tokens, credentials, or secrets.
9. WHEN a metric dimension could have unbounded values THEN it SHALL be normalized, bucketed, omitted, or rejected.
10. WHEN tests run THEN they SHALL cover at least the main privacy/cardinality guardrails.

## Requirement 13: Metrics failure isolation

### User story

As a user, I want app behavior to continue even if metrics recording breaks.

### Acceptance criteria

1. WHEN metrics recording fails during an HTTP request THEN the request SHALL still complete.
2. WHEN metrics recording fails during a background job THEN the job SHALL continue according to normal job behavior.
3. WHEN metrics aggregation fails for one group THEN admin summary SHALL still return other groups where possible.
4. WHEN metrics storage is unavailable THEN the system SHALL degrade to in-memory/no-op behavior if configured.
5. WHEN metrics errors are logged THEN they SHALL be safe and rate-limited where practical.
6. WHEN metrics fail THEN user-facing responses SHALL not expose metrics internals.

## Requirement 14: Performance overhead

### User story

As an operator, I want metrics to have low overhead so instrumentation does not slow down the app.

### Acceptance criteria

1. WHEN metrics are recorded on hot request paths THEN recording SHALL be non-blocking or low-cost.
2. WHEN durable metric snapshots are used THEN the system SHALL not write a database row for every request unless explicitly designed for that load.
3. WHEN histograms/timers are recorded THEN they SHALL be bounded in memory.
4. WHEN metrics labels are recorded THEN high-cardinality values SHALL be rejected or normalized.
5. WHEN admin summary is generated THEN it SHALL complete within a reasonable timeout.
6. WHEN metrics collection is disabled THEN instrumentation SHALL become no-op or minimal overhead.

## Requirement 15: Optional Prometheus compatibility

### User story

As an operator, I may want to integrate metrics with Prometheus or another monitoring system later.

### Acceptance criteria

1. WHEN Prometheus compatibility is implemented THEN the system SHALL expose metrics in Prometheus-compatible format.
2. WHEN a `/metrics` endpoint is exposed THEN it SHALL be protected by deployment/network controls or admin auth according to project policy.
3. WHEN Prometheus labels are emitted THEN they SHALL follow privacy and cardinality rules.
4. WHEN Prometheus compatibility is not implemented in this spec THEN the admin JSON summary SHALL still satisfy baseline metrics requirements.
5. WHEN external metrics backend is configured THEN metrics recording SHALL remain compatible with the central recorder abstraction.

## Requirement 16: Test coverage

### User story

As a maintainer, I want tests for metrics instrumentation so operational visibility does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover metrics recorder counters, gauges, and timings.
2. WHEN tests run THEN they SHALL cover HTTP request metrics.
3. WHEN tests run THEN they SHALL cover HTTP error metrics.
4. WHEN tests run THEN they SHALL cover queue/worker metrics where infrastructure exists.
5. WHEN tests run THEN they SHALL cover translation metrics.
6. WHEN tests run THEN they SHALL cover crawl metrics.
7. WHEN tests run THEN they SHALL cover cache hit/miss metrics.
8. WHEN tests run THEN they SHALL cover public reader metrics.
9. WHEN tests run THEN they SHALL cover export metrics where practical.
10. WHEN tests run THEN they SHALL cover admin summary authorization.
11. WHEN tests run THEN they SHALL cover admin summary response shape.
12. WHEN tests run THEN they SHALL cover privacy/cardinality guardrails.
13. WHEN tests run THEN they SHALL cover metrics failure isolation.

## Requirement 17: Completion verification

### User story

As an operator, I want a clear verification path so metrics baseline is complete only when useful operational data is visible.

### Acceptance criteria

1. WHEN test traffic is sent through the app THEN HTTP request counts SHALL increase.
2. WHEN test errors are generated THEN HTTP error rate SHALL reflect them.
3. WHEN test jobs are queued THEN queue depth or job metrics SHALL reflect them.
4. WHEN test translations run THEN translation metrics SHALL update.
5. WHEN test crawls run THEN crawl metrics SHALL update.
6. WHEN cache hits/misses are generated THEN cache hit rate SHALL update.
7. WHEN public reader requests are made THEN public reader latency and count SHALL update.
8. WHEN fallback/unavailable reader behavior is simulated THEN public reader degradation metrics SHALL update.
9. WHEN admin metrics summary is requested by admin THEN it SHALL show the baseline metric groups.
10. WHEN admin metrics summary is requested by non-admin THEN it SHALL be blocked.
11. WHEN metrics output is inspected THEN it SHALL not include private identifiers or secrets.
