from __future__ import annotations

import logging

import httpx

from src.models import FetchResult
from src.utils import utc_now_iso

logger = logging.getLogger(__name__)


class ChapterFetcher:
    """HTTP fetcher for chapter pages."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        user_agent: str = "NovelAIBook-ChapterPipeline/1.0",
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, url: str) -> FetchResult:
        logger.info("Fetching chapter URL: %s", url)
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
        return FetchResult(
            url=str(response.url),
            html=response.text,
            fetched_at=utc_now_iso(),
            status_code=response.status_code,
        )

