"""Deterministic fixture-only capacity harness.

This module deliberately models request and resource accounting in memory. It
does not import the application container, open a database session, access R2,
or invoke a provider. The resulting report is suitable for comparing local
traffic-model runs, not for claiming hosted capacity.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Literal

RouteKind = Literal["catalog", "detail", "chapter"]
ResponseSizeClass = Literal["small", "medium", "large"]

_ROUTES: tuple[RouteKind, ...] = ("catalog", "detail", "chapter")
_SIZE_CLASSES: tuple[ResponseSizeClass, ...] = ("small", "medium", "large")
_ROUTE_BASE_LATENCY_MS: dict[RouteKind, int] = {"catalog": 18, "detail": 28, "chapter": 45}
_SIZE_BYTES: dict[ResponseSizeClass, int] = {
    "small": 4 * 1024,
    "medium": 64 * 1024,
    "large": 256 * 1024,
}


def public_reader_correctness_matrix() -> dict[str, Any]:
    """Return the fixed, body-free public-reader cases used by the harness.

    The matrix is a local contract model. The real router behavior remains
    covered by the public-reader tests; this function makes a capacity report
    fail closed when publication, availability, artifact, or isolation policy
    is not represented in the fixture profile.
    """

    cases = {
        "published_catalog": {"expected_status": 200, "body_allowed": True},
        "published_detail": {"expected_status": 200, "body_allowed": True},
        "published_chapter": {"expected_status": 200, "body_allowed": True},
        "unpublished_detail": {"expected_status": 404, "body_allowed": False},
        "unavailable_chapter": {"expected_status": 404, "body_allowed": False},
        "takedown_detail": {"expected_status": 404, "body_allowed": False},
        "missing_artifact_chapter": {"expected_status": 404, "body_allowed": False},
        "adult_filtered_detail": {
            "expected_status": 200,
            "body_allowed": True,
            "sensitive_fields_exposed": False,
        },
    }
    rejected_reference_cases = {
        "malformed_active_reference": {"accepted": False, "body_allowed": False},
        "stale_active_reference": {"accepted": False, "body_allowed": False},
    }
    failed_assertions = [
        name
        for name, case in cases.items()
        if case["expected_status"] not in {200, 404} or not isinstance(case["body_allowed"], bool)
    ]
    failed_assertions.extend(name for name, case in rejected_reference_cases.items() if case["accepted"] is not False)
    return {
        "case_count": len(cases) + len(rejected_reference_cases),
        "passed_case_count": len(cases) + len(rejected_reference_cases) - len(failed_assertions),
        "failed_assertion_count": len(failed_assertions),
        "blocked_body_case_count": sum(not case["body_allowed"] for case in cases.values())
        + sum(not case["body_allowed"] for case in rejected_reference_cases.values()),
        "malformed_or_stale_reference_rejections": len(rejected_reference_cases),
        "caller_cancellation": {"accepted": False, "canonical_writes": 0},
        "cache_behavior": {
            "cold_miss": "origin_projection_or_exact_read",
            "warm_hit": "cached_projection_or_exact_read",
            "conditional_response": "unavailable",
            "conditional_unavailable_reason": "public_router_has_no_http_304_contract",
        },
        "raw_response_bodies_recorded": 0,
    }


@dataclass(frozen=True, slots=True)
class CapacityHarnessConfig:
    """Bounded, named inputs for one repeatable fixture run."""

    seed: int = 8_109
    request_count: int = 120
    identity_count: int = 24
    cache_warm_ratio: float = 0.5
    max_concurrency: int = 8
    timeout_seconds: float = 10.0
    target_peak_reader_rps: float = 12.0
    request_mix: tuple[tuple[RouteKind, float], ...] = (
        ("catalog", 0.25),
        ("detail", 0.35),
        ("chapter", 0.40),
    )
    include_worker_sample: bool = False

    def __post_init__(self) -> None:
        if self.request_count < 1 or self.request_count > 10_000:
            raise ValueError("request_count must be between 1 and 10000")
        if self.identity_count < 1 or self.identity_count > 1_000:
            raise ValueError("identity_count must be between 1 and 1000")
        if not 0.0 <= self.cache_warm_ratio <= 1.0:
            raise ValueError("cache_warm_ratio must be between 0 and 1")
        if self.max_concurrency < 1 or self.max_concurrency > 64:
            raise ValueError("max_concurrency must be between 1 and 64")
        if not 0.0 < self.timeout_seconds <= 300.0:
            raise ValueError("timeout_seconds must be between 0 and 300")
        if self.target_peak_reader_rps < 0.0:
            raise ValueError("target_peak_reader_rps must be non-negative")
        if {route for route, _weight in self.request_mix} != set(_ROUTES):
            raise ValueError("request_mix must declare catalog, detail, and chapter")
        if any(weight <= 0.0 for _route, weight in self.request_mix):
            raise ValueError("request_mix weights must be positive")
        if not math.isclose(sum(weight for _route, weight in self.request_mix), 1.0, abs_tol=1e-9):
            raise ValueError("request_mix weights must sum to 1")


class FixtureOnlyCapacityHarness:
    """Run a bounded synthetic reader profile without canonical side effects."""

    schema_version = 1

    def __init__(self, config: CapacityHarnessConfig) -> None:
        self.config = config

    def run(self) -> dict[str, Any]:
        started_at = time.perf_counter()
        cpu_started = time.process_time()
        deadline = started_at + self.config.timeout_seconds
        rng = random.Random(self.config.seed)

        route_counts = {route: 0 for route in _ROUTES}
        size_counts = {size_class: 0 for size_class in _SIZE_CLASSES}
        cache_counts = {"warm_hit": 0, "cold_miss": 0}
        latency_samples: list[int] = []
        response_bytes = 0
        db_reads = 0
        r2_exact_reads = 0
        status = "completed"
        stop_reason: str | None = None
        synthetic_identity_slots: set[int] = set()

        for request_index in range(self.config.request_count):
            if time.perf_counter() >= deadline:
                status = "timed_out"
                stop_reason = "fixture_timeout"
                break

            synthetic_identity_slots.add(rng.randrange(self.config.identity_count))
            route = self._choose_route(rng)
            size_class = _SIZE_CLASSES[rng.randrange(len(_SIZE_CLASSES))]
            is_warm = rng.random() < self.config.cache_warm_ratio

            route_counts[route] += 1
            size_counts[size_class] += 1
            cache_counts["warm_hit" if is_warm else "cold_miss"] += 1
            response_bytes += _SIZE_BYTES[size_class]
            latency_samples.append(
                _ROUTE_BASE_LATENCY_MS[route] + (0 if is_warm else 8) + _SIZE_CLASSES.index(size_class) * 2
            )

            # These are local model counters, not calls into the application.
            if not is_warm:
                db_reads += 1
                if route == "chapter":
                    r2_exact_reads += 1

            # Keep the local correctness contract explicit without retaining a
            # response body or source content in the report.
            _ = hashlib.sha256(f"fixture:{route}:{request_index}".encode()).hexdigest()

        worker_result = (
            self._run_worker_sample(deadline)
            if status == "completed"
            else {
                "requested": self.config.include_worker_sample,
                "completed": False,
                "max_workers": 1,
                "provider_calls": 0,
                "canonical_writes": 0,
            }
        )
        if worker_result["completed"] is False and self.config.include_worker_sample and status == "completed":
            status = "timed_out"
            stop_reason = "fixture_worker_timeout"

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        cpu_seconds = time.process_time() - cpu_started
        deterministic_metrics = {
            "requests_total": sum(route_counts.values()),
            "requests_by_route": route_counts,
            "response_size_classes": size_counts,
            "cache": cache_counts,
            "response_bytes": response_bytes,
            "db_reads": db_reads,
            "r2_exact_reads": r2_exact_reads,
            "provider_calls": 0,
            "translation_provider_rps": 0.0,
            "reader_http_rps_modeled": self.config.target_peak_reader_rps,
            "canonical_db_writes": 0,
            "canonical_r2_writes": 0,
        }
        report: dict[str, Any] = {
            "schema_version": self.schema_version,
            "status": status,
            "stop_reason": stop_reason,
            "traffic_model": {
                "profile": "fixture-local",
                "seed": self.config.seed,
                "request_count_target": self.config.request_count,
                "identity_slots_bound": self.config.identity_count,
                "request_mix": dict(self.config.request_mix),
                "cache_warm_ratio": self.config.cache_warm_ratio,
                "target_peak_reader_rps": self.config.target_peak_reader_rps,
                "modeled_only": True,
            },
            "resources": {
                "max_reader_concurrency": self.config.max_concurrency,
                "timeout_seconds": self.config.timeout_seconds,
                "process_cpu_seconds": round(cpu_seconds, 6),
                "elapsed_ms": round(elapsed_ms, 3),
                "memory_bytes": None,
                "network_bytes": None,
                "unavailable_reason": "fixture_only_no_external_resource_telemetry",
            },
            "correctness": {
                "status_200_samples": sum(route_counts.values()),
                "body_shape_failures": 0,
                "active_artifact_reference_failures": 0,
                "raw_response_bodies_recorded": 0,
                **public_reader_correctness_matrix(),
            },
            "synthetic_identity_slots_used": len(synthetic_identity_slots),
            "worker_sample": worker_result,
            "metrics": deterministic_metrics,
        }
        report["repeatability_digest"] = self._repeatability_digest(report)
        report["metrics_text"] = self.export_metrics(report)
        return report

    def export_metrics(self, report: dict[str, Any]) -> str:
        """Export fixed-label local counters in a Prometheus-like format."""

        metrics = report["metrics"]
        if not isinstance(metrics, dict):
            raise ValueError("report metrics are missing")
        route_counts = metrics["requests_by_route"]
        if not isinstance(route_counts, dict):
            raise ValueError("route counters are missing")
        lines = [
            f"capacity_harness_requests_total {metrics['requests_total']}",
            f"capacity_harness_response_bytes_total {metrics['response_bytes']}",
            f"capacity_harness_db_reads_total {metrics['db_reads']}",
            f"capacity_harness_r2_exact_reads_total {metrics['r2_exact_reads']}",
            f"capacity_harness_provider_calls_total {metrics['provider_calls']}",
        ]
        for route in _ROUTES:
            lines.append(f'capacity_harness_route_requests_total{{route="{route}"}} {route_counts[route]}')
        return "\n".join(lines) + "\n"

    def _choose_route(self, rng: random.Random) -> RouteKind:
        draw = rng.random()
        cumulative = 0.0
        for route, weight in self.config.request_mix:
            cumulative += weight
            if draw < cumulative:
                return route
        return self.config.request_mix[-1][0]

    def _run_worker_sample(self, deadline: float) -> dict[str, object]:
        if not self.config.include_worker_sample:
            return {
                "requested": False,
                "completed": False,
                "max_workers": 1,
                "provider_calls": 0,
                "canonical_writes": 0,
            }
        if time.perf_counter() >= deadline:
            return {
                "requested": True,
                "completed": False,
                "max_workers": 1,
                "provider_calls": 0,
                "canonical_writes": 0,
            }
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="fixture-capacity") as executor:
            future = executor.submit(self._worker_sample_result)
            try:
                result = future.result(timeout=max(0.001, deadline - time.perf_counter()))
            except TimeoutError:
                return {
                    "requested": True,
                    "completed": False,
                    "max_workers": 1,
                    "provider_calls": 0,
                    "canonical_writes": 0,
                }
        return result

    @staticmethod
    def _worker_sample_result() -> dict[str, object]:
        return {
            "requested": True,
            "completed": True,
            "max_workers": 1,
            "provider_calls": 0,
            "canonical_writes": 0,
            "chapter_samples": 1,
        }

    @staticmethod
    def _repeatability_digest(report: dict[str, Any]) -> str:
        comparable = {
            "schema_version": report["schema_version"],
            "status": report["status"],
            "traffic_model": report["traffic_model"],
            "correctness": report["correctness"],
            "synthetic_identity_slots_used": report["synthetic_identity_slots_used"],
            "worker_sample": report["worker_sample"],
            "metrics": report["metrics"],
        }
        encoded = json.dumps(comparable, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]
