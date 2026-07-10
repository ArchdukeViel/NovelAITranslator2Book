"""Shared helpers for OperationsService.

Extracted from operations.py to keep the service class focused on orchestration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from novelai.storage.service import StorageService

# Novel-level concurrency guard — prevents concurrent translation runs per novel
_novel_translation_locks: dict[str, asyncio.Lock] = {}


def get_novel_translation_lock(novel_id: str) -> asyncio.Lock:
    if novel_id not in _novel_translation_locks:
        _novel_translation_locks[novel_id] = asyncio.Lock()
    return _novel_translation_locks[novel_id]


@dataclass(frozen=True)
class ExportOperationResult:
    path: str
    media_type: str
    filename: str


class OperationError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def require_novel_meta(storage: StorageService, novel_id: str, *, error_detail: Any = None) -> dict[str, Any]:
    """Load novel metadata or raise OperationError(404).

    Returns the metadata dict on success.
    """
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise OperationError(404, error_detail or {"error": "Novel not found", "novel_id": novel_id})
    return meta
