# Tasks: Crawl and Fetch Observability

## Overview

Implement crawl/fetch observability by persisting existing crawl diagnostics into activity metadata, enriching per-chapter failure records, exposing running crawl progress, and deriving source-health summaries from stored activity records.

Scope boundaries:

- No new storage files.
- No new database tables or migrations.
- No new API endpoints.
- No retry behavior changes beyond recording retry telemetry.
- No distributed tracing or metrics backend.
- No translation pipeline observability changes.

## Task List

- [x] 1. Preflight Current Crawl and Activity Flow
  - [x] 1.1 Inspect `backend/src/novelai/activity/worker.py` and locate `_run_crawl_activity`.
  - [x] 1.2 Inspect how crawl activity status, metadata, and top-level errors are currently written.
  - [x] 1.3 Inspect `backend/src/novelai/activity/queue.py` for `update_activity_status`, activity storage shape, source-health methods, and existing locks.
  - [x] 1.4 Inspect `backend/src/novelai/api/routers/activity.py` and response models for activity and source-health routes.
  - [x] 1.5 Inspect `backend/src/novelai/services/orchestration/crawler.py` for `_scrape_chapters_impl`, failure construction, image handling, quality gates, and `progress_callback`.
  - [x] 1.6 Inspect `backend/src/novelai/utils/retry_decorator.py` for retry attempt numbering and backoff flow.
  - [x] 1.7 Inspect `backend/src/novelai/infrastructure/http/fetch_service.py` and source adapter `fetch_chapter_payload` signatures.
  - [x] 1.8 Confirm whether source adapters share a protocol or abstract base class that needs an `on_retry` signature update.
  - [x] 1.9 Inspect existing crawler/activity tests and fixtures for local conventions.

- [x] 2. Lock Observability Semantics
  - [x] 2.1 Define `metadata.crawl_result` as the completed crawl summary.
  - [x] 2.2 Define `metadata.progress` as the running progress object.
  - [x] 2.3 Store progress only under `metadata.progress`, not as root-level metadata fields.
  - [x] 2.4 Define `retry_attempts` as retries after the initial attempt.
  - [x] 2.5 Ensure a 3-attempt exhausted fetch records `retry_attempts=2`.
  - [x] 2.6 Define `image_download_failures` as affected chapter count, not failed image asset count.
  - [x] 2.7 Define fatal crawl behavior: if `scrape_chapters` raises, leave `metadata.crawl_result` absent or null and rely on the top-level activity error.
  - [x] 2.8 Define failure messages as admin-safe and free of credentials, cookies, full HTML, full chapter text, secrets, and local filesystem paths.

- [x] 3. Add Safe Activity Metadata Updates
  - [x] 3.1 Add `update_activity_metadata(activity_id: str, patch: dict) -> bool` to `ActivityQueueService`.
  - [x] 3.2 Return `False` when the activity does not exist.
  - [x] 3.3 Merge `patch` into the existing metadata dictionary instead of replacing metadata.
  - [x] 3.4 Merge nested `progress` patches into existing `metadata.progress`.
  - [x] 3.5 Preserve `metadata.progress` when writing final `crawl_result`.
  - [x] 3.6 Preserve `metadata.crawl_result` when updating progress.
  - [x] 3.7 Use the existing queue/activity lock or equivalent atomic update pattern.
  - [x] 3.8 Reuse `update_activity_status` only if it does not reset timestamps, errors, or unrelated activity state.
  - [x] 3.9 Invalidate source-health cache after successful metadata mutation.

- [x] 4. Add Source-Health Cache Infrastructure
  - [x] 4.1 Add an in-memory source-health cache to `ActivityQueueService`.
  - [x] 4.2 Use a 60-second TTL.
  - [x] 4.3 Use cache keys that distinguish all-source health from specific `source_key` health.
  - [x] 4.4 Invalidate cache when `update_activity_status` mutates an activity.
  - [x] 4.5 Invalidate cache when `update_activity_metadata` mutates an activity.
  - [x] 4.6 Keep TTL as the fallback freshness guarantee if any mutation path cannot invalidate safely.

- [x] 5. Add Retry Callback Support
  - [x] 5.1 Add optional `on_retry: Callable[[int, Exception], None] | None = None` to `Retrier.execute_async`.
  - [x] 5.2 Call `on_retry(retry_number, exc)` before each backoff sleep.
  - [x] 5.3 Ensure first retry after the initial failure reports `retry_number=1`.
  - [x] 5.4 Do not call `on_retry` for the initial attempt.
  - [x] 5.5 Do not call `on_retry` after the final exhausted attempt.
  - [x] 5.6 Swallow and debug-log callback exceptions.
  - [x] 5.7 Preserve behavior for callers that do not pass `on_retry`.

- [x] 6. Thread Retry Telemetry Through Fetching
  - [x] 6.1 Add optional `on_retry` to the private fetch retry method such as `FetchService._with_retry`.
  - [x] 6.2 Add optional `on_retry` to the public fetch method used by chapter fetching, such as `FetchService.get_text`.
  - [x] 6.3 Pass `on_retry` from public fetch method to private retry helper.
  - [x] 6.4 Update source adapter `fetch_chapter_payload` methods that use retried fetches to accept optional `on_retry`.
  - [x] 6.5 Pass `on_retry` from source adapters into fetch service calls.
  - [x] 6.6 Keep every new `on_retry` parameter optional with default `None`.
  - [x] 6.7 Update adapter protocols or abstract base classes if present.
  - [x] 6.8 Leave adapters that cannot support callbacks compatible; their failures should record `retry_attempts=0`.

- [x] 7. Add Error Helper Functions
  - [x] 7.1 Add `_extract_http_status(exc: Exception) -> int | None` in `crawler.py`.
  - [x] 7.2 Prefer `httpx.HTTPStatusError.response.status_code`.
  - [x] 7.3 Fall back to `exc.response.status_code` when present.
  - [x] 7.4 Fall back to `exc.status_code` when present.
  - [x] 7.5 Parse safe message formats: `status=503`, `status_code=503`, `HTTP 503`, standalone `429`, `404`, and `5xx`.
  - [x] 7.6 Add `_classify_error(exc, error_message, http_status_code) -> str`.
  - [x] 7.7 Classify `rate_limited` for HTTP 429 or rate-limit text.
  - [x] 7.8 Classify `not_found` for HTTP 404 or not-found text.
  - [x] 7.9 Classify `timeout` for `httpx.TimeoutException` or timeout text.
  - [x] 7.10 Classify `server_error` for HTTP 500-599.
  - [x] 7.11 Classify `quality_gate` for `_apply_chapter_quality_gate` or equivalent quality-check failures.
  - [x] 7.12 Classify other `SourceError` failures as `fetch_error`.
  - [x] 7.13 Classify unrecognized errors as `unknown`.
  - [x] 7.14 Add or reuse a safe error-message sanitizer if current messages can leak unsafe content.

- [x] 8. Enrich Per-Chapter Failure Records
  - [x] 8.1 In `_scrape_chapters_impl`, initialize retry tracking before each chapter fetch.
  - [x] 8.2 Use a local mutable holder such as `retry_attempts = [0]`.
  - [x] 8.3 Define an `on_retry(retry_number, exc)` callback that records the latest retry number.
  - [x] 8.4 Pass the callback into `source.fetch_chapter_payload(..., on_retry=on_retry)` where supported.
  - [x] 8.5 On chapter failure, compute `error_message`, `http_status_code`, and `error_category`.
  - [x] 8.6 Add `error_category` to each failure dict.
  - [x] 8.7 Add `http_status_code` to each failure dict.
  - [x] 8.8 Add `retry_attempts` to each failure dict.
  - [x] 8.9 Preserve existing fields such as `chapter_id`, `chapter_number`, `title`, `source_url`, `error_type`, and `error_message`.
  - [x] 8.10 Default `http_status_code` to `None`.
  - [x] 8.11 Default `retry_attempts` to `0`.

- [x] 9. Count Image Download Failures
  - [x] 9.1 Track successfully saved chapter payloads or equivalent saved chapter data.
  - [x] 9.2 Count chapters where `payload.get("images")` contains at least one item with `download_error`.
  - [x] 9.3 Store that count as `image_download_failures`.
  - [x] 9.4 Add `image_download_failures` to the dict returned by `scrape_chapters`.
  - [x] 9.5 Do not count failed chapter fetches unless a saved payload contains image error metadata.

- [x] 10. Persist Completed Crawl Result
  - [x] 10.1 Capture the return value of `scrape_chapters` in `_run_crawl_activity`.
  - [x] 10.2 Build `crawl_result` with `succeeded`, `skipped`, `failed`, `failures`, and `image_download_failures`.
  - [x] 10.3 Persist it with `update_activity_metadata(activity_id, {"crawl_result": crawl_result})`.
  - [x] 10.4 Ensure the final update preserves existing `metadata.progress`.
  - [x] 10.5 Return the existing activity result shape with `crawl_result` included where appropriate.
  - [x] 10.6 If `scrape_chapters` raises, do not write `metadata.crawl_result`.
  - [x] 10.7 Let the existing fatal error path mark activity failure and set top-level error.

- [x] 11. Persist Running Crawl Progress
  - [x] 11.1 Compute `total` from the chapter list being scraped when available.
  - [x] 11.2 Fall back to `len(metadata["chapters"])` or the local equivalent when needed.
  - [x] 11.3 Create a progress callback before calling `scrape_chapters`.
  - [x] 11.4 Increment `completed` after each chapter success, skip, or per-chapter failure.
  - [x] 11.5 Write progress as `{"progress": {"completed": completed, "total": total, "current_label": message}}`.
  - [x] 11.6 Catch and debug-log metadata update errors inside the callback.
  - [x] 11.7 Ensure progress persistence cannot fail the crawl.
  - [x] 11.8 Pass the callback into `scrape_chapters(..., progress_callback=progress_cb)`.
  - [x] 11.9 If response models expose top-level `completed` and `total`, derive or mirror from `metadata.progress` without changing the stored contract.

- [x] 12. Enrich Source Health
  - [x] 12.1 Update `list_source_health()` to scan stored activity records with dict-shaped `metadata.crawl_result`.
  - [x] 12.2 Group source-health data by `source_key`.
  - [x] 12.3 Compute `total_chapters_attempted = succeeded + skipped + failed`.
  - [x] 12.4 Compute `total_chapters_succeeded`.
  - [x] 12.5 Compute `total_chapters_failed`.
  - [x] 12.6 Compute `error_category_counts`, defaulting missing categories to `unknown`.
  - [x] 12.7 Compute `http_status_counts` from known `http_status_code` values.
  - [x] 12.8 Compute `last_crawl_at` from the latest completed or finished crawl activity timestamp.
  - [x] 12.9 Ignore activity records without valid crawl result metadata.
  - [x] 12.10 Ensure `get_source_health(source_key)` returns the enriched record for one source.
  - [x] 12.11 Apply the 60-second cache without hiding fresh data after activity mutations.

- [x] 13. Update API Response Models Only If Needed
  - [x] 13.1 If source-health endpoints return raw dicts, make no model change.
  - [x] 13.2 If source-health endpoints use strict response models, add:
    - [x] 13.2.1 `total_chapters_attempted`
    - [x] 13.2.2 `total_chapters_succeeded`
    - [x] 13.2.3 `total_chapters_failed`
    - [x] 13.2.4 `error_category_counts`
    - [x] 13.2.5 `http_status_counts`
    - [x] 13.2.6 `last_crawl_at`
  - [x] 13.3 Confirm `ActivityRecordResponse` exposes `metadata: dict`.
  - [x] 13.4 Do not add new endpoints.

- [x] 14. Add Test File and Fixtures
  - [x] 14.1 Create `backend/tests/test_crawl_fetch_observability.py`.
  - [x] 14.2 Reuse existing activity queue fixtures where possible.
  - [x] 14.3 Reuse existing crawler/orchestrator fixtures where possible.
  - [x] 14.4 Use fake source adapters or mocks.
  - [x] 14.5 Do not perform real HTTP.
  - [x] 14.6 Add fixture helpers for successful scrape results.
  - [x] 14.7 Add fixture helpers for partial failure scrape results.
  - [x] 14.8 Add fixture helpers for saved chapter payloads containing image `download_error`.
  - [x] 14.9 Add fixture helpers for source-health activities with stored `metadata.crawl_result`.

- [x] 15. Write Crawl Result Tests
  - [x] 15.1 Test completed crawl persists `metadata.crawl_result`.
  - [x] 15.2 Assert `crawl_result` includes `succeeded`, `skipped`, `failed`, `failures`, and `image_download_failures`.
  - [x] 15.3 Assert failure records preserve existing fields.
  - [x] 15.4 Test fatal crawl errors leave `metadata.crawl_result` absent or null.
  - [x] 15.5 Assert fatal crawl errors still set top-level activity error.
  - [x] 15.6 Test final `crawl_result` write preserves existing `metadata.progress`.

- [x] 16. Write Failure Telemetry Tests
  - [x] 16.1 Test HTTP 429 or rate-limit text classifies as `rate_limited`.
  - [x] 16.2 Test `httpx.HTTPStatusError` with status 503 records `http_status_code=503`.
  - [x] 16.3 Test message parsing for `status=503`.
  - [x] 16.4 Test message parsing for `status_code=503`.
  - [x] 16.5 Test message parsing for `HTTP 503`.
  - [x] 16.6 Test `timeout` classification.
  - [x] 16.7 Test `not_found` classification.
  - [x] 16.8 Test `server_error` classification.
  - [x] 16.9 Test `quality_gate` classification.
  - [x] 16.10 Test a 3-attempt exhausted fetch records `retry_attempts == 2`.
  - [x] 16.11 Test exceptions raised by `on_retry` do not break retry behavior.
  - [x] 16.12 Test unsafe error-message content is sanitized or omitted if sanitizer is added.

- [x] 17. Write Progress Tests
  - [x] 17.1 Test progress callback updates activity metadata during crawl.
  - [x] 17.2 Assert progress is stored under `metadata.progress`.
  - [x] 17.3 Assert progress includes `completed`, `total`, and `current_label`.
  - [x] 17.4 Assert progress increments after success.
  - [x] 17.5 Assert progress increments after skip where supported.
  - [x] 17.6 Assert progress increments after per-chapter failure.
  - [x] 17.7 If API exposes top-level progress fields, test they derive from `metadata.progress`.

- [x] 18. Write Image Failure Tests
  - [x] 18.1 Test one chapter with one image `download_error` records `image_download_failures == 1`.
  - [x] 18.2 Test one chapter with multiple image errors still counts as `1`.
  - [x] 18.3 Test multiple affected chapters count by affected chapter count.
  - [x] 18.4 Test failed chapter fetches without saved payloads do not increase the count.

- [x] 19. Write Source Health Tests
  - [x] 19.1 Test source health includes `total_chapters_attempted`.
  - [x] 19.2 Test source health includes `total_chapters_succeeded`.
  - [x] 19.3 Test source health includes `total_chapters_failed`.
  - [x] 19.4 Test source health includes `error_category_counts`.
  - [x] 19.5 Test source health includes `http_status_counts`.
  - [x] 19.6 Test source health includes `last_crawl_at`.
  - [x] 19.7 Test activities without dict-shaped `metadata.crawl_result` are ignored.
  - [x] 19.8 Test source-health cache invalidates after `update_activity_metadata`.
  - [x] 19.9 Test source-health cache invalidates after `update_activity_status`.
  - [x] 19.10 Add API-level source-health response test if strict response models are used.

- [x] 20. Backward Compatibility Checks
  - [x] 20.1 Confirm existing activity records without `metadata.crawl_result` still load and serialize.
  - [x] 20.2 Confirm existing callers of `Retrier.execute_async` work without `on_retry`.
  - [x] 20.3 Confirm existing source adapters work without `on_retry`.
  - [x] 20.4 Confirm no DB migration files are created.
  - [x] 20.5 Confirm no storage format files are changed.
  - [x] 20.6 Confirm no new endpoints are added.
  - [x] 20.7 Confirm retry delay, max attempts, and retryable exception behavior are unchanged.

- [x] 21. Run Verification
  - [x] 21.1 Run `pytest backend/tests/test_crawl_fetch_observability.py --tb=short -q`.
  - [x] 21.2 Run existing crawler tests if present.
  - [x] 21.3 Run existing activity queue/API tests if present.
  - [x] 21.4 Run `ruff check` on changed backend source and test files.
  - [x] 21.5 Include `fetch_service.py` and changed source adapters in lint checks if edited.
  - [x] 21.6 Run the configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 21.7 Fix test, lint, and type failures caused by this work.

- [x] 22. Final Acceptance Review
  - [x] 22.1 Verify completed crawl activity responses expose `metadata.crawl_result`.
  - [x] 22.2 Verify each persisted failure includes `error_category`, `http_status_code`, and `retry_attempts`.
  - [x] 22.3 Verify running crawl responses expose `metadata.progress.completed`, `metadata.progress.total`, and `metadata.progress.current_label`.
  - [x] 22.4 Verify source health exposes attempted, succeeded, failed, category counts, HTTP status counts, and last crawl timestamp.
  - [x] 22.5 Verify HTTP 429 failures record `rate_limited` and `http_status_code=429`.
  - [x] 22.6 Verify quality gate failures record `quality_gate`.
  - [x] 22.7 Verify image download failures use affected-chapter count semantics.
  - [x] 22.8 Verify fatal crawl errors do not create a misleading partial `crawl_result`.
  - [x] 22.9 Verify source-health cache invalidates on activity mutation or refreshes within TTL.
  - [x] 22.10 Verify all required tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Persist Crawl Result Metadata | 2, 3, 10, 15, 20, 22 |
| REQ-2 Safe Activity Metadata Updates | 3, 10, 15, 17, 19 |
| REQ-3 Crawl Progress Metadata | 2, 3, 11, 17, 22 |
| REQ-4 Failure Classification | 7, 8, 16, 22 |
| REQ-5 HTTP Status and Retry Attempts | 5, 6, 7, 8, 16, 20, 22 |
| REQ-6 Retry Callback Support | 5, 6, 16, 20 |
| REQ-7 Image Download Failures | 9, 10, 18, 22 |
| REQ-8 Source Health Enrichment | 4, 12, 13, 19, 22 |
| REQ-9 Source Health Cache | 3, 4, 12, 19, 22 |
| REQ-10 Safety and Compatibility | 2, 8, 13, 20, 21 |
| REQ-11 Tests | 14, 15, 16, 17, 18, 19, 21 |

## Definition of Done

- [x] `metadata.crawl_result` is persisted after non-fatal crawl completion.
- [x] Fatal crawl errors leave `metadata.crawl_result` absent or null and use top-level activity error.
- [x] Failure records include `error_category`, `http_status_code`, and `retry_attempts`.
- [x] Retry telemetry is threaded from `Retrier` through fetch/source code where supported.
- [x] Running crawl progress is stored under `metadata.progress`.
- [x] Final crawl result updates preserve progress metadata.
- [x] Source health includes aggregate crawl success/failure counts.
- [x] Source health includes `error_category_counts` and `http_status_counts`.
- [x] Source health cache has a 60-second TTL and invalidates on activity mutation.
- [x] Image download failures are counted by affected chapter count.
- [x] New retry callback parameters default to `None`.
- [x] Existing callers remain compatible.
- [x] No DB migration, storage format change, or endpoint addition is introduced.
- [x] Focused tests, lint checks, and configured type checks pass.

### Verification Results

- **Tests:** 48/48 pass in `test_crawl_fetch_observability.py` (4.98s).
- **Existing tests:** 18/18 pass in `test_job_queue_service.py` + `test_job_worker_service.py` + `test_activity_provider_errors.py`.
- **Ruff:** All checks passed on all 10 modified files.
- **Pyright:** 0 errors on all 10 modified files.
- **Bug fix:** Fixed cache invalidation in `update_activity_status` — was only invalidating when `metadata` was passed; now invalidates on all status updates.