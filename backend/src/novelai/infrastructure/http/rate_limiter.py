from __future__ import annotations

import time
from collections.abc import Callable, Mapping

try:
    import redis
except ImportError:
    redis = None  # type: ignore

from novelai.config.settings import settings


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


class RedisRateLimiter(RateLimiter):
    """Redis-backed fixed-window rate limiter suitable for multi-instance deployments."""

    def __init__(
        self,
        limits: Mapping[str, int] | None = None,
        window_seconds: int = 60,
        hits_storage: dict[str, list[float]] | None = None,
    ) -> None:
        if redis is None:
            raise ImportError("The 'redis' package is required for the redis rate limiter backend.")

        redis_url = settings.REDIS_URL
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is required when WEB_RATE_LIMITER_BACKEND=redis")

        self.window = int(window_seconds)
        self.limits = dict(limits or {})
        self._redis = redis.from_url(redis_url)

    def hit(self, client_id: str, action: str) -> bool:
        limit = int(self.limits.get(action, 0))
        if limit <= 0:
            return True

        window_id = int(time.time() // self.window)
        key = f"rate_limit:{client_id}:{action}:{window_id}"

        try:
            count = self._redis.incr(key)
            if count == 1:
                self._redis.expire(key, self.window + 1)
            return count <= limit
        except Exception as exc:
            # Fail closed: if Redis is unreachable, deny the request to protect the service
            raise RuntimeError(f"Redis rate limiter unavailable: {exc}") from exc


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
register_rate_limiter_backend(
    "redis",
    lambda limits, window_seconds, hits_storage: RedisRateLimiter(
        limits=limits,
        window_seconds=window_seconds,
        hits_storage=hits_storage,
    ),
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
    if _DEFAULT is None or signature != _DEFAULT_SIGNATURE:
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
