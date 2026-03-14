from __future__ import annotations

import asyncio
import importlib
from collections.abc import Mapping
from typing import Any

from novelai.config.settings import settings
from novelai.core.errors import ProviderError
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider


class GeminiProvider(TranslationProvider):
    """Google Gemini translation provider using a per-request client instance."""

    @property
    def key(self) -> str:
        return "gemini"

    def available_models(self) -> list[str]:
        return [
            "gemini-3-flash-preview",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite-preview",
        ]

    def _api_key_string(self) -> str:
        api_key = settings.PROVIDER_GEMINI_API_KEY
        if not api_key:
            raise ProviderError(
                "Gemini API key not configured. Set PROVIDER_GEMINI_API_KEY environment variable."
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

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        api_key_str = self._api_key_string()
        model_name = model or "gemini-3-flash-preview"
        request = kwargs.pop("request", None)
        json_schema = kwargs.pop("json_schema", None)
        if request is not None and not isinstance(request, TranslationRequest):
            raise TypeError("request must be a TranslationRequest instance.")

        Client = self._modern_client()
        if Client is None:
            raise ProviderError(
                "google-genai package required; install it to enable Gemini provider support."
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

        response = await asyncio.to_thread(_invoke)
        return {
            "text": self._extract_text(response),
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

        model_name = model or "gemini-3-flash-preview"

        def _invoke() -> None:
            client = Client(api_key=api_key_str)
            client.models.generate_content(model=model_name, contents="ping")

        try:
            await asyncio.to_thread(_invoke)
        except Exception as exc:  # noqa: BLE001
            return False, f"Validation failed: {exc}"

        return True, "Gemini API key is valid and the service is reachable."
