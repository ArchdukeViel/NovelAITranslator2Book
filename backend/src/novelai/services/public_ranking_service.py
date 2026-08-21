"""Public ranking aggregation over privacy-safe novel-detail view events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from novelai.config.settings import settings
from novelai.db.models.analytics_event import AnalyticsEvent
from novelai.db.models.novel import Novel
from novelai.services.public_catalog_service import PublicCatalogService
from novelai.services.public_ranking_cache import RankingCacheKey, public_ranking_cache

RankingPeriod = Literal["daily", "weekly", "monthly"]
PERIOD_DAYS: dict[str, int] = {"daily": 1, "weekly": 7, "monthly": 30}
PUBLIC_PROJECTION_SCHEMA_VERSION = "public-projection-v1"


class PublicRankingService:
    """Build truthful rankings from distinct authenticated/anonymous viewers."""

    def __init__(self, *, db_session: Session, catalog_service: PublicCatalogService) -> None:
        self.db = db_session
        self.catalog = catalog_service

    def list_rankings(self, *, period: RankingPeriod, limit: int) -> dict[str, object]:
        generated_at = datetime.now(UTC)
        if not settings.ANALYTICS_ENABLED:
            return self._response(period, generated_at, [], reason="analytics_disabled")

        cutoff = generated_at - timedelta(days=PERIOD_DAYS[period])
        cache_key: RankingCacheKey | None = None
        if settings.PUBLIC_RANKING_CACHE_ENABLED:
            cache_key = self._cache_key(period=period, limit=limit)
            cached = public_ranking_cache.get(cache_key)
            if cached is not None:
                return cached

        # The trusted detail-view path stores either user_id or the signed,
        # opaque anonymous session digest. A single CASE expression therefore
        # counts distinct viewers without counting chapter navigation or raw
        # repeated requests. The two viewer namespaces are mutually exclusive
        # at ingestion time and no IP address participates in this query.
        viewer_identity = case(
            (AnalyticsEvent.user_id.isnot(None), cast(AnalyticsEvent.user_id, String)),
            else_=AnalyticsEvent.session_id,
        )
        unique_views = func.count(func.distinct(viewer_identity)).label("unique_views")
        ranking_rows = (
            self.db.query(Novel, unique_views)
            .join(AnalyticsEvent, AnalyticsEvent.novel_id == Novel.slug)
            .options(selectinload(Novel.genres), selectinload(Novel.tags))
            .filter(
                Novel.is_published.is_(True),
                Novel.title != Novel.slug,
                AnalyticsEvent.event_name == "public_novel.view",
                AnalyticsEvent.created_at >= cutoff,
                or_(AnalyticsEvent.user_id.isnot(None), AnalyticsEvent.session_id.isnot(None)),
            )
            .group_by(Novel.id)
            .order_by(unique_views.desc(), func.lower(Novel.title).asc(), Novel.slug.asc())
            .limit(limit)
            .all()
        )

        if not ranking_rows:
            return self._response(period, generated_at, [], reason="no_data")

        items: list[dict[str, object]] = []
        for novel, viewers in ranking_rows:
            summary = self.catalog.build_public_novel_summary(novel, include_adult=False)
            if summary is None:
                continue
            items.append(
                {
                    "rank": len(items) + 1,
                    "unique_views": int(viewers or 0),
                    "novel": summary,
                }
            )
        result = self._response(period, generated_at, items, reason=None if items else "no_data")
        if cache_key is not None:
            public_ranking_cache.set(cache_key, result)
        return result

    def _cache_key(self, *, period: RankingPeriod, limit: int) -> RankingCacheKey:
        latest_projection_update = (
            self.db.query(func.max(Novel.updated_at)).filter(Novel.is_published.is_(True)).scalar()
        )
        projection_version = latest_projection_update.isoformat() if latest_projection_update is not None else "empty"
        return (period, f"{PUBLIC_PROJECTION_SCHEMA_VERSION}:{projection_version}", limit)

    @staticmethod
    def _response(
        period: RankingPeriod,
        generated_at: datetime,
        items: list[dict[str, object]],
        *,
        reason: str | None,
    ) -> dict[str, object]:
        return {
            "period": period,
            "metric": "unique_novel_views",
            "available": bool(items),
            "reason": reason,
            "retention_days": settings.ANALYTICS_RETENTION_DAYS,
            "generated_at": generated_at,
            "items": items,
        }
