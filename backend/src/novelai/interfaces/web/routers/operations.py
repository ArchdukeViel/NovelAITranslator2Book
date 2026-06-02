from __future__ import annotations

from fastapi import APIRouter

from novelai.interfaces.web.routers._route_groups import include_legacy_routes

router = APIRouter()

include_legacy_routes(
    router,
    [
        "/{novel_id}/scrape",
        "/{novel_id}/import",
        "/{novel_id}/translate",
        "/{novel_id}/export",
    ],
)
