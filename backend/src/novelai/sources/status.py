from __future__ import annotations

from typing import Any

# REQ-16 / AC-16 (frontend-audit-remediation, 2026-09-06): added "cancelled"
# alongside the original 4 variants. "cancelled" represents author-dropped
# works whose source syndication markers indicate the work is over and the
# author is not continuing. It is distinct from `onboarding_status="cancelled"`
# (a runtime crawl-abort signal in storage/r2_catalog.py) and from "hiatus"
# (author intends to return).
PUBLICATION_STATUS_VALUES = {"ongoing", "completed", "hiatus", "cancelled", "unknown"}

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
# Conservative author-dropped markers. Only phrases that semantically mean
# "the work is over and the author is not continuing" qualify. "休載" alone
# is NOT included (it means the author is on break, not that the work is
# dropped); ambiguous markers fall through to the unknown branch.
_CANCELLED_MARKERS = (
    "cancelled",
    "canceled",
    "abandoned",
    "discontinued",
    "dropped",
    "連載中止",
    "中止",
    "打ち切り",
    "休載中",
    "連載停止",
    "更新停止",
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
    # Order matters: completed > cancelled > hiatus > ongoing > unknown.
    # A phrase like "完結 (打ち切り)" (an uncommon but plausible source note)
    # should classify as completed, not cancelled, because the author finished
    # the work even if the label uses 打ち切り colloquially.
    if any(marker in text for marker in _COMPLETED_MARKERS):
        return "completed"
    if any(marker in text for marker in _CANCELLED_MARKERS):
        return "cancelled"
    if any(marker in text for marker in _HIATUS_MARKERS):
        return "hiatus"
    if any(marker in text for marker in _ONGOING_MARKERS):
        return "ongoing"
    return "unknown"


def publication_status_payload(raw_status: Any) -> dict[str, str]:
    status = normalize_publication_status(raw_status)
    payload = {
        "publication_status": status,
    }
    if isinstance(raw_status, str) and raw_status.strip():
        payload["source_publication_status"] = raw_status.strip()
    return payload
