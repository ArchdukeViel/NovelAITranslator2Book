from __future__ import annotations

from novelai.api.routers import activity


class TestActivityRouterStructure:
    """Verify the activity router has the expected endpoints and structure.
    Full endpoint behavior is tested via test_activity_provider_errors.py
    and the e2e suite; this covers the router surface itself.
    """

    def test_router_has_csrf_dependency(self) -> None:
        deps = [type(d).__name__ for d in activity.router.dependencies]
        assert len(deps) > 0, "activity router should have CSRF dependency"

    def test_router_has_expected_routes(self) -> None:
        route_paths = {route.path for route in activity.router.routes}
        assert "/activity" in route_paths
        assert "/activity/{activity_id}" in route_paths
        assert "/activity/run-next" in route_paths

    def test_crawl_activity_request_defaults(self) -> None:
        req = activity.CrawlActivityRequest(novel_id="n1", source_key="syosetu_ncode")
        assert req.kind == "chapters"
        assert req.chapters == "all"
        assert req.source_url is None
        assert req.metadata is None

    def test_translation_activity_request_defaults(self) -> None:
        req = activity.TranslationActivityRequest(novel_id="n1")
        assert req.kind == "translate"
        assert req.chapters == "all"
        assert req.provider_key is None
        assert req.provider_model is None
        assert req.allow_cross_provider_fallback is True
        assert req.skip_glossary_gate is False

    def test_activity_status_update_request_defaults(self) -> None:
        req = activity.ActivityStatusUpdateRequest(status="completed")
        assert req.error is None
        assert req.metadata is None

    def test_compat_aliases_match(self) -> None:
        assert activity.CrawlJobRequest is activity.CrawlActivityRequest
        assert activity.TranslationJobRequest is activity.TranslationActivityRequest
        assert activity.JobStatusUpdateRequest is activity.ActivityStatusUpdateRequest
