from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

LAYER_NAMES = (
    "proxy_connect",
    "proxy_upstream",
    "application",
    "db_checkout",
    "db_statement",
    "db_commit",
    "r2_exact_read",
    "serialization",
    "network_remainder",
)


def attribute_route_latency(timings: Mapping[str, float | None]) -> dict[str, Any]:
    """Build a fixed-label, non-overlapping attribution contract."""
    if set(timings) != set(LAYER_NAMES):
        raise ValueError("timings must contain every fixed attribution layer")

    cursor = 0.0
    layers: dict[str, dict[str, Any]] = {}
    observed: dict[str, float] = {}
    for name in LAYER_NAMES:
        value = timings[name]
        if value is None:
            layers[name] = {
                "status": "unavailable",
                "unavailable_reason": "runtime_state_unavailable",
            }
            continue
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} timing must be finite and non-negative")
        duration = float(value)
        layers[name] = {
            "status": "observed",
            "p50_ms": duration,
            "p95_ms": duration,
            "p99_ms": duration,
            "interval_start_ms": cursor,
            "interval_end_ms": cursor + duration,
        }
        observed[name] = duration
        cursor += duration

    return {
        "schema_version": 1,
        "campaign_id": "camp-test",
        "routes": [
            {
                "route": "detail",
                "layers": layers,
                "largest_contributor": max(observed.items(), key=lambda item: item[1])[0]
                if observed
                else "unavailable",
            }
        ],
    }


def validate_attribution_contract(payload: dict[str, Any]) -> bool:
    if payload.get("schema_version") != 1 or not payload.get("campaign_id"):
        return False
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        return False
    for route in routes:
        layers = route.get("layers") if isinstance(route, dict) else None
        if not isinstance(layers, dict) or set(layers) != set(LAYER_NAMES):
            return False
        previous_end = 0.0
        observed_names: list[str] = []
        for name in LAYER_NAMES:
            layer = layers[name]
            if not isinstance(layer, dict):
                return False
            status = layer.get("status")
            if status == "unavailable":
                if not layer.get("unavailable_reason"):
                    return False
                continue
            if status != "observed":
                return False
            values = [layer.get(key) for key in ("p50_ms", "p95_ms", "p99_ms")]
            if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in values):
                return False
            start = layer.get("interval_start_ms")
            end = layer.get("interval_end_ms")
            if (
                not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
                or start < previous_end
                or end < start
            ):
                return False
            previous_end = float(end)
            observed_names.append(name)
        largest = route.get("largest_contributor")
        if observed_names and largest not in observed_names:
            return False
        if not observed_names and largest != "unavailable":
            return False
    return True


def test_reader_latency_attribution():
    timings = {
        "proxy_connect": 2.0,
        "proxy_upstream": 20.0,
        "application": 15.0,
        "db_checkout": 3.0,
        "db_statement": 25.0,
        "db_commit": 1.0,
        "r2_exact_read": 180.0,
        "serialization": 10.0,
        "network_remainder": 4.0,
    }
    result = attribute_route_latency(timings)
    assert result["schema_version"] == 1
    assert result["routes"][0]["largest_contributor"] == "r2_exact_read"
    assert validate_attribution_contract(result) is True


def test_reader_latency_attribution_accepts_explicit_unavailable_layers():
    result = attribute_route_latency({name: None for name in LAYER_NAMES})
    assert validate_attribution_contract(result) is True


def test_reader_latency_attribution_rejects_overlap_and_missing_layers():
    result = attribute_route_latency({name: 1.0 for name in LAYER_NAMES})
    result["routes"][0]["layers"]["application"]["interval_start_ms"] = 0.0
    assert validate_attribution_contract(result) is False

    incomplete = attribute_route_latency({name: 1.0 for name in LAYER_NAMES})
    del incomplete["routes"][0]["layers"]["network_remainder"]
    assert validate_attribution_contract(incomplete) is False
