from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts.models import TranslationRequest
from novelai.prompts.responses_api import (
    build_basic_responses_payload,
    build_translation_responses_payload,
)
from novelai.providers.base import TranslationProvider


class OpenAIProvider(TranslationProvider):
    """OpenAI translation provider using per-request client instances.

    IMPORTANT: Uses thread-safe per-request client instances. API key is passed
    directly to each client, never stored globally. This is safe for concurrent requests.
    """

    @property
    def key(self) -> str:
        return "openai"

    def available_models(self) -> list[str]:
        return [
            "gpt-5.4",
            "gpt-5.2",
        ]

    def _api_key_string(self) -> str:
        api_key = settings.PROVIDER_OPENAI_API_KEY
        if not api_key:
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.key,
                provider_model="gpt-5.4",
                message="OpenAI API key not configured. Set PROVIDER_OPENAI_API_KEY environment variable.",
            )
        return api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)

    @staticmethod
    def _modern_async_client() -> Any | None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return None
        return AsyncOpenAI

    @staticmethod
    def _extract_message_text(response: Any) -> str:
        output_text = response.get("output_text") if isinstance(response, Mapping) else getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        if isinstance(output_text, list):
            fragments = [fragment for fragment in output_text if isinstance(fragment, str)]
            if fragments:
                return "".join(fragments).strip()

        outputs = response.get("output", []) if isinstance(response, Mapping) else getattr(response, "output", [])
        fragments: list[str] = []
        for item in outputs or []:
            content = item.get("content", []) if isinstance(item, Mapping) else getattr(item, "content", [])
            for chunk in content or []:
                chunk_type = chunk.get("type") if isinstance(chunk, Mapping) else getattr(chunk, "type", None)
                if chunk_type not in {"output_text", "text"}:
                    continue
                text = chunk.get("text") if isinstance(chunk, Mapping) else getattr(chunk, "text", None)
                if isinstance(text, str):
                    fragments.append(text)
        if fragments:
            return "".join(fragments).strip()

        if isinstance(response, Mapping):
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
        choices = getattr(response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content.strip()
        return ""

    @staticmethod
    def _extract_usage(response: Any) -> Mapping[str, Any] | None:
        usage = response.get("usage") if isinstance(response, Mapping) else getattr(response, "usage", None)
        if usage is None:
            return None
        if isinstance(usage, Mapping):
            input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
            output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": usage.get("total_tokens"),
            }
        input_tokens = getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", None))
        output_tokens = getattr(usage, "output_tokens", getattr(usage, "completion_tokens", None))
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    @staticmethod
    def _utc_after_seconds(seconds: int | None) -> str | None:
        if seconds is None:
            return None
        return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _field(cls, value: Any, *names: str) -> Any:
        current = value
        for name in names:
            if isinstance(current, Mapping):
                current = current.get(name)
            else:
                current = getattr(current, name, None)
            if current is None:
                return None
        return current

    @classmethod
    def _walk_values(cls, value: Any, *, depth: int = 0) -> list[Any]:
        if depth > 4 or value is None:
            return []
        if isinstance(value, (str, int, float, bool)):
            return [value]
        if isinstance(value, Mapping):
            values: list[Any] = []
            for item in value.values():
                values.extend(cls._walk_values(item, depth=depth + 1))
            return values
        if isinstance(value, (list, tuple, set)):
            values = []
            for item in value:
                values.extend(cls._walk_values(item, depth=depth + 1))
            return values
        values = []
        for name in ("code", "type", "param", "message", "body", "error", "status", "details"):
            item = getattr(value, name, None)
            if item is not None:
                values.extend(cls._walk_values(item, depth=depth + 1))
        return values

    @classmethod
    def _extract_retry_after_seconds(cls, exc: BaseException) -> int | None:
        headers = getattr(exc, "headers", None) or cls._field(exc, "response", "headers")
        candidates = [
            getattr(exc, "retry_after", None),
            getattr(exc, "retry_after_seconds", None),
        ]
        if isinstance(headers, Mapping):
            candidates.extend(
                [
                    headers.get("retry-after"),
                    headers.get("Retry-After"),
                    headers.get("x-ratelimit-reset-seconds"),
                ]
            )
        for candidate in candidates:
            if isinstance(candidate, timedelta):
                return max(0, int(candidate.total_seconds()))
            if isinstance(candidate, (int, float)):
                return max(0, int(candidate))
            if isinstance(candidate, str):
                text = candidate.strip()
                if text.endswith("s"):
                    text = text[:-1]
                if text.isdigit():
                    return int(text)
        return None

    @classmethod
    def _structured_status(cls, exc: BaseException) -> str:
        values = [
            getattr(exc, "status_code", None),
            getattr(exc, "code", None),
            getattr(exc, "type", None),
            getattr(exc, "param", None),
            cls._field(exc, "response", "status_code"),
            cls._field(exc, "response", "status"),
            cls._field(exc, "body", "error", "code"),
            cls._field(exc, "body", "error", "type"),
            cls._field(exc, "body", "error", "message"),
            cls._field(exc, "error", "code"),
            cls._field(exc, "error", "type"),
            cls._field(exc, "error", "message"),
        ]
        values.extend(cls._walk_values(getattr(exc, "body", None)))
        return " ".join(str(value) for value in values if value is not None)

    @classmethod
    def _classify_exception(cls, exc: BaseException) -> tuple[ProviderErrorCode, int | None, dict[str, Any]]:
        status_text = cls._structured_status(exc)
        message = str(exc)
        combined = f"{status_text} {message}".lower()
        retry_after = cls._extract_retry_after_seconds(exc)
        details = {
            "provider_status": cls._safe_string(status_text),
            "error_type": exc.__class__.__name__,
            "raw_message": message,
        }

        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in combined or "timed out" in combined:
            return ProviderErrorCode.TIMEOUT, retry_after, details
        if any(marker in combined for marker in ("safety", "refusal", "content_policy", "content policy", "blocked")):
            return ProviderErrorCode.SAFETY_BLOCKED, retry_after, details
        if "deprecated" in combined:
            return ProviderErrorCode.MODEL_DEPRECATED, retry_after, details
        if any(marker in combined for marker in ("model_not_found", "model not found", "invalid model", "does not exist", "not found")):
            return ProviderErrorCode.MODEL_UNAVAILABLE, retry_after, details
        if any(marker in combined for marker in ("context_length", "maximum context", "too many tokens", "context window", "maximum tokens")):
            return ProviderErrorCode.CONTEXT_TOO_LARGE, retry_after, details
        if "429" in combined or "rate_limit" in combined or "rate limit" in combined or "quota" in combined or "insufficient_quota" in combined:
            if any(marker in combined for marker in ("insufficient_quota", "quota exceeded", "quota exhausted", "billing", "hard limit")):
                return ProviderErrorCode.QUOTA_EXHAUSTED, retry_after, details
            return ProviderErrorCode.RATE_LIMITED, retry_after, details
        return ProviderErrorCode.UNKNOWN, retry_after, details

    def _provider_error_from_exception(self, exc: BaseException, *, provider_model: str) -> ProviderError:
        code, retry_after, details = self._classify_exception(exc)
        cooldown_until = self._utc_after_seconds(retry_after) if code == ProviderErrorCode.RATE_LIMITED else None
        return ProviderError(
            code,
            provider_key=self.key,
            provider_model=provider_model,
            message=self._public_message_for_code(code),
            retry_after_seconds=retry_after,
            cooldown_until=cooldown_until,
            details=details,
        )

    @staticmethod
    def _public_message_for_code(code: ProviderErrorCode) -> str:
        messages = {
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
            ProviderErrorCode.UNKNOWN: "Provider request failed",
        }
        return messages[code]

    @classmethod
    def _response_status(cls, response: Any) -> str | None:
        return cls._safe_string(response.get("status") if isinstance(response, Mapping) else getattr(response, "status", None))

    @classmethod
    def _incomplete_reason(cls, response: Any) -> str | None:
        details = response.get("incomplete_details") if isinstance(response, Mapping) else getattr(response, "incomplete_details", None)
        reason = details.get("reason") if isinstance(details, Mapping) else getattr(details, "reason", None)
        return cls._safe_string(reason)

    @classmethod
    def _finish_reasons(cls, response: Any) -> list[str]:
        reasons: list[str] = []
        outputs = response.get("output", []) if isinstance(response, Mapping) else getattr(response, "output", [])
        for item in outputs or []:
            reason = item.get("finish_reason") if isinstance(item, Mapping) else getattr(item, "finish_reason", None)
            if reason is not None:
                reasons.append(str(reason))
        choices = response.get("choices", []) if isinstance(response, Mapping) else getattr(response, "choices", [])
        for choice in choices or []:
            reason = choice.get("finish_reason") if isinstance(choice, Mapping) else getattr(choice, "finish_reason", None)
            if reason is not None:
                reasons.append(str(reason))
        return reasons

    @classmethod
    def _has_refusal(cls, response: Any) -> bool:
        outputs = response.get("output", []) if isinstance(response, Mapping) else getattr(response, "output", [])
        for item in outputs or []:
            content = item.get("content", []) if isinstance(item, Mapping) else getattr(item, "content", [])
            for chunk in content or []:
                chunk_type = chunk.get("type") if isinstance(chunk, Mapping) else getattr(chunk, "type", None)
                refusal = chunk.get("refusal") if isinstance(chunk, Mapping) else getattr(chunk, "refusal", None)
                if chunk_type == "refusal" or refusal:
                    return True
        return False

    def _response_error(self, response: Any, *, text: str, provider_model: str, expect_json: bool) -> ProviderError | None:
        status = (self._response_status(response) or "").lower()
        incomplete_reason = self._incomplete_reason(response)
        finish_reasons = [reason.lower() for reason in self._finish_reasons(response)]
        details = {
            "response_status": status or None,
            "incomplete_reason": incomplete_reason,
            "finish_reasons": finish_reasons or None,
        }
        if self._has_refusal(response) or any(reason in {"content_filter", "safety", "refusal"} for reason in finish_reasons):
            return ProviderError(
                ProviderErrorCode.SAFETY_BLOCKED,
                provider_key=self.key,
                provider_model=provider_model,
                message=self._public_message_for_code(ProviderErrorCode.SAFETY_BLOCKED),
                details=details,
            )
        if status == "incomplete" or any(reason in {"length", "max_tokens", "max_output_tokens"} for reason in finish_reasons):
            return ProviderError(
                ProviderErrorCode.PARTIAL_OUTPUT,
                provider_key=self.key,
                provider_model=provider_model,
                message=self._public_message_for_code(ProviderErrorCode.PARTIAL_OUTPUT),
                details=details,
            )
        if not text.strip():
            return ProviderError(
                ProviderErrorCode.EMPTY_OUTPUT,
                provider_key=self.key,
                provider_model=provider_model,
                message=self._public_message_for_code(ProviderErrorCode.EMPTY_OUTPUT),
                details=details,
            )
        if expect_json:
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                return ProviderError(
                    ProviderErrorCode.INVALID_JSON,
                    provider_key=self.key,
                    provider_model=provider_model,
                    message=self._public_message_for_code(ProviderErrorCode.INVALID_JSON),
                    details={**details, "json_error": exc.msg},
                )
        return None

    @staticmethod
    def _build_payload(
        prompt: str,
        model: str,
        *,
        request: TranslationRequest | None = None,
        max_output_tokens: int | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if request is not None:
            return build_translation_responses_payload(
                model,
                request,
                max_output_tokens=max_output_tokens,
            )
        payload = build_basic_responses_payload(
            model,
            prompt,
            system_prompt="You are a translation assistant.",
            max_output_tokens=max_output_tokens,
        )
        if isinstance(json_schema, dict):
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "structured_output",
                    "schema": json_schema,
                    "strict": True,
                }
            }
        return payload

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """Translate by calling OpenAI chat endpoint.

        Thread-safe: Uses per-request client instance, not global state.
        """
        api_key_str = self._api_key_string()
        model = model or "gpt-5.4"
        request = kwargs.pop("request", None)
        json_schema = kwargs.pop("json_schema", None)
        if request is not None and not isinstance(request, TranslationRequest):
            raise TypeError("request must be a TranslationRequest instance.")
        payload = self._build_payload(
            prompt,
            model,
            request=request,
            max_output_tokens=max_tokens,
            json_schema=json_schema if isinstance(json_schema, dict) else None,
        )

        AsyncOpenAI = self._modern_async_client()
        if AsyncOpenAI is None:
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.key,
                provider_model=model,
                message="openai package required; install or upgrade it to a version with AsyncOpenAI Responses API support.",
            )
        try:
            async with AsyncOpenAI(api_key=api_key_str) as client:
                response = await client.responses.create(
                    **payload,
                    **kwargs,
                )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - OpenAI SDK exception classes vary by installed version.
            raise self._provider_error_from_exception(exc, provider_model=model) from exc

        text = self._extract_message_text(response)
        response_error = self._response_error(
            response,
            text=text,
            provider_model=model,
            expect_json=bool((request is not None and request.json_output) or isinstance(json_schema, dict)),
        )
        if response_error is not None:
            raise response_error

        return {
            "text": text,
            "provider": self.key,
            "model": model,
            "metadata": {
                "usage": self._extract_usage(response),
            },
        }

    async def validate_connection(self, model: str | None = None, **kwargs: Any) -> tuple[bool, str]:
        try:
            api_key_str = self._api_key_string()
        except ProviderError as exc:
            return False, str(exc)

        try:
            AsyncOpenAI = self._modern_async_client()
            if AsyncOpenAI is None:
                return False, "openai package required; install or upgrade it to a version with AsyncOpenAI support."
            async with AsyncOpenAI(api_key=api_key_str) as client:
                await client.models.list()
        except Exception as exc:
            return False, f"Validation failed: {exc}"

        return True, "OpenAI API key is valid and the service is reachable."

