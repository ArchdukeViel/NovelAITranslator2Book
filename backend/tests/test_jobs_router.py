from __future__ import annotations

from novelai.api.routers import activity, jobs


class TestJobsCompatShim:
    """jobs.py is a compatibility re-export of activity.py.
    Verify all symbols are re-exported correctly.
    """

    def test_router_is_same_object(self) -> None:
        assert jobs.router is activity.router

    def test_request_models_are_same_object(self) -> None:
        assert jobs.CrawlActivityRequest is activity.CrawlActivityRequest
        assert jobs.TranslationActivityRequest is activity.TranslationActivityRequest
        assert jobs.ActivityStatusUpdateRequest is activity.ActivityStatusUpdateRequest

    def test_compat_aliases_are_same_object(self) -> None:
        assert jobs.CrawlJobRequest is activity.CrawlJobRequest
        assert jobs.TranslationJobRequest is activity.TranslationJobRequest
        assert jobs.JobStatusUpdateRequest is activity.JobStatusUpdateRequest

    def test_endpoint_functions_are_same_object(self) -> None:
        assert jobs.create_crawl_activity is activity.create_crawl_activity
        assert jobs.create_translation_activity is activity.create_translation_activity
        assert jobs.list_activity is activity.list_activity
        assert jobs.get_activity is activity.get_activity
        assert jobs.delete_activity is activity.delete_activity
        assert jobs.run_activity is activity.run_activity
        assert jobs.run_next_activity is activity.run_next_activity
        assert jobs.update_activity_status is activity.update_activity_status
        assert jobs.get_source_health is activity.get_source_health
        assert jobs.list_source_health is activity.list_source_health

    def test_all_exports_match_activity(self) -> None:
        for name in jobs.__all__:
            assert hasattr(jobs, name), f"jobs.__all__ lists {name!r} but it's missing from jobs module"
            assert hasattr(activity, name), f"jobs.{name} not found in activity module"
            assert getattr(jobs, name) is getattr(activity, name), f"jobs.{name} is not the same object as activity.{name}"
