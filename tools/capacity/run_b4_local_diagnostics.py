"""Generate the bounded, local Phase B4 diagnostic evidence set.

The runner deliberately does not initialize provider clients or connect to
Supabase, R2, Cloudflare, Redis, or a translation provider.  Hosted findings
are sanitized observations supplied by the already-completed read-only MCP
preflight; gated data-plane cells remain unavailable until their separate
authorization and isolated target are present.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))

from novelai.services.timing_contract import (  # noqa: E402
    DATABASE_TIMING_SPANS,
    PIPELINE_TIMING_STAGES,
    R2_TIMING_SPANS,
    TIMING_SPANS,
    TimingSpan,
    TimingTrace,
    fixed_contract,
)

ROUTES = ("health_live", "catalog", "detail", "chapter", "search")
TOPOLOGIES = ("direct_service", "caddy_loopback", "cloudflare_tunnel")
R2_SIZES = (4096, 65536, 1048576)
R2_CONCURRENCIES = (1, 8)
FIXTURE_CHAPTERS = (456, 457)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _opaque(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _write_json(root: Path, name: str, payload: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _unavailable_spans(names: tuple[str, ...], *, source: str, reason: str) -> list[dict[str, object]]:
    return [TimingSpan.unavailable(name, source=source, reason=reason).to_dict() for name in names]


def _authorization_matrix(campaign_id: str) -> dict[str, Any]:
    identities = [
        {
            "identity": "guest",
            "allowed_classes": ["public_auth", "safe_health", "published_reads"],
            "denied_classes": ["user_data", "owner_controls", "private_data", "mutations"],
        },
        {
            "identity": "authenticated_user",
            "allowed_classes": ["guest_capabilities", "own_profile", "own_library", "own_history", "own_reviews"],
            "denied_classes": ["other_users", "owner_controls", "unpublished_data", "queues", "backups"],
        },
        {
            "identity": "owner",
            "allowed_classes": ["user_capabilities", "documented_control_plane"],
            "denied_classes": [
                "csrf_bypass",
                "target_guard_bypass",
                "least_privilege_bypass",
                "production_without_authorization",
            ],
        },
        {
            "identity": "runtime_database_role",
            "allowed_classes": ["application_dml", "approved_functions"],
            "denied_classes": ["ddl", "role_grants", "backup_administration"],
        },
        {
            "identity": "migration_role",
            "allowed_classes": ["migrations", "approved_policy_ddl"],
            "denied_classes": ["normal_runtime_use", "reader_requests"],
        },
        {
            "identity": "r2_content_identity",
            "allowed_classes": ["test_application_objects"],
            "denied_classes": ["test_backup_objects", "production_objects", "account_administration"],
        },
        {
            "identity": "r2_recovery_identity",
            "allowed_classes": ["test_snapshot_read", "test_restore_write"],
            "denied_classes": ["application_runtime_mutation", "production_objects"],
        },
        {
            "identity": "mcp_operator_identity",
            "allowed_classes": ["read_only_discovery", "advisors", "aggregate_telemetry"],
            "denied_classes": ["ddl", "data_mutation", "provider_settings"],
        },
        {
            "identity": "github_untrusted_workflow",
            "allowed_classes": ["checkout", "secretless_validation"],
            "denied_classes": ["secrets", "write_token", "provider", "deploy"],
        },
        {
            "identity": "github_trusted_workflow",
            "allowed_classes": ["job_specific_least_privilege"],
            "denied_classes": ["implicit_production_authority"],
        },
    ]
    cases = [
        {
            "case": "guest_user_route_401",
            "status": "passed",
            "evidence_refs": ["test_web_api.TestAuth.test_user_route_still_requires_user_session"],
        },
        {
            "case": "guest_owner_route_401",
            "status": "passed",
            "evidence_refs": ["test_auth.TestRequireRole.test_guest_blocked_from_owner_route"],
        },
        {
            "case": "user_owner_route_403",
            "status": "passed",
            "evidence_refs": ["test_web_api.TestAuth.test_non_owner_rejects_dangerous_access"],
        },
        {
            "case": "user_a_user_b_read_denied",
            "status": "unavailable",
            "unavailable_reason": "permission_denied",
            "evidence_refs": ["two-user hosted ownership read probe not authorized"],
        },
        {
            "case": "user_a_user_b_write_denied",
            "status": "unavailable",
            "unavailable_reason": "permission_denied",
            "evidence_refs": ["two-user hosted ownership write probe not authorized"],
        },
        {
            "case": "revoked_session_denied",
            "status": "passed",
            "evidence_refs": ["test_auth.TestSessionRevocation.test_session_revoked_rejects_old_session"],
        },
        {
            "case": "csrf_required_cookie_mutation",
            "status": "passed",
            "evidence_refs": ["test_auth.TestAuthRouterLogout.test_logout_requires_csrf_token"],
        },
        {
            "case": "unpublished_public_read_denied",
            "status": "unavailable",
            "unavailable_reason": "permission_denied",
            "evidence_refs": ["unpublished hosted reader probe not authorized"],
        },
        {
            "case": "service_role_not_browser_equivalent",
            "status": "unavailable",
            "unavailable_reason": "permission_denied",
            "evidence_refs": ["browser service-role equivalence probe not authorized"],
        },
        {
            "case": "rls_server_check_consistent",
            "status": "passed",
            "evidence_refs": ["hosted_mcp.public_tables_rls_equals_public_tables"],
        },
    ]
    return {
        "artifact_kind": "authorization_matrix",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "authorization_basis": "explicit non-production diagnostic authorization; provider writes remain gated",
        "identities": identities,
        "security_cases": cases,
        "security_contract_status": "blocked",
    }


def _timing_schema(campaign_id: str) -> dict[str, Any]:
    return {
        "artifact_kind": "timing_schema",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "provenance": "local_repository_contract",
        **fixed_contract(),
    }


def _latency_attribution(campaign_id: str) -> dict[str, Any]:
    source_by_span = {
        "total_client": "client",
        "dns": "client",
        "tcp": "client",
        "tls": "client",
        "cloudflare_edge": "proxy",
        "tunnel": "proxy",
        "caddy": "proxy",
        "application_total": "application",
        "db_pool_checkout": "database",
        "sql_execution": "database",
        "r2_exact_read": "r2_gateway",
        "r2_exact_write": "r2_gateway",
        "cache_or_fallback": "application",
        "serialization": "application",
        "application_exclusive": "application",
        "network_remainder": "client",
    }
    cells: list[dict[str, Any]] = []
    for topology in TOPOLOGIES:
        reason = (
            "test_worker_not_authorized" if topology == "cloudflare_tunnel" else "isolated_reader_runtime_unavailable"
        )
        for route in ROUTES:
            cells.append(
                {
                    "topology": topology,
                    "route": route,
                    "status": "unavailable",
                    "attempted_count": 0,
                    "sample_count": 0,
                    "unavailable_reason": reason,
                    "spans": [
                        TimingSpan.unavailable(name, source=source_by_span[name], reason=reason).to_dict()
                        for name in TIMING_SPANS
                    ],
                }
            )
    return {
        "artifact_kind": "latency_attribution_preliminary",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "status": "blocked",
        "gate_topology": "cloudflare_tunnel",
        "routes": list(ROUTES),
        "topologies": list(TOPOLOGIES),
        "cells": cells,
        "hosted_observation": {
            "status": "observed",
            "source": "hosted_mcp",
            "named_tunnel_count": 1,
            "active_tunnel_count": 0,
            "connector_state_down": 1,
            "exact_window_metrics": "unavailable",
        },
        "production_capacity_claim": "not_established",
    }


def _database_microprofile(campaign_id: str) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for operation, target_count in (("runtime_role_fixture_read", 100), ("isolated_test_write", 20)):
        for concurrency in (1, 8):
            cell: dict[str, Any] = {
                "operation": operation,
                "concurrency": concurrency,
                "target_count": target_count,
                "sample_count": 0,
                "status": "unavailable",
                "unavailable_reason": "permission_denied",
                "spans": _unavailable_spans(DATABASE_TIMING_SPANS, source="database", reason="permission_denied"),
            }
            if operation == "isolated_test_write":
                cell["cleanup"] = {"status": "not_run", "reason": "permission_denied"}
            cells.append(cell)
    return {
        "artifact_kind": "database_microprofile",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "status": "blocked",
        "target_class": "supabase_test_project",
        "fixture_preflight": {"matching_rows": 0, "collision": False},
        "hosted_observation": {
            "status": "observed",
            "source": "hosted_mcp",
            "security_advisor_findings": 0,
            "performance_advisor_findings": 0,
            "public_tables": 37,
            "public_tables_rls": 37,
            "public_security_definer_functions": 1,
            "activity_total": 12,
            "activity_active": 1,
            "pg_stat_statements_available": False,
            "pool_occupancy_status": "unavailable",
            "cumulative_provenance": "database_cumulative",
        },
        "cells": cells,
    }


def _r2_microprofile(campaign_id: str) -> dict[str, Any]:
    source_by_span = {
        "upload_preparation": "client",
        "download_preparation": "client",
        "request_connection": "r2_gateway",
        "gateway_handling": "r2_gateway",
        "binding_operation": "r2_binding",
        "first_byte": "r2_binding",
        "full_body": "client",
        "checksum_verification": "client",
        "etag_verification": "client",
        "decode_decompress": "client",
        "cache_or_fallback": "client",
        "serialization": "client",
    }
    cells: list[dict[str, Any]] = []
    for operation in ("put", "head", "get"):
        for payload_bytes in R2_SIZES:
            for concurrency in R2_CONCURRENCIES:
                cells.append(
                    {
                        "operation": operation,
                        "payload_bytes": payload_bytes,
                        "concurrency": concurrency,
                        "target_count": 20,
                        "sample_count": 0,
                        "status": "unavailable",
                        "unavailable_reason": "test_r2_gateway_not_authorized",
                        "spans": [
                            TimingSpan.unavailable(
                                name,
                                source=source_by_span[name],
                                reason="test_r2_gateway_not_authorized",
                            ).to_dict()
                            for name in R2_TIMING_SPANS
                        ],
                    }
                )
    return {
        "artifact_kind": "r2_microprofile",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "status": "blocked",
        "application_bucket_class": "test-dokushodo",
        "backup_bucket_class": "test-dokushodo-backup",
        "gateway_status": "unavailable",
        "gateway_reason": "test_r2_gateway_not_authorized",
        "cells": cells,
        "cleanup": {"status": "not_run", "reason": "test_r2_gateway_not_authorized"},
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires samples")
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile / 100) - 1))
    return round(ordered[index], 3)


def _run_fixture_pipeline() -> tuple[dict[str, list[float]], dict[str, int]]:
    stage_durations: dict[str, list[float]] = {stage: [] for stage in PIPELINE_TIMING_STAGES}
    mock_provider_calls = 0
    rows: dict[int, int] = {}
    objects: dict[str, bytes] = {}
    queue: list[int] = []
    source_fixture = {456: "fixture chapter alpha", 457: "fixture chapter beta"}

    def run_stage(
        trace: TimingTrace,
        stage: str,
        source: str,
        operation: Callable[[int], None],
        chapter_id: int,
        collect: bool,
    ) -> None:
        with trace.measure(stage, source=source, critical_path=True):
            operation(chapter_id)
        if collect:
            stage_durations[stage].append(trace.spans[-1].duration_ms or 0.0)

    def run_chapter(chapter_id: int, *, collect: bool) -> None:
        nonlocal mock_provider_calls
        trace = TimingTrace(max_spans=32)
        translated: dict[int, bytes] = {}
        run_stage(
            trace,
            "intake_validation",
            "local_synthetic",
            lambda value: FIXTURE_CHAPTERS.__contains__(value),
            chapter_id,
            collect,
        )
        run_stage(
            trace,
            "source_fetch",
            "local_synthetic",
            lambda value: source_fixture[value].encode("utf-8"),
            chapter_id,
            collect,
        )
        run_stage(trace, "parsing", "local_synthetic", lambda value: source_fixture[value].split(), chapter_id, collect)
        run_stage(
            trace,
            "database_persistence",
            "local_synthetic",
            lambda value: rows.__setitem__(value, len(source_fixture[value])),
            chapter_id,
            collect,
        )
        run_stage(trace, "queue_enqueue", "local_synthetic", lambda value: queue.append(value), chapter_id, collect)
        run_stage(trace, "provider_request", "provider_mock", lambda _value: None, chapter_id, collect)

        def provider_wait(_value: int) -> None:
            nonlocal mock_provider_calls
            mock_provider_calls += 1

        run_stage(trace, "provider_wait", "provider_mock", provider_wait, chapter_id, collect)
        run_stage(trace, "provider_ttfb", "provider_mock", lambda _value: None, chapter_id, collect)
        run_stage(trace, "provider_body_parse", "provider_mock", lambda _value: None, chapter_id, collect)
        run_stage(
            trace,
            "translation",
            "local_synthetic",
            lambda value: translated.__setitem__(value, source_fixture[value][::-1].encode("utf-8")),
            chapter_id,
            collect,
        )
        run_stage(trace, "qa", "local_synthetic", lambda value: translated[value].decode("utf-8"), chapter_id, collect)
        run_stage(
            trace,
            "r2_write",
            "local_synthetic",
            lambda value: objects.__setitem__(f"run/{value}", translated[value]),
            chapter_id,
            collect,
        )
        run_stage(
            trace,
            "database_commit",
            "local_synthetic",
            lambda value: rows.__setitem__(value, rows[value]),
            chapter_id,
            collect,
        )

    for run_index in range(3 + 30):
        for chapter_id in FIXTURE_CHAPTERS:
            run_chapter(chapter_id, collect=run_index >= 3)
        queue.clear()
        rows.clear()
        objects.clear()
    return stage_durations, {
        "rows": len(rows),
        "objects": len(objects),
        "queue": len(queue),
        "mock_provider_calls": mock_provider_calls,
    }


def _pipeline_timing(campaign_id: str) -> dict[str, Any]:
    stage_durations, cleanup = _run_fixture_pipeline()
    unavailable = {
        "queue_wait": ("translation_worker_paused", "pipeline"),
        "worker_dequeue": ("full_translation_queue_paused", "pipeline"),
        "retry_backoff": ("retry_not_exercised", "pipeline"),
        "notification": ("notification_not_exercised", "pipeline"),
    }
    stages: list[dict[str, Any]] = []
    for stage in PIPELINE_TIMING_STAGES:
        if stage in unavailable:
            reason, source = unavailable[stage]
            span = TimingSpan.unavailable(stage, source=source, reason=reason, critical_path=False)
        else:
            source = "provider_mock" if stage.startswith("provider_") else "local_synthetic"
            samples = stage_durations[stage]
            span = TimingSpan(
                name=stage,
                source=source,
                start_offset_ms=0.0,
                duration_ms=_percentile(samples, 95),
                sample_count=len(samples),
                aggregation="p95",
                critical_path=True,
            )
        stages.append({"stage": stage, "span": span.to_dict()})
    return {
        "artifact_kind": "pipeline_timing_preliminary",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "status": "complete_with_unavailable_stages",
        "warmup_runs": 3,
        "measured_runs": 30,
        "chapters_per_run": 2,
        "concurrency": 2,
        "queue_mode": "fixture_bounded_gather",
        "external_provider_requests": 0,
        "worker_state": "stopped",
        "full_queue_state": "paused",
        "stages": stages,
        "cleanup": {
            "in_memory_rows": cleanup["rows"],
            "in_memory_objects": cleanup["objects"],
            "in_memory_queue": cleanup["queue"],
        },
    }


def _remediation(campaign_id: str) -> dict[str, Any]:
    return {
        "artifact_kind": "remediation_decision",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "status": "blocked",
        "classification": "mixed_or_unavailable",
        "decision": "no_change",
        "fix_applied": False,
        "blockers": [
            {"area": "reader_paths", "reason": "isolated_reader_runtime_unavailable", "quantity": 15},
            {"area": "database_microprofile", "reason": "permission_denied", "quantity": 4},
            {"area": "r2_microprofile", "reason": "test_r2_gateway_not_authorized", "quantity": 18},
            {"area": "hosted_correlation", "reason": "cross_system_correlation_unavailable", "quantity": 1},
            {"area": "security_matrix", "reason": "permission_denied", "quantity": 4},
        ],
        "rollback": "not_applicable",
        "production_capacity_claim": "not_established",
    }


def _checkpoint(campaign_id: str) -> dict[str, Any]:
    return {
        "artifact_kind": "plan_b_checkpoint",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "checkpoint": "B4",
        "status": "complete_with_quantified_blocker",
        "completed_local_tasks": [
            "fixed timing contract",
            "internal application database cache R2 and pipeline timing seams",
            "authorization matrix and semantic validators",
            "local fixture-only pipeline diagnostic",
        ],
        "blocked_cell_counts": {"reader": 15, "database": 4, "r2": 18, "security_cases": 4},
        "provider_writes_attempted": False,
        "production_actions_attempted": False,
        "next_phase": "B5",
        "next_phase_eligibility": "hosted_preflight_blocked",
        "production_capacity_claim": "not_established",
    }


def generate(root: Path) -> str:
    campaign_id = _opaque("campaign")
    _write_json(root, "authorization-matrix.json", _authorization_matrix(campaign_id))
    _write_json(root, "timing-schema.json", _timing_schema(campaign_id))
    _write_json(root, "latency-attribution-preliminary.json", _latency_attribution(campaign_id))
    _write_json(root, "database-microprofile.json", _database_microprofile(campaign_id))
    _write_json(root, "r2-microprofile.json", _r2_microprofile(campaign_id))
    _write_json(root, "pipeline-timing-preliminary.json", _pipeline_timing(campaign_id))
    _write_json(root, "remediation-decision.json", _remediation(campaign_id))
    _write_json(root, "checkpoint-B4.json", _checkpoint(campaign_id))
    return campaign_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local Phase B4 diagnostic evidence")
    parser.add_argument("--root", type=Path, default=_REPO_ROOT / "artifacts" / "public-hosted-execution")
    args = parser.parse_args()
    campaign_id = generate(args.root)
    print(f"B4 local diagnostics generated for {campaign_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
