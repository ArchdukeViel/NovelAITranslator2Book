from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ImportedAsset:
    source_ref: str | None = None
    content: bytes | None = None
    content_type: str | None = None
    placeholder: str | None = None
    alt: str | None = None
    title: str | None = None
    ocr_text: str | None = None
    region_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ImportedUnit:
    unit_id: str
    import_order: int
    text: str
    title: str | None = None
    source_ref: str | None = None
    unit_type: str = "chapter"
    images: tuple[ImportedAsset, ...] = ()
    ocr_required: bool = False
    ocr_artifacts: tuple[dict[str, Any], ...] = ()
    region_metadata: tuple[dict[str, Any], ...] = ()
    context_group_id: str | None = None


@dataclass(frozen=True)
class ImportedDocument:
    adapter_key: str
    origin_type: str
    origin_uri_or_path: str
    document_type: str
    title: str
    author: str | None = None
    source_language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    units: tuple[ImportedUnit, ...] = ()

