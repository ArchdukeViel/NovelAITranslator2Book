# tasks.md

# Tasks: Metrics Dashboard Baseline

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing logging and metrics libraries.
  * [ ] 0.2 Inspect backend request middleware stack.
  * [ ] 0.3 Inspect queue/worker implementation and queue depth access.
  * [ ] 0.4 Inspect translation pipeline entry/exit points.
  * [ ] 0.5 Inspect crawl/fetch/scrape pipeline entry/exit points.
  * [ ] 0.6 Inspect cache abstraction and cache call sites.
  * [ ] 0.7 Inspect public reader endpoints and fallback/degradation behavior if implemented.
  * [ ] 0.8 Inspect export service and manifest flow.
  * [ ] 0.9 Inspect storage/object-storage abstraction.
  * [ ] 0.10 Inspect existing admin auth/router/frontend patterns.
  * [ ] 0.11 Inspect existing tests for middleware, pipeline, cache, reader, and admin endpoints.

* [ ] 1. Define metrics architecture

  * [ ] 1.1 Choose in-memory, external, or hybrid metrics backend for baseline. (REQ-1)
  * [ ] 1.2 Define metrics recorder interface. (REQ-1)
  * [ ] 1.3 Define counter API. (REQ-1)
  * [ ] 1.4 Define gauge API. (REQ-1)
  * [ ] 1.5 Define timer/histogram API. (REQ-1)
  * [ ] 1.6 Define metrics snapshot/summary API. (REQ-10)
  * [ ] 1.7 Define no-op recorder behavior. (REQ-1, REQ-13)
  * [ ] 1.8 Define privacy/cardinality label allowlist. (REQ-12)
  * [ ] 1.9 Define supported windows such as 5m, 15m, 1h, and 24h if supported. (REQ-10)

* [ ] 2. Add metrics configuration

  * [ ] 2.1 Add metrics enabled flag. (REQ-1, REQ-14)
  * [ ] 2.2 Add metrics backend selection if needed. (REQ-1)
  * [ ] 2.3 Add rolling window size config if in-memory metrics are used. (REQ-10)
  * [ ] 2.4 Add histogram bucket or percentile config if needed. (REQ-14)
  * [ ] 2.5 Add admin metrics enabled flag if needed. (REQ-10)
  * [ ] 2.6 Add Prometheus/export endpoint flag if implemented. (REQ-15)
  * [ ] 2.7 Validate metrics config. (REQ-14)

* [ ] 3. Implement metrics recorder

  * [ ] 3.1 Implement counter recording. (REQ-1)
  * [ ] 3.2 Implement gauge recording. (REQ-1)
  * [ ] 3.3 Implement duration/timer recording. (REQ-1)
  * [ ] 3.4 Implement safe label normalization. (REQ-12)
  * [ ] 3.5 Implement high-cardinality label rejection or omission. (REQ-12, REQ-14)
  * [ ] 3.6 Implement failure isolation around recorder internals. (REQ-13)
  * [ ] 3.7 Implement snapshot aggregation. (REQ-10)
  * [ ] 3.8 Add tests for counters, gauges, timers, labels, snapshots, and failure isolation. (REQ-1, REQ-12, REQ-13, REQ-16)

* [ ] 4. Add HTTP metrics middleware

  * [ ] 4.1 Add request count recording. (REQ-2)
  * [ ] 4.2 Add response status class recording. (REQ-2)
  * [ ] 4.3 Add request duration recording. (REQ-2)
  * [ ] 4.4 Add in-flight request gauge if practical. (REQ-2)
  * [ ] 4.5 Use route template instead of raw URL. (REQ-2, REQ-12)
  * [ ] 4.6 Exclude query strings and tokens from labels. (REQ-2, REQ-12)
  * [ ] 4.7 Ensure middleware failure does not fail request. (REQ-13)
  * [ ] 4.8 Add tests for successful request, error response, route template, and failure isolation. (REQ-2, REQ-13, REQ-16)

* [ ] 5. Instrument queue and worker metrics

  * [ ] 5.1 Record queue depth where available. (REQ-3)
  * [ ] 5.2 Record oldest queued job age where available. (REQ-3)
  * [ ] 5.3 Record job started count. (REQ-3)
  * [ ] 5.4 Record job completed count. (REQ-3)
  * [ ] 5.5 Record job failed count. (REQ-3)
  * [ ] 5.6 Record job duration. (REQ-3)
  * [ ] 5.7 Record worker heartbeat age or active worker count if available. (REQ-3)
  * [ ] 5.8 Use safe labels: queue name, job type, status. (REQ-3, REQ-12)
  * [ ] 5.9 Add tests for job lifecycle metrics and unavailable queue metrics. (REQ-3, REQ-16)

* [ ] 6. Instrument translation metrics

  * [ ] 6.1 Record translation job started. (REQ-4)
  * [ ] 6.2 Record translation job completed. (REQ-4)
  * [ ] 6.3 Record translation job failed. (REQ-4)
  * [ ] 6.4 Record translated chapter count. (REQ-4)
  * [ ] 6.5 Record translation duration. (REQ-4)
  * [ ] 6.6 Record token counts when available. (REQ-4)
  * [ ] 6.7 Record provider errors by safe category. (REQ-4)
  * [ ] 6.8 Record quality/glossary warning counts if available. (REQ-4)
  * [ ] 6.9 Ensure prompts, source text, translated text, and user IDs are never labels. (REQ-4, REQ-12)
  * [ ] 6.10 Add tests for translation success, failure, provider error, and label safety. (REQ-4, REQ-12, REQ-16)

* [ ] 7. Instrument crawl metrics

  * [ ] 7.1 Record crawl job started. (REQ-5)
  * [ ] 7.2 Record crawl job completed. (REQ-5)
  * [ ] 7.3 Record crawl job failed. (REQ-5)
  * [ ] 7.4 Record discovered chapter count. (REQ-5)
  * [ ] 7.5 Record successful chapter scrape count. (REQ-5)
  * [ ] 7.6 Record failed chapter scrape count. (REQ-5)
  * [ ] 7.7 Record crawl duration. (REQ-5)
  * [ ] 7.8 Record crawl error categories. (REQ-5)
  * [ ] 7.9 Record image download failure count if available. (REQ-5)
  * [ ] 7.10 Use safe source key and error category labels. (REQ-5, REQ-12)
  * [ ] 7.11 Add tests for crawl success, failure, chapter failures, image failures, and error categories. (REQ-5, REQ-16)

* [ ] 8. Instrument cache metrics

  * [ ] 8.1 Record cache request count. (REQ-6)
  * [ ] 8.2 Record cache hit count. (REQ-6)
  * [ ] 8.3 Record cache miss count. (REQ-6)
  * [ ] 8.4 Record cache error count. (REQ-6)
  * [ ] 8.5 Record cache eviction count if available. (REQ-6)
  * [ ] 8.6 Compute cache hit rate. (REQ-6)
  * [ ] 8.7 Use safe cache name and operation labels. (REQ-6, REQ-12)
  * [ ] 8.8 Add tests for hit, miss, error, eviction, and hit-rate summary. (REQ-6, REQ-16)

* [ ] 9. Instrument public reader metrics

  * [ ] 9.1 Record public reader request count. (REQ-7)
  * [ ] 9.2 Record public reader duration. (REQ-7)
  * [ ] 9.3 Record public reader error count. (REQ-7)
  * [ ] 9.4 Record fallback served count. (REQ-7)
  * [ ] 9.5 Record degraded response count. (REQ-7)
  * [ ] 9.6 Record unavailable response count. (REQ-7)
  * [ ] 9.7 Record fallback snapshot age if available. (REQ-7)
  * [ ] 9.8 Record optional annotation failure count if available. (REQ-7)
  * [ ] 9.9 Use safe endpoint type, status class, and degradation state labels. (REQ-7, REQ-12)
  * [ ] 9.10 Add tests for normal reader request, error, fallback, degraded, unavailable, and annotation failure metrics. (REQ-7, REQ-16)

* [ ] 10. Instrument export metrics

  * [ ] 10.1 Record export request count. (REQ-8)
  * [ ] 10.2 Record export completed count. (REQ-8)
  * [ ] 10.3 Record export failed count. (REQ-8)
  * [ ] 10.4 Record export duration. (REQ-8)
  * [ ] 10.5 Record artifact size if available. (REQ-8)
  * [ ] 10.6 Record safe export error category. (REQ-8)
  * [ ] 10.7 Use safe format/status/error-category labels. (REQ-8, REQ-12)
  * [ ] 10.8 Add tests for export success, failure, duration, size, and safe labels. (REQ-8, REQ-16)

* [ ] 11. Instrument storage/object-storage metrics

  * [ ] 11.1 Record storage operation count where practical. (REQ-9)
  * [ ] 11.2 Record storage operation duration where practical. (REQ-9)
  * [ ] 11.3 Record storage error count. (REQ-9)
  * [ ] 11.4 Record object storage error count. (REQ-9)
  * [ ] 11.5 Use safe backend, operation, status, and error-category labels. (REQ-9, REQ-12)
  * [ ] 11.6 Ensure bucket secrets, signed URLs, and paths are not labels. (REQ-9, REQ-12)
  * [ ] 11.7 Add tests for storage success, failure, and label redaction where practical. (REQ-9, REQ-16)

* [ ] 12. Implement metrics summary service

  * [ ] 12.1 Aggregate HTTP metrics. (REQ-10)
  * [ ] 12.2 Aggregate queue metrics. (REQ-10)
  * [ ] 12.3 Aggregate translation metrics. (REQ-10)
  * [ ] 12.4 Aggregate crawl metrics. (REQ-10)
  * [ ] 12.5 Aggregate cache metrics. (REQ-10)
  * [ ] 12.6 Aggregate public reader metrics. (REQ-10)
  * [ ] 12.7 Aggregate export metrics if available. (REQ-8, REQ-10)
  * [ ] 12.8 Aggregate storage metrics if available. (REQ-9, REQ-10)
  * [ ] 12.9 Return safe unavailable/partial markers for missing groups. (REQ-10, REQ-13)
  * [ ] 12.10 Include generated timestamp and window. (REQ-10)
  * [ ] 12.11 Add tests for full summary, partial summary, empty summary, and unavailable group behavior. (REQ-10, REQ-13, REQ-16)

* [ ] 13. Add admin metrics API

  * [ ] 13.1 Add `GET /admin/metrics/summary`. (REQ-10)
  * [ ] 13.2 Protect endpoint with admin auth. (REQ-10)
  * [ ] 13.3 Validate `window` query param. (REQ-10)
  * [ ] 13.4 Return metrics summary response. (REQ-10)
  * [ ] 13.5 Reject unauthenticated users. (REQ-10)
  * [ ] 13.6 Reject non-admin users. (REQ-10)
  * [ ] 13.7 Ensure response does not include private identifiers or secrets. (REQ-10, REQ-12)
  * [ ] 13.8 Add API tests for admin, non-admin, unauthenticated, valid window, invalid window, and response shape. (REQ-10, REQ-16)

* [ ] 14. Add optional admin metrics dashboard

  * [ ] 14.1 Add `/admin/metrics` route if admin frontend exists and dashboard is in scope. (REQ-11)
  * [ ] 14.2 Add frontend API client for metrics summary. (REQ-11)
  * [ ] 14.3 Render HTTP request/error/latency cards. (REQ-11)
  * [ ] 14.4 Render queue depth/job failure cards. (REQ-11)
  * [ ] 14.5 Render translation throughput/failure cards. (REQ-11)
  * [ ] 14.6 Render crawl failure cards. (REQ-11)
  * [ ] 14.7 Render cache hit-rate card. (REQ-11)
  * [ ] 14.8 Render public reader performance/fallback cards. (REQ-11)
  * [ ] 14.9 Render partial/unavailable states safely. (REQ-11)
  * [ ] 14.10 Add frontend tests for admin access, blocked access, and summary rendering. (REQ-11, REQ-16)

* [ ] 15. Add privacy and cardinality guardrails

  * [ ] 15.1 Implement label allowlist or sanitizer. (REQ-12)
  * [ ] 15.2 Reject or normalize raw URLs. (REQ-12)
  * [ ] 15.3 Reject or omit query strings. (REQ-12)
  * [ ] 15.4 Reject user IDs and emails in labels. (REQ-12)
  * [ ] 15.5 Reject IP addresses in labels. (REQ-12)
  * [ ] 15.6 Reject novel/chapter titles in labels. (REQ-12)
  * [ ] 15.7 Reject prompt/source/translation text in labels. (REQ-12)
  * [ ] 15.8 Reject secrets/tokens/credentials in labels. (REQ-12)
  * [ ] 15.9 Add tests for guardrail rejection/normalization. (REQ-12, REQ-16)

* [ ] 16. Add metrics failure isolation

  * [ ] 16.1 Wrap recorder calls in safe failure boundaries. (REQ-13)
  * [ ] 16.2 Add no-op fallback when metrics disabled. (REQ-13, REQ-14)
  * [ ] 16.3 Add no-op or in-memory fallback when external backend unavailable if supported. (REQ-13)
  * [ ] 16.4 Ensure metrics aggregation failure for one group does not fail whole summary. (REQ-13)
  * [ ] 16.5 Log metrics errors safely and avoid log spam where practical. (REQ-13)
  * [ ] 16.6 Add tests for recorder exception during request, job, and summary generation. (REQ-13, REQ-16)

* [ ] 17. Add performance safeguards

  * [ ] 17.1 Avoid synchronous durable writes per request. (REQ-14)
  * [ ] 17.2 Bound in-memory metric storage. (REQ-14)
  * [ ] 17.3 Bound histogram/timer sample storage. (REQ-14)
  * [ ] 17.4 Bound label cardinality. (REQ-14)
  * [ ] 17.5 Add timeout or efficient aggregation for admin summary. (REQ-14)
  * [ ] 17.6 Add tests or benchmarks for bounded storage where practical. (REQ-14, REQ-16)

* [ ] 18. Add optional Prometheus compatibility

  * [ ] 18.1 Decide whether `/metrics` endpoint is in scope. (REQ-15)
  * [ ] 18.2 Add Prometheus formatter if implemented. (REQ-15)
  * [ ] 18.3 Protect `/metrics` according to project policy. (REQ-15)
  * [ ] 18.4 Ensure Prometheus labels follow privacy/cardinality rules. (REQ-15)
  * [ ] 18.5 Add tests for endpoint access and label safety if implemented. (REQ-15, REQ-16)

* [ ] 19. Documentation

  * [ ] 19.1 Document metric groups and meanings. (REQ-10)
  * [ ] 19.2 Document admin metrics summary endpoint. (REQ-10)
  * [ ] 19.3 Document optional dashboard. (REQ-11)
  * [ ] 19.4 Document privacy/cardinality rules. (REQ-12)
  * [ ] 19.5 Document metrics enabled/disabled config. (REQ-14)
  * [ ] 19.6 Document Prometheus compatibility if implemented. (REQ-15)
  * [ ] 19.7 Document operational interpretation for latency, error rate, queue depth, translation throughput, crawl failures, cache hit rate, and reader fallback. (REQ-17)

* [ ] 20. Test coverage pass

  * [ ] 20.1 Add recorder tests. (REQ-1, REQ-16)
  * [ ] 20.2 Add HTTP middleware tests. (REQ-2, REQ-16)
  * [ ] 20.3 Add queue/worker metrics tests. (REQ-3, REQ-16)
  * [ ] 20.4 Add translation metrics tests. (REQ-4, REQ-16)
  * [ ] 20.5 Add crawl metrics tests. (REQ-5, REQ-16)
  * [ ] 20.6 Add cache metrics tests. (REQ-6, REQ-16)
  * [ ] 20.7 Add public reader metrics tests. (REQ-7, REQ-16)
  * [ ] 20.8 Add export metrics tests. (REQ-8, REQ-16)
  * [ ] 20.9 Add storage metrics tests where practical. (REQ-9, REQ-16)
  * [ ] 20.10 Add admin metrics API tests. (REQ-10, REQ-16)
  * [ ] 20.11 Add dashboard tests if implemented. (REQ-11, REQ-16)
  * [ ] 20.12 Add privacy/cardinality tests. (REQ-12, REQ-16)
  * [ ] 20.13 Add failure isolation tests. (REQ-13, REQ-16)
  * [ ] 20.14 Add performance/bounded storage tests where practical. (REQ-14, REQ-16)

* [ ] 21. Completion verification

  * [ ] 21.1 Send test HTTP traffic and verify request count increases. (REQ-17)
  * [ ] 21.2 Generate test HTTP errors and verify error rate changes. (REQ-17)
  * [ ] 21.3 Queue test jobs and verify queue/job metrics update. (REQ-17)
  * [ ] 21.4 Run test translation and verify translation metrics update. (REQ-17)
  * [ ] 21.5 Run test crawl and verify crawl metrics update. (REQ-17)
  * [ ] 21.6 Generate cache hits/misses and verify hit rate updates. (REQ-17)
  * [ ] 21.7 Request public reader pages and verify reader metrics update. (REQ-17)
  * [ ] 21.8 Simulate reader fallback/unavailable and verify degradation metrics update. (REQ-17)
  * [ ] 21.9 Run export and verify export metrics update if export instrumentation is implemented. (REQ-17)
  * [ ] 21.10 Request admin metrics summary as admin and verify baseline groups appear. (REQ-10, REQ-17)
  * [ ] 21.11 Request admin metrics summary as non-admin and verify access is blocked. (REQ-10, REQ-17)
  * [ ] 21.12 Inspect metric labels and verify no private identifiers or secrets appear. (REQ-12, REQ-17)
  * [ ] 21.13 Mark `metrics-dashboard-baseline` complete only after admin summary shows operational baseline metrics safely.
