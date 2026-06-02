from __future__ import annotations

from fastapi import APIRouter

from novelai.interfaces.web.routers._route_groups import include_legacy_routes

router = APIRouter()

include_legacy_routes(
    router,
    [
        "/{novel_id}/chapters/{chapter_id}/translated/versions",
        "/{novel_id}/chapters/{chapter_id}/translated/edit-history",
        ("/{novel_id}/chapters/{chapter_id}/translated", ["PUT"]),
        "/{novel_id}/chapters/{chapter_id}/translated/rollback",
    ],
)
