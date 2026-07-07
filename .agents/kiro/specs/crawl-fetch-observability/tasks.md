# Tasks: Crawl and Fetch Observability

## Overview

Implement crawl/fetch observability by persisting the existing crawl result data into activity metadata, enriching per-chapter failure records with actionable diagnostics, exposing running crawl progress, and extending source health summaries from stored activity records.

Scope boundaries:

- No new storage files.
- No new database tables.
- No new API endpoints.
- No retry behavior changes beyond recording retry telemetry.
- No distributed tracing or metrics backend.
- Translation pipeline observability is out of scope.

## Task List

- [ ] 0. Preflight API and Interface Review
  - [ ] 0.1 Inspect `backend/src/novelai/activity/worker.py` and identify `_run_crawl_activity` and how activity status/errors are currently written.
  - [ ] 0.2 Inspect `backend/src/novelai/activity/queue.py` and identify `update_activity_status`, `list_source_health`, `get_source_health`, activity storage shape, and any locking already used.
  - [ ] 0.3 Inspect `backend/src/novelai/api/routers/activity.py` and any activity/source-health response models to confirm whether new source health fields require response model updates.
  - [ ] 0.4 Inspect `backend/src/novelai/services/orchestration/crawler.py` and identify `_scrape_chapters_impl`, failure record construction, quality gate errors, image handling, and `progress_callback` usage.
  - [ ] 0.5 Inspect `backend/src/novelai/utils/retry_decorator.py` and confirm the retry loop's attempt numbering and backoff flow.
  - [ ] 0.6 Inspect `backend/src/novelai/infrastructure/http/fetch_service.py` and source adapter `fetch_chapter_payload` signatures to choose the retry telemetry propagation path.
  - [ ] 0.7 Confirm whether source adapters share a base protocol/abstract method that must be updated for `on_retry`.
  - [ ] 0.8 Inspect existing activity/crawler tests and fixtures so new tests reuse local conventions.

- [ ] 1. Define Telemetry Semantics Before Coding
  - [ ] 1.1 Define `metadata.crawl_result` as the canonical completed crawl summary. (REQ-1)
  - [ ] 1.2 Define `metadata.progress` as the canonical running progress object. (REQ-4)
  - [ ] 1.3 Store progress as `{"progress": {"completed": n, "total": total, "current_label": message}}`, not as root-level metadata fields.
  - [ ] 1.4 Define `retry_attempts` as retries after the initial attempt. Example: a failed fetch configured for 3 total attempts records `retry_attempts=2`. (REQ-3.2, REQ-3.4)
  - [ ] 1.5 If the implementation needs total attempts, use an internal variable or optional `attempts_total`; do not silently redefine `retry_attempts`.
  - [ ] 1.6 Define `image_download_failures` as the number of chapters with at least one image entry containing `download_error`, not the total number of failed images. (REQ-6.1, REQ-6.2)
  - [ ] 1.7 Define fatal crawl behavior: when `scrape_chapters` raises, leave `metadata.crawl_result` absent and rely on the top-level activity error. (REQ-1.5)

- [ ] 2. Add Safe Metadata Patch Support to `ActivityQueueService`
  - [ ] 2.1 Add `update_activity_metadata(activity_id: str, patch: dict) -> bool` to `backend/src/novelai/activity/queue.py`. (REQ-4.5)
  - [ ] 2.2 Load the existing activity and return `False` if the activity does not exist.
  - [ ] 2.3 Merge the patch into the existing metadata dict instead of replacing metadata wholesale.
  - [ ] 2.4 Preserve existing metadata keys when adding `crawl_result`.
  - [ ] 2.5 Preserve existing metadata keys when updating `progress`.
  - [ ] 2.6 For nested `progress` patches, merge into existing `metadata.progress` rather than replacing unrelated progress fields.
  - [ ] 2.7 Use any existing queue/activity lock around the full read-modify-write operation; if no lock exists, add the smallest local lock consistent with the service style.
  - [ ] 2.8 Reuse `update_activity_status` only if doing so does not reset timestamps, error fields, or other activity state incorrectly.
  - [ ] 2.9 Invalidate source health cache after successful metadata mutation.

- [ ] 3. Add Source Health Cache Infrastructure
  - [ ] 3.1 Add a simple in-memory source health cache to `ActivityQueueService`.
  - [ ] 3.2 Use a 60-second TTL for cached source health results. (REQ-5.3)
  - [ ] 3.3 Include cache keys that distinguish all-source health from a specific `source_key`, if both paths are cached.
  - [ ] 3.4 Invalidate the source health cache when `update_activity_status` mutates an activity.
  - [ ] 3.5 Invalidate the source health cache when `update_activity_metadata` mutates an activity.
  - [ ] 3.6 Keep stale reads bounded by TTL even if one mutation path misses invalidation.

- [ ] 4. Add `on_retry` Support to `Retrier`
  - [ ] 4.1 Add optional `on_retry: Callable[[int, Exception], None] | None = None` to `Retrier.execute_async` in `backend/src/novelai/utils/retry_decorator.py`. (REQ-3.3)
  - [ ] 4.2 Call `on_retry(retry_number, exc)` before each backoff sleep.
  - [ ] 4.3 Use retry numbering that matches the chosen semantics: first retry after initial failure should report `1`.
  - [ ] 4.4 Do not call `on_retry` for the initial attempt.
  - [ ] 4.5 Do not call `on_retry` after the final exhausted attempt if there will be no retry sleep.
  - [ ] 4.6 Wrap callback execution in `try/except` so callback failures do not affect retry logic. (REQ-3.3)
  - [ ] 4.7 Preserve existing behavior for all callers that do not pass `on_retry`.

- [ ] 5. Thread Retry Telemetry Through the Fetch Stack
  - [ ] 5.1 Add optional `on_retry` to the private fetch/retry method that calls `Retrier.execute_async`, such as `FetchService._with_retry`.
  - [ ] 5.2 Add optional `on_retry` to the public fetch method used by chapter payload fetching, such as `FetchService.get_text` or the local equivalent.
  - [ ] 5.3 Pass `on_retry` from the public fetch method to `_with_retry`.
  - [ ] 5.4 Update source adapter `fetch_chapter_payload` methods that use the retried fetch service to accept optional `on_retry`.
  - [ ] 5.5 Pass `on_retry` from source adapter `fetch_chapter_payload` into the fetch service call.
  - [ ] 5.6 Keep every new `on_retry` parameter optional with default `None`.
  - [ ] 5.7 Update any abstract base class, protocol, or typing definition for source adapters if the project has one.
  - [ ] 5.8 If a source adapter cannot support retry callbacks, leave it compatible and document that failures from that adapter record `retry_attempts=0`.

- [ ] 6. Add Error Classification Helpers in `crawler.py`
  - [ ] 6.1 Add `_extract_http_status(exc: Exception) -> int | None` in `backend/src/novelai/services/orchestration/crawler.py`. (REQ-3.1)
  - [ ] 6.2 Prefer structured status sources before regex parsing:
    - [ ] 6.2.1 `httpx.HTTPStatusError.response.status_code`
    - [ ] 6.2.2 `exc.response.status_code` when present
    - [ ] 6.2.3 `exc.status_code` when present
  - [ ] 6.3 Add regex parsing for common message formats:
    - [ ] 6.3.1 `status=503`
    - [ ] 6.3.2 `status_code=503`
    - [ ] 6.3.3 `HTTP 503`
    - [ ] 6.3.4 standalone `429`, `404`, or `5xx` tokens when safe to parse
  - [ ] 6.4 Add `_classify_error(exc: Exception, error_message: str, http_status_code: int | None = None) -> str`. (REQ-2.1, REQ-2.2)
  - [ ] 6.5 Classify `rate_limited` for HTTP 429 or rate-limit text.
  - [ ] 6.6 Classify `not_found` for HTTP 404 or not-found text.
  - [ ] 6.7 Classify `timeout` for `httpx.TimeoutException` or timeout text.
  - [ ] 6.8 Classify `server_error` for HTTP 500-599.
  - [ ] 6.9 Classify `quality_gate` for errors raised by `_apply_chapter_quality_gate` or quality check functions.
  - [ ] 6.10 Classify any other `SourceError` as `fetch_error`.
  - [ ] 6.11 Classify anything else as `unknown`.
  - [ ] 6.12 Keep helper behavior deterministic and easy to unit test.

- [ ] 7. Enrich Per-Chapter Failure Records
  - [ ] 7.1 In `_scrape_chapters_impl`, initialize per-chapter retry tracking before fetching the chapter payload. (REQ-3.2)
  - [ ] 7.2 Use a local `retry_attempts = [0]` or equivalent mutable holder.
  - [ ] 7.3 Define a local `on_retry(retry_number: int, exc: Exception) -> None` callback that records the latest retry number.
  - [ ] 7.4 Pass the callback into `source.fetch_chapter_payload(..., on_retry=on_retry)` when supported.
  - [ ] 7.5 On chapter failure, compute `error_message = str(exc)`.
  - [ ] 7.6 Compute `http_status_code` using `_extract_http_status(exc)`.
  - [ ] 7.7 Compute `error_category` using `_classify_error(exc, error_message, http_status_code)`.
  - [ ] 7.8 Add these fields to each failure dict:
    - [ ] 7.8.1 `error_category`
    - [ ] 7.8.2 `http_status_code`
    - [ ] 7.8.3 `retry_attempts`
  - [ ] 7.9 Preserve existing failure fields:
    - [ ] 7.9.1 `chapter_id`
    - [ ] 7.9.2 `chapter_number`
    - [ ] 7.9.3 `title`
    - [ ] 7.9.4 `source_url`
    - [ ] 7.9.5 `error_type`
    - [ ] 7.9.6 `error_message`
  - [ ] 7.10 Default `http_status_code` to `None` when not applicable. (REQ-3.4)
  - [ ] 7.11 Default `retry_attempts` to `0` when retry telemetry is unavailable or not applicable. (REQ-3.4)

- [ ] 8. Count Image Download Failures
  - [ ] 8.1 Track successfully saved chapter payloads in `scrape_chapters` or `_scrape_chapters_impl`. (REQ-6.2)
  - [ ] 8.2 After the chapter loop, count chapters where `payload.get("images")` contains at least one item with `download_error`. (REQ-6.1)
  - [ ] 8.3 Store that count as `image_download_failures`.
  - [ ] 8.4 Add `image_download_failures` to the dict returned by `scrape_chapters`. (REQ-6.3)
  - [ ] 8.5 Do not count failed chapter fetches as image download failures unless a saved payload actually contains image error metadata.

- [ ] 9. Persist Crawl Result in `worker.py`
  - [ ] 9.1 Capture the return value of `scrape_chapters` in `_run_crawl_activity`. (REQ-1.1)
  - [ ] 9.2 Build `crawl_result` with:
    - [ ] 9.2.1 `succeeded`
    - [ ] 9.2.2 `skipped`
    - [ ] 9.2.3 `failed`
    - [ ] 9.2.4 `failures`
    - [ ] 9.2.5 `image_download_failures`
  - [ ] 9.3 Persist the result using `self.activity_log.update_activity_metadata(activity_id, {"crawl_result": crawl_result})`. (REQ-1.2, REQ-1.3)
  - [ ] 9.4 Ensure the final `crawl_result` update preserves existing `metadata.progress`.
  - [ ] 9.5 Return `{"chapters": chapters, "crawl_result": crawl_result}` or the closest existing return shape with `crawl_result` included.
  - [ ] 9.6 If `scrape_chapters` raises, do not set `metadata.crawl_result`. (REQ-1.5)
  - [ ] 9.7 Let the existing fatal error path mark the activity failed and set the top-level activity error.

- [ ] 10. Add Running Crawl Progress Metadata
  - [ ] 10.1 In `_run_crawl_activity`, load novel metadata before scraping.
  - [ ] 10.2 Compute `total` from the chapter list that will actually be scraped when possible; otherwise fall back to `len(meta.get("chapters", []))`. (REQ-4.2)
  - [ ] 10.3 Create a progress callback before calling `scrape_chapters`. (REQ-4.1)
  - [ ] 10.4 Increment `completed` after each chapter completion, success, skip, or failure. (REQ-4.3)
  - [ ] 10.5 Write progress as `{"progress": {"completed": completed, "total": total, "current_label": message}}`. (REQ-4.2)
  - [ ] 10.6 Catch and ignore metadata update errors inside the callback so progress persistence cannot fail the crawl.
  - [ ] 10.7 Pass the callback into `scrape_chapters(..., progress_callback=progress_cb)`.
  - [ ] 10.8 If `ActivityRecordResponse` has top-level `completed` and `total`, ensure they are populated from existing fields or can be derived from `metadata.progress`. (REQ-4.4)

- [ ] 11. Enrich Source Health Computation
  - [ ] 11.1 Update `list_source_health()` in `backend/src/novelai/activity/queue.py` to scan stored activity records. (REQ-5.1, REQ-5.2)
  - [ ] 11.2 Only include activities that have dict-shaped `metadata.crawl_result`.
  - [ ] 11.3 Group health data by `source_key`.
  - [ ] 11.4 Compute `total_chapters_attempted` as `succeeded + skipped + failed`.
  - [ ] 11.5 Compute `total_chapters_succeeded` from `crawl_result.succeeded`.
  - [ ] 11.6 Compute `total_chapters_failed` from `crawl_result.failed`.
  - [ ] 11.7 Compute `error_category_counts` by scanning each failure's `error_category`, defaulting missing categories to `unknown`.
  - [ ] 11.8 Compute `last_crawl_at` from the most recent completed/finished crawl activity timestamp.
  - [ ] 11.9 Include `image_download_failures` in source health only if the existing source health shape already has a safe place for summary counters; otherwise keep it only in `crawl_result`.
  - [ ] 11.10 Ensure `get_source_health(source_key)` returns the enriched record for that source.
  - [ ] 11.11 Apply the 60-second cache without hiding freshly updated data after activity mutation. (REQ-5.3)

- [ ] 12. Update API Response Models Only If Needed
  - [ ] 12.1 If source health endpoints return raw dicts, no API model change is needed.
  - [ ] 12.2 If source health endpoints use strict Pydantic models, add the new fields to the relevant model so they are not dropped:
    - [ ] 12.2.1 `total_chapters_attempted`
    - [ ] 12.2.2 `total_chapters_succeeded`
    - [ ] 12.2.3 `total_chapters_failed`
    - [ ] 12.2.4 `error_category_counts`
    - [ ] 12.2.5 `last_crawl_at`
  - [ ] 12.3 Confirm `ActivityRecordResponse` already exposes `metadata: dict`. (REQ-1.4)
  - [ ] 12.4 Do not add new endpoints.

- [ ] 13. Add Test File and Fixtures
  - [ ] 13.1 Create `backend/tests/test_crawl_fetch_observability.py`. (REQ-7.1)
  - [ ] 13.2 Reuse existing activity queue fixtures where possible.
  - [ ] 13.3 Reuse existing crawler/orchestrator fixtures where possible.
  - [ ] 13.4 Use fake source adapters or mocks; do not perform real HTTP.
  - [ ] 13.5 Add fixture helpers for successful scrape results.
  - [ ] 13.6 Add fixture helpers for partial failure scrape results.
  - [ ] 13.7 Add fixture helpers for saved chapter payloads containing image `download_error`.
  - [ ] 13.8 Add fixture helpers for source health activities with stored `metadata.crawl_result`.

- [ ] 14. Write Crawl Result Persistence Tests
  - [ ] 14.1 Write `test_crawl_result_persisted_in_activity`: after `_run_crawl_activity` completes, activity metadata has `crawl_result` with `succeeded`, `skipped`, `failed`, `failures`, and `image_download_failures`. (REQ-7.2)
  - [ ] 14.2 Assert persisted failure records keep existing fields like `chapter_id`, `source_url`, `error_type`, and `error_message`.
  - [ ] 14.3 Write `test_fatal_crawl_error_does_not_set_crawl_result`: when `scrape_chapters` raises, `metadata.crawl_result` is absent and the top-level activity error is set. (REQ-7.8)
  - [ ] 14.4 Write a regression test that the final `crawl_result` write does not remove existing `metadata.progress`.

- [ ] 15. Write Failure Telemetry Tests
  - [ ] 15.1 Write `test_failure_record_includes_error_category`: mock `fetch_chapter_payload` to raise a `SourceError` with `429` or rate-limit text; assert `error_category == "rate_limited"`. (REQ-7.3)
  - [ ] 15.2 Write `test_failure_record_includes_http_status`: mock `fetch_chapter_payload` to raise `httpx.HTTPStatusError` with status 503; assert `http_status_code == 503`. (REQ-7.4)
  - [ ] 15.3 Write a test for message parsing of `status=503` or `status_code=503`.
  - [ ] 15.4 Write a test for `timeout` classification.
  - [ ] 15.5 Write a test for `not_found` classification.
  - [ ] 15.6 Write a test for `server_error` classification.
  - [ ] 15.7 Write a test for `quality_gate` classification.
  - [ ] 15.8 Write a retry semantics test: a fetch configured for 3 total attempts and failing after exhaustion records `retry_attempts == 2`.
  - [ ] 15.9 Write a callback safety test proving an exception raised by `on_retry` does not break retry behavior.

- [ ] 16. Write Progress Tests
  - [ ] 16.1 Write `test_progress_callback_updates_activity_metadata`: assert progress metadata updates during scrape. (REQ-7.5)
  - [ ] 16.2 Assert progress is stored under `metadata.progress`.
  - [ ] 16.3 Assert progress includes `completed`, `total`, and `current_label`.
  - [ ] 16.4 Assert progress increments after success.
  - [ ] 16.5 Assert progress increments after per-chapter failure.
  - [ ] 16.6 If the API exposes top-level `completed` and `total`, test that the activity response exposes those values correctly.

- [ ] 17. Write Image Failure Tests
  - [ ] 17.1 Write `test_image_download_failures_counted`: chapter payload with one image `download_error` produces `image_download_failures == 1`. (REQ-7.7)
  - [ ] 17.2 Add a test where one chapter has multiple image errors and assert it still counts as one affected chapter.
  - [ ] 17.3 Add a test where multiple chapters have image errors and assert the count equals affected chapter count.
  - [ ] 17.4 Add a test where failed chapter fetches without saved payloads do not increase `image_download_failures`.

- [ ] 18. Write Source Health Tests
  - [ ] 18.1 Write `test_source_health_includes_error_category_counts`: create two activities with different `crawl_result.failures` and assert category aggregation. (REQ-7.6)
  - [ ] 18.2 Assert source health includes `total_chapters_attempted`.
  - [ ] 18.3 Assert source health includes `total_chapters_succeeded`.
  - [ ] 18.4 Assert source health includes `total_chapters_failed`.
  - [ ] 18.5 Assert source health includes `last_crawl_at`.
  - [ ] 18.6 Assert activities without dict-shaped `metadata.crawl_result` are ignored.
  - [ ] 18.7 Add a cache invalidation test proving updated crawl metadata is reflected after `update_activity_metadata`.
  - [ ] 18.8 Add an API-level test if source health has a response model, proving the new fields are returned through the actual endpoint.

- [ ] 19. Backward Compatibility Checks
  - [ ] 19.1 Confirm existing activity records without `metadata.crawl_result` still serialize and load.
  - [ ] 19.2 Confirm existing callers of `Retrier.execute_async` continue to work without passing `on_retry`.
  - [ ] 19.3 Confirm existing source adapters continue to work when no `on_retry` callback is passed.
  - [ ] 19.4 Confirm no DB migration files are created.
  - [ ] 19.5 Confirm no storage format files are changed.
  - [ ] 19.6 Confirm no new endpoints are added.
  - [ ] 19.7 Confirm no retry delay, max attempt, or retry-on behavior changes.

- [ ] 20. Run Focused Verification
  - [ ] 20.1 Run `pytest backend/tests/test_crawl_fetch_observability.py --tb=short -q`.
  - [ ] 20.2 Run existing crawler tests, if present.
  - [ ] 20.3 Run existing activity queue/API tests, if present.
  - [ ] 20.4 Run `ruff check backend/src/novelai/activity/worker.py backend/src/novelai/services/orchestration/crawler.py backend/src/novelai/utils/retry_decorator.py backend/src/novelai/activity/queue.py`.
  - [ ] 20.5 If `fetch_service.py` or source adapters were changed, include them in the `ruff check` command.
  - [ ] 20.6 Run the repository's normal backend type checker if configured, such as `pyright` or `mypy`.
  - [ ] 20.7 Fix test, lint, and type failures caused by this work.

- [ ] 21. Final Acceptance Review
  - [ ] 21.1 Verify completed crawl activity responses expose `metadata.crawl_result` with `succeeded`, `skipped`, `failed`, `image_download_failures`, and per-chapter `failures`.
  - [ ] 21.2 Verify each persisted failure includes `error_category`, `http_status_code`, and `retry_attempts`.
  - [ ] 21.3 Verify source health responses expose `total_chapters_attempted`, `total_chapters_succeeded`, `total_chapters_failed`, `error_category_counts`, and `last_crawl_at`.
  - [ ] 21.4 Verify running crawl activity responses expose `metadata.progress.completed`, `metadata.progress.total`, and `metadata.progress.current_label`.
  - [ ] 21.5 Verify HTTP 429 failures record `error_category == "rate_limited"` and `http_status_code == 429`.
  - [ ] 21.6 Verify quality gate failures record `error_category == "quality_gate"`.
  - [ ] 21.7 Verify image download failures are counted according to the documented chapter-count semantics.
  - [ ] 21.8 Verify fatal crawl errors do not create a misleading partial `crawl_result`.
  - [ ] 21.9 Verify source health cache invalidates on activity metadata changes or refreshes within the documented TTL.
  - [ ] 21.10 Verify all required tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Persist Per-Chapter Failure Details | 1, 2, 9, 14, 19, 21 |
| REQ-2 Error Classification | 6, 7, 15, 21 |
| REQ-3 HTTP Fetch Telemetry | 1, 4, 5, 6, 7, 15, 19, 21 |
| REQ-4 Crawl Progress Metadata | 1, 2, 10, 16, 21 |
| REQ-5 Source Health Enrichment | 3, 11, 12, 18, 21 |
| REQ-6 Image Download Failure Visibility | 1, 8, 9, 17, 21 |
| REQ-7 Tests | 13, 14, 15, 16, 17, 18, 20 |

## Definition of Done

- [ ] `metadata.crawl_result` is persisted after non-fatal crawl completion.
- [ ] Fatal crawl errors leave `metadata.crawl_result` absent and use the top-level activity error.
- [ ] Failure records include `error_category`, `http_status_code`, and `retry_attempts`.
- [ ] Retry telemetry is threaded from `Retrier` through fetch/source code where supported.
- [ ] Running crawl progress is stored under `metadata.progress`.
- [ ] Final crawl result updates preserve progress metadata.
- [ ] Source health includes aggregate crawl success/failure counts and error category counts.
- [ ] Source health caching has a 60-second TTL and invalidates on activity mutation.
- [ ] Image download failures are counted as affected chapter count.
- [ ] Existing callers remain compatible because new retry callback parameters default to `None`.
- [ ] No DB migration, storage format, or endpoint additions are introduced.
- [ ] Focused tests, lint checks, and configured type checks pass.
