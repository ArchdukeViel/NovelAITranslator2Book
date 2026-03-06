"""Shared exception types for Novel AI."""


class NovelAIError(Exception):
    """Base exception for all Novel AI errors."""


class ConfigError(NovelAIError):
    """Configuration or initialization errors."""


class ProviderError(NovelAIError):
    """Provider-specific errors (API calls, authentication, rate limits)."""


class ProviderConfigError(ProviderError):
    """Provider configuration missing or invalid."""


class ProviderAPIError(ProviderError):
    """Provider API call failed (transient or permanent)."""


class SourceError(NovelAIError):
    """Source scraping / parsing errors."""


class SourceConfigError(SourceError):
    """Source configuration missing or invalid."""


class SourceFetchError(SourceError):
    """Failed to fetch from source (network, parsing, etc)."""


class PipelineError(NovelAIError):
    """Pipeline execution errors."""


class PipelineStageError(PipelineError):
    """Individual pipeline stage error."""


class StorageError(NovelAIError):
    """Storage layer errors."""


class ExportError(NovelAIError):
    """Export generation errors."""
