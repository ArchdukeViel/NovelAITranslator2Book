"""Cost-envelope model tests."""

from __future__ import annotations

import json

from tests.capacity_cost_model import TrafficAssumptions, build_cost_envelope
from tests.capacity_harness import CapacityHarnessConfig, FixtureOnlyCapacityHarness


def _report() -> dict[str, object]:
    return FixtureOnlyCapacityHarness(
        CapacityHarnessConfig(seed=42, request_count=80, target_peak_reader_rps=12.0)
    ).run()


def test_cost_envelope_separates_actuals_from_local_proxies() -> None:
    envelope = build_cost_envelope(
        _report(),
        assumptions=TrafficAssumptions(
            sessions_per_user_per_day=1.0,
            requests_per_session=10.0,
            peak_window_fraction=0.2,
            peak_window_seconds=3_600.0,
        ),
        source_timestamp="2026-08-24T00:00:00Z",
    )

    assert envelope["claim_boundary"]["hosted_actuals_available"] is False
    assert envelope["claim_boundary"]["production_capacity_claim"] is False
    assert all(field["status"] == "unavailable" for field in envelope["hosted_actuals"].values())
    assert envelope["local_proxies"]["application_response_bytes"]["status"] == "local_fixture_estimate"
    assert envelope["rate_domains"]["translation_provider_rps"]["key_count_does_not_multiply_quota"] is True
    assert envelope["rate_domains"]["reader_http_rps"]["independent_from_translation_provider"] is True


def test_cost_envelope_projects_named_stages_without_claiming_capacity() -> None:
    envelope = build_cost_envelope(
        _report(),
        assumptions=TrafficAssumptions(
            sessions_per_user_per_day=1.0,
            requests_per_session=10.0,
            peak_window_fraction=0.2,
            peak_window_seconds=3_600.0,
        ),
        source_timestamp="2026-08-24T00:00:00Z",
    )
    projection = envelope["projections"]["1000"]

    assert projection["status"] == "unavailable_hosted_gate"
    assert projection["daily_reader_requests"] == 10_000.0
    assert projection["peak_reader_http_rps"] == 10_000.0 * 0.2 / 3_600.0
    assert projection["is_capacity_claim"] is False
    assert envelope["projections"]["100000"]["is_capacity_claim"] is False


def test_cost_envelope_is_json_safe_and_preserves_unavailable_reasons() -> None:
    envelope = build_cost_envelope(
        _report(),
        assumptions=TrafficAssumptions(
            sessions_per_user_per_day=2.0,
            requests_per_session=4.0,
            peak_window_fraction=0.1,
            peak_window_seconds=1_800.0,
        ),
        source_timestamp="2026-08-24T00:00:00Z",
    )
    encoded = json.dumps(envelope, sort_keys=True)

    assert "api_key" not in encoded.lower()
    assert "authorization" not in encoded.lower()
    assert "source_text" not in encoded.lower()
    assert "no_approved_hosted_report_in_environment" in encoded
    assert "synthetic_fixture_counter_not_billing_attribution" in encoded
    print("COST_ENVELOPE " + encoded)
