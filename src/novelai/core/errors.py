"""Shared exception types."""


class NovelAIError(Exception):
    """Base exception for Novel AI."""


class ProviderError(NovelAIError):
    """Provider-specific exceptions."""


class SourceError(NovelAIError):
    """Source scraping / parsing exceptions."""


class ExportError(NovelAIError):
    """Export generation exceptions."""
