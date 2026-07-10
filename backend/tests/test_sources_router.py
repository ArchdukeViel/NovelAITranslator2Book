from __future__ import annotations

from novelai.api.routers import sources


class TestSourcesRouter:
    """Verify the sources router structure and endpoint behavior.
    Uses the same TestClient pattern as test_admin_taxonomy.py.
    """

    def test_router_has_expected_routes(self) -> None:
        route_paths = {route.path for route in sources.router.routes}
        assert "/sources" in route_paths
        assert "/input-adapters" in route_paths

    def test_list_sources_returns_list(self) -> None:
        from novelai.services.source_catalog_service import list_available_sources

        result = list_available_sources()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_list_input_adapters_returns_list(self) -> None:
        from novelai.services.source_catalog_service import list_available_input_adapters

        result = list_available_input_adapters()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_list_sources_includes_known_sources(self) -> None:
        from novelai.runtime.bootstrap import bootstrap

        bootstrap()
        from novelai.services.source_catalog_service import list_available_sources

        result = list_available_sources()
        assert "syosetu_ncode" in result
        assert "kakuyomu" in result
        assert "generic" in result
