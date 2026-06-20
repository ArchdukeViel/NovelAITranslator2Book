from __future__ import annotations

from typing import Any


PUBLICATION_STATUS_VALUES = {"ongoing", "completed", "hiatus", "unknown"}

_COMPLETED_MARKERS = (
    "completed",
    "complete",
    "finished",
    "ended",
    "完結",
    "完了",
    "連載終了",
    "完結済",
    "完結",
    "完了",
    "連載終了",
)
_HIATUS_MARKERS = (
    "hiatus",
    "suspended",
    "paused",
    "on hold",
    "休載",
    "停止",
    "中断",
    "一時停止",
    "休載",
    "停止",
    "中断",
)
_ONGOING_MARKERS = (
    "ongoing",
    "serial",
    "serializing",
    "in progress",
    "連載中",
    "連載",
    "更新中",
    "連載中",
    "連載",
    "更新中",
)


def normalize_publication_status(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    text = value.strip().lower()
    if not text:
        return "unknown"
    if text in PUBLICATION_STATUS_VALUES:
        return text
    if any(marker in text for marker in _COMPLETED_MARKERS):
        return "completed"
    if any(marker in text for marker in _HIATUS_MARKERS):
        return "hiatus"
    if any(marker in text for marker in _ONGOING_MARKERS):
        return "ongoing"
    return "unknown"


def publication_status_payload(raw_status: Any) -> dict[str, str]:
    status = normalize_publication_status(raw_status)
    payload = {
        "publication_status": status,
        "status": status,
    }
    if isinstance(raw_status, str) and raw_status.strip():
        payload["source_publication_status"] = raw_status.strip()
    return payload
