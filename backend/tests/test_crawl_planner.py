from novelai.services.orchestration.planner import CrawlPlan, create_crawl_plan, update_source_state


def test_create_crawl_plan_full_mode_fetches_all():
    selected = [
        {"id": "1", "num": 1, "title": "Ch 1"},
        {"id": "2", "num": 2, "title": "Ch 2"},
    ]
    source_state = {"episode_map": {"1": {"source_update_date": "2024-01-01"}}}
    existing = {"1": {"text": "ch1 text"}}

    plan = create_crawl_plan("n1234ab", selected, source_state, existing, mode="full")
    assert isinstance(plan, CrawlPlan)
    assert plan.total_chapters == 2
    assert len(plan.chapters_to_fetch) == 2
    assert len(plan.chapters_to_skip) == 0


def test_create_crawl_plan_skips_unchanged_chapters():
    selected = [
        {"id": "1", "source_episode_id": "1", "source_update_date": "2024-01-01"},
        {"id": "2", "source_episode_id": "2", "source_update_date": "2024-02-01"},
    ]
    source_state = {
        "episode_map": {
            "1": {"source_episode_id": "1", "source_update_date": "2024-01-01"},
            "2": {"source_episode_id": "2", "source_update_date": "2024-01-15"},
        }
    }
    existing = {
        "1": {"text": "ch1 text"},
        "2": {"text": "ch2 old text"},
    }

    plan = create_crawl_plan("n1234ab", selected, source_state, existing, mode="update")
    assert plan.total_chapters == 2
    assert len(plan.chapters_to_fetch) == 1
    assert plan.chapters_to_fetch[0]["id"] == "2"
    assert len(plan.chapters_to_skip) == 1
    assert plan.chapters_to_skip[0]["id"] == "1"


def test_update_source_state_builds_valid_snapshot():
    meta = {"source_key": "syosetu_ncode", "source_novel_id": "n1234ab", "publication_status": "ongoing"}
    scraped = [
        {"id": "1", "source_episode_id": "1", "source_update_date": "2024-01-01", "content_hash": "abc123hash"},
    ]
    state = update_source_state("n1234ab", None, meta, scraped)

    assert state["novel_id"] == "n1234ab"
    assert state["source_key"] == "syosetu_ncode"
    assert state["scraped_chapter_count"] == 1
    assert "1" in state["episode_map"]
    assert state["episode_map"]["1"]["content_hash"] == "abc123hash"


def test_undated_chapter_enters_periodic_revalidation():
    """Undated episodes must never be permanently skipped just because local
    data and a source-state entry both exist (PR-41 blocker 3)."""
    selected = [
        {"id": "1", "source_episode_id": "1"},
        {"id": "2", "source_episode_id": "2"},
    ]
    source_state = {
        "episode_map": {
            "1": {"source_update_date": None, "last_updated_at": "2026-01-01T00:00:00Z"},
            "2": {"source_update_date": None, "last_updated_at": "2026-01-01T00:00:00Z"},
        }
    }
    existing = {"1": {"text": "ch1"}, "2": {"text": "ch2"}}

    plan = create_crawl_plan("n1234ab", selected, source_state, existing, mode="update")
    assert plan.reusable_episode_ids == ()
    assert set(plan.rolling_revalidation_episode_ids) == {"1", "2"}
    assert len(plan.chapters_to_fetch_set) == 2


def test_recent_window_unchanged_chapter_is_revalidated():
    """A dated unchanged chapter inside the rolling window is revalidated."""
    selected = []
    source_state_map = {}
    existing = {}
    for i in range(1, 11):
        selected.append(
            {
                "id": str(i),
                "source_episode_id": str(i),
                "source_update_date": f"2024-01-{i:02d}",
            }
        )
        source_state_map[str(i)] = {
            "source_update_date": f"2024-01-{i:02d}",
            "last_updated_at": "2024-01-15",
        }
        existing[str(i)] = {"text": f"ch{i}"}

    plan = create_crawl_plan(
        "n1234ab",
        selected,
        {"episode_map": source_state_map},
        existing,
        mode="update",
        revalidation_window=3,
    )
    # Old dated-unchanged chapters 1-7 are reusable (no HTTP body request).
    assert set(plan.reusable_episode_ids) == {str(i) for i in range(1, 8)}
    # Recent window 8-10 revalidated.
    assert set(plan.rolling_revalidation_episode_ids) == {"8", "9", "10"}
