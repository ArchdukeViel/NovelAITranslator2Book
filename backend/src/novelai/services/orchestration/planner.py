"""Incremental crawl planner and source state management (DEBT-CRAWL-01, DEBT-STATE-01, Section 10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CrawlPlan:
    """Planning decision for a crawl run matching Section 6 contract."""

    total_index_entries: int
    new_episode_ids: tuple[str, ...]
    missing_local_episode_ids: tuple[str, ...]
    changed_index_episode_ids: tuple[str, ...]
    rolling_revalidation_episode_ids: tuple[str, ...]
    explicitly_selected_episode_ids: tuple[str, ...]

    reusable_episode_ids: tuple[str, ...]
    removed_episode_ids: tuple[str, ...]
    reordered_episode_ids: tuple[str, ...]

    metadata_refresh: bool
    index_refresh: bool
    full_reconciliation_required: bool

    reasons: dict[str, Any] = field(default_factory=dict)

    @property
    def chapters_to_fetch_set(self) -> set[str]:
        return set(
            self.new_episode_ids
            + self.missing_local_episode_ids
            + self.changed_index_episode_ids
            + self.rolling_revalidation_episode_ids
            + self.explicitly_selected_episode_ids
        )

    # Legacy compatibility properties
    @property
    def total_chapters(self) -> int:
        return self.total_index_entries

    @property
    def chapters_to_fetch(self) -> list[dict[str, Any]]:
        return [{"id": ep_id, "source_episode_id": ep_id} for ep_id in self.chapters_to_fetch_set]

    @property
    def chapters_to_skip(self) -> list[dict[str, Any]]:
        return [{"id": ep_id, "source_episode_id": ep_id} for ep_id in self.reusable_episode_ids]

    @property
    def plan_reason(self) -> dict[str, Any]:
        return self.reasons


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_crawl_plan(
    novel_id: str,
    selected_chapters: list[dict[str, Any]],
    source_state: dict[str, Any] | None,
    existing_chapters: dict[str, dict[str, Any]],
    *,
    mode: str = "update",
    revalidation_window: int = 5,
    all_chapters: list[dict[str, Any]] | None = None,
) -> CrawlPlan:
    """Build an incremental crawl plan determining which chapters require fetching."""
    full_index = all_chapters if all_chapters is not None else selected_chapters
    total = len(full_index)
    episode_map = source_state.get("episode_map") if isinstance(source_state, dict) else {}
    if not isinstance(episode_map, dict):
        episode_map = {}

    new_eps: list[str] = []
    missing_local_eps: list[str] = []
    changed_index_eps: list[str] = []
    rolling_reval_eps: list[str] = []
    explicit_eps: list[str] = []
    reusable_eps: list[str] = []

    if mode == "full" or not source_state:
        for ch in selected_chapters:
            ch_id = str(ch.get("id") or ch.get("source_episode_id") or ch.get("num") or "")
            explicit_eps.append(ch_id)

        return CrawlPlan(
            total_index_entries=total,
            new_episode_ids=(),
            missing_local_episode_ids=(),
            changed_index_episode_ids=(),
            rolling_revalidation_episode_ids=(),
            explicitly_selected_episode_ids=tuple(explicit_eps),
            reusable_episode_ids=(),
            removed_episode_ids=(),
            reordered_episode_ids=(),
            metadata_refresh=True,
            index_refresh=True,
            full_reconciliation_required=(mode == "full"),
            reasons={"mode": mode, "reason": "Full mode or missing source state forces refetch"},
        )

    # Calculate rolling revalidation target IDs (last N chapters in selected list).
    # The window is only applied when the index exceeds the window size; for
    # smaller indices every confidently-dated unchanged chapter is reused
    # without a body request (PR-41 blocker 3 contract). Undated episodes are
    # always revalidated regardless of the window below.
    reval_targets = set()
    if revalidation_window > 0 and len(selected_chapters) > revalidation_window:
        reval_targets = {
            str(ch.get("id") or ch.get("source_episode_id") or ch.get("num") or "")
            for ch in selected_chapters[-revalidation_window:]
        }

    for ch in selected_chapters:
        ch_id = str(ch.get("id") or ch.get("num") or "")
        ep_id = str(ch.get("source_episode_id") or ch_id)

        existing = existing_chapters.get(ch_id)
        recorded_ep = episode_map.get(ep_id)

        if not recorded_ep:
            new_eps.append(ep_id)
        elif not existing:
            missing_local_eps.append(ep_id)
        else:
            index_date = ch.get("source_update_date") or ch.get("date_added")
            recorded_date = recorded_ep.get("source_update_date") or recorded_ep.get("last_updated_at")

            index_date_s = str(index_date).strip() if index_date is not None else ""
            recorded_date_s = str(recorded_date).strip() if recorded_date is not None else ""

            if index_date_s and recorded_date_s and index_date_s != recorded_date_s:
                changed_index_eps.append(ep_id)
            elif index_date_s and recorded_date_s and index_date_s == recorded_date_s:
                # Confidently dated and unchanged.
                if ep_id in reval_targets:
                    rolling_reval_eps.append(ep_id)
                else:
                    reusable_eps.append(ep_id)
            elif ep_id in reval_targets:
                # Recent window always revalidated regardless of date signal.
                rolling_reval_eps.append(ep_id)
            else:
                # Undated (no reliable change signal): never permanently reuse;
                # enter periodic revalidation so changes are not missed.
                rolling_reval_eps.append(ep_id)

    # Check for removed episode IDs (present in recorded episode_map but absent from complete index)
    complete_ep_ids = {str(ch.get("source_episode_id") or ch.get("id") or ch.get("num")) for ch in full_index}
    removed_eps = [ep_id for ep_id in episode_map if ep_id not in complete_ep_ids]

    # Calculate reordered episode IDs (compare relative order of common episode IDs)
    prev_ordered_ep_ids = [ep_id for ep_id in episode_map if ep_id in complete_ep_ids]
    curr_ordered_ep_ids = [
        str(ch.get("source_episode_id") or ch.get("id") or ch.get("num"))
        for ch in full_index
        if str(ch.get("source_episode_id") or ch.get("id") or ch.get("num")) in episode_map
    ]
    reordered_eps = []
    if len(prev_ordered_ep_ids) == len(curr_ordered_ep_ids):
        for ep_prev, ep_curr in zip(prev_ordered_ep_ids, curr_ordered_ep_ids, strict=False):
            if ep_prev != ep_curr:
                reordered_eps.append(ep_curr)

    return CrawlPlan(
        total_index_entries=total,
        new_episode_ids=tuple(new_eps),
        missing_local_episode_ids=tuple(missing_local_eps),
        changed_index_episode_ids=tuple(changed_index_eps),
        rolling_revalidation_episode_ids=tuple(rolling_reval_eps),
        explicitly_selected_episode_ids=tuple(explicit_eps),
        reusable_episode_ids=tuple(reusable_eps),
        removed_episode_ids=tuple(removed_eps),
        reordered_episode_ids=tuple(reordered_eps),
        metadata_refresh=False,
        index_refresh=False,
        full_reconciliation_required=False,
        reasons={
            "mode": mode,
            "new_count": len(new_eps),
            "missing_local_count": len(missing_local_eps),
            "changed_count": len(changed_index_eps),
            "revalidation_count": len(rolling_reval_eps),
            "reusable_count": len(reusable_eps),
            "removed_count": len(removed_eps),
            "reordered_count": len(reordered_eps),
        },
    )


def update_source_state(
    novel_id: str,
    existing_state: dict[str, Any] | None,
    metadata: dict[str, Any],
    scraped_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build updated source state dict preserving existing episodes.

    Section 10 contract: persists ``ordered_episode_ids`` matching the
    current complete index, and per-episode ``source_availability`` /
    ``first_seen_at`` / ``last_seen_at`` / ``missing_since``. Episodes
    absent from the current index are marked ``missing_from_current_index``
    rather than deleted; raw and translated history is retained.
    """
    state = dict(existing_state) if existing_state else {}
    episode_map: dict[str, Any] = dict(state.get("episode_map") or {})

    now_iso = _utc_now_iso()

    chapters_list = metadata.get("chapters") if isinstance(metadata, dict) else None
    if not isinstance(chapters_list, list):
        chapters_list = []

    current_episode_ids: list[str] = []
    for chapter in chapters_list:
        if not isinstance(chapter, dict):
            continue
        ep_id = str(
            chapter.get("source_episode_id")
            or chapter.get("id")
            or chapter.get("chapter_id")
            or chapter.get("num")
            or ""
        )
        if ep_id:
            current_episode_ids.append(ep_id)

    for ch in scraped_chapters:
        ch_id = str(ch.get("id") or ch.get("chapter_id") or ch.get("num") or "")
        episode_id = str(ch.get("source_episode_id") or ch_id)
        if not episode_id:
            continue

        prev_ep = episode_map.get(episode_id) or {}
        index_date = ch.get("source_update_date") or ch.get("date_added")
        first_seen = prev_ep.get("first_seen_at") or prev_ep.get("scraped_at") or now_iso
        episode_map[episode_id] = {
            "chapter_id": ch_id,
            "source_episode_id": episode_id,
            "source_update_date": index_date,
            "content_hash": ch.get("content_hash") or prev_ep.get("content_hash"),
            "structure_hash": ch.get("structure_hash") or prev_ep.get("structure_hash"),
            "scraped_at": now_iso,
            "first_seen_at": first_seen,
            "last_seen_at": now_iso,
            "last_updated_at": index_date or prev_ep.get("last_updated_at") or now_iso,
            "source_availability": "active",
            "missing_since": None,
        }

    for ep_id, prev_ep in episode_map.items():
        if ep_id not in current_episode_ids:
            if prev_ep.get("source_availability") != "missing_from_current_index":
                episode_map[ep_id] = {
                    **prev_ep,
                    "source_availability": "missing_from_current_index",
                    "missing_since": prev_ep.get("missing_since") or now_iso,
                    "last_seen_at": prev_ep.get("last_seen_at") or now_iso,
                }
        else:
            if prev_ep.get("source_availability") == "missing_from_current_index":
                episode_map[ep_id] = {
                    **prev_ep,
                    "source_availability": "active",
                    "missing_since": None,
                    "last_seen_at": now_iso,
                }

    return {
        "novel_id": novel_id,
        "source_key": metadata.get("source_key") or state.get("source_key"),
        "source_novel_id": metadata.get("source_novel_id") or state.get("source_novel_id"),
        "source_publication_status": metadata.get("publication_status") or state.get("source_publication_status"),
        "scraped_chapter_count": len(episode_map),
        "last_scraped_at": now_iso,
        "episode_map": episode_map,
        "ordered_episode_ids": current_episode_ids,
    }
