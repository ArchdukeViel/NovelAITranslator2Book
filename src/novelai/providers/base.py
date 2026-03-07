from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Protocol


class TranslationProvider(ABC):
    """Base interface for translation model providers."""

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique provider key used in configuration."""

    def available_models(self) -> list[str]:
        """Return user-facing model options for this provider."""
        return []

    async def validate_connection(self, model: str | None = None, **kwargs: Any) -> tuple[bool, str]:
        """Validate provider configuration and connectivity if supported."""
        return True, f"{self.key} is ready."

    @abstractmethod
    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """Translate the given prompt and return structured results.

        Returns a dictionary containing at least a `text` key.
        """


class ProviderFactory(Protocol):
    """Factory signature for provider registrations."""

    def __call__(self, settings: Any) -> TranslationProvider:
        ...
