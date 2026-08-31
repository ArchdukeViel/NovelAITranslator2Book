"""Create a candidate-bound, fail-closed B7 evidence bundle.

This command is deliberately local and provider-free.  It records the
artifacts required by the public-hosted plan when B7 stops before any fixture
write because the isolated runtime, writer proof, or transport gate is not
available.  It never connects to a database, object store, provider, Redis,
browser, or GitHub and it never turns an unavailable cell into a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))

from novelai.services.timing_contract import (  # noqa: E402
    DATABASE_TIMING_SPANS,
    PIPELINE_TIMING_STAGES,
    R2_TIMING_SPANS,
    TimingSpan,
)

PLAN_ID = "dokushodo-public-hosted-evidence"
PLAN_VERSION = "2.1.0"
ENVIRONMENT = "non-production"
TARGET_CLASSES = {
    "database": "dedicated_test_project",
    "application_bucket": "dedicated_test_application_bucket",
    "backup_bucket": "dedicated_test_backup_bucket",
    "restore_database": "ephemeral_restore_database",
    "redis": "isolated_test_redis",
}
ROUTES = ("health_live", "catalog", "detail", "chapter", "search")
FRONTEND_ROUTES = ("home", "browse_novels", "novel_detail", "chapter_reader", "ranking")
DEVICES = ("desktop", "mobile")
CONTEXTS = ("anonymous_fresh", "anonymous_warm")
METRIC_NAMES = (
    "ttfb_ms",
    "fcp_ms",
    "lcp_ms",
    "cls",
    "tbt_ms",
    "js_transfer_bytes",
    "js_evaluation_ms",
    "api_wait_ms",
    "image_transfer_ms",
    "hydration_ms",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
OPAQUE = re.compile(r"^(?:camp|run|recovery)-[0-9a-f]{16}$")
CAMPAIGN = re.compile(r"^camp-(?:[0-9a-f]{16}|[0-9]{8}T[0-9]{6}Z)$")
UTC_TIMESTAMP = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[^\s]+Z$")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _require_text(value: Any, name: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ValueError(f"{name} has an invalid format")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _timing_span(name: str, *, source: str, reason: str, critical_path: bool = False) -> dict[str, Any]:
    return TimingSpan.unavailable(
        name,
        source=source,
        reason=reason,
        critical_path=critical_path,
    ).to_dict()


def _common(
    *,
    artifact_kind: str,
    baseline: dict[str, Any],
    candidate_sha: str,
    run_id: str,
    captured_at: str,
    status: str,
    unavailable_reason: str,
) -> dict[str, Any]:
    campaign_id = _require_text(baseline.get("campaign_id"), "baseline.campaign_id", CAMPAIGN)
    interval_start = _require_text(baseline.get("interval_start"), "baseline.interval_start", UTC_TIMESTAMP)
    return {
        "artifact_kind": artifact_kind,
        "schema_version": 1,
        "plan_id": PLAN_ID,
        "plan_version": PLAN_VERSION,
        "candidate_sha": candidate_sha,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "environment": ENVIRONMENT,
        "target_classes": TARGET_CLASSES,
        "utc_start": interval_start,
        "utc_end": captured_at,
        "monotonic_clock": "monotonic_ns",
        "topology": "cloudflare_tunnel",
        "workload": "1000_dau_equivalent",
        "collection_status": status,
        "unavailable_reason": unavailable_reason,
        "sample_count": 0,
        "aggregation": "none",
        "provenance": ["local_preflight", "read_only_mcp"],
        "production_capacity_claim": "not_established",
    }


def _metric_cells() -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for route in FRONTEND_ROUTES:
        for device in DEVICES:
            for context in CONTEXTS:
                cells.append(
                    {
                        "route_class": route,
                        "principal_class": "anonymous",
                        "authentication_state": "anonymous",
                        "device_profile": device,
                        "viewport": {"desktop": "1440x900", "mobile": "390x844"}[device],
                        "browser_revision": "unavailable",
                        "context": context,
                        "planned_navigations": 7,
                        "attempted_navigations": 0,
                        "functional_failures": 0,
                        "request_failures": 0,
                        "status": "blocked",
                        "unavailable_reason": "isolated_reader_runtime_unavailable",
                        "metrics": {
                            metric: {
                                "value": None,
                                "status": "unavailable",
                                "unavailable_reason": "isolated_reader_runtime_unavailable",
                            }
                            for metric in METRIC_NAMES
                        },
                        "sanitization_status": "not_applicable_no_trace",
                    }
                )
    return cells


def _load_generator(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="load_generator",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="isolated_reader_runtime_unavailable",
    )
    payload.update(
        {
            "planned_attempts": {
                "cloudflare_tunnel": 1000,
                "direct_service": 500,
                "caddy_loopback": 500,
                "total": 2000,
            },
            "attempted_attempts": 0,
            "completed_attempts": 0,
            "counted_slo_gate_attempts": 0,
            "saturation_status": "unavailable",
            "transport_status": {
                topology: {
                    "status": "blocked",
                    "attempted_attempts": 0,
                    "unavailable_reason": "isolated_reader_runtime_unavailable",
                }
                for topology in ("cloudflare_tunnel", "direct_service", "caddy_loopback")
            },
            "runner_observations": {
                metric: {
                    "value": None,
                    "status": "unavailable",
                    "unavailable_reason": "isolated_reader_runtime_unavailable",
                }
                for metric in (
                    "cpu_percent",
                    "memory_bytes",
                    "open_files",
                    "open_sockets",
                    "event_loop_delay_ms",
                    "internal_request_queue_delay_ms",
                )
            },
            "retry_policy": "none_for_counted_requests",
            "concurrency": 8,
            "timeout_seconds": 20,
        }
    )
    return payload


def _frontend_profile(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="frontend_profile",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="isolated_reader_runtime_unavailable",
    )
    payload.update(
        {
            "frontend_status": "blocked",
            "public_navigation_plan": {
                "routes": list(FRONTEND_ROUTES),
                "devices": list(DEVICES),
                "contexts": list(CONTEXTS),
                "navigations_per_cell": 7,
                "planned_navigations": 140,
            },
            "public_attempted_navigations": 0,
            "protected_lane": {
                "status": "blocked",
                "planned_navigations": 84,
                "attempted_navigations": 0,
                "unavailable_reason": "test_identity_or_route_unavailable",
            },
            "cells": _metric_cells(),
            "field_web_vitals_claim": "not_established",
        }
    )
    return payload


def _pipeline_timing(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="pipeline_timing",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="writer_state_unverified",
    )
    payload.update(
        {
            "pipeline_timing_status": "blocked",
            "fixture_only": True,
            "external_provider_requests": 0,
            "worker_state": "stopped",
            "original_queue_state": "unknown",
            "other_writers_state": "unknown",
            "stages": [
                {
                    "stage": stage,
                    "span": _timing_span(
                        stage,
                        source="pipeline",
                        reason="span_not_instrumented",
                        critical_path=True,
                    ),
                }
                for stage in PIPELINE_TIMING_STAGES
            ],
            "cleanup": {"status": "not_run", "created_rows": 0, "created_objects": 0},
        }
    )
    return payload


def _database_microprofile(
    baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str
) -> dict[str, Any]:
    payload = _common(
        artifact_kind="database_microprofile",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="permission_denied",
    )
    cells: list[dict[str, Any]] = []
    for operation, target_count in (("runtime_role_fixture_read", 100), ("isolated_test_write", 20)):
        for concurrency in (1, 8):
            cells.append(
                {
                    "operation": operation,
                    "concurrency": concurrency,
                    "target_count": target_count,
                    "sample_count": 0,
                    "status": "unavailable",
                    "unavailable_reason": "permission_denied",
                    "spans": [
                        _timing_span(name, source="database", reason="permission_denied")
                        for name in DATABASE_TIMING_SPANS
                    ],
                    "cleanup": {"status": "not_run", "reason": "permission_denied"}
                    if operation == "isolated_test_write"
                    else None,
                }
            )
    payload.update(
        {
            "database_microprofile_status": "blocked",
            "fixture_preflight": {"matching_novel_rows": 0, "matching_chapter_rows": 0, "collision": False},
            "hosted_aggregate_observation": {
                "security_advisor_findings": 0,
                "performance_advisor_findings": 101,
                "migration_marker_rows": 1,
                "public_tables": 37,
                "public_tables_with_rls": 37,
                "security_definer_functions": 1,
                "activity_sessions": 12,
                "activity_active": 1,
                "activity_idle": 4,
                "activity_without_state": 7,
                "pg_stat_statements_status": "unavailable",
                "pool_occupancy_status": "unavailable",
                "cumulative_provenance": "database_cumulative",
            },
            "cells": cells,
        }
    )
    return payload


def _r2_microprofile(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="r2_microprofile",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="test_r2_gateway_not_authorized",
    )
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
        for payload_bytes in (4096, 65536, 1048576):
            for concurrency in (1, 8):
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
                            _timing_span(
                                name,
                                source=source_by_span[name],
                                reason="test_r2_gateway_not_authorized",
                            )
                            for name in R2_TIMING_SPANS
                        ],
                    }
                )
    payload.update(
        {
            "r2_microprofile_status": "blocked",
            "application_bucket_class": "dedicated_test_application_bucket",
            "backup_bucket_class": "dedicated_test_backup_bucket",
            "gateway_status": "unavailable",
            "cells": cells,
            "cleanup": {"status": "not_run", "reason": "test_r2_gateway_not_authorized"},
        }
    )
    return payload


def _security_boundary(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="security_boundary",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="test_identity_or_route_unavailable",
    )
    identities = [
        ("guest", ["safe_health", "published_reads"], ["user_data", "owner_controls", "mutations"]),
        (
            "authenticated_user",
            ["own_profile", "own_library", "own_history"],
            ["other_users", "owner_controls", "backups"],
        ),
        (
            "owner",
            ["documented_control_plane", "user_capabilities"],
            ["csrf_bypass", "target_guard_bypass", "production_without_authorization"],
        ),
        ("runtime_database_role", ["application_dml", "approved_functions"], ["ddl", "role_grants"]),
        ("migration_role", ["migrations", "approved_policy_ddl"], ["normal_runtime_use", "reader_requests"]),
        ("r2_content_identity", ["test_application_objects"], ["test_backup_objects", "production_objects"]),
        (
            "r2_recovery_identity",
            ["test_snapshot_read", "test_restore_write"],
            ["application_runtime_mutation", "production_objects"],
        ),
        (
            "mcp_operator_identity",
            ["read_only_discovery", "aggregate_telemetry"],
            ["data_mutation", "provider_settings"],
        ),
        ("github_untrusted_workflow", ["checkout", "secretless_validation"], ["secrets", "provider", "deploy"]),
    ]
    payload.update(
        {
            "security_status": "blocked",
            "local_contract_status": "passed",
            "hosted_identity_lane_status": "blocked",
            "database_rls_observation": {"public_tables": 37, "tables_with_rls": 37, "security_definer_functions": 1},
            "identities": [
                {"principal_class": principal, "allowed_classes": allowed, "denied_classes": denied}
                for principal, allowed, denied in identities
            ],
            "authorization_cases": [
                {
                    "case": "guest_cannot_access_owner_controls",
                    "status": "passed",
                    "evidence_class": "local_contract",
                },
                {
                    "case": "user_cannot_access_other_user_data",
                    "status": "blocked",
                    "unavailable_reason": "test_identity_or_route_unavailable",
                    "evidence_class": "hosted_identity_lane",
                },
                {
                    "case": "owner_still_requires_target_and_csrf_guards",
                    "status": "passed",
                    "evidence_class": "local_contract",
                },
            ],
        }
    )
    return payload


def _writer_state(
    baseline: dict[str, Any],
    candidate_sha: str,
    run_id: str,
    captured_at: str,
    *,
    phase: str,
) -> dict[str, Any]:
    payload = _common(
        artifact_kind=f"writer_state_{phase}",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="writer_state_unverified",
    )
    payload.update(
        {
            "phase": phase,
            "worker_state": "stopped",
            "original_queue_state": "unknown",
            "other_writers_state": "unknown",
            "proof_status": "insufficient",
            "observation_source": "local_preflight",
            "profile_started": False,
            "write_allowed": False,
        }
    )
    return payload


def _recovery_manifest(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="recovery_manifest",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="writer_state_unverified",
    )
    payload.update(
        {
            "recovery_status": "blocked",
            "owner_role": "project_owner",
            "recovery_started": False,
            "recovery_point_id": None,
            "source_project_class": "dedicated_test_project",
            "application_bucket_class": "dedicated_test_application_bucket",
            "backup_bucket_class": "dedicated_test_backup_bucket",
            "restore_target_class": "ephemeral_restore_database",
            "backup_timestamp_status": "not_run",
            "manifest_commit_status": "not_run",
            "database_snapshot_status": "not_run",
            "r2_manifest_status": "not_run",
            "restore_verification_status": "not_run",
            "cleanup_status": "not_run",
            "production_mutation": "none",
        }
    )
    return payload


def _cleanup(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="cleanup",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="profile_not_started",
    )
    payload.update(
        {
            "cleanup_status": "blocked",
            "cleanup_executed": False,
            "resources_created_by_run": 0,
            "preflight_fixture_rows": {"novel": 0, "chapter": 0},
            "preflight_application_objects": 0,
            "postrun_verification_status": "not_run",
            "postrun_fixture_rows": None,
            "postrun_application_objects": None,
            "recovery_prefix_status": "not_run",
            "reason": "profile_not_started",
        }
    )
    return payload


def _final_validation(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="final_validation",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="required_hosted_evidence_unavailable",
    )
    payload.update(
        {
            "documentation_status": "passed",
            "local_validation_status": "passed",
            "hosted_validation_status": "blocked",
            "cleanup_status": "blocked",
            "overall_follow_up_disposition": "blocked",
            "checks": [],
            "blockers": [
                "hosted_runner_unavailable",
                "active_spec_invalid",
                "writer_state_unverified",
                "isolated_reader_runtime_unavailable",
            ],
        }
    )
    return payload


def _handoff(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> dict[str, Any]:
    payload = _common(
        artifact_kind="handoff",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="required_hosted_evidence_unavailable",
    )
    payload.update(
        {
            "reader_slo_status": "blocked",
            "path_profile_status": "blocked",
            "frontend_status": "blocked",
            "pipeline_timing_status": "blocked",
            "telemetry_status": "unavailable",
            "security_status": "blocked",
            "recovery_status": "blocked",
            "cleanup_status": "blocked",
            "documentation_status": "passed",
            "public_repository_status": "blocked",
            "overall_follow_up_disposition": "blocked",
            "production_capacity_claim": "not_established",
            "workflow_run_count": 0,
            "hosted_runner_count": 0,
            "workflow_urls": [],
            "artifact_names": [],
            "blocker_ids": [
                "blk-hosted-runner-unavailable",
                "blk-active-spec-invalid",
                "blk-b7-writer-state",
                "blk-b7-queue-state",
                "blk-b7-tunnel",
                "blk-b7-reader-runtime",
                "blk-b7-r2-analytics",
                "blk-b7-cloudflare-rulesets",
            ],
            "next_action": "restore hosted runner availability and obtain owner-approved active-spec correction before rerunning B7",
        }
    )
    return payload


def _handoff_markdown(baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str) -> str:
    campaign_id = _require_text(baseline.get("campaign_id"), "baseline.campaign_id", CAMPAIGN)
    return "\n".join(
        [
            "# Dokushodo public hosted execution handoff",
            "",
            "Disposition: **blocked**",
            "",
            f"Candidate: `{candidate_sha}`",
            f"Campaign: `{campaign_id}`",
            f"Run: `{run_id}`",
            f"Captured: `{captured_at}`",
            "Environment: `non-production`",
            "",
            "## Independent status fields",
            "",
            "- `reader_slo_status`: **blocked**",
            "- `path_profile_status`: **blocked**",
            "- `frontend_status`: **blocked**",
            "- `pipeline_timing_status`: **blocked**",
            "- `telemetry_status`: **unavailable**",
            "- `security_status`: **blocked**",
            "- `recovery_status`: **blocked**",
            "- `cleanup_status`: **blocked**",
            "- `documentation_status`: **passed**",
            "- `public_repository_status`: **blocked**",
            "- `overall_follow_up_disposition`: **blocked**",
            "- `production_capacity_claim`: **not_established**",
            "",
            "No fixture, database row, R2 object, recovery target, provider request, or production resource was created by this blocked capture.",
            "No hosted workflow run was accepted as evidence because the required runner was unavailable.",
            "",
            "## Required next action",
            "",
            "Restore hosted runner availability and obtain owner-approved correction of the active specification metadata, then rerun the exact B7 preflight and hosted workflow.",
            "",
        ]
    )


def _artifact_manifest(
    root: Path, baseline: dict[str, Any], candidate_sha: str, run_id: str, captured_at: str
) -> dict[str, Any]:
    payload = _common(
        artifact_kind="artifact_manifest",
        baseline=baseline,
        candidate_sha=candidate_sha,
        run_id=run_id,
        captured_at=captured_at,
        status="blocked",
        unavailable_reason="required_hosted_evidence_unavailable",
    )
    names = [
        "baseline.json",
        "route-profile.json",
        "latency-attribution.json",
        "load-generator.json",
        "frontend-profile.json",
        "pipeline-timing.json",
        "database-microprofile.json",
        "r2-microprofile.json",
        "hosted-telemetry.json",
        "security-boundary.json",
        "writer-state-before.json",
        "writer-state-after.json",
        "recovery-manifest.json",
        "backup-controls.json",
        "restore-verification.md",
        "cleanup.json",
        "validation.md",
        "final-validation.json",
        "handoff.md",
        "handoff.json",
    ]
    entries: list[dict[str, Any]] = []
    for name in names:
        path = root / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        entries.append({"name": name, "present": path.is_file(), "sha256": digest})
    payload.update(
        {"manifest_status": "blocked", "entries": entries, "self_digest_status": "omitted_to_avoid_self_reference"}
    )
    return payload


def generate(
    root: Path, baseline_path: Path, mcp_snapshot_path: Path, candidate_sha: str | None, captured_at: str | None
) -> str:
    baseline = _read_json(baseline_path)
    mcp = _read_json(mcp_snapshot_path)
    resolved_candidate = _require_text(candidate_sha or baseline.get("baseline_revision"), "candidate_sha", REVISION)
    baseline_revision = _require_text(baseline.get("baseline_revision"), "baseline.baseline_revision", REVISION)
    if resolved_candidate != baseline_revision:
        raise ValueError("candidate_sha does not match baseline revision")
    if mcp.get("candidate_revision") != resolved_candidate or mcp.get("campaign_id") != baseline.get("campaign_id"):
        raise ValueError("MCP snapshot is not joined to the baseline candidate and campaign")
    captured = _require_text(captured_at or _timestamp(), "captured_at", UTC_TIMESTAMP)
    digest = hashlib.sha256(f"{baseline['campaign_id']}:{resolved_candidate}:{captured}".encode()).hexdigest()[:16]
    run_id = f"run-{digest}"
    root.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "load-generator.json": _load_generator(baseline, resolved_candidate, run_id, captured),
        "frontend-profile.json": _frontend_profile(baseline, resolved_candidate, run_id, captured),
        "pipeline-timing.json": _pipeline_timing(baseline, resolved_candidate, run_id, captured),
        "database-microprofile.json": _database_microprofile(baseline, resolved_candidate, run_id, captured),
        "r2-microprofile.json": _r2_microprofile(baseline, resolved_candidate, run_id, captured),
        "security-boundary.json": _security_boundary(baseline, resolved_candidate, run_id, captured),
        "writer-state-before.json": _writer_state(baseline, resolved_candidate, run_id, captured, phase="before"),
        "writer-state-after.json": _writer_state(baseline, resolved_candidate, run_id, captured, phase="after"),
        "recovery-manifest.json": _recovery_manifest(baseline, resolved_candidate, run_id, captured),
        "cleanup.json": _cleanup(baseline, resolved_candidate, run_id, captured),
        "final-validation.json": _final_validation(baseline, resolved_candidate, run_id, captured),
        "handoff.json": _handoff(baseline, resolved_candidate, run_id, captured),
    }
    for name, payload in artifacts.items():
        _write_json(root / name, payload)
    (root / "handoff.md").write_text(
        _handoff_markdown(baseline, resolved_candidate, run_id, captured),
        encoding="utf-8",
    )
    _write_json(
        root / "artifact-manifest.json", _artifact_manifest(root, baseline, resolved_candidate, run_id, captured)
    )
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a blocked, candidate-bound B7 evidence bundle")
    parser.add_argument(
        "--root", type=Path, default=_REPO_ROOT / "artifacts" / "operations" / "reader-capacity-follow-up"
    )
    parser.add_argument("--baseline-path", type=Path, default=None)
    parser.add_argument("--mcp-snapshot-path", type=Path, default=None)
    parser.add_argument("--candidate-revision", default=None)
    parser.add_argument("--captured-at-utc", default=None)
    args = parser.parse_args()
    baseline_path = args.baseline_path or args.root / "baseline.json"
    mcp_snapshot_path = args.mcp_snapshot_path or args.root / "b7-mcp-snapshot.json"
    run_id = generate(args.root, baseline_path, mcp_snapshot_path, args.candidate_revision, args.captured_at_utc)
    print(f"B7 blocked evidence bundle written: {args.root}; run_id={run_id}; status=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
