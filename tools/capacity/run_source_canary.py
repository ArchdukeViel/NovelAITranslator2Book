"""Run one bounded application-service translation canary.

This module is intended to run inside the backend container with the worker
container stopped. It selects one existing non-terminal chapter, creates one
translation activity through the normal queue service, runs that activity once,
and emits only fixed-label, secret-free outcome fields.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select

from novelai.activity.queue import ActivityQueueService
from novelai.db.engine import session_scope
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.runtime.container import Container

SOURCE_KEYS = ("syosetu_ncode", "kakuyomu", "novel18_syosetu")
TERMINAL_STATES = {
    "completed",
    "failed",
    "cancelled",
    "paused",
    "paused_until_cooldown",
    "paused_until_quota_reset",
}


def _select_candidate() -> tuple[str, str, int] | None:
    with session_scope() as db:
        candidate = db.execute(
            select(Novel.slug, Novel.source_site, Chapter.chapter_number)
            .join(Chapter, Chapter.novel_id == Novel.id)
            .where(
                Novel.source_site.in_(SOURCE_KEYS),
                Chapter.chapter_number == 1,
                Chapter.translation_status != "completed",
            )
            .order_by(Novel.slug, Novel.source_site)
            .limit(1)
        ).first()
    if candidate is None:
        return None
    return str(candidate[0]), str(candidate[1]), int(candidate[2])


def _safe_activity_report(
    *,
    candidate: tuple[str, str, int] | None,
    queue: ActivityQueueService,
    activity_id: str | None,
    result: Any,
    exception: BaseException | None,
) -> dict[str, Any]:
    after = queue.get_activity(activity_id) if activity_id else None
    status = str(after.get("status")) if after is not None else "not_created"
    return {
        "candidate_found": candidate is not None,
        "source_key": candidate[1] if candidate is not None else None,
        "chapter_number": candidate[2] if candidate is not None else None,
        "activity_created": activity_id is not None,
        "activity_id_present": bool(activity_id),
        "final_status": status,
        "terminal": status in TERMINAL_STATES,
        "retry_count": int(after.get("retry_count") or 0) if after is not None else 0,
        "error_present": bool(after.get("error")) if after is not None else False,
        "exception_type": type(exception).__name__ if exception is not None else None,
        "result_keys": sorted(str(key) for key in result) if isinstance(result, dict) else [],
    }


async def _run_activity(container: Container, activity_id: str) -> Any:
    return await container.activity_worker.run_activity(activity_id)


def main() -> int:
    candidate = _select_candidate()
    container = Container()
    queue = container.activity_log
    activity_id: str | None = None
    result: Any = None
    exception: BaseException | None = None

    if candidate is not None:
        novel_id, source_key, chapter_number = candidate
        activity = queue.create_translation_activity(
            novel_id=novel_id,
            source_key=source_key,
            kind="translate",
            chapters=str(chapter_number),
            provider_key="gemini",
            provider_model=container.preferences.get_preferred_model(),
            metadata={
                "activity_subtype": "translation",
                "activity_phase": "translate_novel",
                "source_canary": True,
                "allow_cross_provider_fallback": False,
                "skip_glossary_gate": True,
                "source_language": "Japanese",
                "target_language": "English",
            },
            idempotency_key=f"pac-canary-{uuid.uuid4().hex}",
        )
        activity_id = str(activity.get("activity_id") or "") or None
        if activity_id is not None:
            try:
                result = asyncio.run(_run_activity(container, activity_id))
            except BaseException as exc:  # pragma: no cover - live provider boundary
                exception = exc

    report = _safe_activity_report(
        candidate=candidate,
        queue=queue,
        activity_id=activity_id,
        result=result,
        exception=exception,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
