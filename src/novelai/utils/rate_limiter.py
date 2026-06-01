from __future__ import annotations

import time
from collections.abc import Mapping
from collections.abc import Callable
from typing import Any


class RateLimiter:
    """Protocol for rate limiter implementations."""

    def hit(self, client_id: str, action: str) -> bool:
        """Record a hit for (client_id, action). Return True if allowed."""
        raise NotImplementedError()


RateLimiterFactory = Callable[
    [Mapping[str, int] | None, int, dict[str, list[float]] | None], RateLimiter
]


class InMemoryRateLimiter(RateLimiter):
    """Simple in-process sliding window rate limiter.

    Not suitable for multi-process deployments but fine as a default.
    """

    def __init__(
        self,
        limits: Mapping[str, int] | None = None,
        window_seconds: int = 60,
        hits_storage: dict[str, list[float]] | None = None,
    ) -> None:
        self.window = float(window_seconds)
        self.limits = dict(limits or {})
        self._hits: dict[str, list[float]] = hits_storage if hits_storage is not None else {}

    def hit(self, client_id: str, action: str) -> bool:
        key = f"{client_id}:{action}"
        now = time.monotonic()
        window_start = now - self.window
        hits = [t for t in self._hits.get(key, []) if t > window_start]
        limit = int(self.limits.get(action, 0))
        if limit > 0 and len(hits) >= limit:
            # do not append the new hit if limit exceeded
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True


class DisabledRateLimiter(RateLimiter):
    """Limiter that allows every request."""

    def hit(self, client_id: str, action: str) -> bool:
        return True


_BACKENDS: dict[str, RateLimiterFactory] = {}


def register_rate_limiter_backend(name: str, factory: RateLimiterFactory) -> None:
    backend_name = name.strip().lower()
    if not backend_name:
        raise ValueError("Rate limiter backend name must not be empty.")
    _BACKENDS[backend_name] = factory


def create_rate_limiter(
    backend: str,
    limits: Mapping[str, int] | None = None,
    window_seconds: int = 60,
    hits_storage: dict[str, list[float]] | None = None,
) -> RateLimiter:
    backend_name = backend.strip().lower()
    try:
        factory = _BACKENDS[backend_name]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKENDS)) or "<none>"
        raise ValueError(f"Unknown rate limiter backend: {backend!r}. Available backends: {available}") from exc
    return factory(limits, window_seconds, hits_storage)


register_rate_limiter_backend(
    "memory",
    lambda limits, window_seconds, hits_storage: InMemoryRateLimiter(
        limits=limits,
        window_seconds=window_seconds,
        hits_storage=hits_storage,
    ),
)
register_rate_limiter_backend(
    "disabled",
    lambda limits, window_seconds, hits_storage: DisabledRateLimiter(),
)


_DEFAULT: RateLimiter | None = None
_DEFAULT_SIGNATURE: tuple[str, tuple[tuple[str, int], ...], int] | None = None


def get_default_rate_limiter(
    backend: str = "memory",
    limits: Mapping[str, int] | None = None,
    window_seconds: int = 60,
    hits_storage: dict[str, list[float]] | None = None,
) -> RateLimiter:
    global _DEFAULT, _DEFAULT_SIGNATURE
    signature = (backend.strip().lower(), tuple(sorted((limits or {}).items())), int(window_seconds))
    if _DEFAULT is None or _DEFAULT_SIGNATURE != signature:
        _DEFAULT = create_rate_limiter(
            backend,
            limits=limits,
            window_seconds=window_seconds,
            hits_storage=hits_storage,
        )
        _DEFAULT_SIGNATURE = signature
    return _DEFAULT


def set_default_rate_limiter(limiter: RateLimiter | None) -> None:
    global _DEFAULT, _DEFAULT_SIGNATURE
    _DEFAULT = limiter
    _DEFAULT_SIGNATURE = None
