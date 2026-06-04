from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from novelai.config.settings import settings


@dataclass
class _DomainThrottleState:
    last_request_at: float = 0.0
    penalty_seconds: float = 0.0


class DomainThrottle:
    """Simple shared per-domain throttle with adaptive penalties."""

    def __init__(
        self,
        *,
        min_delay_seconds: float | None = None,
        max_delay_seconds: float = 30.0,
    ) -> None:
        self.min_delay_seconds = (
            float(settings.SCRAPE_DELAY_SECONDS)
            if min_delay_seconds is None
            else max(0.0, float(min_delay_seconds))
        )
        self.max_delay_seconds = max(self.min_delay_seconds, float(max_delay_seconds))
        self._states: dict[str, _DomainThrottleState] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _domain(url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    async def before_request(self, url: str) -> None:
        domain = self._domain(url)
        if not domain:
            return

        async with self._lock:
            state = self._states.setdefault(domain, _DomainThrottleState())
            delay = min(self.max_delay_seconds, self.min_delay_seconds + state.penalty_seconds)
            wait_seconds = max(0.0, delay - (time.monotonic() - state.last_request_at))

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        async with self._lock:
            self._states.setdefault(domain, _DomainThrottleState()).last_request_at = time.monotonic()

    async def after_response(self, url: str, status_code: int) -> None:
        domain = self._domain(url)
        if not domain:
            return

        async with self._lock:
            state = self._states.setdefault(domain, _DomainThrottleState())
            if status_code == 429 or 500 <= status_code <= 599:
                state.penalty_seconds = min(
                    self.max_delay_seconds,
                    max(1.0, state.penalty_seconds * 2 if state.penalty_seconds else self.min_delay_seconds or 1.0),
                )
            elif 200 <= status_code < 400:
                state.penalty_seconds = max(0.0, state.penalty_seconds * 0.5)

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            domain: {
                "last_request_at": state.last_request_at,
                "penalty_seconds": state.penalty_seconds,
            }
            for domain, state in self._states.items()
        }
