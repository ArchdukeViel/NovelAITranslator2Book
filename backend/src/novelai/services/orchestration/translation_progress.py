"""Translation progress recording — extracted from translation.py.

Aggregates per-chapter task results into a summary dict and identifies the
first error for re-raising. Previously inline at the end of
``translate_chapters``.
"""

from __future__ import annotations

from typing import Any

from novelai.translation.scheduler import build_scheduler_summary, collect_scheduler_decisions


def _build_chapter_summary(
    *,
    selected_numbers: list[int],
    task_results: list[Any],
    chapters: str,
    force: bool,
    target_language: str,
) -> tuple[dict[str, Any], BaseException | None]:
    """Aggregate per-chapter progress in source order. REQ-3.3.

    Returns ``(summary, first_error)``. The caller should attach
    ``chapter_progress`` and ``chapter_summary`` to ``first_error`` before
    re-raising so the activity worker can surface a partial-failure summary.
    """
    chapter_progress: dict[str, dict[str, str]] = {}
    succeeded_count = 0
    failed_count = 0
    skipped_count = 0
    first_error: BaseException | None = None
    for cn, result in zip(selected_numbers, task_results, strict=False):
        chapter_id = str(cn)
        if isinstance(result, BaseException):
            chapter_progress[chapter_id] = {"status": "failed", "error": str(result)[:512]}
            failed_count += 1
            if first_error is None:
                first_error = result
            continue
        if not isinstance(result, dict):
            chapter_progress[chapter_id] = {"status": "failed", "error": "unknown_result"}
            failed_count += 1
            continue
        status = str(result.get("status") or "")
        reason = result.get("reason")
        entry: dict[str, str] = {"status": status}
        if isinstance(reason, str) and reason:
            entry["reason"] = reason
        chapter_progress[chapter_id] = entry
        if status == "succeeded":
            succeeded_count += 1
        elif status == "skipped":
            skipped_count += 1
        else:
            failed_count += 1

    summary: dict[str, Any] = {
        "chapters": chapters,
        "force": force,
        "target_language": target_language,
        "chapter_progress": chapter_progress,
        "succeeded": succeeded_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": len(selected_numbers),
        "scheduler_summary": build_scheduler_summary(collect_scheduler_decisions()),
    }
    return summary, first_error
