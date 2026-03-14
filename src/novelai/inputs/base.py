from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from novelai.inputs.models import ImportedAsset, ImportedDocument, ImportedUnit


class DocumentAdapter(ABC):
    @property
    @abstractmethod
    def key(self) -> str:
        """Unique adapter key."""

    @abstractmethod
    def probe(self, source: str | Path) -> bool:
        """Return True when this adapter can import *source*."""

    @abstractmethod
    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        """Import the provided source into a normalized document model."""

    def list_units(self, document: ImportedDocument) -> list[ImportedUnit]:
        return list(document.units)

    def load_unit(self, document: ImportedDocument, unit_id: str) -> ImportedUnit:
        for unit in document.units:
            if unit.unit_id == unit_id:
                return unit
        raise KeyError(f"Unknown unit id: {unit_id}")

    async def load_assets(self, document: ImportedDocument, unit: ImportedUnit) -> list[ImportedAsset]:
        return list(unit.images)
