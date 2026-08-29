from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib
import json
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider
from novelai.services.gemini_request_control import (
    GeminiQuotaController,
    QuotaRejection,
    QuotaReservation,
    estimate_gemini_tokens,
    get_gemini_quota_controller,
)
from novelai.services.provider_metrics import record_provider_timing
from novelai.services.usage_service import UsageService


class GeminiProvider(TranslationProvider):
    """Google Gemini provider with isolated credentials and reusable clients."""

    DEFAULT_TEXT_MODEL = GEMINI_DEFAULT_MODEL

    def __init__(
        self,
        *,
        api_key: str | None = None,
        usage_service: UsageService | None = None,
        quota_controller: GeminiQuotaController | None = None,
    ) -> None:
        # An explicit key is used only by the contributor credential lease.
        # It is never copied into global preferences or settings.
        self._explicit_api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self._usage_service = usage_service or UsageService()
        self._quota_controller = quota_controller or get_gemini_quota_controller()
        self._client: Any | None = None
        self._client_lock = threading.Lock()

    @property
    def key(self) -> str:
        return "gemini"

    def available_models(self) -> list[str]:
        return [GEMINI_DEFAULT_MODEL]

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _int_usage(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _validate_model_name(model_name: str) -> None:
        if model_name != GEMINI_DEFAULT_MODEL:
            raise ProviderError(
                ProviderErrorCode.CONFIGURATION,
                provider_key="gemini",
                provider_model=model_name,
                message=f"Gemini production model must be {GEMINI_DEFAULT_MODEL}.",
                details={"expected_model": GEMINI_DEFAULT_MODEL},
            )

    def _api_key_string(self) -> str:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        api_key = settings.PROVIDER_GEMINI_API_KEY
        if not api_key:
            raise ProviderError(
                ProviderErrorCode.CONFIGURATION,
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

    def _get_client(self, client_type: Any, api_key: str) -> Any:
        """Create one client per provider instance without sharing credential state."""
        with self._client_lock:
            if self._client is None:
                self._client = client_type(api_key=api_key)
            return self._client

    @staticmethod
    def _normalize_response_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
        """Remove JSON Schema fields unsupported by Gemini's response schema."""

        def normalize(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: normalize(child) for key, child in value.items() if key != "additionalProperties"}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        normalized = normalize(dict(schema))
        if not isinstance(normalized, dict):
            raise TypeError("Gemini response schema must be a mapping.")
        return normalized

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
        for name in (
            "code",
            "status",
            "reason",
            "message",
            "details",
            "metadata",
            "error",
            "retry_delay",
            "retryDelay",
        ):
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
        safe_status_values = [
            getattr(exc, "status_code", None),
            getattr(exc, "code", None),
            getattr(exc, "status", None),
            cls._field(exc, "response", "status_code"),
            cls._field(exc, "response", "status"),
            cls._field(exc, "error", "status"),
            cls._field(exc, "error", "code"),
        ]
        details = {
            "provider_status": cls._safe_string(
                " ".join(str(value) for value in safe_status_values if value is not None)
            ),
            "error_type": exc.__class__.__name__,
        }

        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in combined or "deadline" in combined:
            return ProviderErrorCode.TIMEOUT, retry_after, details
        if "safety" in combined or "blocked" in combined or "prohibited_content" in combined:
            return ProviderErrorCode.SAFETY_BLOCKED, retry_after, details
        status_codes = [
            getattr(exc, "status_code", None),
            cls._field(exc, "response", "status_code"),
            cls._field(exc, "response", "status"),
        ]
        if any(isinstance(value, int) and value >= 500 for value in status_codes) or any(
            marker in combined for marker in ("internal server error", "temporarily unavailable", "service unavailable")
        ):
            return ProviderErrorCode.TEMPORARY, retry_after, details
        if "deprecated" in combined:
            return ProviderErrorCode.MODEL_DEPRECATED, retry_after, details
        if any(
            marker in combined for marker in ("not found", "unsupported model", "model is not supported", "unavailable")
        ):
            return ProviderErrorCode.MODEL_UNAVAILABLE, retry_after, details
        if "429" in combined or "resource_exhausted" in combined or "rate limit" in combined or "quota" in combined:
            quota_markers = ("daily", "per day", "quota exceeded", "quota exhausted", "billing", "free tier")
            rate_markers = (
                "rpm",
                "per minute",
                "rate limit",
                "retrydelay",
                "retry delay",
                "too many requests",
            )
            if any(marker in combined for marker in quota_markers) and not any(
                marker in combined for marker in rate_markers
            ):
                return ProviderErrorCode.QUOTA_EXHAUSTED, retry_after, details
            return ProviderErrorCode.RATE_LIMITED, retry_after, details
        if any(
            marker in combined
            for marker in (
                "context",
                "context window",
                "context length",
                "input token",
                "maximum number of tokens",
                "max output",
                "maximum output",
                "too many tokens",
                "too large",
                "token limit",
            )
        ):
            return ProviderErrorCode.CONTEXT_TOO_LARGE, retry_after, details
        return ProviderErrorCode.UNKNOWN, retry_after, details

    def _provider_error_from_exception(self, exc: BaseException, *, model_name: str) -> ProviderError:
        code, retry_after, details = self._classify_exception(exc)
        cooldown_until = (
            self._utc_after_seconds(retry_after)
            if code
            in {
                ProviderErrorCode.RATE_LIMITED,
                ProviderErrorCode.TEMPORARY,
                ProviderErrorCode.TIMEOUT,
            }
            else None
        )
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
            ProviderErrorCode.CONFIGURATION: "Provider configuration is invalid",
            ProviderErrorCode.RATE_LIMITED: "Provider rate limit reached",
            ProviderErrorCode.QUOTA_EXHAUSTED: "Provider quota exhausted",
            ProviderErrorCode.MODEL_UNAVAILABLE: "Provider model unavailable",
            ProviderErrorCode.MODEL_DEPRECATED: "Provider model deprecated",
            ProviderErrorCode.CONTEXT_TOO_LARGE: "Provider context window exceeded",
            ProviderErrorCode.SAFETY_BLOCKED: "Provider safety filter blocked the response",
            ProviderErrorCode.TIMEOUT: "Provider request timed out",
            ProviderErrorCode.TEMPORARY: "Provider temporary failure",
            ProviderErrorCode.INVALID_JSON: "Provider returned invalid JSON",
            ProviderErrorCode.EMPTY_OUTPUT: "Provider returned empty output",
            ProviderErrorCode.PARTIAL_OUTPUT: "Provider returned partial output",
            ProviderErrorCode.UNKNOWN: "Provider request failed",
        }
        return messages[code]

    def _record_request(
        self,
        *,
        purpose: str,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        reservation: QuotaReservation | None,
        usage: Mapping[str, Any] | None,
        success: bool,
        retry_attempt: int,
        chapter_id: Any = None,
        chunk_id: Any = None,
        cache_status: Any = None,
        error: ProviderError | None = None,
        request_made: bool = True,
        provider_wait_ms: float | None = None,
        provider_execution_ms: float | None = None,
        quota_reservation_ms: float | None = None,
    ) -> None:
        input_tokens = self._int_usage(usage.get("input_tokens")) if isinstance(usage, Mapping) else None
        if input_tokens is None and isinstance(usage, Mapping):
            input_tokens = self._int_usage(usage.get("prompt_tokens"))
        output_tokens = self._int_usage(usage.get("output_tokens")) if isinstance(usage, Mapping) else None
        if output_tokens is None and isinstance(usage, Mapping):
            output_tokens = self._int_usage(usage.get("completion_tokens"))
        total_tokens = self._int_usage(usage.get("total_tokens")) if isinstance(usage, Mapping) else None
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        if reservation is not None:
            with contextlib.suppress(Exception):
                self._quota_controller.reconcile(
                    reservation,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    success=success,
                )
        usage_write_ms: float | None = None
        with contextlib.suppress(Exception):
            usage_write_ms = self._usage_service.record_provider_request(
                timestamp=self._utc_now_iso(),
                provider_key=self.key,
                provider_model=model_name,
                purpose=purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                success=success,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error_code=error.provider_error_code.value if error is not None else None,
                request_made=request_made,
                provider_wait_ms=provider_wait_ms,
                provider_execution_ms=provider_execution_ms,
                quota_reservation_ms=quota_reservation_ms,
                usage_write_ms=None,
            )
        record_provider_timing(
            wait_ms=provider_wait_ms,
            execution_ms=provider_execution_ms,
            quota_reservation_ms=quota_reservation_ms,
            usage_write_ms=usage_write_ms,
            retry_attempt=retry_attempt,
            success=success,
        )

    def _reserve_request(
        self,
        *,
        purpose: str,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> QuotaReservation:
        try:
            decision = self._quota_controller.reserve(
                purpose=purpose,
                model=model_name,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
            )
        except TimeoutError as exc:
            raise ProviderError(
                ProviderErrorCode.TEMPORARY,
                provider_key=self.key,
                provider_model=model_name,
                message=self._public_message_for_code(ProviderErrorCode.TEMPORARY),
                retry_after_seconds=5,
                cooldown_until=self._utc_after_seconds(5),
                details={"quota_deferred": True, "quota_control": "lock_timeout"},
            ) from exc
        if isinstance(decision, QuotaRejection):
            code = (
                ProviderErrorCode.QUOTA_EXHAUSTED
                if decision.code == "quota_exhausted"
                else ProviderErrorCode.RATE_LIMITED
            )
            raise ProviderError(
                code,
                provider_key=self.key,
                provider_model=model_name,
                message=self._public_message_for_code(code),
                retry_after_seconds=decision.retry_after_seconds,
                cooldown_until=self._utc_after_seconds(decision.retry_after_seconds),
                exhausted_until=self._utc_after_seconds(decision.retry_after_seconds)
                if code == ProviderErrorCode.QUOTA_EXHAUSTED
                else None,
                details={
                    "quota_deferred": True,
                    "quota_dimension": decision.dimension,
                    "requests_this_minute": decision.current_requests_this_minute,
                    "tokens_this_minute": decision.current_tokens_this_minute,
                    "requests_today": decision.current_requests_today,
                    "estimated_input_tokens": decision.estimated_input_tokens,
                    "estimated_output_tokens": decision.estimated_output_tokens,
                },
                requests_this_minute=decision.current_requests_this_minute,
                requests_today=decision.current_requests_today,
            )
        return decision

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
        model_name = model or self.DEFAULT_TEXT_MODEL
        purpose = str(kwargs.pop("request_purpose", "body_translation"))
        chapter_id = kwargs.pop("chapter_id", None)
        chunk_id = kwargs.pop("chunk_id", None)
        cache_status = kwargs.pop("cache_status", None)
        retry_attempt_value = kwargs.pop("retry_attempt", 0)
        retry_attempt = int(retry_attempt_value) if isinstance(retry_attempt_value, (int, float)) else 0
        request_id = kwargs.pop("request_id", None)
        request = kwargs.pop("request", None)
        json_schema = kwargs.pop("json_schema", None)
        if isinstance(json_schema, Mapping):
            json_schema = self._normalize_response_schema(json_schema)
        expect_json = bool(kwargs.pop("expect_json", False))
        if request is not None and not isinstance(request, TranslationRequest):
            raise TypeError("request must be a TranslationRequest instance.")

        try:
            self._validate_model_name(model_name)
        except ProviderError as exc:
            input_estimate, output_estimate = estimate_gemini_tokens(prompt, max_output_tokens=max_tokens)
            self._record_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=None,
                usage=None,
                success=False,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error=exc,
                request_made=False,
            )
            raise

        contents = request.user_prompt if isinstance(request, TranslationRequest) else prompt
        system_prompt = request.system_prompt if isinstance(request, TranslationRequest) else ""
        input_estimate, output_estimate = estimate_gemini_tokens(
            system_prompt,
            contents,
            json.dumps(json_schema, ensure_ascii=False) if isinstance(json_schema, dict) else "",
            max_output_tokens=max_tokens,
        )
        reservation: QuotaReservation | None = None
        quota_reservation_ms: float | None = None
        quota_started = time.perf_counter()
        try:
            api_key_str = self._api_key_string()
            reservation = self._reserve_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
            )
            quota_reservation_ms = (time.perf_counter() - quota_started) * 1000
        except ProviderError as exc:
            quota_reservation_ms = (time.perf_counter() - quota_started) * 1000
            self._record_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=None,
                usage=None,
                success=False,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error=exc,
                request_made=reservation is not None,
                provider_wait_ms=quota_reservation_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
            raise

        Client = self._modern_client()
        if Client is None:
            error = ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.key,
                provider_model=model_name,
                message="google-genai package required; install it to enable Gemini provider support.",
            )
            self._record_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=reservation,
                usage=None,
                success=False,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error=error,
                request_made=False,
                provider_wait_ms=quota_reservation_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
            raise error

        temperature = kwargs.pop("temperature", 0.0)
        config_payload: dict[str, Any] = {
            "temperature": float(temperature) if isinstance(temperature, (int, float)) else 0.0
        }
        if request is not None and request.system_prompt:
            config_payload["system_instruction"] = request.system_prompt
        if max_tokens is not None:
            config_payload["max_output_tokens"] = max_tokens
        if expect_json or (request is not None and request.json_output):
            config_payload["response_mime_type"] = "application/json"
        if isinstance(json_schema, dict):
            config_payload["response_mime_type"] = "application/json"
            config_payload["response_schema"] = json_schema

        audit_config = dict(config_payload)
        system_instruction = audit_config.pop("system_instruction", None)
        if isinstance(system_instruction, str):
            audit_config["system_instruction_chars"] = len(system_instruction)
            audit_config["system_instruction_sha256"] = hashlib.sha256(system_instruction.encode("utf-8")).hexdigest()

        def _invoke() -> Any:
            client = self._get_client(Client, api_key_str)
            generate_kwargs: dict[str, Any] = {
                "model": model_name,
                "contents": contents,
            }
            if config_payload:
                generate_kwargs["config"] = config_payload
            return client.models.generate_content(**generate_kwargs)

        execution_started = time.perf_counter()
        execution_ms: float | None = None
        try:
            response = await asyncio.to_thread(_invoke)
            execution_ms = (time.perf_counter() - execution_started) * 1000
        except ProviderError as exc:
            execution_ms = (time.perf_counter() - execution_started) * 1000
            self._record_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=reservation,
                usage=None,
                success=False,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error=exc,
                request_made=True,
                provider_wait_ms=quota_reservation_ms,
                provider_execution_ms=execution_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
            raise
        except Exception as exc:
            execution_ms = (time.perf_counter() - execution_started) * 1000
            error = self._provider_error_from_exception(exc, model_name=model_name)
            self._record_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=reservation,
                usage=None,
                success=False,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error=error,
                request_made=True,
                provider_wait_ms=quota_reservation_ms,
                provider_execution_ms=execution_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
            raise error from exc
        text = self._extract_text(response)
        usage = self._extract_usage(response)
        response_error = self._response_error(
            response,
            text=text,
            model_name=model_name,
            expect_json=bool(
                expect_json or (request is not None and request.json_output) or isinstance(json_schema, dict)
            ),
        )
        if response_error is not None:
            self._record_request(
                purpose=purpose,
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=reservation,
                usage=usage,
                success=False,
                retry_attempt=retry_attempt,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                cache_status=cache_status,
                error=response_error,
                request_made=True,
                provider_wait_ms=quota_reservation_ms,
                provider_execution_ms=execution_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
            raise response_error
        self._record_request(
            purpose=purpose,
            model_name=model_name,
            estimated_input_tokens=input_estimate,
            estimated_output_tokens=output_estimate,
            reservation=reservation,
            usage=usage,
            success=True,
            retry_attempt=retry_attempt,
            chapter_id=chapter_id,
            chunk_id=chunk_id,
            cache_status=cache_status,
            provider_wait_ms=quota_reservation_ms,
            provider_execution_ms=execution_ms,
            quota_reservation_ms=quota_reservation_ms,
        )
        return {
            "text": text,
            "provider": self.key,
            "model": model_name,
            "metadata": {
                "usage": usage,
                "usage_accounting_recorded": True,
                "request_id": request_id,
                "request_purpose": purpose,
                "request_config": {
                    "sdk": "google.genai.Client.models.generate_content",
                    "model": model_name,
                    "config": audit_config,
                },
            },
        }

    async def validate_connection(self, model: str | None = None, **kwargs: Any) -> tuple[bool, str]:
        model_name = model or self.DEFAULT_TEXT_MODEL
        input_estimate, output_estimate = estimate_gemini_tokens("ping", max_output_tokens=32)
        reservation: QuotaReservation | None = None
        quota_reservation_ms: float | None = None
        execution_ms: float | None = None
        try:
            self._validate_model_name(model_name)
            api_key_str = self._api_key_string()
            Client = self._modern_client()
            if Client is None:
                raise ProviderError(
                    ProviderErrorCode.UNKNOWN,
                    provider_key=self.key,
                    provider_model=model_name,
                    message="google-genai package required; install it to enable Gemini provider support.",
                )
            quota_started = time.perf_counter()
            reservation = self._reserve_request(
                purpose="provider_validation",
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
            )
            quota_reservation_ms = (time.perf_counter() - quota_started) * 1000

            def _invoke() -> Any:
                client = self._get_client(Client, api_key_str)
                return client.models.generate_content(
                    model=model_name,
                    contents="ping",
                    config={"temperature": 0.0, "max_output_tokens": 32},
                )

            execution_started = time.perf_counter()
            response = await asyncio.to_thread(_invoke)
            execution_ms = (time.perf_counter() - execution_started) * 1000
            response_error = self._response_error(
                response,
                text=self._extract_text(response),
                model_name=model_name,
                expect_json=False,
            )
            if response_error is not None:
                raise response_error
            self._record_request(
                purpose="provider_validation",
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=reservation,
                usage=self._extract_usage(response),
                success=True,
                retry_attempt=0,
                request_made=True,
                provider_wait_ms=quota_reservation_ms,
                provider_execution_ms=execution_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, ProviderError)
                else self._provider_error_from_exception(exc, model_name=model_name)
            )
            self._record_request(
                purpose="provider_validation",
                model_name=model_name,
                estimated_input_tokens=input_estimate,
                estimated_output_tokens=output_estimate,
                reservation=reservation,
                usage=None,
                success=False,
                retry_attempt=0,
                error=error,
                request_made=reservation is not None,
                provider_wait_ms=quota_reservation_ms,
                provider_execution_ms=execution_ms,
                quota_reservation_ms=quota_reservation_ms,
            )
            return False, error.message

        return True, "Gemini API key is valid and the service is reachable."
