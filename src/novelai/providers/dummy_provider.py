from __future__ import annotations

from typing import Any, Mapping, Optional

from novelai.providers.base import TranslationProvider


class DummyProvider(TranslationProvider):
    """A no-op provider for offline development and testing."""

    @property
    def key(self) -> str:
        return "dummy"

    def available_models(self) -> list[str]:
        return ["dummy"]

    async def translate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        # A very small transformation so it's obvious translation occurred.
        return {
            "text": prompt.replace("\n", " ").strip(),
            "provider": self.key,
            "model": model or "dummy",
            "metadata": {"note": "dummy provider (echo)"},
        }

    async def validate_connection(self, model: Optional[str] = None, **kwargs: Any) -> tuple[bool, str]:
        return True, "Dummy provider does not require an API key."


