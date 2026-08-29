"""Hosted-versus-modeled cost envelope for local capacity evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TrafficAssumptions:
    """Explicit local inputs; callers must not treat them as operator approval."""

    sessions_per_user_per_day: float
    requests_per_session: float
    peak_window_fraction: float
    peak_window_seconds: float

    def __post_init__(self) -> None:
        if self.sessions_per_user_per_day <= 0.0:
            raise ValueError("sessions_per_user_per_day must be positive")
        if self.requests_per_session <= 0.0:
            raise ValueError("requests_per_session must be positive")
        if not 0.0 < self.peak_window_fraction <= 1.0:
            raise ValueError("peak_window_fraction must be between 0 and 1")
        if self.peak_window_seconds <= 0.0:
            raise ValueError("peak_window_seconds must be positive")


def build_cost_envelope(
    local_report: Mapping[str, Any],
    *,
    assumptions: TrafficAssumptions,
    source_timestamp: str,
) -> dict[str, Any]:
    """Build a report that cannot silently turn local estimates into actuals."""

    metrics = local_report.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("fixture report metrics are required")
    request_count = int(metrics.get("requests_total", 0))
    response_bytes = int(metrics.get("response_bytes", 0))
    route_counts = metrics.get("requests_by_route")
    if not isinstance(route_counts, Mapping) or request_count <= 0:
        raise ValueError("fixture report route counters are required")
    chapter_requests = int(route_counts.get("chapter", 0))
    response_bytes_per_request = response_bytes / request_count
    chapter_request_ratio = chapter_requests / request_count

    actual_unavailable = {
        "status": "unavailable",
        "value": None,
        "unit": None,
        "reason": "no_approved_hosted_report_in_environment",
        "source": "not connected",
        "source_timestamp": source_timestamp,
    }
    model_proxy = {
        "status": "local_fixture_estimate",
        "value": response_bytes_per_request,
        "unit": "bytes_per_reader_request",
        "reason": "synthetic_fixture_counter_not_billing_attribution",
        "source": "backend/tests/test_capacity_harness.py",
        "source_timestamp": source_timestamp,
    }

    stage_specs: tuple[tuple[str, int | None, str], ...] = (
        ("fixture-local", None, "completed_local_fixture"),
        ("1000", 1_000, "unavailable_hosted_gate"),
        ("10000", 10_000, "unavailable_hosted_gate"),
        ("100000", 100_000, "unavailable_hosted_gate"),
    )
    stage_projections: dict[str, Any] = {}
    for name, dau_equivalent, stage_status in stage_specs:
        if dau_equivalent is None:
            stage_projections[name] = {
                "status": stage_status,
                "dau_equivalent": None,
                "daily_reader_requests": None,
                "peak_reader_http_rps": None,
                "response_bytes_per_day": None,
                "r2_exact_reads_per_day": None,
                "is_capacity_claim": False,
            }
            continue
        daily_requests = dau_equivalent * assumptions.sessions_per_user_per_day * assumptions.requests_per_session
        stage_projections[name] = {
            "status": stage_status,
            "dau_equivalent": dau_equivalent,
            "daily_reader_requests": daily_requests,
            "peak_reader_http_rps": (
                daily_requests * assumptions.peak_window_fraction / assumptions.peak_window_seconds
            ),
            "response_bytes_per_day": daily_requests * response_bytes_per_request,
            "r2_exact_reads_per_day": daily_requests * chapter_request_ratio,
            "is_capacity_claim": False,
        }

    return {
        "schema_version": 1,
        "generated_at": source_timestamp,
        "claim_boundary": {
            "hosted_actuals_available": False,
            "production_capacity_claim": False,
            "billing_claim": False,
            "unapproved_traffic_assumptions": True,
        },
        "traffic_model": {
            "source": "backend/tests/test_capacity_harness.py",
            "source_timestamp": source_timestamp,
            "request_count": request_count,
            "response_bytes": response_bytes,
            "chapter_request_ratio": chapter_request_ratio,
            "assumptions": {
                "sessions_per_user_per_day": assumptions.sessions_per_user_per_day,
                "requests_per_session": assumptions.requests_per_session,
                "peak_window_fraction": assumptions.peak_window_fraction,
                "peak_window_seconds": assumptions.peak_window_seconds,
                "approved": False,
            },
        },
        "hosted_actuals": {
            "supabase_billed_egress": actual_unavailable,
            "r2_class_a_operations": actual_unavailable,
            "r2_class_b_operations": actual_unavailable,
            "r2_storage_bytes": actual_unavailable,
            "provider_token_usage": actual_unavailable,
            "provider_quota_usage": actual_unavailable,
            "compute_usage": actual_unavailable,
            "observability_usage": actual_unavailable,
        },
        "local_proxies": {
            "application_response_bytes": model_proxy,
            "database_read_counter": {
                "status": "local_fixture_counter",
                "value": int(metrics.get("db_reads", 0)),
                "unit": "reads",
                "source": "backend/tests/test_capacity_harness.py",
                "source_timestamp": source_timestamp,
            },
            "r2_exact_read_counter": {
                "status": "local_fixture_counter",
                "value": int(metrics.get("r2_exact_reads", 0)),
                "unit": "reads",
                "source": "backend/tests/test_capacity_harness.py",
                "source_timestamp": source_timestamp,
            },
        },
        "rate_domains": {
            "translation_provider_rps": {
                "fixture_value": float(metrics.get("translation_provider_rps", 0.0)),
                "hosted_actual": actual_unavailable,
                "key_count_does_not_multiply_quota": True,
            },
            "reader_http_rps": {
                "fixture_modeled_peak": float(metrics.get("reader_http_rps_modeled", 0.0)),
                "hosted_actual": actual_unavailable,
                "independent_from_translation_provider": True,
            },
        },
        "contributor_pool": {
            "status": "local_synthetic_only",
            "pool_size": None,
            "eligible_credential_count": None,
            "verified_quota_domain_count": 0,
            "quota_domain_assumption": "shared_project_unverified",
            "source": "T-024 local tests; no live credential activation",
            "source_timestamp": source_timestamp,
        },
        "projections": stage_projections,
        "uncertainty": [
            "Supabase billed egress report is unavailable.",
            "R2 operation/storage billing data is unavailable.",
            "Provider token/quota and price sources are unavailable.",
            "Traffic assumptions are local and unapproved.",
            "Fixture response bytes are not hosted response-byte attribution.",
        ],
    }
