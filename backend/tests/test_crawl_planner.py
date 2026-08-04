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
