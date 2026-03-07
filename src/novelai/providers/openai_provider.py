from __future__ import annotations

from typing import Any, Mapping, Optional

from novelai.config.settings import settings
from novelai.core.errors import ProviderError
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
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-3.5-turbo",
        ]

    def _api_key_string(self) -> str:
        api_key = settings.PROVIDER_OPENAI_API_KEY
        if not api_key:
            raise ProviderError(
                "OpenAI API key not configured. Set PROVIDER_OPENAI_API_KEY environment variable."
            )
        return api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)

    @staticmethod
    def _legacy_openai_module() -> Any:
        import openai

        return openai

    @staticmethod
    def _modern_async_client() -> Any | None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return None
        return AsyncOpenAI

    @staticmethod
    def _extract_message_text(response: Any) -> str:
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
            return {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

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
        model = model or "gpt-4o-mini"
        messages = [
            {"role": "system", "content": "You are a translation assistant."},
            {"role": "user", "content": prompt},
        ]

        AsyncOpenAI = self._modern_async_client()
        if AsyncOpenAI is not None:
            async with AsyncOpenAI(api_key=api_key_str) as client:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    **kwargs,
                )
        else:
            try:
                openai = self._legacy_openai_module()
            except ImportError as e:
                raise ProviderError(
                    "openai package required; install or upgrade it to a version with async support."
                ) from e
            response = await openai.ChatCompletion.acreate(
                api_key=api_key_str,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
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
            if AsyncOpenAI is not None:
                async with AsyncOpenAI(api_key=api_key_str) as client:
                    await client.models.list()
            else:
                openai = self._legacy_openai_module()
                await openai.Model.alist(api_key=api_key_str)
        except Exception as exc:
            return False, f"Validation failed: {exc}"

        return True, "OpenAI API key is valid and the service is reachable."


