# tasks.md

# Tasks: Public Reader Graceful Degradation

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect public reader chapter endpoint flow.
  * [ ] 0.2 Inspect public novel/catalog endpoint flow.
  * [ ] 0.3 Inspect publication and availability checks.
  * [ ] 0.4 Inspect takedown/unpublish/tombstone behavior if any.
  * [ ] 0.5 Inspect reader content storage and object storage access.
  * [ ] 0.6 Inspect public projection/snapshot storage, if any.
  * [ ] 0.7 Inspect public reader cache/CDN headers, if any.
  * [ ] 0.8 Inspect optional reader features such as glossary annotations.
  * [ ] 0.9 Inspect existing error handling and structured error format.
  * [ ] 0.10 Inspect existing public reader tests.

* [ ] 1. Define degradation contract

  * [ ] 1.1 Define degradation states: normal, degraded, fallback, unavailable. (REQ-1, REQ-9)
  * [ ] 1.2 Define public-safe response metadata fields. (REQ-9)
  * [ ] 1.3 Define public-safe unavailable response shape. (REQ-8)
  * [ ] 1.4 Define degradation error categories. (REQ-8, REQ-12)
  * [ ] 1.5 Define which optional features may fail open. (REQ-7)
  * [ ] 1.6 Define which dependencies are required for normal path. (REQ-2)
  * [ ] 1.7 Define fallback safety requirements. (REQ-4, REQ-6, REQ-13)
  * [ ] 1.8 Document fields that must not appear in public responses. (REQ-13)

* [ ] 2. Add configuration

  * [ ] 2.1 Add public reader circuit breaker enabled flag. (REQ-3)
  * [ ] 2.2 Add circuit breaker failure threshold. (REQ-3)
  * [ ] 2.3 Add circuit breaker recovery interval. (REQ-3)
  * [ ] 2.4 Add half-open max probe calls if needed. (REQ-3)
  * [ ] 2.5 Add public reader total timeout. (REQ-2)
  * [ ] 2.6 Add catalog/database timeout. (REQ-2)
  * [ ] 2.7 Add storage/object-storage timeout. (REQ-2)
  * [ ] 2.8 Add snapshot fallback timeout. (REQ-2)
  * [ ] 2.9 Add optional feature timeout. (REQ-2, REQ-7)
  * [ ] 2.10 Add snapshot fallback enabled flag. (REQ-4)
  * [ ] 2.11 Add snapshot max age. (REQ-5)
  * [ ] 2.12 Add allow-stale-snapshot-on-outage flag. (REQ-5)
  * [ ] 2.13 Validate configuration. (REQ-15)

* [ ] 3. Implement timeout helpers

  * [ ] 3.1 Add bounded call wrapper for catalog lookup. (REQ-2)
  * [ ] 3.2 Add bounded call wrapper for reader storage lookup. (REQ-2)
  * [ ] 3.3 Add bounded call wrapper for object storage read. (REQ-2)
  * [ ] 3.4 Add bounded call wrapper for snapshot lookup. (REQ-2)
  * [ ] 3.5 Add bounded call wrapper for optional feature lookup. (REQ-2, REQ-7)
  * [ ] 3.6 Convert timeout failures into safe error categories. (REQ-2, REQ-8)
  * [ ] 3.7 Add tests for each timeout path. (REQ-2, REQ-14)

* [ ] 4. Implement circuit breaker helper

  * [ ] 4.1 Add circuit breaker states: closed, open, half-open. (REQ-3)
  * [ ] 4.2 Track failure counts per dependency key. (REQ-3)
  * [ ] 4.3 Open circuit after configured threshold. (REQ-3)
  * [ ] 4.4 Fail fast while open. (REQ-3)
  * [ ] 4.5 Enter half-open after recovery interval. (REQ-3)
  * [ ] 4.6 Close circuit after successful half-open probe. (REQ-3)
  * [ ] 4.7 Reopen circuit after failed half-open probe. (REQ-3)
  * [ ] 4.8 Support disabled circuit breaker config. (REQ-3)
  * [ ] 4.9 Add tests for open, fail-fast, half-open, close, reopen, and disabled behavior. (REQ-3, REQ-14)

* [ ] 5. Define public snapshot fallback reader

  * [ ] 5.1 Identify existing public projection/snapshot format. (REQ-4)
  * [ ] 5.2 Define fallback snapshot key lookup by public novel/chapter identity. (REQ-4)
  * [ ] 5.3 Add snapshot read method. (REQ-4)
  * [ ] 5.4 Validate snapshot JSON/schema. (REQ-4)
  * [ ] 5.5 Validate snapshot generated time. (REQ-5)
  * [ ] 5.6 Validate snapshot was generated for public reader use. (REQ-4, REQ-6)
  * [ ] 5.7 Convert snapshot into current public chapter response shape. (REQ-4, REQ-11)
  * [ ] 5.8 Add tests for valid snapshot, missing snapshot, malformed snapshot, and schema mismatch. (REQ-4, REQ-14)

* [ ] 6. Implement snapshot freshness policy

  * [ ] 6.1 Compare snapshot generated time to max age. (REQ-5)
  * [ ] 6.2 Allow fresh snapshots. (REQ-5)
  * [ ] 6.3 Reject stale snapshots when stale fallback disabled. (REQ-5)
  * [ ] 6.4 Allow stale snapshots with degraded marker when stale fallback enabled. (REQ-5)
  * [ ] 6.5 Treat missing/invalid generated time as unsafe or stale. (REQ-5)
  * [ ] 6.6 Add tests for fresh, stale allowed, stale disallowed, and missing timestamp. (REQ-5, REQ-14)

* [ ] 7. Add publication and takedown safety checks

  * [ ] 7.1 Confirm fallback snapshots are generated only by public projection/publish pipeline. (REQ-6)
  * [ ] 7.2 Add check for unpublished novel/chapter when catalog is available. (REQ-6)
  * [ ] 7.3 Add tombstone/revocation check if tombstone store exists. (REQ-6)
  * [ ] 7.4 Prevent fallback when publication state cannot be safely established and no public projection guarantee exists. (REQ-6, REQ-13)
  * [ ] 7.5 Ensure unpublish/takedown deletes, invalidates, or blocks snapshots. (REQ-6, REQ-10)
  * [ ] 7.6 Ensure fallback never reads from raw private chapter storage. (REQ-4, REQ-13)
  * [ ] 7.7 Add tests for unpublished, takedown/tombstone, unknown state, and public projection guarantee behavior. (REQ-6, REQ-13, REQ-14)

* [ ] 8. Wire fallback into public chapter endpoint

  * [ ] 8.1 Wrap primary catalog lookup with timeout/circuit breaker. (REQ-2, REQ-3)
  * [ ] 8.2 Wrap primary reader content lookup with timeout/circuit breaker. (REQ-2, REQ-3)
  * [ ] 8.3 On primary dependency failure, attempt safe snapshot fallback. (REQ-4)
  * [ ] 8.4 On valid fallback, return snapshot response with safe degraded metadata. (REQ-4, REQ-9)
  * [ ] 8.5 On missing/unsafe fallback, return safe unavailable response. (REQ-8)
  * [ ] 8.6 Preserve existing not-found behavior for true unpublished/missing content. (REQ-6, REQ-8)
  * [ ] 8.7 Preserve existing normal response behavior when no failure occurs. (REQ-1)
  * [ ] 8.8 Add endpoint tests for normal, fallback, unavailable, and safety cases. (REQ-1, REQ-4, REQ-8, REQ-14)

* [ ] 9. Wire fallback into public novel/catalog endpoints where safe

  * [ ] 9.1 Identify endpoints where cached public projection exists. (REQ-4)
  * [ ] 9.2 Add fallback only for endpoints with safe public snapshots. (REQ-4, REQ-6)
  * [ ] 9.3 Return safe unavailable response when no safe fallback exists. (REQ-8)
  * [ ] 9.4 Avoid serving stale catalog data that includes unpublished/taken-down content. (REQ-6, REQ-10)
  * [ ] 9.5 Add tests for catalog/detail fallback if implemented. (REQ-4, REQ-6, REQ-14)

* [ ] 10. Make optional reader features fail open

  * [ ] 10.1 Identify optional reader feature calls. (REQ-7)
  * [ ] 10.2 Wrap glossary annotation lookup with timeout/error isolation if not already done. (REQ-7)
  * [ ] 10.3 Return empty annotations or omitted optional data on failure. (REQ-7)
  * [ ] 10.4 Ensure optional feature failure does not block core reader response. (REQ-7)
  * [ ] 10.5 Add safe degraded metadata only if response contract allows it. (REQ-7, REQ-9)
  * [ ] 10.6 Add tests for optional feature failure and timeout. (REQ-7, REQ-14)

* [ ] 11. Add public unavailable response handling

  * [ ] 11.1 Add project-standard temporary unavailable error for reader outages. (REQ-8)
  * [ ] 11.2 Use HTTP 503 or existing standard response. (REQ-8)
  * [ ] 11.3 Add public-safe message. (REQ-8)
  * [ ] 11.4 Add cache-control behavior to avoid long-lived caching of 503 responses. (REQ-8, REQ-10)
  * [ ] 11.5 Redact dependency details and stack traces. (REQ-8, REQ-13)
  * [ ] 11.6 Add tests for safe unavailable response and redaction. (REQ-8, REQ-14)

* [ ] 12. Add response metadata or headers

  * [ ] 12.1 Decide whether degraded state is returned in body metadata or headers. (REQ-9)
  * [ ] 12.2 Add normal response metadata behavior. (REQ-9)
  * [ ] 12.3 Add fallback response metadata behavior. (REQ-9)
  * [ ] 12.4 Add stale snapshot metadata behavior. (REQ-9)
  * [ ] 12.5 Add optional feature degraded metadata behavior if used. (REQ-9)
  * [ ] 12.6 Ensure metadata is public-safe. (REQ-9, REQ-13)
  * [ ] 12.7 Add tests for metadata/header behavior. (REQ-9, REQ-14)

* [ ] 13. Ensure cache compatibility

  * [ ] 13.1 Inspect public reader cache keys. (REQ-10)
  * [ ] 13.2 Ensure fallback responses do not poison normal cache entries. (REQ-10)
  * [ ] 13.3 Ensure 503 responses are not cached long-term. (REQ-10)
  * [ ] 13.4 Ensure unpublish invalidates or blocks cached fallback content. (REQ-10)
  * [ ] 13.5 Ensure takedown invalidates or blocks cached fallback content. (REQ-10)
  * [ ] 13.6 Ensure stale cache policy follows configured snapshot freshness. (REQ-5, REQ-10)
  * [ ] 13.7 Add cache compatibility tests where practical. (REQ-10, REQ-14)

* [ ] 14. Add admin/operator status hook

  * [ ] 14.1 Add `PublicReaderResilienceService.get_status()`. (REQ-11)
  * [ ] 14.2 Include circuit breaker states. (REQ-11)
  * [ ] 14.3 Include recent fallback/unavailable counts if tracked. (REQ-11)
  * [ ] 14.4 Include last safe error category. (REQ-11)
  * [ ] 14.5 Add optional admin endpoint if project has operations routes. (REQ-11)
  * [ ] 14.6 Protect optional admin endpoint with admin auth. (REQ-11)
  * [ ] 14.7 Add tests for service status and endpoint authorization if implemented. (REQ-11, REQ-14)

* [ ] 15. Add observability logs

  * [ ] 15.1 Log public reader dependency failures. (REQ-12)
  * [ ] 15.2 Log fallback served events. (REQ-12)
  * [ ] 15.3 Log fallback unavailable events. (REQ-12)
  * [ ] 15.4 Log circuit breaker state changes. (REQ-12)
  * [ ] 15.5 Log optional feature failure events. (REQ-12)
  * [ ] 15.6 Use public-safe identifiers. (REQ-12, REQ-13)
  * [ ] 15.7 Avoid logging full chapter text or private metadata. (REQ-12, REQ-13)
  * [ ] 15.8 Add log tests only where project conventions support them. (REQ-12, REQ-14)

* [ ] 16. Security and privacy hardening

  * [ ] 16.1 Verify fallback never reads raw private storage. (REQ-13)
  * [ ] 16.2 Verify fallback never includes admin-only metadata. (REQ-13)
  * [ ] 16.3 Verify fallback never includes private glossary data. (REQ-13)
  * [ ] 16.4 Verify fallback is blocked for unpublished content. (REQ-6, REQ-13)
  * [ ] 16.5 Verify fallback is blocked for takedown/tombstone content. (REQ-6, REQ-13)
  * [ ] 16.6 Verify public errors do not expose secrets or internal paths. (REQ-8, REQ-13)
  * [ ] 16.7 Add security-focused tests for unsafe fallback scenarios. (REQ-13, REQ-14)

* [ ] 17. Backend test coverage pass

  * [ ] 17.1 Add normal-path reader response test. (REQ-1, REQ-14)
  * [ ] 17.2 Add catalog/database timeout test. (REQ-2, REQ-14)
  * [ ] 17.3 Add storage/object-storage failure test. (REQ-2, REQ-14)
  * [ ] 17.4 Add safe snapshot fallback test. (REQ-4, REQ-14)
  * [ ] 17.5 Add no-snapshot unavailable response test. (REQ-8, REQ-14)
  * [ ] 17.6 Add stale snapshot allowed/disallowed tests. (REQ-5, REQ-14)
  * [ ] 17.7 Add unpublished content fallback block test. (REQ-6, REQ-14)
  * [ ] 17.8 Add takedown/tombstone fallback block test. (REQ-6, REQ-14)
  * [ ] 17.9 Add optional feature failure test. (REQ-7, REQ-14)
  * [ ] 17.10 Add circuit breaker open/half-open/close tests. (REQ-3, REQ-14)
  * [ ] 17.11 Add public error redaction tests. (REQ-8, REQ-13, REQ-14)
  * [ ] 17.12 Add cache compatibility tests where practical. (REQ-10, REQ-14)
  * [ ] 17.13 Add admin status authorization tests if endpoint implemented. (REQ-11, REQ-14)

* [ ] 18. Documentation

  * [ ] 18.1 Document degradation states. (REQ-9)
  * [ ] 18.2 Document circuit breaker configuration. (REQ-3)
  * [ ] 18.3 Document dependency timeout configuration. (REQ-2)
  * [ ] 18.4 Document snapshot fallback requirements. (REQ-4)
  * [ ] 18.5 Document snapshot freshness behavior. (REQ-5)
  * [ ] 18.6 Document publication/takedown safety rules. (REQ-6, REQ-13)
  * [ ] 18.7 Document optional feature fail-open behavior. (REQ-7)
  * [ ] 18.8 Document staging verification procedure. (REQ-15)

* [ ] 19. Completion verification

  * [ ] 19.1 Verify normal public reader response is unchanged while dependencies are healthy. (REQ-1, REQ-15)
  * [ ] 19.2 Create or identify safe public snapshot for a published chapter. (REQ-4, REQ-15)
  * [ ] 19.3 Simulate primary storage failure and verify fallback snapshot is served. (REQ-4, REQ-15)
  * [ ] 19.4 Simulate missing snapshot and verify safe unavailable response. (REQ-8, REQ-15)
  * [ ] 19.5 Simulate catalog failure where publication state cannot be verified and verify unsafe fallback is blocked. (REQ-6, REQ-15)
  * [ ] 19.6 Unpublish or tombstone content and verify fallback is blocked. (REQ-6, REQ-15)
  * [ ] 19.7 Simulate optional annotation failure and verify chapter still loads. (REQ-7, REQ-15)
  * [ ] 19.8 Trigger repeated dependency failures and verify circuit opens. (REQ-3, REQ-15)
  * [ ] 19.9 Restore dependency and verify circuit closes after probe. (REQ-3, REQ-15)
  * [ ] 19.10 Inspect public responses and verify no internal errors or secrets leak. (REQ-13, REQ-15)
  * [ ] 19.11 Mark `public-reader-graceful-degradation` complete only after safe fallback and unsafe-fallback-block tests pass.
