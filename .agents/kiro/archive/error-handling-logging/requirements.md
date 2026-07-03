# Requirements: Enhanced Error Handling and Logging

## Introduction

Pipeline errors are currently surfaced inconsistently. Some errors produce detailed logs, others are swallowed. Error responses from the API lack a uniform structure, making it difficult for frontend code and monitoring tools to handle failures programmatically. There is no per-chapter error tracking, no error categorization, and no structured logging that correlates errors across pipeline stages.

This spec adds structured error handling and logging across the translation pipeline and API layer, ensuring all errors are categorized, logged with consistent context, and surfaced with a uniform response shape.

## Requirements

### REQ-1: Structured Error Response Format

All API error responses must follow a consistent JSON schema.

- REQ-1.1: Define a canonical `ErrorResponse` model:
  ```json
  {
    "error": "string",
    "detail": "string",
    "error_code": "string",
    "request_id": "string | null",
    "timestamp": "string (ISO 8601)"
  }
  ```
- REQ-1.2: The `error_code` must use a dot-separated hierarchy: `pipeline.fetch.timeout`, `pipeline.translate.rate_limit`, `auth.unauthorized`, `storage.not_found`.
- REQ-1.3: All existing `HTTPException` usages must be reviewed and updated to include `error_code`.
- REQ-1.4: A new exception class `StructuredHTTPException` (extending `HTTPException`) must carry `error_code`, `detail`, and `request_id`.
- REQ-1.5: A FastAPI exception handler must convert `StructuredHTTPException` to the canonical `ErrorResponse` JSON shape.

### REQ-2: Error Categorization

Errors must be categorized by source and severity.

- REQ-2.1: Define an `ErrorCategory` enum with values: `VALIDATION`, `AUTH`, `NOT_FOUND`, `CONFLICT`, `PIPELINE`, `PROVIDER`, `STORAGE`, `INTERNAL`.
- REQ-2.2: Each `StructuredHTTPException` must carry an `ErrorCategory`.
- REQ-2.3: Each error category must map to a default HTTP status code (e.g. `VALIDATION` -> 422, `AUTH` -> 401/403, `NOT_FOUND` -> 404, `INTERNAL` -> 500).

### REQ-3: Per-Chapter Structured Logging

Pipeline stage execution must produce structured log records that can be correlated.

- REQ-3.1: A `PipelineContext` object must be created at the start of each chapter translation, containing: `novel_id`, `chapter_id`, `request_id` (UUID), `stage`, and `timestamp`.
- REQ-3.2: Every pipeline stage must log entry and exit via `PipelineContext` with duration in milliseconds.
- REQ-3.3: Log records must use structured format (JSON lines) with fields: `timestamp`, `level`, `logger`, `novel_id`, `chapter_id`, `request_id`, `stage`, `duration_ms`, `message`.
- REQ-3.4: A helper `get_pipeline_logger(novel_id, chapter_id, request_id)` must create a logger instance pre-configured with these contextual fields.
- REQ-3.5: On pipeline stage failure, the error must be logged with `level=ERROR` including `error_code`, `stack_trace` (truncated to 1000 chars), and the stage name.

### REQ-4: Error Aggregation and Monitoring Support

The logging infrastructure must support downstream aggregation.

- REQ-4.1: All structured logs must be emitted to stdout in JSON format when `LOG_FORMAT=json` is set in the environment.
- REQ-4.2: When `LOG_FORMAT` is not set or is `text`, use the current human-readable format for development.
- REQ-4.3: A `/health` endpoint must expose error rate metrics since last restart: total errors by category and by pipeline stage.
- REQ-4.4: The error metrics must be available via `GET /api/admin/health/errors`.

### REQ-5: Recovery Guidance in Error Responses

API error responses should help the caller understand how to recover.

- REQ-5.1: When applicable, the `detail` field should include a recovery hint. Example: `"Rate limit exceeded. Retry after {retry_after_seconds} seconds."`
- REQ-5.2: The `ErrorResponse` model must include an optional `retry_after` field (ISO duration string) for rate-limit and transient errors.
- REQ-5.3: Errors from the provider layer must include the provider name and model in the detail.

## Non-Goals

- This spec does not change the underlying pipeline logic or translation algorithms.
- This spec does not add a full monitoring dashboard or alerting system.
- This spec does not change existing API endpoint signatures or response shapes (except to add `error_code`).
- This spec does not require a new database table or migration.
