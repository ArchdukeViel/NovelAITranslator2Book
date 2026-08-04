"""Incremental crawl planner and source state management (DEBT-CRAWL-01, DEBT-STATE-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CrawlPlan:
    """Planning decision for a crawl run."""

    total_chapters: int
    chapters_to_fetch: list[dict[str, Any]]
    chapters_to_skip: list[dict[str, Any]]
    plan_reason: dict[str, Any] = field(default_factory=dict)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_crawl_plan(
    novel_id: str,
    selected_chapters: list[dict[str, Any]],
    source_state: dict[str, Any] | None,
    existing_chapters: dict[str, dict[str, Any]],
    *,
    mode: str = "update",
) -> CrawlPlan:
    """Build an incremental crawl plan determining which chapters require fetching.

    In ``mode == "full"``, all selected chapters are fetched regardless of state.
    In ``mode == "update"``, a chapter is skipped if:
    1. It already exists in local storage.
    2. Its ``source_episode_id`` or ``id`` is present in ``source_state["episode_map"]``.
    3. The index update timestamp (``source_update_date`` / ``date_added``) matches the
       recorded timestamp in source state.
    """
    total = len(selected_chapters)
    if mode == "full" or not source_state:
        return CrawlPlan(
            total_chapters=total,
            chapters_to_fetch=list(selected_chapters),
            chapters_to_skip=[],
            plan_reason={
                "mode": mode,
                "reason": "Full mode or missing source state forces full refetch",
                "fetch_count": total,
                "skip_count": 0,
            },
        )

    episode_map = source_state.get("episode_map") or {}
    to_fetch: list[dict[str, Any]] = []
    to_skip: list[dict[str, Any]] = []

    for chapter in selected_chapters:
        ch_id = str(chapter.get("id") or chapter.get("num") or "")
        episode_id = str(chapter.get("source_episode_id") or ch_id)

        existing = existing_chapters.get(ch_id)
        recorded_ep = episode_map.get(episode_id)

        if not existing or not recorded_ep:
            to_fetch.append(chapter)
            continue

        index_date = chapter.get("source_update_date") or chapter.get("date_added")
        recorded_date = recorded_ep.get("source_update_date") or recorded_ep.get("last_updated_at")

        if index_date and recorded_date and str(index_date).strip() != str(recorded_date).strip():
            # Source index indicates chapter was updated since last crawl
            to_fetch.append(chapter)
        else:
            to_skip.append(chapter)

    return CrawlPlan(
        total_chapters=total,
        chapters_to_fetch=to_fetch,
        chapters_to_skip=to_skip,
        plan_reason={
            "mode": mode,
            "fetch_count": len(to_fetch),
            "skip_count": len(to_skip),
        },
    )


def update_source_state(
    novel_id: str,
    existing_state: dict[str, Any] | None,
    metadata: dict[str, Any],
    scraped_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build updated source state dict preserving existing episodes and updating scraped ones."""
    state = dict(existing_state) if existing_state else {}
    episode_map: dict[str, Any] = dict(state.get("episode_map") or {})

    now_iso = _utc_now_iso()

    for ch in scraped_chapters:
        ch_id = str(ch.get("id") or ch.get("chapter_id") or ch.get("num") or "")
        episode_id = str(ch.get("source_episode_id") or ch_id)
        if not episode_id:
            continue

        prev_ep = episode_map.get(episode_id) or {}
        index_date = ch.get("source_update_date") or ch.get("date_added")

        episode_map[episode_id] = {
            "chapter_id": ch_id,
            "source_episode_id": episode_id,
            "source_update_date": index_date,
            "content_hash": ch.get("content_hash") or prev_ep.get("content_hash"),
            "scraped_at": now_iso,
            "last_updated_at": index_date or prev_ep.get("last_updated_at") or now_iso,
        }

    return {
        "novel_id": novel_id,
        "source_key": metadata.get("source_key") or state.get("source_key"),
        "source_novel_id": metadata.get("source_novel_id") or state.get("source_novel_id"),
        "source_publication_status": metadata.get("publication_status") or state.get("source_publication_status"),
        "scraped_chapter_count": len(episode_map),
        "last_scraped_at": now_iso,
        "episode_map": episode_map,
    }
