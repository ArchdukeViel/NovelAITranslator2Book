from __future__ import annotations

import asyncio
import importlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider


class GeminiProvider(TranslationProvider):
    """Google Gemini translation provider using a per-request client instance."""

    DEFAULT_TEXT_MODEL = "gemini-2.5-flash"

    @property
    def key(self) -> str:
        return "gemini"

    def available_models(self) -> list[str]:
        return [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3-pro-preview",
            "gemini-3.1-flash-preview",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-flash-latest",
            "gemini-pro-latest",
            "gemini-2.0-flash",
        ]

    def _api_key_string(self) -> str:
        api_key = settings.PROVIDER_GEMINI_API_KEY
        if not api_key:
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.key,
                provider_model=self.DEFAULT_TEXT_MODEL,
                message="Gemini API key not configured. Set PROVIDER_GEMINI_API_KEY environment variable.",
            )
        return api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)

    @staticmethod
    def _modern_client() -> Any | None:
        try:
            genai_module = importlib.import_module("google.genai")
        except ImportError:
            return None
        return getattr(genai_module, "Client", None)

    @staticmethod
    def _extract_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, list):
            fragments: list[str] = []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None)
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    part_text = getattr(part, "text", None)
                    if isinstance(part_text, str):
                        fragments.append(part_text)
            if fragments:
                return "".join(fragments).strip()

        return ""

    @staticmethod
    def _extract_usage(response: Any) -> Mapping[str, Any] | None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return None

        input_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": total_tokens,
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
        for name in ("code", "status", "reason", "message", "details", "metadata", "error", "retry_delay", "retryDelay"):
            item = getattr(value, name, None)
            if item is not None:
                values.extend(cls._walk_values(item, depth=depth + 1))
        return values

    @classmethod
    def _extract_retry_after_seconds(cls, exc: BaseException) -> int | None:
        def _retry_delay_values(value: Any, *, depth: int = 0) -> list[Any]:
            if depth > 4 or value is None:
                return []
            if isinstance(value, Mapping):
                found: list[Any] = []
                for key, item in value.items():
                    if str(key) in {"retryDelay", "retry_delay", "retryAfter", "retry_after"}:
                        found.append(item)
                    found.extend(_retry_delay_values(item, depth=depth + 1))
                return found
            if isinstance(value, (list, tuple, set)):
                found = []
                for item in value:
                    found.extend(_retry_delay_values(item, depth=depth + 1))
                return found
            return []

        candidates = [
            getattr(exc, "retry_after", None),
            getattr(exc, "retry_after_seconds", None),
            cls._field(exc, "response", "headers", "retry-after"),
            cls._field(exc, "response", "headers", "Retry-After"),
        ]
        candidates.extend(_retry_delay_values(getattr(exc, "details", None)))
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
            getattr(exc, "status", None),
            cls._field(exc, "response", "status_code"),
            cls._field(exc, "response", "status"),
            cls._field(exc, "error", "status"),
            cls._field(exc, "error", "code"),
        ]
        values.extend(cls._walk_values(getattr(exc, "details", None)))
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

        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in combined or "deadline" in combined:
            return ProviderErrorCode.TIMEOUT, retry_after, details
        if "safety" in combined or "blocked" in combined or "prohibited_content" in combined:
            return ProviderErrorCode.SAFETY_BLOCKED, retry_after, details
        if "deprecated" in combined:
            return ProviderErrorCode.MODEL_DEPRECATED, retry_after, details
        if any(marker in combined for marker in ("not found", "unsupported model", "model is not supported", "unavailable")):
            return ProviderErrorCode.MODEL_UNAVAILABLE, retry_after, details
        if any(marker in combined for marker in ("context", "token", "too large", "maximum", "max output")):
            return ProviderErrorCode.CONTEXT_TOO_LARGE, retry_after, details
        if "429" in combined or "resource_exhausted" in combined or "rate limit" in combined or "quota" in combined:
            quota_markers = ("daily", "per day", "quota exceeded", "quota exhausted", "billing", "free tier")
            rate_markers = ("rpm", "per minute", "rate limit", "retrydelay", "retry delay")
            if any(marker in combined for marker in quota_markers) and not any(marker in combined for marker in rate_markers):
                return ProviderErrorCode.QUOTA_EXHAUSTED, retry_after, details
            return ProviderErrorCode.RATE_LIMITED, retry_after, details
        return ProviderErrorCode.UNKNOWN, retry_after, details

    def _provider_error_from_exception(self, exc: BaseException, *, model_name: str) -> ProviderError:
        code, retry_after, details = self._classify_exception(exc)
        cooldown_until = self._utc_after_seconds(retry_after) if code == ProviderErrorCode.RATE_LIMITED else None
        return ProviderError(
            code,
            provider_key=self.key,
            provider_model=model_name,
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
    def _finish_reasons(cls, response: Any) -> list[str]:
        candidates = getattr(response, "candidates", None)
        if not isinstance(candidates, list):
            return []
        reasons: list[str] = []
        for candidate in candidates:
            reason = getattr(candidate, "finish_reason", None)
            if reason is not None:
                reasons.append(str(reason))
        return reasons

    def _response_error(self, response: Any, *, text: str, model_name: str, expect_json: bool) -> ProviderError | None:
        finish_reasons = [reason.upper() for reason in self._finish_reasons(response)]
        details = {"finish_reasons": finish_reasons or None}
        if any(reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"} for reason in finish_reasons):
            return ProviderError(
                ProviderErrorCode.SAFETY_BLOCKED,
                provider_key=self.key,
                provider_model=model_name,
                message=self._public_message_for_code(ProviderErrorCode.SAFETY_BLOCKED),
                details=details,
            )
        if any(reason in {"MAX_TOKENS"} for reason in finish_reasons):
            return ProviderError(
                ProviderErrorCode.PARTIAL_OUTPUT,
                provider_key=self.key,
                provider_model=model_name,
                message=self._public_message_for_code(ProviderErrorCode.PARTIAL_OUTPUT),
                details=details,
            )
        if not text.strip():
            return ProviderError(
                ProviderErrorCode.EMPTY_OUTPUT,
                provider_key=self.key,
                provider_model=model_name,
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
                    provider_model=model_name,
                    message=self._public_message_for_code(ProviderErrorCode.INVALID_JSON),
                    details={**details, "json_error": exc.msg},
                )
        return None

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        api_key_str = self._api_key_string()
        model_name = model or self.DEFAULT_TEXT_MODEL
        request = kwargs.pop("request", None)
        json_schema = kwargs.pop("json_schema", None)
        if request is not None and not isinstance(request, TranslationRequest):
            raise TypeError("request must be a TranslationRequest instance.")

        Client = self._modern_client()
        if Client is None:
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.key,
                provider_model=model_name,
                message="google-genai package required; install it to enable Gemini provider support.",
            )

        def _invoke() -> Any:
            client = Client(api_key=api_key_str)
            config_payload: dict[str, Any] = {}
            if request is not None and request.system_prompt:
                config_payload["system_instruction"] = request.system_prompt
            if max_tokens is not None:
                config_payload["max_output_tokens"] = max_tokens
            if request is not None and request.json_output:
                config_payload["response_mime_type"] = "application/json"
            if isinstance(json_schema, dict):
                config_payload["response_mime_type"] = "application/json"
                config_payload["response_schema"] = json_schema
            temperature = kwargs.pop("temperature", None)
            if isinstance(temperature, (int, float)):
                config_payload["temperature"] = float(temperature)

            contents = request.user_prompt if isinstance(request, TranslationRequest) else prompt
            generate_kwargs: dict[str, Any] = {
                "model": model_name,
                "contents": contents,
            }
            if config_payload:
                generate_kwargs["config"] = config_payload
            return client.models.generate_content(**generate_kwargs)

        try:
            response = await asyncio.to_thread(_invoke)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - SDK exceptions vary by installed google-genai version.
            raise self._provider_error_from_exception(exc, model_name=model_name) from exc
        text = self._extract_text(response)
        response_error = self._response_error(
            response,
            text=text,
            model_name=model_name,
            expect_json=bool((request is not None and request.json_output) or isinstance(json_schema, dict)),
        )
        if response_error is not None:
            raise response_error
        return {
            "text": text,
            "provider": self.key,
            "model": model_name,
            "metadata": {
                "usage": self._extract_usage(response),
            },
        }

    async def validate_connection(self, model: str | None = None, **kwargs: Any) -> tuple[bool, str]:
        try:
            api_key_str = self._api_key_string()
        except ProviderError as exc:
            return False, str(exc)

        Client = self._modern_client()
        if Client is None:
            return False, "google-genai package required; install it to enable Gemini provider support."

        model_name = model or self.DEFAULT_TEXT_MODEL

        def _invoke() -> None:
            client = Client(api_key=api_key_str)
            client.models.generate_content(model=model_name, contents="ping")

        try:
            await asyncio.to_thread(_invoke)
        except Exception as exc:  # noqa: BLE001
            return False, f"Validation failed: {exc}"

        return True, "Gemini API key is valid and the service is reachable."
