"""Tests for enhanced error handling and logging."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.errors import (
    CATEGORY_TO_STATUS,
    ErrorCategory,
    ErrorResponse,
    StructuredHTTPException,
    get_error_metrics,
    record_error,
)
from novelai.api.routers.admin import router as admin_router


class TestStructuredHTTPException:
    def test_to_response_serialization(self) -> None:
        exc = StructuredHTTPException(
            status_code=422,
            detail="Invalid input",
            error_code="validation.request",
            category=ErrorCategory.VALIDATION,
            request_id="req-123",
        )
        resp = exc.to_response()
        assert isinstance(resp, ErrorResponse)
        assert resp.error == "validation"
        assert resp.detail == "Invalid input"
        assert resp.error_code == "validation.request"
        assert resp.request_id == "req-123"
        assert resp.timestamp is not None
        # ISO 8601
        assert re.match(r"\d{4}-\d{2}-\d{2}T", resp.timestamp)

    def test_to_response_with_retry_after(self) -> None:
        exc = StructuredHTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            error_code="pipeline.translate.rate_limit",
            category=ErrorCategory.PROVIDER,
            retry_after="PT30S",
        )
        resp = exc.to_response()
        assert resp.retry_after == "PT30S"

    def test_to_response_default_fields(self) -> None:
        exc = StructuredHTTPException(status_code=500, detail="Oops")
        resp = exc.to_response()
        assert resp.error_code == "internal.error"
        assert resp.request_id is None
        assert resp.retry_after is None


class TestErrorResponseModel:
    def test_can_dump_json(self) -> None:
        resp = ErrorResponse(
            error="validation",
            detail="Bad field",
            error_code="validation.request",
            timestamp=datetime.now(UTC).isoformat(),
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["error"] == "validation"
        assert "request_id" not in dumped
        assert "retry_after" not in dumped

    def test_with_optional_fields(self) -> None:
        resp = ErrorResponse(
            error="auth",
            detail="Unauthorized",
            error_code="auth.unauthorized",
            request_id="req-1",
            timestamp=datetime.now(UTC).isoformat(),
            retry_after="PT10S",
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["request_id"] == "req-1"
        assert dumped["retry_after"] == "PT10S"


class TestCategoryToStatusMapping:
    def test_all_categories_mapped(self) -> None:
        for category in ErrorCategory:
            assert category in CATEGORY_TO_STATUS
            status = CATEGORY_TO_STATUS[category]
            assert isinstance(status, int)
            assert 100 <= status <= 599


class TestErrorMetrics:
    def test_record_and_get(self) -> None:
        # Fresh counters (other tests may have added noise, so just check structure)
        record_error("provider", stage="translate")
        record_error("validation")
        metrics = get_error_metrics()
        assert "by_category" in metrics
        assert "by_stage" in metrics


class TestStructuredExceptionHandler:
    def test_handler_returns_structured_json(self) -> None:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
        current: dict = {"user": SessionUser(user_id=None, email=None, role="guest")}

        def _user_override():
            return current["user"]

        app.dependency_overrides[get_current_user] = _user_override

        from novelai.api.error_handlers import add_error_handlers
        add_error_handlers(app)

        @app.get("/test-structured-error")
        async def raise_structured():
            raise StructuredHTTPException(
                status_code=422,
                detail="Test validation error",
                error_code="validation.request",
                category=ErrorCategory.VALIDATION,
            )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-structured-error")
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"] == "validation"
        assert data["detail"] == "Test validation error"
        assert data["error_code"] == "validation.request"
        assert "timestamp" in data


class TestPipelineStateLogging:
    def test_stage_lifecycle_logs_json(self) -> None:
        from novelai.services.pipeline.context import StageLogContext

        records: list[logging.LogRecord] = []

        class ListHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        logger = logging.getLogger("test_pipeline_ctx")
        logger.addHandler(ListHandler())
        logger.setLevel(logging.INFO)

        ctx = StageLogContext(novel_id="n1", chapter_id="c1", request_id="req-1", logger=logger)
        marker = ctx.stage_enter("TestStage")
        ctx.stage_exit(marker)

        assert len(records) == 2
        enter = records[0]
        assert enter.levelno == logging.INFO
        assert enter.__dict__["stage"] == "TestStage"
        assert enter.__dict__["event"] == "stage_enter"

        exit_record = records[1]
        assert exit_record.__dict__["event"] == "stage_exit"
        assert exit_record.__dict__["duration_ms"] >= 0

    def test_stage_error_logs_error_level(self) -> None:
        from novelai.services.pipeline.context import StageLogContext

        records: list[logging.LogRecord] = []

        class ListHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        logger = logging.getLogger("test_pipeline_err")
        logger.addHandler(ListHandler())
        logger.setLevel(logging.INFO)

        ctx = StageLogContext(novel_id="n1", chapter_id="c1", request_id="req-1", logger=logger)
        marker = ctx.stage_enter("FailStage")
        ctx.stage_error(marker, error_code="pipeline.fetch.timeout", stack_trace="  File \"test.py\", line 1, in test\n")

        assert len(records) == 2
        error_record = records[1]
        assert error_record.levelno == logging.ERROR
        assert error_record.__dict__["error_code"] == "pipeline.fetch.timeout"
        assert "test.py" in error_record.__dict__["stack_trace"]


class TestJsonFormatter:
    def test_output_is_valid_json(self) -> None:
        from novelai.logging_config import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self) -> None:
        from novelai.logging_config import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="t.py",
            lineno=1,
            msg="warning msg",
            args=(),
            exc_info=None,
        )
        record.novel_id = "n1"
        record.stage = "FetchStage"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["novel_id"] == "n1"
        assert parsed["stage"] == "FetchStage"

    def test_includes_exception_info(self) -> None:
        from novelai.logging_config import JsonFormatter

        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="t.py",
                lineno=1,
                msg="error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "test error" in parsed["exception"]


class TestHealthErrorsEndpoint:
    def test_endpoint_returns_metrics(self) -> None:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
        current: dict = {"user": SessionUser(user_id=1, email="admin@test.com", role="owner")}

        def _user_override():
            return current["user"]

        app.dependency_overrides[get_current_user] = _user_override
        app.include_router(admin_router, prefix="/api")

        from novelai.api.error_handlers import add_error_handlers
        add_error_handlers(app)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/admin/health/errors")
        assert resp.status_code == 200
        data = resp.json()
        assert "by_category" in data
        assert "by_stage" in data
