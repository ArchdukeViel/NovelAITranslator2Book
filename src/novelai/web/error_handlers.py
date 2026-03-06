"""Error handler middleware and utilities for FastAPI.

Provides consistent error responses and logging for Novel AI errors.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from novelai.core.errors import (
    ConfigError,
    ExportError,
    NovelAIError,
    PipelineError,
    ProviderAPIError,
    ProviderConfigError,
    ProviderError,
    SourceError,
    SourceFetchError,
    StorageError,
)

logger = logging.getLogger(__name__)


def add_error_handlers(app: FastAPI) -> None:
    """Register error handlers for Novel AI exceptions.
    
    Usage:
        app = FastAPI()
        add_error_handlers(app)
    """

    @app.exception_handler(ProviderConfigError)
    async def provider_config_error_handler(request: Request, exc: ProviderConfigError):
        """Provider configuration missing or invalid."""
        logger.warning(f"Provider config error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "provider_config_error", "detail": str(exc)},
        )

    @app.exception_handler(ProviderAPIError)
    async def provider_api_error_handler(request: Request, exc: ProviderAPIError):
        """Provider API call failed."""
        logger.error(f"Provider API error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "provider_unavailable",
                "detail": "Translation service temporarily unavailable. Please try again later.",
            },
        )

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError):
        """Generic provider error."""
        logger.error(f"Provider error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "provider_error", "detail": str(exc)},
        )

    @app.exception_handler(SourceFetchError)
    async def source_fetch_error_handler(request: Request, exc: SourceFetchError):
        """Failed to fetch from source."""
        logger.error(f"Source fetch error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "source_unavailable",
                "detail": "Failed to fetch from source. Please check the source is available.",
            },
        )

    @app.exception_handler(SourceError)
    async def source_error_handler(request: Request, exc: SourceError):
        """Generic source error."""
        logger.error(f"Source error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "source_error", "detail": str(exc)},
        )

    @app.exception_handler(PipelineError)
    async def pipeline_error_handler(request: Request, exc: PipelineError):
        """Pipeline execution error."""
        logger.error(f"Pipeline error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "pipeline_error",
                "detail": "Translation pipeline failed. Please try again.",
            },
        )

    @app.exception_handler(StorageError)
    async def storage_error_handler(request: Request, exc: StorageError):
        """Storage layer error."""
        logger.error(f"Storage error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "storage_error",
                "detail": "Storage service error. Please try again.",
            },
        )

    @app.exception_handler(ExportError)
    async def export_error_handler(request: Request, exc: ExportError):
        """Export generation error."""
        logger.error(f"Export error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "export_error",
                "detail": "Failed to generate export. Please try again.",
            },
        )

    @app.exception_handler(ConfigError)
    async def config_error_handler(request: Request, exc: ConfigError):
        """Configuration error."""
        logger.critical(f"Config error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "config_error",
                "detail": "Server configuration error. Contact administrator.",
            },
        )

    @app.exception_handler(NovelAIError)
    async def novel_ai_error_handler(request: Request, exc: NovelAIError):
        """Catch-all for Novel AI errors."""
        logger.error(f"Novel AI error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "detail": "An error occurred."},
        )
