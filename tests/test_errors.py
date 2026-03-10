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
    error = ProviderAPIError("api failed")
    assert isinstance(error, ProviderError)
    assert isinstance(error, NovelAIError)
    assert str(error) == "api failed"


def test_source_fetch_error_is_source_error() -> None:
    error = SourceFetchError("network timeout")
    assert isinstance(error, SourceError)


def test_pipeline_stage_error_is_pipeline_error() -> None:
    error = PipelineStageError("stage crashed")
    assert isinstance(error, PipelineError)
