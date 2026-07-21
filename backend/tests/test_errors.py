"""Tests for the exception hierarchy in core.errors."""

from __future__ import annotations

from novelai.core.errors import (
    ConfigError,
    ExportError,
    NovelAIError,
    PipelineError,
    PipelineStageError,
    ProviderAPIError,
    ProviderConfigError,
    ProviderError,
    ProviderErrorCode,
    SourceConfigError,
    SourceError,
    SourceFetchError,
    StorageError,
)


def test_all_exceptions_inherit_from_novelai_error() -> None:
    for cls in (
        ConfigError,
        ProviderError,
        ProviderConfigError,
        ProviderAPIError,
        SourceError,
        SourceConfigError,
        SourceFetchError,
        PipelineError,
        PipelineStageError,
        StorageError,
        ExportError,
    ):
        assert issubclass(cls, NovelAIError)


def test_provider_api_error_is_provider_error() -> None:
    error = ProviderAPIError(
        ProviderErrorCode.UNKNOWN,
        provider_key="gemini",
        provider_model="gemini-3.1-flash-lite",
        message="api failed",
    )
    assert isinstance(error, ProviderError)
    assert isinstance(error, NovelAIError)
    assert str(error) == "api failed"


def test_provider_config_error_uses_structured_code() -> None:
    error = ProviderConfigError(
        ProviderErrorCode.CONFIGURATION,
        provider_key="gemini",
        provider_model="gemini-3.1-flash-lite",
        message="Provider is not configured",
    )

    assert error.provider_error_code == ProviderErrorCode.CONFIGURATION
    assert error.provider_key == "gemini"
    assert str(error) == "Provider is not configured"


def test_provider_error_exposes_public_details() -> None:
    error = ProviderError(
        ProviderErrorCode.RATE_LIMITED,
        provider_key="gemini",
        provider_model="gemini-2.5-flash-lite",
        message="Provider rate limit reached",
        retry_after_seconds=21,
        cooldown_until="2026-06-04T12:00:00Z",
        details={"raw_message": "429 RESOURCE_EXHAUSTED"},
        requests_this_minute=60,
    )

    assert error.public_details() == {
        "provider_key": "gemini",
        "provider_model": "gemini-2.5-flash-lite",
        "provider_error_code": "provider_rate_limited",
        "retry_after_seconds": 21,
        "cooldown_until": "2026-06-04T12:00:00Z",
        "exhausted_until": None,
        "requests_this_minute": 60,
    }
    assert error.activity_details()["provider_error_details"]["raw_message"] == "429 RESOURCE_EXHAUSTED"


def test_source_fetch_error_is_source_error() -> None:
    error = SourceFetchError("network timeout")
    assert isinstance(error, SourceError)


def test_pipeline_stage_error_is_pipeline_error() -> None:
    error = PipelineStageError("stage crashed")
    assert isinstance(error, PipelineError)
