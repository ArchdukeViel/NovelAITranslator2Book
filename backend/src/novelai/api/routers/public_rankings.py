"""Guest-visible public ranking endpoint."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import get_db_session, get_public_catalog_service
from novelai.api.routers.public_contracts import PublicRankingResponse
from novelai.services.public_catalog_service import PublicCatalogService
from novelai.services.public_ranking_service import PublicRankingService

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/rankings", response_model=PublicRankingResponse)
def list_public_rankings(
    period: Literal["daily", "weekly", "monthly"] = Query(default="weekly"),
    limit: int = Query(default=10, ge=1, le=50),
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db_session),
    catalog: PublicCatalogService = Depends(get_public_catalog_service),
) -> dict[str, object]:
    result = PublicRankingService(db_session=db, catalog_service=catalog).list_rankings(period=period, limit=limit)
    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=60"
    return result
