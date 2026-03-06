from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Protocol


class TranslationProvider(ABC):
    """Base interface for translation model providers."""

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique provider key used in configuration."""

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
