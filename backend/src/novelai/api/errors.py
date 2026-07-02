"""Structured error types and response models for the Novel AI API."""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    AUTH = "auth"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PIPELINE = "pipeline"
    PROVIDER = "provider"
    STORAGE = "storage"
    INTERNAL = "internal"


# Default HTTP status code per category
CATEGORY_TO_STATUS: dict[ErrorCategory, int] = {
    ErrorCategory.VALIDATION: 422,
    ErrorCategory.AUTH: 401,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.CONFLICT: 409,
    ErrorCategory.PIPELINE: 500,
    ErrorCategory.PROVIDER: 502,
    ErrorCategory.STORAGE: 500,
    ErrorCategory.INTERNAL: 500,
}

# Dot-separated error code hierarchy constants
ERROR_CODES = {
    # pipeline.*
    "PIPELINE_FETCH_TIMEOUT": "pipeline.fetch.timeout",
    "PIPELINE_TRANSLATE_RATE_LIMIT": "pipeline.translate.rate_limit",
    "PIPELINE_TRANSLATE_QUOTA": "pipeline.translate.quota_exhausted",
    "PIPELINE_TRANSLATE_MODEL_UNAVAILABLE": "pipeline.translate.model_unavailable",
    "PIPELINE_PARSE_FAILED": "pipeline.parse.failed",
    "PIPELINE_SEGMENT_FAILED": "pipeline.segment.failed",
    "PIPELINE_EXPORT_FAILED": "pipeline.export.failed",
    # auth.*
    "AUTH_UNAUTHORIZED": "auth.unauthorized",
    "AUTH_FORBIDDEN": "auth.forbidden",
    "AUTH_CSRF_INVALID": "auth.csrf_invalid",
    # storage.*
    "STORAGE_NOT_FOUND": "storage.not_found",
    "STORAGE_IO_ERROR": "storage.io_error",
    "STORAGE_PERMISSION": "storage.permission_denied",
    # provider.*
    "PROVIDER_API_ERROR": "provider.api_error",
    "PROVIDER_CONFIG_ERROR": "provider.config_error",
    # validation.*
    "VALIDATION_REQUEST": "validation.request",
    # internal.*
    "INTERNAL_ERROR": "internal.error",
}


class ErrorResponse(BaseModel):
    error: str
    detail: str
    error_code: str
    request_id: str | None = None
    timestamp: str
    retry_after: str | None = None  # ISO duration, e.g. "PT30S"


class StructuredHTTPException(HTTPException):
    """HTTPException with structured error metadata."""

    def __init__(
        self,
        status_code: int,
        detail: str = "",
        error_code: str = "internal.error",
        category: ErrorCategory = ErrorCategory.INTERNAL,
        request_id: str | None = None,
        retry_after: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code
        self.category = category
        self.request_id = request_id
        self.retry_after = retry_after

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            error=self.category.value,
            detail=str(self.detail),
            error_code=self.error_code,
            request_id=self.request_id,
            timestamp=datetime.now(UTC).isoformat(),
            retry_after=self.retry_after,
        )


# ---------------------------------------------------------------------------
# In-memory error counters (reset on restart)
# ---------------------------------------------------------------------------

_counter_lock = threading.Lock()
_counters: dict[str, dict[str, int]] = {
    "by_category": defaultdict(int),
    "by_stage": defaultdict(int),
}


def record_error(category: str, stage: str | None = None) -> None:
    with _counter_lock:
        _counters["by_category"][category] += 1
        if stage:
            _counters["by_stage"][stage] += 1


def get_error_metrics() -> dict[str, Any]:
    with _counter_lock:
        return {
            "by_category": dict(_counters["by_category"]),
            "by_stage": dict(_counters["by_stage"]),
        }
