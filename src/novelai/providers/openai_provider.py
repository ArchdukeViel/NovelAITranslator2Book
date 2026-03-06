from __future__ import annotations

from typing import Any, Mapping, Optional

from novelai.config.settings import settings
from novelai.providers.base import TranslationProvider
from novelai.services.settings_service import SettingsService


class OpenAIProvider(TranslationProvider):
    """Example provider adapter for OpenAI endpoints."""

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
        """Translate by calling OpenAI completion/chat endpoints.

        This is a minimal stub implementation; it is expected to be extended.
        """

        try:
            import openai  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "openai package is required for OpenAIProvider; install it via `pip install openai`"
            ) from e

        api_key = settings.PROVIDER_OPENAI_API_KEY
        if api_key is None:
            # fallback to persisted key in settings service (TUI)
            api_key = SettingsService().get_api_key()

        if not api_key:
            raise RuntimeError("OpenAI API key not configured. Set it in settings or env (PROVIDER_OPENAI_API_KEY).")

        openai.api_key = api_key if isinstance(api_key, str) else api_key.get_secret_value()
        model = model or "gpt-4o-mini"

        response = await openai.ChatCompletion.acreate(
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
            "metadata": {"usage": getattr(response, "usage", None)},
        }


