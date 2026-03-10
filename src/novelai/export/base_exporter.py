from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class BaseExporter(ABC):
    """Base exporter interface."""

    @abstractmethod
    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str, **options: Any) -> str:
        """Export chapters to a file and return the output path."""
