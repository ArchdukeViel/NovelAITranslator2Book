from __future__ import annotations

from typing import Any, Mapping, Optional

from novelai.config.settings import settings
from novelai.core.errors import ProviderError
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
                "OpenAI API key not configured. Set PROVIDER_OPENAI_API_KEY environment variable."
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
    def _build_payload(
        prompt: str,
        model: str,
        *,
        request: TranslationRequest | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        if request is not None:
            return build_translation_responses_payload(
                model,
                request,
                max_output_tokens=max_output_tokens,
            )
        return build_basic_responses_payload(
            model,
            prompt,
            system_prompt="You are a translation assistant.",
            max_output_tokens=max_output_tokens,
        )

    async def translate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """Translate by calling OpenAI chat endpoint.
        
        Thread-safe: Uses per-request client instance, not global state.
        """
        api_key_str = self._api_key_string()
        model = model or "gpt-5.4"
        request = kwargs.pop("request", None)
        if request is not None and not isinstance(request, TranslationRequest):
            raise TypeError("request must be a TranslationRequest instance.")
        payload = self._build_payload(
            prompt,
            model,
            request=request,
            max_output_tokens=max_tokens,
        )

        AsyncOpenAI = self._modern_async_client()
        if AsyncOpenAI is None:
            raise ProviderError(
                "openai package required; install or upgrade it to a version with AsyncOpenAI Responses API support."
            )
        async with AsyncOpenAI(api_key=api_key_str) as client:
            response = await client.responses.create(
                **payload,
                **kwargs,
            )

        return {
            "text": self._extract_message_text(response),
            "provider": self.key,
            "model": model,
            "metadata": {
                "usage": self._extract_usage(response),
            },
        }

    async def validate_connection(self, model: Optional[str] = None, **kwargs: Any) -> tuple[bool, str]:
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


