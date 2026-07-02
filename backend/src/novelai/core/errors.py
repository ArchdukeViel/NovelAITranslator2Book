"""Shared exception types for Novel AI."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class NovelAIError(Exception):
    """Base exception for all Novel AI errors."""


class ConfigError(NovelAIError):
    """Configuration or initialization errors."""


class ProviderErrorCode(StrEnum):
    RATE_LIMITED = "provider_rate_limited"
    QUOTA_EXHAUSTED = "provider_quota_exhausted"
    MODEL_UNAVAILABLE = "provider_model_unavailable"
    MODEL_DEPRECATED = "provider_model_deprecated"
    CONTEXT_TOO_LARGE = "provider_context_too_large"
    SAFETY_BLOCKED = "provider_safety_blocked"
    TIMEOUT = "provider_timeout"
    INVALID_JSON = "provider_invalid_json"
    EMPTY_OUTPUT = "provider_empty_output"
    PARTIAL_OUTPUT = "provider_partial_output"
    UNKNOWN = "provider_unknown_error"


class ProviderError(NovelAIError):
    """Provider-specific errors with normalized scheduler/API metadata."""

    category = "provider"

    def __init__(
        self,
        code: ProviderErrorCode | str = ProviderErrorCode.UNKNOWN,
        provider_key: str | None = None,
        provider_model: str | None = None,
        message: str | None = None,
        retry_after_seconds: int | None = None,
        cooldown_until: str | None = None,
        exhausted_until: str | None = None,
        details: dict[str, Any] | None = None,
        requests_this_minute: int | None = None,
        requests_today: int | None = None,
    ) -> None:
        # Backward compatibility for older call sites: ProviderError("message").
        if message is None and not isinstance(code, ProviderErrorCode):
            raw_code = str(code)
            if raw_code not in {item.value for item in ProviderErrorCode}:
                message = raw_code
                code = ProviderErrorCode.UNKNOWN

        self.provider_error_code = self._normalize_code(code)
        self.provider_key = provider_key or "unknown_provider"
        self.provider_model = provider_model or "unknown_model"
        self.message = message or self.provider_error_code.value.replace("_", " ").title()
        self.retry_after_seconds = retry_after_seconds
        self.cooldown_until = cooldown_until
        self.exhausted_until = exhausted_until
        self.details = dict(details or {})
        self.requests_this_minute = requests_this_minute
        self.requests_today = requests_today
        super().__init__(self.message)

    @staticmethod
    def _normalize_code(code: ProviderErrorCode | str) -> ProviderErrorCode:
        if isinstance(code, ProviderErrorCode):
            return code
        try:
            return ProviderErrorCode(str(code))
        except ValueError:
            return ProviderErrorCode.UNKNOWN

    def public_details(self) -> dict[str, Any]:
        details: dict[str, Any] = {
            "provider_key": self.provider_key,
            "provider_model": self.provider_model,
            "provider_error_code": self.provider_error_code.value,
            "retry_after_seconds": self.retry_after_seconds,
            "cooldown_until": self.cooldown_until,
            "exhausted_until": self.exhausted_until,
        }
        if self.requests_this_minute is not None:
            details["requests_this_minute"] = self.requests_this_minute
        if self.requests_today is not None:
            details["requests_today"] = self.requests_today
        return details

    def activity_details(self) -> dict[str, Any]:
        payload = self.public_details()
        if self.details:
            payload["provider_error_details"] = dict(self.details)
        return payload


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


class TranslationInProgressError(RuntimeError):
    """Raised when a translation is attempted for a chapter already being translated."""
