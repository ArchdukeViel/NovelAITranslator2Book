# Design: Enhanced Error Handling and Logging

## Overview

Four additive changes: (1) define `ErrorResponse` model and `StructuredHTTPException`, (2) add `ErrorCategory` enum and error code hierarchy, (3) introduce `PipelineContext` for per-chapter structured logging, (4) add error metrics to `/health`. No new dependencies. No DB migrations.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/api/errors.py` | New — `ErrorResponse`, `StructuredHTTPException`, `ErrorCategory`, exception handler |
| `backend/src/novelai/api/routers/health.py` | New or update — error metrics endpoint |
| `backend/src/novelai/services/pipeline/context.py` | New — `PipelineContext` and `get_pipeline_logger` |
| `backend/src/novelai/services/pipeline/stages/*.py` | Update — wrap each stage entry/exit with logging |
| `backend/src/novelai/main.py` | Update — register exception handler |
| `backend/src/novelai/logging_config.py` | New or update — JSON log formatter |

### Files Not Touched

- DB models — no change
- Storage layer — no change
- Source adapters — no change
- Frontend — no change

## Component Design

### 1. `ErrorResponse` and `StructuredHTTPException` (`api/errors.py`)

```python
from enum import Enum
from fastapi import HTTPException
from pydantic import BaseModel

class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    AUTH = "auth"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PIPELINE = "pipeline"
    PROVIDER = "provider"
    STORAGE = "storage"
    INTERNAL = "internal"

CATEGORY_TO_STATUS: dict[ErrorCategory, int] = {
    ErrorCategory.VALIDATION: 422,
    ErrorCategory.AUTH: 403,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.CONFLICT: 409,
    ErrorCategory.PIPELINE: 500,
    ErrorCategory.PROVIDER: 502,
    ErrorCategory.STORAGE: 500,
    ErrorCategory.INTERNAL: 500,
}

class ErrorResponse(BaseModel):
    error: str
    detail: str
    error_code: str
    request_id: str | None = None
    timestamp: str
    retry_after: str | None = None

class StructuredHTTPException(HTTPException):
    def __init__(
        self,
        category: ErrorCategory,
        error_code: str,
        detail: str,
        request_id: str | None = None,
        retry_after: str | None = None,
    ):
        status_code = CATEGORY_TO_STATUS[category]
        self.error_code = error_code
        self.category = category
        self.retry_after = retry_after
        self.request_id = request_id
        super().__init__(status_code=status_code, detail=detail)
```

### 2. Exception Handler Registration (`main.py`)

```python
from novelai.api.errors import StructuredHTTPException, ErrorResponse

@app.exception_handler(StructuredHTTPException)
async def structured_exception_handler(request, exc: StructuredHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.error_code.split(".")[-1],
            detail=exc.detail,
            error_code=exc.error_code,
            request_id=exc.request_id,
            timestamp=datetime.utcnow().isoformat(),
            retry_after=exc.retry_after,
        ).model_dump(),
    )
```

### 3. Error Code Hierarchy

Error codes follow a `domain.subdomain.problem` format:

| Category | Example error_code |
|---|---|
| Validation | `validation.invalid_slug` |
| Auth | `auth.unauthorized`, `auth.forbidden` |
| Not Found | `not_found.novel`, `not_found.chapter` |
| Conflict | `conflict.already_exists` |
| Pipeline | `pipeline.fetch.failed`, `pipeline.translate.rate_limit` |
| Provider | `provider.timeout`, `provider.quota_exceeded` |
| Storage | `storage.write_failed`, `storage.read_failed` |
| Internal | `internal.unexpected` |

### 4. `PipelineContext` and Structured Logging (`services/pipeline/context.py`)

```python
import logging
import uuid
from datetime import datetime

class PipelineContext:
    def __init__(self, novel_id: str, chapter_id: str):
        self.novel_id = novel_id
        self.chapter_id = chapter_id
        self.request_id = str(uuid.uuid4())
        self.stage: str | None = None
        self._start_time: float | None = None

    def stage_enter(self, stage: str) -> None:
        self.stage = stage
        self._start_time = time.monotonic()
        logger = get_pipeline_logger(self)
        logger.info("Stage started")

    def stage_exit(self) -> None:
        duration_ms = (time.monotonic() - self._start_time) * 1000
        logger = get_pipeline_logger(self)
        logger.info("Stage completed", extra={"duration_ms": duration_ms})
        self.stage = None
        self._start_time = None

    def stage_error(self, error_code: str, message: str, exc_info=None) -> None:
        duration_ms = (time.monotonic() - self._start_time) * 1000 if self._start_time else 0
        logger = get_pipeline_logger(self)
        logger.error(
            message,
            extra={"error_code": error_code, "duration_ms": duration_ms},
            exc_info=exc_info,
        )


# Per-thread/request logger with structured extras
_PIPELINE_LOGGER = logging.getLogger("novelai.pipeline")

def get_pipeline_logger(ctx: PipelineContext) -> logging.Logger:
    """Return a logger with PipelineContext fields in its extra."""

    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            kwargs.setdefault("extra", {})
            kwargs["extra"].update({
                "novel_id": ctx.novel_id,
                "chapter_id": ctx.chapter_id,
                "request_id": ctx.request_id,
                "stage": ctx.stage,
            })
            return msg, kwargs

    return ContextAdapter(_PIPELINE_LOGGER, {})
```

### 5. JSON Log Formatter (`logging_config.py`)

```python
import json
import logging

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra fields if present
        for key in ("novel_id", "chapter_id", "request_id", "stage",
                     "duration_ms", "error_code"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)[:1000]
        return json.dumps(log_entry, ensure_ascii=False)
```

### 6. Error Metrics on `/health`

```python
from collections import Counter

_error_counters: dict[str, Counter] = {
    "by_category": Counter(),
    "by_stage": Counter(),
}

def record_error(category: ErrorCategory, stage: str | None = None):
    _error_counters["by_category"][category.value] += 1
    if stage:
        _error_counters["by_stage"][stage] += 1

# Health endpoint exposes:
# GET /api/admin/health/errors -> {"by_category": {...}, "by_stage": {...}}
```

## Migration and Backward Compatibility

- Existing `HTTPException` uses remain unchanged. The new `StructuredHTTPException` is additive.
- Existing text-format logs remain unchanged when `LOG_FORMAT` is unset.
- The `/health/errors` endpoint is new and does not affect existing health checks.
- Error codes are added to responses; they do not change existing response shapes.

## Acceptance Criteria

1. `GET /api/admin/health/errors` returns error counters by category and stage.
2. A `StructuredHTTPException` with `ErrorCategory.NOT_FOUND` and `error_code="not_found.novel"` produces a JSON response with all `ErrorResponse` fields.
3. Pipeline stage entry/exit is logged with `novel_id`, `chapter_id`, `request_id`, and `duration_ms`.
4. When `LOG_FORMAT=json` is set, all logs are valid JSON lines.
5. Existing tests that check HTTP error responses continue to pass.
