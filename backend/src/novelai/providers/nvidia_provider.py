from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from novelai.config.settings import NVIDIA_DEFAULT_MODEL, settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider


class NVIDIAProvider(TranslationProvider):
    """NVIDIA NIM provider using OpenAI-compatible chat completions over httpx."""

    DEFAULT_TEXT_MODEL = NVIDIA_DEFAULT_MODEL

    @property
    def key(self) -> str:
        return "nvidia"

    def available_models(self) -> list[str]:
        return [settings.NVIDIA_DEFAULT_MODEL or self.DEFAULT_TEXT_MODEL]

    def _api_key_string(self) -> str:
        api_key = settings.NVIDIA_API_KEY
        if not api_key:
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.key,
                provider_model=settings.NVIDIA_DEFAULT_MODEL or self.DEFAULT_TEXT_MODEL,
                message="NVIDIA API key not configured. Set NVIDIA_API_KEY environment variable.",
            )
        return api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)

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

    @staticmethod
    def _field(value: Any, *names: str) -> Any:
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
    def _error_payload(cls, exc: BaseException) -> Mapping[str, Any] | None:
        response = cls._field(exc, "response")
        if response is None:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        return payload if isinstance(payload, Mapping) else None

    @classmethod
    def _structured_status(cls, exc: BaseException) -> str:
        payload = cls._error_payload(exc)
        values = [
            getattr(exc, "status_code", None),
            getattr(exc, "code", None),
            cls._field(exc, "response", "status_code"),
            cls._field(payload, "error", "code"),
            cls._field(payload, "error", "type"),
            cls._field(payload, "error", "message"),
        ]
        return " ".join(str(value) for value in values if value is not None)

    @classmethod
    def _extract_retry_after_seconds(cls, exc: BaseException) -> int | None:
        headers = cls._field(exc, "response", "headers")
        candidates = [
            getattr(exc, "retry_after", None),
            getattr(exc, "retry_after_seconds", None),
        ]
        if isinstance(headers, Mapping):
            candidates.extend([headers.get("retry-after"), headers.get("Retry-After")])
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

        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)) or "timeout" in combined:
            return ProviderErrorCode.TIMEOUT, retry_after, details
        if "safety" in combined or "blocked" in combined or "content filter" in combined:
            return ProviderErrorCode.SAFETY_BLOCKED, retry_after, details
        if "deprecated" in combined:
            return ProviderErrorCode.MODEL_DEPRECATED, retry_after, details
        if any(marker in combined for marker in ("not found", "unsupported model", "model is not supported", "unavailable")):
            return ProviderErrorCode.MODEL_UNAVAILABLE, retry_after, details
        if any(marker in combined for marker in ("context length", "context window", "too many tokens", "maximum context")):
            return ProviderErrorCode.CONTEXT_TOO_LARGE, retry_after, details
        if "429" in combined or "rate limit" in combined or "rate_limit" in combined or "quota" in combined:
            quota_markers = ("quota exceeded", "quota exhausted", "daily", "per day", "billing", "insufficient_quota")
            if any(marker in combined for marker in quota_markers):
                return ProviderErrorCode.QUOTA_EXHAUSTED, retry_after, details
            return ProviderErrorCode.RATE_LIMITED, retry_after, details
        return ProviderErrorCode.UNKNOWN, retry_after, details

    def _provider_error(self, exc: BaseException, *, model: str) -> ProviderError:
        code, retry_after, details = self._classify_exception(exc)
        cooldown_until = self._utc_after_seconds(retry_after) if code == ProviderErrorCode.RATE_LIMITED else None
        exhausted_until = self._utc_after_seconds(24 * 60 * 60) if code == ProviderErrorCode.QUOTA_EXHAUSTED else None
        return ProviderError(
            code,
            provider_key=self.key,
            provider_model=model,
            message=self._public_message_for_code(code),
            retry_after_seconds=retry_after,
            cooldown_until=cooldown_until,
            exhausted_until=exhausted_until,
            details=details,
        )

    @staticmethod
    def _public_message_for_code(code: ProviderErrorCode) -> str:
        return {
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
        }[code]

    @staticmethod
    def _extract_text(payload: Mapping[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, Mapping):
            return ""
        message = first.get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                fragments: list[str] = []
                for item in content:
                    if isinstance(item, str):
                        fragments.append(item)
                    elif isinstance(item, Mapping) and isinstance(item.get("text"), str):
                        fragments.append(str(item["text"]))
                return "".join(fragments).strip()
        text = first.get("text")
        return text.strip() if isinstance(text, str) else ""

    @staticmethod
    def _extract_usage(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
        usage = payload.get("usage")
        if not isinstance(usage, Mapping):
            return None
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": usage.get("total_tokens"),
        }

    @staticmethod
    def _finish_reason(payload: Mapping[str, Any]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            return None
        reason = choices[0].get("finish_reason")
        return reason.strip().lower() if isinstance(reason, str) else None

    def _validate_response(self, payload: Mapping[str, Any], *, model: str, expect_json: bool) -> None:
        finish_reason = self._finish_reason(payload)
        if finish_reason in {"content_filter", "safety"}:
            raise ProviderError(
                ProviderErrorCode.SAFETY_BLOCKED,
                provider_key=self.key,
                provider_model=model,
                message=self._public_message_for_code(ProviderErrorCode.SAFETY_BLOCKED),
            )
        if finish_reason == "length":
            raise ProviderError(
                ProviderErrorCode.PARTIAL_OUTPUT,
                provider_key=self.key,
                provider_model=model,
                message=self._public_message_for_code(ProviderErrorCode.PARTIAL_OUTPUT),
            )

        text = self._extract_text(payload)
        if not text:
            raise ProviderError(
                ProviderErrorCode.EMPTY_OUTPUT,
                provider_key=self.key,
                provider_model=model,
                message=self._public_message_for_code(ProviderErrorCode.EMPTY_OUTPUT),
            )
        if expect_json:
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    ProviderErrorCode.INVALID_JSON,
                    provider_key=self.key,
                    provider_model=model,
                    message=self._public_message_for_code(ProviderErrorCode.INVALID_JSON),
                ) from exc

    @staticmethod
    def _prompt_from_request(prompt: str, request: Any | None) -> str:
        if request is None:
            return prompt
        if not isinstance(request, TranslationRequest):
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key="nvidia",
                provider_model=settings.NVIDIA_DEFAULT_MODEL or NVIDIA_DEFAULT_MODEL,
                message="NVIDIA provider expected a TranslationRequest for request payloads.",
            )
        return request.user_prompt or request.text or prompt

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        model_name = model or settings.NVIDIA_DEFAULT_MODEL or self.DEFAULT_TEXT_MODEL
        api_key = self._api_key_string()
        request = kwargs.get("request")
        prompt_text = self._prompt_from_request(prompt, request)
        expect_json = bool(kwargs.get("json_schema")) or bool(getattr(request, "json_output", False))

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt_text}],
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        temperature = kwargs.get("temperature")
        if isinstance(temperature, (int, float)):
            payload["temperature"] = float(temperature)
        top_p = kwargs.get("top_p")
        if isinstance(top_p, (int, float)):
            payload["top_p"] = float(top_p)
        chat_template_kwargs = kwargs.get("chat_template_kwargs")
        if isinstance(chat_template_kwargs, Mapping):
            payload["chat_template_kwargs"] = dict(chat_template_kwargs)
        if expect_json:
            payload["response_format"] = {"type": "json_object"}

        base_url = str(settings.NVIDIA_BASE_URL or "").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.NVIDIA_TIMEOUT_SECONDS) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                raw_payload = response.json()
        except ProviderError:
            raise
        except Exception as exc:
            raise self._provider_error(exc, model=model_name) from exc

        if not isinstance(raw_payload, Mapping):
            raise ProviderError(
                ProviderErrorCode.EMPTY_OUTPUT,
                provider_key=self.key,
                provider_model=model_name,
                message=self._public_message_for_code(ProviderErrorCode.EMPTY_OUTPUT),
            )

        self._validate_response(raw_payload, model=model_name, expect_json=expect_json)
        return {
            "text": self._extract_text(raw_payload),
            "metadata": {
                "provider": self.key,
                "model": model_name,
                "usage": self._extract_usage(raw_payload),
            },
        }

    async def validate_connection(self, model: str | None = None, **kwargs: Any) -> tuple[bool, str]:
        model_name = model or settings.NVIDIA_DEFAULT_MODEL or self.DEFAULT_TEXT_MODEL
        try:
            result = await self.translate("ping", model=model_name, max_tokens=8)
        except ProviderError as exc:
            return False, exc.message
        except Exception as exc:
            return False, str(exc)
        return bool(str(result.get("text", "")).strip()), f"NVIDIA model {model_name} is reachable."
