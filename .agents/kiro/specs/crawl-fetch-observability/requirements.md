# Requirements: Crawl and Fetch Observability

## Introduction

The crawl/fetch infrastructure already has solid runtime behavior: per-chapter partial failures, concurrency locks, domain throttling, in-memory caching, and retry with exponential backoff. The gap is observability. Useful diagnostics such as HTTP status codes, retry counts, image download failures, and per-chapter failure details are produced during execution but are not reliably persisted into activity records.

Today, diagnosing a partially failed crawl often requires reading logs. This spec makes crawl/fetch diagnostics available through existing activity and source-health APIs by persisting compact crawl metadata.

This work is additive. It does not change crawl behavior, retry policy, storage schemas, database models, or public reader behavior.

## Requirements

### REQ-1: Persist Crawl Result Metadata

The result returned by `scrape_chapters` must be stored in the crawl activity record.

- REQ-1.1: In `backend/src/novelai/activity/worker.py`, `_run_crawl_activity` must capture the return value of `scrape_chapters`.
- REQ-1.2: The activity metadata must store the completed crawl summary under `metadata.crawl_result`.
- REQ-1.3: `metadata.crawl_result` must include `succeeded`, `skipped`, `failed`, `failures`, and `image_download_failures`.
- REQ-1.4: The activity response model must continue exposing `metadata` as a dictionary; no activity schema migration is required.
- REQ-1.5: If `scrape_chapters` raises a fatal exception, `metadata.crawl_result` must remain absent or `null`; the existing top-level activity error remains the source of truth.
- REQ-1.6: Writing `crawl_result` must preserve existing activity metadata such as `metadata.progress`.

Example:

```json
{
  "crawl_result": {
    "succeeded": 10,
    "skipped": 2,
    "failed": 1,
    "image_download_failures": 1,
    "failures": [
      {
        "chapter_id": "5",
        "chapter_number": 5,
        "title": "Chapter Title",
        "source_url": "https://example.test/chapter-5",
        "error_type": "SourceError",
        "error_message": "HTTP 429 Too Many Requests",
        "error_category": "rate_limited",
        "http_status_code": 429,
        "retry_attempts": 2
      }
    ]
  }
}
```

### REQ-2: Add Safe Activity Metadata Updates

Activity metadata updates must merge patches without replacing unrelated metadata.

- REQ-2.1: `ActivityQueueService` must expose `update_activity_metadata(activity_id, metadata_patch)` or an equivalent helper.
- REQ-2.2: Metadata patches must merge into the existing metadata dictionary.
- REQ-2.3: Nested `progress` patches must merge into existing `metadata.progress`.
- REQ-2.4: Updating progress must not delete `crawl_result`.
- REQ-2.5: Writing final `crawl_result` must not delete `progress`.
- REQ-2.6: Metadata updates must use the existing queue/activity lock or equivalent atomic update pattern.

### REQ-3: Record Crawl Progress During Execution

Running crawl activities must expose chapter progress through activity metadata.

- REQ-3.1: `_run_crawl_activity` must create a progress callback before calling `scrape_chapters`.
- REQ-3.2: The progress callback must update `metadata.progress`.
- REQ-3.3: The canonical progress shape is:

```json
{
  "progress": {
    "completed": 4,
    "total": 20,
    "current_label": "Chapter 4"
  }
}
```

- REQ-3.4: Progress must update after each completed chapter attempt, including success, skip, and per-chapter failure.
- REQ-3.5: If activity responses expose top-level `completed` or `total`, those fields may be derived from `metadata.progress`; the stored contract remains nested under `metadata.progress`.

### REQ-4: Classify Per-Chapter Failures

Each per-chapter failure record must include a normalized `error_category`.

- REQ-4.1: In `backend/src/novelai/services/orchestration/crawler.py`, `_scrape_chapters_impl` must add `error_category` to each failure dict.
- REQ-4.2: `error_category` must be derived from exception type, HTTP status, and safe message text.
- REQ-4.3: Supported categories must include:
  - `rate_limited`
  - `not_found`
  - `timeout`
  - `server_error`
  - `fetch_error`
  - `quality_gate`
  - `unknown`
- REQ-4.4: HTTP 429 or rate-limit messages must classify as `rate_limited`.
- REQ-4.5: HTTP 404 or not-found messages must classify as `not_found`.
- REQ-4.6: `httpx.TimeoutException` or timeout messages must classify as `timeout`.
- REQ-4.7: HTTP 5xx statuses must classify as `server_error`.
- REQ-4.8: Other `SourceError` failures must classify as `fetch_error`.
- REQ-4.9: Errors raised by `_apply_chapter_quality_gate` or equivalent quality checks must classify as `quality_gate`.
- REQ-4.10: Unrecognized errors must classify as `unknown`.

### REQ-5: Capture HTTP Status and Retry Attempts

Failure records must include HTTP status and retry telemetry when available.

- REQ-5.1: Add `http_status_code: int | null` to each failure record.
- REQ-5.2: HTTP status extraction must prefer structured exception data such as `httpx.HTTPStatusError.response.status_code`.
- REQ-5.3: If structured status is unavailable, status extraction may parse safe message patterns such as `status=503`, `status_code=503`, `HTTP 503`, `429`, `404`, and `5xx`.
- REQ-5.4: Add `retry_attempts: int` to each failure record.
- REQ-5.5: `retry_attempts` means retries after the initial attempt.
- REQ-5.6: A fetch configured for 3 total attempts that exhausts all attempts must record `retry_attempts=2`.
- REQ-5.7: `retry_attempts` must default to `0` when retry telemetry is unavailable.
- REQ-5.8: `http_status_code` must default to `null` when no status can be extracted.
- REQ-5.9: If total attempts are exposed later, they must use a separate field such as `attempts_total`.

### REQ-6: Add Retry Callback Support

The retry stack must expose retry telemetry without changing retry behavior.

- REQ-6.1: `Retrier.execute_async` must accept an optional `on_retry: Callable[[int, Exception], None]`.
- REQ-6.2: `on_retry` must default to `None`.
- REQ-6.3: The callback must fire before backoff sleep.
- REQ-6.4: The callback must fire only for failed attempts that will be retried.
- REQ-6.5: The callback must not fire after the final exhausted attempt.
- REQ-6.6: Callback exceptions must be swallowed and logged at debug level.
- REQ-6.7: `FetchService` must pass `on_retry` into retried fetch calls where supported.
- REQ-6.8: Source adapters that call the retried fetch service should accept and forward `on_retry`.
- REQ-6.9: Existing callers must remain compatible.

### REQ-7: Count Image Download Failures

Image download failures must be surfaced in the crawl summary.

- REQ-7.1: Add `image_download_failures: int` to `crawl_result`.
- REQ-7.2: This value must count chapters affected by image download errors, not individual failed image assets.
- REQ-7.3: A chapter with three failed images must contribute `1`.
- REQ-7.4: The count must be computed from successfully saved chapter payloads or equivalent saved chapter data where image entries contain `download_error`.
- REQ-7.5: Failed chapter fetches without saved payloads must not increase `image_download_failures`.

### REQ-8: Enrich Source Health

The existing source-health surface must summarize crawl success and failure patterns.

- REQ-8.1: `ActivityQueueService.list_source_health()` and `get_source_health(source_key)` must derive enriched fields from stored activity metadata.
- REQ-8.2: Source health must include:
  - `total_chapters_attempted`
  - `total_chapters_succeeded`
  - `total_chapters_failed`
  - `error_category_counts`
  - `http_status_counts`
  - `last_crawl_at`
- REQ-8.3: `total_chapters_attempted` must be computed as `succeeded + skipped + failed`.
- REQ-8.4: `error_category_counts` must aggregate categories from `crawl_result.failures`.
- REQ-8.5: `http_status_counts` must aggregate known `http_status_code` values from `crawl_result.failures`.
- REQ-8.6: `last_crawl_at` must use the latest completed or finished crawl activity timestamp for the source.
- REQ-8.7: Source health must ignore activity records without a valid dict-shaped `metadata.crawl_result`.
- REQ-8.8: If source-health endpoints use strict response models, those models must be updated so enriched fields are returned.

### REQ-9: Cache Source Health Safely

Source-health aggregation must avoid recomputing from scratch on every request.

- REQ-9.1: Cache source-health aggregation in `ActivityQueueService` for up to 60 seconds.
- REQ-9.2: The cache may be an in-memory dictionary with timestamps; Redis or a new metrics store is not required.
- REQ-9.3: Cache must invalidate when activity status changes.
- REQ-9.4: Cache must invalidate when activity metadata changes.
- REQ-9.5: If a mutation path cannot safely invalidate cache, the 60-second TTL must remain the fallback freshness guarantee.

### REQ-10: Safety and Compatibility

The observability metadata must be safe and backward compatible.

- REQ-10.1: Failure messages must not include credentials, cookies, secrets, full HTML bodies, full chapter text, or local filesystem paths.
- REQ-10.2: Existing activity records without `crawl_result` must remain valid.
- REQ-10.3: Existing source adapters may ignore `on_retry` if their fetch path does not use the retried fetch service.
- REQ-10.4: Existing retry timing, max attempts, and retryable exception behavior must not change.
- REQ-10.5: No storage schema changes are allowed.
- REQ-10.6: No database migration is allowed.
- REQ-10.7: No new API endpoint is required.

### REQ-11: Tests

Create `backend/tests/test_crawl_fetch_observability.py`.

- REQ-11.1: `test_crawl_result_persisted_in_activity` must assert completed crawl activity metadata includes `crawl_result`.
- REQ-11.2: `test_failure_record_includes_error_category` must assert a mocked HTTP 429 failure records `rate_limited`.
- REQ-11.3: `test_failure_record_includes_http_status` must assert an `httpx.HTTPStatusError` with status 503 records `http_status_code=503`.
- REQ-11.4: `test_retry_attempts_recorded` must assert a 3-attempt exhausted fetch records `retry_attempts=2`.
- REQ-11.5: `test_progress_callback_updates_activity_metadata` must assert `metadata.progress.completed`, `total`, and `current_label` update during crawl.
- REQ-11.6: `test_progress_survives_crawl_result_update` must assert final `crawl_result` does not delete progress metadata.
- REQ-11.7: `test_source_health_includes_error_category_counts` must assert multiple crawl activities aggregate error categories correctly.
- REQ-11.8: `test_source_health_includes_http_status_counts` must assert HTTP status counts are returned.
- REQ-11.9: `test_source_health_cache_invalidates_on_metadata_update` must assert source health reflects updated crawl metadata after invalidation.
- REQ-11.10: `test_image_download_failures_counted` must assert one chapter with image download errors contributes `1`.
- REQ-11.11: `test_fatal_crawl_error_does_not_set_crawl_result` must assert fatal crawl errors leave `crawl_result` absent or null and set top-level activity error.
- REQ-11.12: Tests must not perform real HTTP requests.

## Non-Goals

- This spec does not add distributed tracing.
- This spec does not add OpenTelemetry, Jaeger, Prometheus, or a metrics database.
- This spec does not add a retry policy UI.
- This spec does not expose retry configuration through the API.
- This spec does not change retry behavior.
- This spec does not add new storage files or DB tables.
- This spec does not change translation pipeline observability.
- This spec does not change public reader behavior.