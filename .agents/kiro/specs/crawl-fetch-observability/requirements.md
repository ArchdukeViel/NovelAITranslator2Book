# Requirements: Crawl and Fetch Observability

## Introduction

The crawl infrastructure has good bones: per-chapter partial-failure semantics, concurrency locks, domain throttling, in-memory caching, and a retry mechanism with exponential backoff. But none of the rich diagnostic data produced at fetch time survives past the Python logger. HTTP status codes, retry attempt counts, elapsed response times, and backoff durations are computed and then discarded. The per-chapter `failures` list from `scrape_chapters` is never stored in the activity record — `_run_crawl_activity` discards the return value. Image download failures are captured in chapter image manifests but never counted or surfaced through the admin API. The result is that diagnosing a crawl that partially failed means reading log files, not querying an endpoint.

This spec persists the diagnostic data that already exists and surfaces it through the activity API.

## Requirements

### REQ-1: Persist Per-Chapter Failure Details in Activity Record

The per-chapter `failures` list from `scrape_chapters` must be stored in the activity record.

- REQ-1.1: In `backend/src/novelai/activity/worker.py`, `_run_crawl_activity` must capture the return value of `scrape_chapters` and extract `failures`, `succeeded`, `skipped`, `failed` counts.
- REQ-1.2: These must be written to the activity's `metadata` dict under `"crawl_result"`:
  ```json
  {
    "crawl_result": {
      "succeeded": 10,
      "skipped": 2,
      "failed": 1,
      "failures": [
        {
          "chapter_id": "5",
          "chapter_number": 5,
          "title": "...",
          "source_url": "...",
          "error_type": "SourceError",
          "error_message": "..."
        }
      ]
    }
  }
  ```
- REQ-1.3: This must be persisted by calling `activity_log.update_activity_status(activity_id, status, metadata={"crawl_result": ...})` or equivalent update after the scrape completes.
- REQ-1.4: The `ActivityRecordResponse` model must already carry `metadata: dict` — no schema change needed.
- REQ-1.5: When `scrape_chapters` raises (a fatal error), the `crawl_result` should not be set (or set to `null`); the top-level `error` field on the activity is sufficient.

### REQ-2: Extend Per-Chapter Failure Record with Error Classification

The per-chapter failure records must include an `error_category` field.

- REQ-2.1: Add `error_category: str` to each failure dict in `_scrape_chapters_impl` in `backend/src/novelai/services/orchestration/crawler.py`.
- REQ-2.2: The `error_category` must be derived from the exception type and HTTP status code when available:
  - `"rate_limited"` — `SourceError` with message containing `"429"` or `"rate"` (case-insensitive)
  - `"not_found"` — `SourceError` with message containing `"404"`
  - `"timeout"` — `SourceError` with message containing `"timeout"` or `httpx.TimeoutException`
  - `"server_error"` — status codes 500-599 in the error message
  - `"fetch_error"` — any other `SourceError`
  - `"quality_gate"` — errors raised by `_apply_chapter_quality_gate` or quality check functions
  - `"unknown"` — anything else
- REQ-2.3: `error_category` must be a string field in the failure dict alongside the existing `error_type` and `error_message`.

### REQ-3: Add HTTP Fetch Telemetry to Failure Records

When a chapter fetch fails after retries, the final HTTP status code must be captured in the failure record.

- REQ-3.1: Add `http_status_code: int | None` to the failure dict. When the exception is `httpx.HTTPStatusError` or when the `error_message` contains a parseable status code, extract and record it.
- REQ-3.2: Add `retry_attempts: int` to the failure dict. When the `Retrier` exhausts attempts, the final attempt number must be accessible. The simplest approach: wrap `fetch_chapter_payload` calls to count attempts via a try/except chain, or add attempt tracking to `Retrier`.
- REQ-3.3: `Retrier.execute_async` must accept an optional `on_retry` callback `Callable[[int, Exception], None]` that fires before each retry. The crawler can use this to count attempts.
- REQ-3.4: `http_status_code` and `retry_attempts` must default to `None` / `0` when not applicable (e.g. non-HTTP errors).
- REQ-3.5: `retry_attempts` means retries after the initial attempt. For example, a fetch configured for 3 total attempts records `retry_attempts=2` when it fails after exhausting all attempts. If the implementation needs total attempts, expose it separately as `attempts_total`.

### REQ-4: Crawl Progress Metadata During Execution

A running crawl activity must expose real-time chapter progress via the activity metadata.

- REQ-4.1: The existing `progress_callback` mechanism in `scrape_chapters` must be extended to write progress to the activity metadata, not just log to a string.
- EQ-4.2: In `_run_crawl_activity`, before calling `scrape_chapters`, create a `progress_callback` that calls `activity_log.update_activity_metadata(activity_id, {"progress": {"completed": n, "total": total, "current_label": message}})` (or equivalent `metadata` update).
- REQ-4.3: Progress updates must happen after each chapter completes (success or failure), not just at the end.
- REQ-4.4: If `ActivityRecordResponse` exposes top-level `completed` and `total` fields, the activity response layer may derive them from `metadata.progress`; the canonical stored shape is `metadata.progress`
- REQ-4.5: `ActivityQueueService` must expose an `update_activity_metadata(activity_id, metadata_patch: dict)` method that merges the patch into the existing metadata dict without replacing all fields.

### REQ-5: Source Health Enrichment

The `source-health` endpoint must expose fetch success/failure counts and HTTP error code distribution.

- REQ-5.1: The existing `list_source_health()` / `get_source_health(source_key)` in `ActivityQueueService` must include in the source health record:
  - `total_chapters_attempted: int` — sum across all crawl activities for that source
  - `total_chapters_succeeded: int`
  - `total_chapters_failed: int`
  - `error_category_counts: dict[str, int]` — e.g. `{"rate_limited": 3, "timeout": 1, "fetch_error": 2}`
  - `last_crawl_at: str | None` — ISO timestamp of the most recent finished crawl activity for this source
- REQ-5.2: These must be computed by scanning the `crawl_result` metadata of completed crawl activities for the given source. This is a read-only computation on stored activity records.
- REQ-5.3: The endpoint must not recompute from scratch on every call — cache the result in the `ActivityQueueService` for up to 60 seconds (simple `dict` + timestamp, no Redis).
- REQ-5.4: If the activity API uses a strict response model for source health, update that response model so the new source health fields are actually returned by the endpoint.

### REQ-6: Image Download Failure Visibility

Image download failures must be counted and surfaced in the crawl result summary.

- REQ-6.1: Add `image_download_failures: int` to the `crawl_result` dict. This value counts chapters where at least one image entry has `download_error`, not the total number of failed images.
- REQ-6.2: This is computed from the chapter payloads that were successfully saved but had image errors embedded in the `images` list.
- REQ-6.3: `image_download_failures` must be included in the `crawl_result` returned by `scrape_chapters` and persisted in the activity metadata.

### REQ-7: Tests

- REQ-7.1: A new test file `backend/tests/test_crawl_fetch_observability.py` must be created.
- REQ-7.2: `test_crawl_result_persisted_in_activity` — after `_run_crawl_activity` completes, the activity record has `metadata.crawl_result` with `succeeded`, `skipped`, `failed`, and `failures`.
- REQ-7.3: `test_failure_record_includes_error_category` — mock `fetch_chapter_payload` to raise a `SourceError` with "429" in the message; assert `error_category="rate_limited"` in the failure.
- REQ-7.4: `test_failure_record_includes_http_status` — mock `fetch_chapter_payload` to raise `httpx.HTTPStatusError` with status 503; assert `http_status_code=503` in the failure.
- REQ-7.5: `test_progress_callback_updates_activity_metadata` — assert `completed` and `total` are updated during scrape via the progress callback.
- REQ-7.6: `test_source_health_includes_error_category_counts` — create two activities with different error categories; assert `error_category_counts` reflects them.
- REQ-7.7: `test_image_download_failures_counted` — chapter with one image download error; assert `image_download_failures=1` in crawl_result.
- REQ-7.8: `test_fatal_crawl_error_does_not_set_crawl_result` — `scrape_chapters` raises; assert `crawl_result` is not in activity metadata (or is null); top-level `error` is set.

## Non-Goals

- This spec does not add distributed tracing (OpenTelemetry, Jaeger, etc.).
- This spec does not add a retry policy UI or expose `Retrier` config through the API.
- This spec does not change the fetch retry behavior itself — only what is recorded.
- This spec does not add a separate metrics store or time-series database.
- This spec does not change the translation pipeline observability (that is owned by `operational-safety-observability`).
