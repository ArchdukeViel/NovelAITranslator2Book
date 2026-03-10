"""Core abstractions and shared types for Novel AI."""

from novelai.core.chapter_state import ChapterMetadata, ChapterState, ChapterStateTransition
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

__all__ = [
    "ChapterMetadata",
    "ChapterState",
    "ChapterStateTransition",
    "ConfigError",
    "ExportError",
    "NovelAIError",
    "PipelineError",
    "PipelineStageError",
    "ProviderAPIError",
    "ProviderConfigError",
    "ProviderError",
    "SourceConfigError",
    "SourceError",
    "SourceFetchError",
    "StorageError",
]
