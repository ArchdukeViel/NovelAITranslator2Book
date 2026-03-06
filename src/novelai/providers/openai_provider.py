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
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ProviderError(
                "openai package required; install: pip install openai>=1.0"
            ) from e

        # Get API key from environment only (secure, no disk persistence)
        api_key = settings.PROVIDER_OPENAI_API_KEY
        if not api_key:
            raise ProviderError(
                "OpenAI API key not configured. Set PROVIDER_OPENAI_API_KEY environment variable."
            )

        # Extract secret value if it's a SecretStr from pydantic
        api_key_str = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)

        model = model or "gpt-4o-mini"

        # Create per-request client instance (thread-safe, no global state)
        async with AsyncOpenAI(api_key=api_key_str) as client:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a translation assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                **kwargs,
            )

            text = response.choices[0].message.content.strip()
            return {
                "text": text,
                "provider": self.key,
                "model": model,
                "metadata": {
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        "total_tokens": response.usage.total_tokens if response.usage else None,
                    } if response.usage else None
                },
            }


