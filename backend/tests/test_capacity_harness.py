"""Fixture-only capacity harness coverage."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.capacity_harness import (
    CapacityHarnessConfig,
    FixtureOnlyCapacityHarness,
    public_reader_correctness_matrix,
)


def test_harness_is_repeatable_for_same_seed_and_configuration() -> None:
    config = CapacityHarnessConfig(seed=42, request_count=80, cache_warm_ratio=0.5)

    first = FixtureOnlyCapacityHarness(config).run()
    second = FixtureOnlyCapacityHarness(config).run()

    assert first["repeatability_digest"] == second["repeatability_digest"]
    assert first["metrics"] == second["metrics"]
    assert first["traffic_model"] == second["traffic_model"]
    assert first["resources"]["memory_bytes"] is None
    assert first["resources"]["network_bytes"] is None


def test_harness_models_request_mix_cache_modes_sizes_and_fixed_metrics() -> None:
    report = FixtureOnlyCapacityHarness(CapacityHarnessConfig(seed=7, request_count=240, cache_warm_ratio=0.5)).run()
    metrics = report["metrics"]

    assert report["status"] == "completed"
    assert metrics["requests_total"] == 240
    assert set(metrics["requests_by_route"]) == {"catalog", "detail", "chapter"}
    assert all(count > 0 for count in metrics["requests_by_route"].values())
    assert metrics["cache"]["warm_hit"] > 0
    assert metrics["cache"]["cold_miss"] > 0
    assert all(count > 0 for count in metrics["response_size_classes"].values())
    assert metrics["canonical_db_writes"] == 0
    assert metrics["canonical_r2_writes"] == 0
    assert metrics["provider_calls"] == 0

    metrics_text = report["metrics_text"]
    assert 'route="catalog"' in metrics_text
    assert 'route="detail"' in metrics_text
    assert 'route="chapter"' in metrics_text
    assert "identity-" not in metrics_text
    assert "source_text" not in metrics_text


def test_harness_worker_sample_is_single_bounded_fixture_job() -> None:
    report = FixtureOnlyCapacityHarness(
        CapacityHarnessConfig(seed=9, request_count=16, include_worker_sample=True)
    ).run()
    worker = report["worker_sample"]

    assert worker["requested"] is True
    assert worker["completed"] is True
    assert worker["max_workers"] == 1
    assert worker["chapter_samples"] == 1
    assert worker["provider_calls"] == 0
    assert worker["canonical_writes"] == 0


def test_harness_public_reader_matrix_fails_closed_without_raw_bodies() -> None:
    matrix = public_reader_correctness_matrix()

    assert matrix["failed_assertion_count"] == 0
    assert matrix["passed_case_count"] == matrix["case_count"]
    assert matrix["malformed_or_stale_reference_rejections"] == 2
    assert matrix["caller_cancellation"] == {"accepted": False, "canonical_writes": 0}
    assert matrix["cache_behavior"]["conditional_response"] == "unavailable"
    assert matrix["raw_response_bodies_recorded"] == 0


def test_harness_timeout_is_truthful_and_has_no_side_effects() -> None:
    report = FixtureOnlyCapacityHarness(
        CapacityHarnessConfig(seed=1, request_count=10_000, timeout_seconds=0.000001)
    ).run()

    assert report["status"] == "timed_out"
    assert report["stop_reason"] == "fixture_timeout"
    assert report["metrics"]["canonical_db_writes"] == 0
    assert report["metrics"]["canonical_r2_writes"] == 0
    assert report["metrics"]["provider_calls"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_count": 0},
        {"identity_count": 0},
        {"cache_warm_ratio": 1.1},
        {"request_mix": (("catalog", 1.0),)},
    ],
)
def test_harness_rejects_unbounded_or_ambiguous_traffic_inputs(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        CapacityHarnessConfig(**kwargs)


def test_report_is_json_serializable_and_contains_no_raw_fixture_body() -> None:
    report = FixtureOnlyCapacityHarness(CapacityHarnessConfig(seed=11, request_count=12)).run()
    encoded = json.dumps(report, sort_keys=True)

    assert "Synthetic local response body" not in encoded
    assert "authorization" not in encoded.lower()
    assert "api_key" not in encoded.lower()
