# Design: Crawl and Fetch Observability

## Overview

This design makes crawl/fetch diagnostics visible through existing activity and source-health APIs without changing crawl behavior.

The crawler already produces useful runtime information: per-chapter outcomes, retry behavior, partial failures, image download errors, and source-specific failure patterns. Today, much of that information is only visible in logs or is lost after the activity completes. This design persists a compact diagnostic summary in activity metadata and derives source health from completed crawl records.

The implementation is intentionally narrow:

- Store completed crawl summaries under `metadata.crawl_result`.
- Store running crawl progress under `metadata.progress`.
- Add per-chapter failure telemetry: `error_category`, `http_status_code`, and `retry_attempts`.
- Thread optional retry callbacks through the fetch stack where supported.
- Count chapters affected by image download failures.
- Enrich source health from persisted crawl results using a short in-memory cache.

No new storage files, database tables, migrations, or API endpoints are added.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/activity/worker.py` | Capture `scrape_chapters` return value, persist `crawl_result`, and add crawl progress callback |
| `backend/src/novelai/activity/queue.py` | Add safe metadata merge, `update_activity_metadata`, source-health enrichment, and cache invalidation |
| `backend/src/novelai/services/orchestration/crawler.py` | Enrich per-chapter failures, count image download failures, and pass retry callback into source fetch |
| `backend/src/novelai/utils/retry_decorator.py` | Add optional `on_retry` callback to `Retrier.execute_async` |
| `backend/src/novelai/infrastructure/http/fetch_service.py` | Thread optional `on_retry` through retried fetch calls |
| Source adapter modules | Accept and pass optional `on_retry` where adapters call the retried fetch service |
| `backend/src/novelai/api/routers/activity.py` | Inspect only; update response usage only if strict models drop metadata |
| API response model module, if needed | Add enriched source-health fields only if strict response models are used |
| `backend/tests/test_crawl_fetch_observability.py` | Add focused observability tests |

### Files Not Touched

- Storage format files.
- Database models and migrations.
- Public reader routes.
- Translation pipeline observability.
- Retry policy configuration.
- Crawl scheduling behavior.

## Data Contracts

### Activity Metadata

Canonical stored metadata shape:

```json
{
  "progress": {
    "completed": 7,
    "total": 20,
    "current_label": "Chapter 7"
  },
  "crawl_result": {
    "succeeded": 16,
    "skipped": 2,
    "failed": 2,
    "image_download_failures": 1,
    "failures": [
      {
        "chapter_id": "18",
        "chapter_number": 18,
        "title": "Chapter Title",
        "source_url": "https://example.test/chapter-18",
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

`metadata.progress` is updated while a crawl is running.

`metadata.crawl_result` is written after a non-fatal scrape completes. If `scrape_chapters` raises a fatal exception, `metadata.crawl_result` remains absent and the existing top-level activity error remains the source of truth.

### Field Semantics

| Field | Meaning |
|---|---|
| `crawl_result.succeeded` | Number of chapters successfully scraped |
| `crawl_result.skipped` | Number of chapters skipped by crawl mode, existing state, or equivalent skip logic |
| `crawl_result.failed` | Number of per-chapter failures captured without failing the whole crawl |
| `crawl_result.failures` | Per-chapter failure records |
| `crawl_result.image_download_failures` | Number of saved chapters where at least one image entry has `download_error` |
| `failure.error_category` | Normalized diagnostic category |
| `failure.http_status_code` | Final known HTTP status code, or `null` |
| `failure.retry_attempts` | Retries after the initial attempt; a 3-attempt exhausted fetch records `2` |
| `progress.completed` | Chapters completed, including success, skip, and per-chapter failure |
| `progress.total` | Chapters expected for this crawl operation |
| `progress.current_label` | Human-readable current or most recently completed chapter label |

## Component Design

### 1. Activity Metadata Merge

Add `update_activity_metadata(activity_id: str, patch: dict) -> bool` to `activity/queue.py`.

Behavior:

- Return `False` if the activity does not exist.
- Merge `patch` into existing `metadata` instead of replacing metadata.
- Merge nested `progress` patches into existing `metadata.progress`.
- Preserve existing `crawl_result` when only progress changes.
- Preserve existing `progress` when final `crawl_result` is written.
- Use the existing queue/activity lock if one exists.
- Invalidate source-health cache after a successful metadata update.

Sketch:

```python
def update_activity_metadata(self, activity_id: str, patch: dict[str, Any]) -> bool:
    with self._lock:
        activity = self.get_activity(activity_id)
        if activity is None:
            return False

        metadata = dict(activity.get("metadata") or {})
        patch = dict(patch or {})

        if isinstance(patch.get("progress"), dict):
            progress = dict(metadata.get("progress") or {})
            progress.update(patch["progress"])
            patch["progress"] = progress

        metadata.update(patch)

        self.update_activity_status(
            activity_id,
            activity["status"],
            metadata=metadata,
        )

        self._invalidate_source_health_cache()
        return True
```

If `update_activity_status` already takes the same lock, avoid double-lock deadlocks by extracting a private no-lock update helper or following the existing lock pattern.

### 2. Crawl Result and Progress Persistence

In `worker.py`, update `_run_crawl_activity` so it captures the value returned by `scrape_chapters`.

Progress callback:

```python
def _make_progress_callback(activity_id: str, total: int) -> Callable[[str], None]:
    completed = [0]

    def callback(message: str) -> None:
        completed[0] += 1
        try:
            self.activity_log.update_activity_metadata(
                activity_id,
                {
                    "progress": {
                        "completed": completed[0],
                        "total": total,
                        "current_label": message,
                    }
                },
            )
        except Exception:
            logger.debug("Failed to update crawl progress", exc_info=True)

    return callback
```

Result persistence:

```python
result = await self.orchestrator.scrape_chapters(
    source_key,
    novel_id,
    chapters,
    mode=mode,
    progress_callback=progress_cb,
)

crawl_result = {
    "succeeded": result.get("succeeded", 0),
    "skipped": result.get("skipped", 0),
    "failed": result.get("failed", 0),
    "failures": result.get("failures", []),
    "image_download_failures": result.get("image_download_failures", 0),
}

self.activity_log.update_activity_metadata(
    activity_id,
    {"crawl_result": crawl_result},
)

return {
    "chapters": chapters,
    "crawl_result": crawl_result,
}
```

When `scrape_chapters` raises, do not write `crawl_result`. Let the existing activity failure path set top-level activity status and error fields.

### 3. Retry Callback Contract

Add optional retry callback support to `Retrier.execute_async`.

Contract:

- `on_retry` defaults to `None`.
- It fires only after a failed attempt that will be retried.
- It fires before backoff sleep.
- It does not fire for the initial attempt itself.
- It does not fire after the final exhausted attempt.
- First retry after the initial failure reports `1`.
- Callback errors are swallowed and logged at debug level.

Sketch:

```python
async def execute_async(
    self,
    fn: Callable[[], Awaitable[T]],
    *,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    for attempt_index in range(self.config.max_attempts):
        try:
            return await fn()
        except self.config.retry_on as exc:
            is_last_attempt = attempt_index + 1 >= self.config.max_attempts
            if is_last_attempt:
                raise

            retry_number = attempt_index + 1
            if on_retry is not None:
                try:
                    on_retry(retry_number, exc)
                except Exception:
                    logger.debug("Retry callback failed", exc_info=True)

            await self._sleep_before_retry(attempt_index)
```

The exact loop should follow the current implementation. The observable contract is the callback timing and retry numbering.

### 4. Fetch Stack Retry Propagation

Use callback propagation as the primary retry telemetry path.

Add optional keyword-only `on_retry` parameters through:

- `Retrier.execute_async(..., on_retry=on_retry)`
- `FetchService._with_retry(..., on_retry=on_retry)`
- the public fetch method used by chapter fetching, such as `FetchService.get_text(..., on_retry=on_retry)`
- source adapter chapter-fetch methods that call the retried fetch service

All new parameters default to `None`.

Adapters that do not call the retried fetch service may ignore the callback. Their failures should still record `retry_attempts=0`.

If the project has a source adapter protocol or abstract base class, update the signature there too:

```python
async def fetch_chapter_payload(
    self,
    chapter_url: str,
    *,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> dict[str, Any]:
    ...
```

### 5. Error Helpers

Add `_extract_http_status`.

Preferred order:

1. `httpx.HTTPStatusError.response.status_code`
2. `exc.response.status_code`, if present
3. `exc.status_code`, if present
4. Regex parsing from message text:
   - `status=503`
   - `status_code=503`
   - `HTTP 503`
   - safe standalone `429`, `404`, or `5xx` status tokens

Sketch:

```python
def _extract_http_status(exc: Exception) -> int | None:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code

    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status

    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status

    message = str(exc)
    for pattern in (
        r"\bstatus=(\d{3})\b",
        r"\bstatus_code=(\d{3})\b",
        r"\bHTTP\s+(\d{3})\b",
        r"\b(429|404|5\d\d)\b",
    ):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None
```

Add `_classify_error`.

Order matters: quality-gate and specific HTTP failures should win over generic fetch/source errors.

```python
def _classify_error(
    exc: Exception,
    error_message: str,
    http_status_code: int | None = None,
) -> str:
    msg = error_message.lower()

    if _is_quality_gate_error(exc, msg):
        return "quality_gate"
    if http_status_code == 429 or "rate limit" in msg or "rate_limited" in msg:
        return "rate_limited"
    if http_status_code == 404 or "not found" in msg:
        return "not_found"
    if isinstance(exc, httpx.TimeoutException) or "timeout" in msg:
        return "timeout"
    if http_status_code is not None and 500 <= http_status_code <= 599:
        return "server_error"
    if isinstance(exc, SourceError):
        return "fetch_error"
    return "unknown"
```

`_is_quality_gate_error` should check the concrete quality-gate exception type if one exists. If not, it may match the known message emitted by `_apply_chapter_quality_gate`.

### 6. Per-Chapter Failure Records

In `_scrape_chapters_impl`, track retries around each chapter fetch:

```python
retry_attempts = [0]

def _on_retry(retry_number: int, exc: Exception) -> None:
    retry_attempts[0] = retry_number

try:
    payload = await source.fetch_chapter_payload(
        chapter_url,
        on_retry=_on_retry,
    )
except Exception as exc:
    error_message = str(exc)
    http_status_code = _extract_http_status(exc)

    failures.append(
        {
            "chapter_id": chapter_id,
            "chapter_number": chapter_number,
            "title": chapter_title,
            "source_url": chapter_url,
            "error_type": type(exc).__name__,
            "error_message": _safe_error_message(error_message),
            "error_category": _classify_error(exc, error_message, http_status_code),
            "http_status_code": http_status_code,
            "retry_attempts": retry_attempts[0],
        }
    )
```

Default behavior:

- `http_status_code` is `None` when unknown.
- `retry_attempts` is `0` when no retry telemetry is available.
- Existing failure fields remain unchanged.
- Failure messages must be safe for admin display and must not include full HTML, full chapter text, credentials, cookies, secrets, or local filesystem paths.

### 7. Image Download Failure Count

Track successfully saved chapter payloads or equivalent saved chapter data during scrape.

After the chapter loop:

```python
image_download_failures = sum(
    1
    for payload in saved_payloads
    if any(img.get("download_error") for img in (payload.get("images") or []))
)
```

This counts affected chapters, not failed image objects. A chapter with three failed images contributes `1`.

Add the value to the scrape return dict:

```python
return {
    "succeeded": succeeded,
    "skipped": skipped,
    "failed": failed,
    "failures": failures,
    "image_download_failures": image_download_failures,
}
```

Failed chapter fetches without saved payloads must not increase `image_download_failures`.

### 8. Source Health Enrichment

Compute source health from stored activity records with dict-shaped `metadata.crawl_result`.

Source health shape:

```json
{
  "source_key": "example",
  "total_chapters_attempted": 25,
  "total_chapters_succeeded": 20,
  "total_chapters_failed": 3,
  "error_category_counts": {
    "rate_limited": 2,
    "timeout": 1
  },
  "http_status_counts": {
    "429": 2,
    "503": 1
  },
  "last_crawl_at": "2026-07-07T14:00:00Z"
}
```

Aggregation rules:

- `total_chapters_attempted = succeeded + skipped + failed`
- `total_chapters_succeeded += succeeded`
- `total_chapters_failed += failed`
- `error_category_counts` scans each failure record and defaults missing category to `unknown`
- `http_status_counts` scans each failure record with a known `http_status_code`
- `last_crawl_at` is the latest completed or finished crawl timestamp for the source

Use a 60-second in-memory cache. Cache invalidates when activities mutate through:

- `update_activity_status`
- `update_activity_metadata`

The TTL remains a fallback if an update path misses invalidation.

### 9. API Response Model Handling

No new endpoints are added. Existing activity endpoints should expose the new data through existing metadata and source-health routes.

Implementation rules:

- If activity/source-health endpoints return raw dicts, no router or model changes are required.
- If source-health endpoints use strict response models, add the enriched fields so the API does not silently drop them.
- Confirm `ActivityRecordResponse` exposes `metadata: dict`; no change is needed if it already does.
- Preserve existing response fields and route paths.

## Migration and Backward Compatibility

- Existing activity records without `metadata.crawl_result` remain valid.
- Source health ignores records where `metadata.crawl_result` is missing or not a dict.
- New failure fields are additive.
- `Retrier.execute_async` remains backward compatible because `on_retry` defaults to `None`.
- Fetch service and source adapter changes are backward compatible because `on_retry` defaults to `None`.
- No retry timing, max-attempt, or retryable-exception behavior changes.
- No storage schema or DB migration is introduced.

## Test Design

Create `backend/tests/test_crawl_fetch_observability.py`.

Core tests:

- `test_crawl_result_persisted_in_activity`
- `test_fatal_crawl_error_does_not_set_crawl_result`
- `test_failure_record_includes_error_category`
- `test_failure_record_includes_http_status`
- `test_progress_callback_updates_activity_metadata`
- `test_source_health_includes_error_category_counts`
- `test_image_download_failures_counted`

Additional regression tests:

- A 3-attempt exhausted fetch records `retry_attempts == 2`.
- An exception raised by `on_retry` does not break retry behavior.
- `quality_gate` errors classify as `quality_gate`.
- `timeout`, `not_found`, and `server_error` classifications work.
- `status=503`, `status_code=503`, and `HTTP 503` message parsing works.
- Final `crawl_result` update preserves `metadata.progress`.
- Source health cache invalidates after metadata mutation.
- Source health API response includes enriched fields when a strict response model is present.
- One chapter with multiple image errors counts as one `image_download_failures`.
- Failed chapter fetches without saved payloads do not increase `image_download_failures`.

No tests should perform real HTTP.

## Acceptance Criteria

1. After a crawl activity completes, `GET /admin/activity/{activity_id}` returns `metadata.crawl_result` with `succeeded`, `skipped`, `failed`, `image_download_failures`, and per-chapter `failures`.
2. Each persisted failure includes `error_category`, `http_status_code`, and `retry_attempts`.
3. `GET /admin/activity/source-health/{source_key}` returns `total_chapters_attempted`, `total_chapters_succeeded`, `total_chapters_failed`, `error_category_counts`, `http_status_counts`, and `last_crawl_at`.
4. During an active crawl, `GET /admin/activity/{activity_id}` exposes `metadata.progress.completed`, `metadata.progress.total`, and `metadata.progress.current_label`.
5. A chapter failure caused by HTTP 429 records `error_category="rate_limited"` and `http_status_code=429`.
6. A quality gate failure records `error_category="quality_gate"`.
7. Chapters with image download errors are counted in `image_download_failures` as affected chapter count.
8. Fatal crawl errors do not create a misleading partial `crawl_result`; the top-level activity error remains the source of truth.
9. Source health cache invalidates when activity metadata changes or refreshes within the documented TTL.
10. All required focused tests pass.