"""Error handler middleware and utilities for FastAPI.

Provides consistent error responses and logging for Novel AI errors.
"""

from __future__ import annotations

import errno
import logging
import os
from pathlib import Path
from typing import Any, NamedTuple

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from novelai.core.errors import (
    ConfigError,
    ExportError,
    NovelAIError,
    PipelineError,
    ProviderAPIError,
    ProviderConfigError,
    ProviderError,
    ProviderErrorCode,
    SourceError,
    SourceFetchError,
    StorageError,
)
from novelai.core.security import redact_secret_text, redact_sensitive

logger = logging.getLogger(__name__)
DEBUG_ERRORS = os.getenv("DEBUG_ERRORS", "false").lower() == "true"

DEFAULT_INTERNAL_STATUS = status.HTTP_500_INTERNAL_SERVER_ERROR
DEFAULT_INTERNAL_CODE = "INTERNAL_ERROR"
DEFAULT_INTERNAL_MESSAGE = "Internal Server Error"

_NON_NOVEL_ROUTE_PARTS = {
    "",
    "activity",
    "admin",
    "input-adapters",
    "jobs",
    "requests",
    "sources",
}


_HTTP_CODE_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "AUTH_FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    424: "FAILED_DEPENDENCY",
    422: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    DEFAULT_INTERNAL_STATUS: DEFAULT_INTERNAL_CODE,
    status.HTTP_502_BAD_GATEWAY: "UPSTREAM_SERVICE_ERROR",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    status.HTTP_504_GATEWAY_TIMEOUT: "OPERATION_TIMEOUT",
    507: "INSUFFICIENT_STORAGE",
}

_EXPLANATION_BY_CODE: dict[str, str] = {
    "APPLICATION_ERROR": "The backend application raised an uncategorized NovelAI error.",
    "ACTIVITY_ERROR": "An activity log operation failed while preparing or running the requested task.",
    "ACTIVITY_VALIDATION_ERROR": "The activity payload is missing required fields or contains unsupported values.",
    "API_KEY_REQUIRED": "The admin API needs a valid bearer token before this action can run.",
    "AUTH_FORBIDDEN": "The supplied API token is missing or does not match the configured backend token.",
    "BAD_REQUEST": "The request payload could not be accepted. Check the input values and try again.",
    "CONFIGURATION_ERROR": "The backend configuration is incomplete or invalid.",
    "CONFLICT": "The requested change conflicts with the current stored state.",
    "EXPORT_ERROR": "The export pipeline could not generate the requested output file.",
    "FAILED_DEPENDENCY": "This action could not complete because a required internal dependency failed.",
    "INSUFFICIENT_STORAGE": "The storage layer could not complete the operation with the current storage state.",
    "INTERNAL_ERROR": "The backend hit an unexpected condition. Check the Activity Log or server logs with the trace ID.",
    "INTERNAL_FIELD_MISSING": "The backend expected an internal field that was not present in the current payload.",
    "INVALID_OPERATION": "The requested operation is not valid for the current data or workflow state.",
    "JOB_ERROR": "A background activity failed while preparing or running the requested task.",
    "JOB_VALIDATION_ERROR": "The activity payload is missing required fields or contains unsupported values.",
    "METADATA_NOT_FOUND": "The novel metadata file is missing. Run metadata crawl before this operation.",
    "NOVEL_IDENTIFIER_REQUIRED": "Enter either the source URL or the source novel ID before starting preliminary crawl.",
    "OPERATION_TIMEOUT": "The action took longer than the configured web request timeout.",
    "REGISTRY_LOOKUP_ERROR": "The backend could not find the requested source, provider, input adapter, or exporter key.",
    "REQUEST_QUEUE_ERROR": "The reader request queue could not process the requested update.",
    "REQUEST_QUEUE_VALIDATION_ERROR": "The reader request payload is missing required fields or contains unsupported values.",
    "RUNTIME_ERROR": "The backend stopped during an application operation.",
    "PIPELINE_ERROR": "The translation pipeline stopped before it could finish the requested work.",
    "PRELIMINARY_CRAWL_FAILED": "The crawler tried the selected source and fallback source, but none returned usable novel metadata. Check the Activity Log payload for each attempted source.",
    "PRELIMINARY_CRAWL_NO_METADATA": "The crawler reached the attempted source pages, but none returned usable novel metadata or chapters.",
    "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT": "At least one source timed out during preliminary crawl, and no fallback source returned usable metadata.",
    "PRELIMINARY_CRAWL_TIMEOUT": "Every attempted source timed out before preliminary crawl could detect metadata.",
    "PROVIDER_API_ERROR": "The translation provider rejected the request or was temporarily unavailable.",
    "PROVIDER_CONFIG_ERROR": "The selected AI provider is missing a token or has invalid provider settings.",
    "PROVIDER_ERROR": "The translation provider failed while processing the request.",
    "RATE_LIMITED": "Too many requests were sent in a short time. Wait a moment, then try again.",
    "RESOURCE_NOT_FOUND": "The requested item was not found in storage.",
    "SERVICE_UNAVAILABLE": "A required backend service is temporarily unavailable.",
    "SOURCE_ERROR": "The source adapter could not parse or use the supplied source.",
    "SOURCE_PARSE_ERROR": "The source adapter returned data the crawler could not use.",
    "SOURCE_FETCH_ERROR": "The crawler could not fetch the source page or received an unusable response.",
    "STORAGE_ERROR": "The storage layer could not read or write the requested data.",
    "STORAGE_FILE_NOT_FOUND": "A required storage file was not found.",
    "STORAGE_IO_ERROR": "The storage layer hit a filesystem read or write error.",
    "STORAGE_PERMISSION_ERROR": "The storage layer does not have permission to read or write the target path.",
    "TRANSLATION_ERROR": "The translation workflow failed while processing the request.",
    "TRANSLATION_MODEL_UNAVAILABLE": "No usable translation model is available for the selected provider.",
    "TRANSLATION_PREFLIGHT_FAILED": "The translation workflow found missing prerequisites before calling the AI provider.",
    "TRANSLATION_REQUEST_ERROR": "The translation request contains invalid values.",
    "UPSTREAM_SERVICE_ERROR": "A scraper, provider, or other upstream service failed while handling the request.",
    "VALIDATION_ERROR": "The request format is invalid. Check required fields and value types.",
}

_PROVIDER_STATUS_BY_CODE: dict[ProviderErrorCode, int] = {
    ProviderErrorCode.CONFIGURATION: status.HTTP_503_SERVICE_UNAVAILABLE,
    ProviderErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ProviderErrorCode.QUOTA_EXHAUSTED: status.HTTP_503_SERVICE_UNAVAILABLE,
    ProviderErrorCode.MODEL_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ProviderErrorCode.MODEL_DEPRECATED: status.HTTP_503_SERVICE_UNAVAILABLE,
    ProviderErrorCode.CONTEXT_TOO_LARGE: status.HTTP_400_BAD_REQUEST,
    ProviderErrorCode.SAFETY_BLOCKED: 422,
    ProviderErrorCode.TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    ProviderErrorCode.INVALID_JSON: status.HTTP_502_BAD_GATEWAY,
    ProviderErrorCode.EMPTY_OUTPUT: status.HTTP_502_BAD_GATEWAY,
    ProviderErrorCode.PARTIAL_OUTPUT: status.HTTP_502_BAD_GATEWAY,
    ProviderErrorCode.UNKNOWN: status.HTTP_502_BAD_GATEWAY,
}


class ErrorClassification(NamedTuple):
    status_code: int
    code: str
    message: str
    explanation: str | None
    details: dict[str, Any]
    category: str


def _as_non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is None:
        return None
    return str(value).strip() or None


def _as_status_code(value: Any, default: int = DEFAULT_INTERNAL_STATUS) -> int:
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    return default


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _find_in_exception_chain[TExc: BaseException](exc: BaseException, cls: type[TExc]) -> TExc | None:
    for item in _exception_chain(exc):
        if isinstance(item, cls):
            return item
    return None


def _extract_novel_code_from_path(path: str) -> str | None:
    parts = [part.strip() for part in path.split("/") if part.strip()]
    for index, part in enumerate(parts):
        if part != "novels" or index + 1 >= len(parts):
            continue
        candidate = parts[index + 1]
        if candidate and candidate not in _NON_NOVEL_ROUTE_PARTS:
            return candidate
    return None


def _is_storage_exhaustion(exc: BaseException) -> bool:
    exhaustion_errnos = {errno.ENOSPC}
    if hasattr(errno, "EDQUOT"):
        exhaustion_errnos.add(errno.EDQUOT)

    for item in _exception_chain(exc):
        if isinstance(item, OSError) and item.errno in exhaustion_errnos:
            return True
        message = str(item).lower()
        if any(marker in message for marker in ("no space left", "disk full", "insufficient storage", "quota exceeded")):
            return True
    return False


def _error_payload(
    *,
    code: str,
    message: str,
    explanation: str | None = None,
    details: Any | None = None,
    category: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    normalized_code = code.strip().upper() or DEFAULT_INTERNAL_CODE
    normalized_message = redact_secret_text(message.strip() or normalized_code.replace("_", " ").title())
    payload: dict[str, Any] = {
        "error": normalized_code,
        "code": normalized_code,
        "detail": normalized_message,
        "message": normalized_message,
        "explanation": explanation or _EXPLANATION_BY_CODE.get(normalized_code) or _EXPLANATION_BY_CODE[DEFAULT_INTERNAL_CODE],
    }
    if category:
        payload["category"] = category
    if details is not None:
        payload["details"] = redact_sensitive(details)
    if trace_id:
        payload["trace_id"] = trace_id
    return payload


def _json_error(
    *,
    status_code: int,
    code: str,
    message: str,
    explanation: str | None = None,
    details: Any | None = None,
    category: str | None = None,
    trace_id: str | None = None,
) -> JSONResponse:
    payload = _error_payload(
        code=code,
        message=message,
        explanation=explanation,
        details=details,
        category=category,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
    )


def _request_trace_id(request: Request) -> str | None:
    for header_name in ("x-request-id", "x-correlation-id", "traceparent"):
        value = request.headers.get(header_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _http_error_detail(exc: StarletteHTTPException) -> tuple[str, str, str | None, Any | None]:
    detail = exc.detail
    default_code = _HTTP_CODE_BY_STATUS.get(exc.status_code, "HTTP_ERROR")
    phrase = _as_non_empty_string(getattr(exc, "phrase", None))
    if isinstance(detail, dict):
        raw_code = detail.get("code") or detail.get("error") or default_code
        code = _as_non_empty_string(raw_code) or default_code
        message = (
            _as_non_empty_string(detail.get("message"))
            or _as_non_empty_string(detail.get("detail"))
            or phrase
            or default_code.replace("_", " ").title()
        )
        explanation = _as_non_empty_string(detail.get("explanation"))
        details = detail.get("details")
        if details is None:
            details = {
                key: value
                for key, value in detail.items()
                if key not in {"code", "error", "message", "detail", "explanation"}
            } or None
        return code, message, explanation, details

    message = _as_non_empty_string(detail) or phrase or default_code.replace("_", " ").title()
    return default_code, message, None, None


def _request_operation(request: Request) -> str:
    path = request.url.path.lower()
    if "/admin" in path:
        if "preliminary-crawl" in path or "scrape" in path or "/crawler" in path:
            return "crawler"
        if "translate" in path or "translation" in path:
            return "translation"
        if "/activity" in path or "/jobs" in path:
            return "activity"
        if "/requests" in path:
            return "requests"
        return "admin"
    # public / API routes
    if "preliminary-crawl" in path or "scrape" in path or "/crawler" in path:
        return "crawler"
    if "translate" in path or "translation" in path:
        return "translation"
    if "import" in path:
        return "import"
    if "export" in path:
        return "export"
    if "/activity" in path or "/jobs" in path:
        return "activity"
    if "/requests" in path:
        return "requests"
    if "/chapters" in path or "/reader" in path or "/novels" in path:
        return "storage"
    return "application"


def _base_details(request: Request, exc: BaseException, operation: str) -> dict[str, Any]:
    chain = _exception_chain(exc)
    cause_chain = [
        {"type": e.__class__.__name__, "message": redact_secret_text(str(e))}
        for e in chain[1:]  # skip the top-level (already in "exception")
    ]
    details = {
        "exception": exc.__class__.__name__,
        "error": redact_secret_text(str(exc)),
        "cause_chain": cause_chain or None,
        "operation": operation,
        "method": request.method,
        "path": request.url.path,
    }
    novel_code = _extract_novel_code_from_path(request.url.path)
    if novel_code:
        details["novel_code"] = novel_code
    return details


def _provider_error_status(exc: ProviderError) -> int:
    return _PROVIDER_STATUS_BY_CODE.get(exc.provider_error_code, status.HTTP_502_BAD_GATEWAY)


def _provider_error_message(exc: ProviderError) -> str:
    messages = {
        ProviderErrorCode.CONFIGURATION: "Provider is not configured",
        ProviderErrorCode.RATE_LIMITED: "Provider rate limit reached",
        ProviderErrorCode.QUOTA_EXHAUSTED: "Provider quota exhausted",
        ProviderErrorCode.MODEL_UNAVAILABLE: "Provider model unavailable",
        ProviderErrorCode.MODEL_DEPRECATED: "Provider model deprecated",
        ProviderErrorCode.CONTEXT_TOO_LARGE: "Provider context window exceeded",
        ProviderErrorCode.SAFETY_BLOCKED: "Provider safety filter blocked the response",
        ProviderErrorCode.TIMEOUT: "Provider request timed out",
        ProviderErrorCode.INVALID_JSON: "Provider returned invalid JSON",
        ProviderErrorCode.EMPTY_OUTPUT: "Provider returned empty output",
        ProviderErrorCode.PARTIAL_OUTPUT: "Provider returned partial output",
        ProviderErrorCode.UNKNOWN: _as_non_empty_string(str(exc)) or "Provider request failed",
    }
    return messages[exc.provider_error_code]


def _provider_error_explanation(exc: ProviderError) -> str:
    if exc.provider_error_code == ProviderErrorCode.CONFIGURATION:
        return "Configure an active provider credential before starting translation."
    if exc.provider_error_code in {ProviderErrorCode.RATE_LIMITED, ProviderErrorCode.QUOTA_EXHAUSTED}:
        return "The selected provider/model cannot complete this request right now."
    if exc.provider_error_code in {ProviderErrorCode.MODEL_UNAVAILABLE, ProviderErrorCode.MODEL_DEPRECATED}:
        return "The selected provider/model is not available for this request."
    if exc.provider_error_code == ProviderErrorCode.CONTEXT_TOO_LARGE:
        return "The translation request is larger than the selected provider/model can accept."
    if exc.provider_error_code == ProviderErrorCode.SAFETY_BLOCKED:
        return "The provider refused to produce output for this request."
    return _EXPLANATION_BY_CODE["PROVIDER_ERROR"]


def _classify_unhandled_error(request: Request, exc: Exception) -> ErrorClassification:
    operation = _request_operation(request)
    message = _as_non_empty_string(str(exc)) or exc.__class__.__name__
    lower_message = message.lower()
    details = _base_details(request, exc, operation)

    if isinstance(exc, TimeoutError):
        return ErrorClassification(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "OPERATION_TIMEOUT",
            message,
            None,
            details,
            operation,
        )

    if isinstance(exc, PermissionError):
        return ErrorClassification(
            DEFAULT_INTERNAL_STATUS,
            "STORAGE_PERMISSION_ERROR",
            message,
            None,
            details,
            "storage",
        )

    if isinstance(exc, FileNotFoundError):
        return ErrorClassification(
            status.HTTP_404_NOT_FOUND,
            "STORAGE_FILE_NOT_FOUND",
            message,
            None,
            details,
            "storage",
        )

    if isinstance(exc, OSError):
        return ErrorClassification(
            DEFAULT_INTERNAL_STATUS,
            "STORAGE_IO_ERROR",
            message,
            None,
            details,
            "storage",
        )

    if isinstance(exc, ValueError):
        code = "VALIDATION_ERROR"
        if operation == "activity":
            code = "ACTIVITY_VALIDATION_ERROR"
        elif operation == "requests":
            code = "REQUEST_QUEUE_VALIDATION_ERROR"
        elif operation == "translation":
            code = "TRANSLATION_REQUEST_ERROR"
        return ErrorClassification(
            status.HTTP_400_BAD_REQUEST,
            code,
            message,
            None,
            details,
            operation,
        )

    if isinstance(exc, KeyError):
        code = "INTERNAL_FIELD_MISSING"
        response_status = DEFAULT_INTERNAL_STATUS
        if "registered" in lower_message or "unknown" in lower_message or "provider" in lower_message or "source" in lower_message:
            code = "REGISTRY_LOOKUP_ERROR"
            response_status = status.HTTP_400_BAD_REQUEST
        return ErrorClassification(
            response_status,
            code,
            message,
            None,
            details,
            operation,
        )

    if isinstance(exc, RuntimeError):
        if "metadata not found" in lower_message:
            return ErrorClassification(
                status.HTTP_404_NOT_FOUND,
                "METADATA_NOT_FOUND",
                message,
                None,
                details,
                "storage",
            )
        if "translation preflight failed" in lower_message:
            return ErrorClassification(
                status.HTTP_400_BAD_REQUEST,
                "TRANSLATION_PREFLIGHT_FAILED",
                message,
                None,
                details,
                "translation",
            )
        if "no translation models available" in lower_message:
            return ErrorClassification(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "TRANSLATION_MODEL_UNAVAILABLE",
                message,
                None,
                details,
                "translation",
            )
        if "metadata translation skipped" in lower_message or "api token" in lower_message or "api key" in lower_message:
            return ErrorClassification(
                status.HTTP_400_BAD_REQUEST,
                "PROVIDER_CONFIG_ERROR",
                message,
                None,
                details,
                "provider",
            )
        if "source returned" in lower_message or "no chapters imported" in lower_message:
            return ErrorClassification(
                status.HTTP_502_BAD_GATEWAY,
                "SOURCE_PARSE_ERROR",
                message,
                None,
                details,
                "crawler",
            )
        if operation == "translation":
            return ErrorClassification(
                status.HTTP_502_BAD_GATEWAY,
                "TRANSLATION_ERROR",
                message,
                None,
                details,
                "translation",
            )
        if operation == "crawler":
            return ErrorClassification(
                status.HTTP_502_BAD_GATEWAY,
                "SOURCE_PARSE_ERROR",
                message,
                None,
                details,
                "crawler",
            )
        if operation == "activity":
            return ErrorClassification(
                424,
                "ACTIVITY_ERROR",
                message,
                None,
                details,
                "activity",
            )
        if operation == "requests":
            return ErrorClassification(
                424,
                "REQUEST_QUEUE_ERROR",
                message,
                None,
                details,
                "requests",
            )
        if operation == "export":
            return ErrorClassification(
                424,
                "EXPORT_ERROR",
                message,
                None,
                details,
                "export",
            )
        if operation == "storage":
            return ErrorClassification(
                DEFAULT_INTERNAL_STATUS,
                "STORAGE_ERROR",
                message,
                None,
                details,
                "storage",
            )
        if operation == "admin":
            return ErrorClassification(
                DEFAULT_INTERNAL_STATUS,
                "INTERNAL_ERROR",
                message,
                None,
                details,
                "admin",
            )
    return ErrorClassification(
        DEFAULT_INTERNAL_STATUS,
        "RUNTIME_ERROR" if isinstance(exc, RuntimeError) else DEFAULT_INTERNAL_CODE,
        message if isinstance(exc, RuntimeError) else DEFAULT_INTERNAL_MESSAGE,
        None,
        details,
        operation,
    )


def add_error_handlers(app: FastAPI) -> None:
    """Register error handlers for Novel AI exceptions.

    Usage:
        app = FastAPI()
        add_error_handlers(app)
    """
    from novelai.api.errors import StructuredHTTPException, record_error

    @app.exception_handler(StructuredHTTPException)
    async def structured_exception_handler(request: Request, exc: StructuredHTTPException):
        """Convert StructuredHTTPException to canonical ErrorResponse JSON."""
        record_error(exc.category.value)
        resp = exc.to_response()
        return JSONResponse(
            status_code=exc.status_code,
            content=resp.model_dump(exclude_none=True),
        )

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
        """FastAPI HTTP errors with structured, UI-readable payloads."""
        code, message, explanation, details = _http_error_detail(exc)
        return _json_error(
            status_code=exc.status_code,
            code=code,
            message=message,
            explanation=explanation,
            details=details,
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Starlette HTTP errors, including router-level 404s."""
        code, message, explanation, details = _http_error_detail(exc)
        return _json_error(
            status_code=exc.status_code,
            code=code,
            message=message,
            explanation=explanation,
            details=details,
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Pydantic/FastAPI request validation errors."""
        logger.warning("Request validation error: %s", exc)
        return _json_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=[
                {
                    "field": " -> ".join(str(p) for p in e.get("loc", [])),
                    "message": e.get("msg", ""),
                    "type": e.get("type", ""),
                }
                for e in exc.errors()
            ],
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(ProviderConfigError)
    async def provider_config_error_handler(request: Request, exc: ProviderConfigError):
        """Provider configuration missing or invalid."""
        logger.warning("Provider config error: %s", exc)
        return _json_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="PROVIDER_CONFIG_ERROR",
            message=str(exc),
            category="provider",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(ProviderAPIError)
    async def provider_api_error_handler(request: Request, exc: ProviderAPIError):
        """Provider API call failed."""
        logger.error(
            "Provider API error: %s details=%s",
            redact_secret_text(str(exc)),
            redact_sensitive(getattr(exc, "details", None)),
        )
        return _json_error(
            status_code=_provider_error_status(exc),
            code="PROVIDER_ERROR",
            message=_provider_error_message(exc),
            explanation=_provider_error_explanation(exc),
            details=exc.public_details(),
            category="provider",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError):
        """Generic provider error."""
        logger.error(
            "Provider error: %s details=%s",
            redact_secret_text(str(exc)),
            redact_sensitive(getattr(exc, "details", None)),
        )
        return _json_error(
            status_code=_provider_error_status(exc),
            code="PROVIDER_ERROR",
            message=_provider_error_message(exc),
            explanation=_provider_error_explanation(exc),
            details=exc.public_details(),
            category="provider",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(SourceFetchError)
    async def source_fetch_error_handler(request: Request, exc: SourceFetchError):
        """Failed to fetch from source."""
        logger.error("Source fetch error: %s", exc)
        details: dict[str, Any] = {"source_error": redact_secret_text(str(exc))}
        source_status = getattr(exc, "status_code", None)
        source_url = getattr(exc, "url", None)
        if source_status is not None:
            details["http_status"] = source_status
        if source_url is not None:
            details["url"] = source_url
        return _json_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SOURCE_FETCH_ERROR",
            message="Failed to fetch from source. Please check the source is available.",
            details=details,
            category="crawler",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(SourceError)
    async def source_error_handler(request: Request, exc: SourceError):
        """Generic source error."""
        logger.error("Source error: %s", exc)
        return _json_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SOURCE_ERROR",
            message=str(exc),
            category="crawler",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(PipelineError)
    async def pipeline_error_handler(request: Request, exc: PipelineError):
        """Pipeline execution error."""
        logger.error("Pipeline error: %s", exc)
        details: dict[str, Any] = {"pipeline_error": str(exc)}
        stage = getattr(exc, "stage", None)
        novel_code = getattr(exc, "novel_code", None)
        if stage is not None:
            details["stage"] = stage
        if novel_code is not None:
            details["novel_code"] = novel_code
        return _json_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="PIPELINE_ERROR",
            message="Translation pipeline failed. Please try again.",
            details=details,
            category="translation",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(StorageError)
    async def storage_error_handler(request: Request, exc: StorageError):
        """Storage layer error."""
        logger.error("Storage error: %s", exc)
        status_code = DEFAULT_INTERNAL_STATUS
        code = "STORAGE_ERROR"
        message = "Storage service error. Please try again."
        if _find_in_exception_chain(exc, FileNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            code = "STORAGE_FILE_NOT_FOUND"
        elif _find_in_exception_chain(exc, PermissionError):
            code = "STORAGE_PERMISSION_ERROR"
        elif _is_storage_exhaustion(exc):
            status_code = 507
            code = "INSUFFICIENT_STORAGE"
        elif _find_in_exception_chain(exc, OSError):
            code = "STORAGE_IO_ERROR"

        cause = exc.__cause__
        os_cause = _find_in_exception_chain(exc, OSError)
        details: dict[str, Any] = {
            "storage_error": exc.__class__.__name__,
            "cause": cause.__class__.__name__ if cause is not None else None,
        }
        if os_cause:
            details["errno"] = os_cause.errno
            if os_cause.filename:
                details["filename"] = Path(str(os_cause.filename)).name
            details["strerror"] = os_cause.strerror

        return _json_error(
            status_code=status_code,
            code=code,
            message=message,
            details=details,
            category="storage",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(ExportError)
    async def export_error_handler(request: Request, exc: ExportError):
        """Export generation error."""
        logger.error("Export error: %s", exc)
        return _json_error(
            status_code=424,
            code="EXPORT_ERROR",
            message="Failed to generate export. Please try again.",
            details={"export_error": str(exc)},
            category="export",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(ConfigError)
    async def config_error_handler(request: Request, exc: ConfigError):
        """Configuration error."""
        logger.critical("Config error: %s", exc)
        return _json_error(
            status_code=DEFAULT_INTERNAL_STATUS,
            code="CONFIGURATION_ERROR",
            message="Server configuration error. Contact administrator.",
            details={"config_error": str(exc)},
            category="config",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(NovelAIError)
    async def novel_ai_error_handler(request: Request, exc: NovelAIError):
        """Catch-all for Novel AI errors."""
        logger.error("Novel AI error: %s", exc)
        details = getattr(exc, "details", None)
        if details is None:
            details = {"application_error": str(exc)}
        message = _as_non_empty_string(getattr(exc, "message", None)) or _as_non_empty_string(str(exc)) or "An application error occurred."
        return _json_error(
            status_code=_as_status_code(getattr(exc, "status_code", DEFAULT_INTERNAL_STATUS)),
            code=_as_non_empty_string(getattr(exc, "code", None)) or "APPLICATION_ERROR",
            message=message,
            explanation=_as_non_empty_string(getattr(exc, "explanation", None)),
            details=details,
            category=_as_non_empty_string(getattr(exc, "category", None)) or "application",
            trace_id=_request_trace_id(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        """Last-resort handler for unexpected backend errors."""
        classified = _classify_unhandled_error(request, exc)
        logger.exception("Unhandled API error classified as %s: %s", classified.code, exc)
        is_server_error = classified.status_code == DEFAULT_INTERNAL_STATUS
        public_message = (
            classified.message
            if DEBUG_ERRORS or not is_server_error
            else DEFAULT_INTERNAL_MESSAGE
        )
        public_details = (
            classified.details
            if DEBUG_ERRORS or not is_server_error
            else {
                "operation": classified.details.get("operation"),
            }
        )
        return _json_error(
            status_code=classified.status_code,
            code=classified.code,
            message=public_message,
            explanation=classified.explanation,
            details=public_details,
            category=classified.category,
            trace_id=_request_trace_id(request),
        )
