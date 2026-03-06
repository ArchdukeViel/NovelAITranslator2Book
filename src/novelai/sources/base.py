from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class SourceAdapter(ABC):
    """Base interface for a novel source / scraper adapter."""

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique key used to identify this source."""

    @abstractmethod
    async def fetch_metadata(self, url: str) -> dict[str, Any]:
        """Fetch novel metadata (title/author, chapter list, etc.)."""

    @abstractmethod
    async def fetch_chapter(self, url: str) -> str:
        """Fetch raw chapter text from the source."""


class SourceFactory(Protocol):
    """Factory signature for source adapter registrations."""

    def __call__(self, settings: Any) -> SourceAdapter:
        ...
