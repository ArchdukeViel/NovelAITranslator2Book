from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from novelai.storage.models import Novel, Chapter


class StorageRepository(ABC):
    """Abstract repository for storing and retrieving novels."""

    @abstractmethod
    def list_novels(self) -> Iterable[Novel]:
        ...

    @abstractmethod
    def get_novel(self, novel_id: str) -> Novel | None:
        ...

    @abstractmethod
    def save_novel(self, novel: Novel) -> None:
        ...

    @abstractmethod
    def save_chapter(self, novel_id: str, chapter: Chapter) -> None:
        ...
