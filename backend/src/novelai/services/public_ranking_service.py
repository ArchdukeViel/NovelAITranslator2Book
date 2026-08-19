"""Public ranking aggregation over privacy-safe novel-detail view events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from novelai.config.settings import settings
from novelai.db.models.analytics_event import AnalyticsEvent
from novelai.db.models.novel import Novel
from novelai.services.public_catalog_service import PublicCatalogService

RankingPeriod = Literal["daily", "weekly", "monthly"]
PERIOD_DAYS: dict[str, int] = {"daily": 1, "weekly": 7, "monthly": 30}


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
        # Authenticated and anonymous identities are mutually exclusive at
        # ingestion time. Counting each separately prevents a raw request
        # count from inflating a ranking when a reader navigates repeatedly.
        user_rows = (
            self.db.query(
                AnalyticsEvent.novel_id,
                func.count(func.distinct(AnalyticsEvent.user_id)).label("viewers"),
            )
            .filter(
                AnalyticsEvent.event_name == "public_novel.view",
                AnalyticsEvent.created_at >= cutoff,
                AnalyticsEvent.novel_id.isnot(None),
                AnalyticsEvent.user_id.isnot(None),
            )
            .group_by(AnalyticsEvent.novel_id)
            .all()
        )
        anonymous_rows = (
            self.db.query(
                AnalyticsEvent.novel_id,
                func.count(func.distinct(AnalyticsEvent.session_id)).label("viewers"),
            )
            .filter(
                AnalyticsEvent.event_name == "public_novel.view",
                AnalyticsEvent.created_at >= cutoff,
                AnalyticsEvent.novel_id.isnot(None),
                AnalyticsEvent.session_id.isnot(None),
            )
            .group_by(AnalyticsEvent.novel_id)
            .all()
        )
        counts: dict[str, int] = {}
        for novel_id, viewers in [*user_rows, *anonymous_rows]:
            if novel_id:
                counts[str(novel_id)] = counts.get(str(novel_id), 0) + int(viewers or 0)
        if not counts:
            return self._response(period, generated_at, [], reason="no_data")

        novels = self.db.query(Novel).filter(Novel.is_published.is_(True), Novel.slug.in_(list(counts))).all()
        novels.sort(key=lambda novel: (-counts.get(novel.slug, 0), novel.title.casefold(), novel.slug))
        items: list[dict[str, object]] = []
        for novel in novels[:limit]:
            summary, _ = self.catalog.get_public_novel_summary(novel.slug, include_adult=False)
            if summary is None:
                continue
            items.append(
                {
                    "rank": len(items) + 1,
                    "unique_views": counts[novel.slug],
                    "novel": summary,
                }
            )
        return self._response(period, generated_at, items, reason=None if items else "no_data")

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
