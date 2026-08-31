from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import text
from starlette.types import Message, Receive, Scope, Send

from novelai.api.middleware.timing import RequestTimingMiddleware
from novelai.db.engine import dispose_engines, get_engine
from novelai.services.timing_contract import (
    MONOTONIC_CLOCK,
    PIPELINE_TIMING_STAGES,
    TIMING_SPANS,
    TimingInterval,
    TimingSpan,
    TimingTrace,
    exclusive_duration_ms,
    fixed_contract,
    network_remainder_ms,
    runtime_timing_traces,
)


def test_fixed_contract_has_no_identity_or_payload_fields() -> None:
    contract = fixed_contract()

    assert contract["schema_version"] == 1
    assert contract["clock"] == MONOTONIC_CLOCK
    assert tuple(cast(tuple[str, ...], contract["spans"])) == TIMING_SPANS
    assert tuple(cast(tuple[str, ...], contract["pipeline_stages"])) == PIPELINE_TIMING_STAGES
    assert all(
        field not in cast(tuple[str, ...], contract["spans"]) for field in ("user_id", "url", "sql", "object_key")
    )


def test_nested_intervals_subtract_the_union_once() -> None:
    parent = TimingInterval(start_offset_ms=10, duration_ms=100)
    children = (
        TimingInterval(start_offset_ms=20, duration_ms=40),
        TimingInterval(start_offset_ms=45, duration_ms=40),
        TimingInterval(start_offset_ms=90, duration_ms=10),
    )

    assert exclusive_duration_ms(parent, children) == 25.0
    assert network_remainder_ms(parent, children) == 25.0


def test_nested_intervals_reject_outside_and_negative_residual_inputs() -> None:
    parent = TimingInterval(start_offset_ms=0, duration_ms=20)

    with pytest.raises(ValueError, match="nested"):
        exclusive_duration_ms(parent, [TimingInterval(start_offset_ms=19, duration_ms=2)])

    with pytest.raises(ValueError, match="finite non-negative"):
        TimingInterval(start_offset_ms=-1, duration_ms=1)


def test_unavailable_spans_require_fixed_reason_and_never_have_duration() -> None:
    span = TimingSpan.unavailable(
        "r2_exact_read",
        source="r2_gateway",
        reason="test_r2_gateway_not_authorized",
    )
    payload = span.to_dict()

    assert payload["available"] is False
    assert payload["duration_ms"] is None
    assert payload["sample_count"] == 0
    assert payload["unavailable_reason"] == "test_r2_gateway_not_authorized"

    with pytest.raises(ValueError, match="fixed reason"):
        TimingSpan.unavailable("r2_exact_read", source="r2_gateway", reason="guess")


def test_trace_uses_monotonic_clock_and_bounded_fixed_fields() -> None:
    trace = TimingTrace(max_spans=4)
    with (
        trace.measure("application_total", source="application", critical_path=True),
        trace.measure("sql_execution", source="database", parent="application_total"),
    ):
        pass

    payload = trace.to_dict()
    assert payload["clock"] == MONOTONIC_CLOCK
    spans = cast(list[dict[str, object]], payload["spans"])
    assert len(spans) == 2
    assert all(
        set(span)
        == {
            "name",
            "source",
            "parent",
            "clock",
            "start_offset_ms",
            "duration_ms",
            "sample_count",
            "aggregation",
            "available",
            "unavailable_reason",
            "critical_path",
        }
        for span in spans
    )
    assert "secret" not in str(payload).lower()


@pytest.mark.asyncio
async def test_request_middleware_records_application_and_explicit_serialization_gap() -> None:
    messages: list[Message] = []

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    runtime_timing_traces.clear()
    middleware = RequestTimingMiddleware(application)
    scope: Scope = {"type": "http", "method": "GET", "path": "/health/live"}
    await middleware(scope, receive, send)

    trace = runtime_timing_traces.snapshot()[-1]
    spans = {span.name: span for span in trace.spans}
    assert messages[-1]["type"] == "http.response.body"
    assert spans["application_total"].available is True
    assert spans["serialization"].available is False
    assert spans["serialization"].unavailable_reason == "span_not_instrumented"


def test_sqlalchemy_timing_records_statement_and_pool_granularity_gap() -> None:
    runtime_timing_traces.clear()
    engine = get_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
        spans = [span for trace in runtime_timing_traces.snapshot() for span in trace.spans]
        names = {span.name for span in spans}
        assert "sql_execution" in names
        pool_span = next(span for span in spans if span.name == "db_pool_checkout")
        assert pool_span.available is False
        assert pool_span.unavailable_reason == "pooler_granularity_unavailable"
    finally:
        dispose_engines()
