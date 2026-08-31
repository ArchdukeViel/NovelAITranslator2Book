"""Internal request timing boundary with no public telemetry fields."""

from __future__ import annotations

from time import perf_counter_ns

from starlette.types import ASGIApp, Receive, Scope, Send

from novelai.services.timing_contract import TimingSpan, TimingTrace, runtime_timing_traces


class RequestTimingMiddleware:
    """Record application duration while keeping serialization honest.

    The ASGI boundary cannot observe framework serialization without also
    including server/network send time, so serialization is recorded as an
    explicit unavailable span instead of being mislabeled.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        trace = TimingTrace(max_spans=2)
        started_ns = perf_counter_ns()
        try:
            await self.app(scope, receive, send)
        finally:
            finished_ns = perf_counter_ns()
            trace.add(
                TimingSpan(
                    name="application_total",
                    source="application",
                    start_offset_ms=0.0,
                    duration_ms=(finished_ns - started_ns) / 1_000_000,
                    sample_count=1,
                    critical_path=True,
                )
            )
            trace.add_unavailable(
                "serialization",
                source="application",
                reason="span_not_instrumented",
                parent="application_total",
            )
            runtime_timing_traces.record(trace)
