from __future__ import annotations

import pytest

from novelai.infrastructure.http.throttle import DomainThrottle


@pytest.mark.asyncio
async def test_domain_throttle_caps_recent_domain_state() -> None:
    throttle = DomainThrottle(min_delay_seconds=0.0)

    for index in range(1001):
        url = f"https://domain-{index}.example.test/"
        await throttle.before_request(url)
        await throttle.after_response(url, 200)

    assert len(throttle.snapshot()) <= 1000
