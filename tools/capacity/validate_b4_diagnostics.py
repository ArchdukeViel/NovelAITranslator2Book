"""Strict semantic validation for Phase B4 preliminary diagnostics.

This validator is intentionally independent of provider clients.  It validates
sanitized evidence produced by the local diagnostic runner and fails closed on
missing cells, missing unavailable reasons, interval-contract violations, and
protected data.  It is not a capacity-result validator.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))

from novelai.services.timing_contract import (  # noqa: E402
    DATABASE_TIMING_SPANS,
    PIPELINE_TIMING_STAGES,
    R2_TIMING_SPANS,
    TIMING_AGGREGATIONS,
    TIMING_SCHEMA_VERSION,
    TIMING_SOURCES,
    TIMING_SPANS,
    UNAVAILABLE_REASONS,
    TimingInterval,
    TimingSpan,
    exclusive_duration_ms,
    fixed_contract,
)

REQUIRED_ARTIFACTS = (
    "authorization-matrix.json",
    "timing-schema.json",
    "latency-attribution-preliminary.json",
    "database-microprofile.json",
    "r2-microprofile.json",
    "pipeline-timing-preliminary.json",
    "remediation-decision.json",
    "checkpoint-B4.json",
)
ROUTES = ("health_live", "catalog", "detail", "chapter", "search")
TOPOLOGIES = ("direct_service", "caddy_loopback", "cloudflare_tunnel")
R2_SIZES = (4096, 65536, 1048576)
R2_CONCURRENCIES = (1, 8)
OPAQUE_ID = re.compile(r"^(?:campaign|run|recovery)-[0-9a-f]{16}$")
TIMESTAMP = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[^\s]+Z$")
URL = re.compile(r"(?:https?|postgres(?:ql)?|redis)://", re.IGNORECASE)
SQL = re.compile(r"\b(?:select|insert|update|delete|create|alter|drop|grant|revoke)\b", re.IGNORECASE)
PROTECTED_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "authorization_header",
    "cookie",
    "user_id",
    "requesting_user_id",
    "credential_id",
    "credential_owner_user_id",
    "object_key",
    "key_name",
    "sql",
    "query",
    "query_text",
    "request_body",
    "response_body",
    "connection_url",
    "connection_string",
    "hostname",
}
SPAN_FIELDS = {
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


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _redaction_errors(value: Any, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in PROTECTED_KEYS:
                _error(errors, f"protected field at {path}.{normalized}")
            errors.extend(_redaction_errors(child, f"{path}.{normalized}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_redaction_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if URL.search(value) or SQL.search(value) or "bearer " in value.lower():
            _error(errors, f"protected text at {path}")
    return errors


def _base_errors(payload: Any, *, artifact_kind: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["artifact must be an object"]
    if payload.get("artifact_kind") != artifact_kind:
        _error(errors, "artifact_kind mismatch")
    if payload.get("schema_version") != TIMING_SCHEMA_VERSION:
        _error(errors, "schema_version mismatch")
    campaign_id = payload.get("campaign_id")
    if not isinstance(campaign_id, str) or not OPAQUE_ID.fullmatch(campaign_id):
        _error(errors, "campaign_id is not an opaque campaign identifier")
    captured_at = payload.get("captured_at_utc")
    if not isinstance(captured_at, str) or not TIMESTAMP.fullmatch(captured_at):
        _error(errors, "captured_at_utc is not a UTC timestamp")
    errors.extend(_redaction_errors(payload))
    return errors


def _validate_span(value: Any, *, expected_name: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["span is not an object"]
    if set(value) != SPAN_FIELDS:
        _error(errors, "span fields are not exact")
        return errors
    if expected_name is not None and value.get("name") != expected_name:
        _error(errors, "span name mismatch")
    try:
        TimingSpan(**value)
    except TypeError, ValueError:
        _error(errors, "span fails fixed timing contract")
    return errors


def _validate_span_list(value: Any, names: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return ["spans must be a list"]
    if len(value) != len(names):
        _error(errors, "span list has the wrong cardinality")
    seen: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                if name in seen:
                    _error(errors, "duplicate span name")
                seen.add(name)
                if name not in names:
                    _error(errors, "span name is outside the requested fixed set")
            errors.extend(_validate_span(item))
        else:
            _error(errors, "span is not an object")
    if seen != set(names):
        _error(errors, "required fixed spans are missing")
    return errors


def validate_authorization_matrix(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="authorization_matrix")
    if not isinstance(payload, dict):
        return errors
    expected_identities = {
        "guest",
        "authenticated_user",
        "owner",
        "runtime_database_role",
        "migration_role",
        "r2_content_identity",
        "r2_recovery_identity",
        "mcp_operator_identity",
        "github_untrusted_workflow",
        "github_trusted_workflow",
    }
    identities = payload.get("identities")
    if not isinstance(identities, list):
        _error(errors, "identities must be a list")
    else:
        names = {item.get("identity") for item in identities if isinstance(item, dict)}
        if names != expected_identities:
            _error(errors, "authorization identities are incomplete or unexpected")
        for item in identities:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("allowed_classes"), list)
                or not isinstance(item.get("denied_classes"), list)
            ):
                _error(errors, "authorization identity entry is malformed")
    required_cases = {
        "guest_user_route_401",
        "guest_owner_route_401",
        "user_owner_route_403",
        "user_a_user_b_read_denied",
        "user_a_user_b_write_denied",
        "revoked_session_denied",
        "csrf_required_cookie_mutation",
        "unpublished_public_read_denied",
        "service_role_not_browser_equivalent",
        "rls_server_check_consistent",
    }
    cases = payload.get("security_cases")
    if not isinstance(cases, list):
        _error(errors, "security_cases must be a list")
    else:
        case_names = {item.get("case") for item in cases if isinstance(item, dict)}
        if case_names != required_cases:
            _error(errors, "required security cases are incomplete or unexpected")
        for item in cases:
            if not isinstance(item, dict) or item.get("status") not in {"passed", "blocked", "unavailable"}:
                _error(errors, "security case status is invalid")
            if not isinstance(item.get("evidence_refs"), list) or not item.get("evidence_refs"):
                _error(errors, "security case evidence reference is missing")
    if payload.get("security_contract_status") not in {"passed", "blocked", "unavailable"}:
        _error(errors, "security_contract_status is invalid")
    return errors


def validate_timing_schema(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="timing_schema")
    if not isinstance(payload, dict):
        return errors
    expected = fixed_contract()
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            _error(errors, f"timing contract field mismatch: {key}")
    if payload.get("provenance") != "local_repository_contract":
        _error(errors, "timing contract provenance is invalid")
    return errors


def _validate_cell_span_contract(cell: dict[str, Any], names: tuple[str, ...]) -> list[str]:
    return _validate_span_list(cell.get("spans"), names)


def validate_latency(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="latency_attribution_preliminary")
    if not isinstance(payload, dict):
        return errors
    if payload.get("status") not in {"blocked", "unavailable"}:
        _error(errors, "preliminary latency status must remain blocked or unavailable")
    if payload.get("gate_topology") != "cloudflare_tunnel":
        _error(errors, "Cloudflare Tunnel is not the latency gate")
    if tuple(payload.get("routes", ())) != ROUTES or tuple(payload.get("topologies", ())) != TOPOLOGIES:
        _error(errors, "latency route or topology set is incomplete")
    if payload.get("production_capacity_claim") != "not_established":
        _error(errors, "production capacity claim must remain not_established")
    cells = payload.get("cells")
    expected = {(topology, route) for topology in TOPOLOGIES for route in ROUTES}
    seen: set[tuple[str, str]] = set()
    if not isinstance(cells, list):
        _error(errors, "latency cells must be a list")
    else:
        for cell in cells:
            if not isinstance(cell, dict):
                _error(errors, "latency cell is not an object")
                continue
            key = (cell.get("topology"), cell.get("route"))
            if key in seen:
                _error(errors, "duplicate latency cell")
            seen.add(key)
            if key not in expected or cell.get("status") not in {"blocked", "unavailable"}:
                _error(errors, "latency cell identity or status is invalid")
            if cell.get("attempted_count") != 0 or cell.get("sample_count") != 0:
                _error(errors, "unavailable latency cell contains samples")
            if cell.get("unavailable_reason") not in UNAVAILABLE_REASONS:
                _error(errors, "latency cell lacks a fixed unavailable reason")
            errors.extend(_validate_cell_span_contract(cell, TIMING_SPANS))
    if seen != expected:
        _error(errors, "required latency cells are missing")
    return errors


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_database(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="database_microprofile")
    if not isinstance(payload, dict):
        return errors
    if payload.get("status") != "blocked" or payload.get("target_class") != "supabase_test_project":
        _error(errors, "database profile must be blocked against the test project class")
    preflight = payload.get("fixture_preflight")
    if (
        not isinstance(preflight, dict)
        or preflight.get("matching_rows") != 0
        or preflight.get("collision") is not False
    ):
        _error(errors, "database fixture preflight is not clean and explicit")
    hosted = payload.get("hosted_observation")
    required_hosted = {
        "status",
        "source",
        "security_advisor_findings",
        "performance_advisor_findings",
        "public_tables",
        "public_tables_rls",
        "public_security_definer_functions",
        "activity_total",
        "activity_active",
        "pg_stat_statements_available",
        "pool_occupancy_status",
        "cumulative_provenance",
    }
    if not isinstance(hosted, dict) or not required_hosted.issubset(hosted):
        _error(errors, "sanitized hosted database observation is incomplete")
    else:
        if hosted.get("status") != "observed" or hosted.get("source") != "hosted_mcp":
            _error(errors, "hosted database observation provenance is invalid")
        for key in required_hosted - {
            "status",
            "source",
            "pg_stat_statements_available",
            "pool_occupancy_status",
            "cumulative_provenance",
        }:
            if not _nonnegative_int(hosted.get(key)):
                _error(errors, f"hosted database count is invalid: {key}")
        if hosted.get("cumulative_provenance") != "database_cumulative":
            _error(errors, "cumulative database provenance is invalid")
        if hosted.get("pool_occupancy_status") != "unavailable":
            _error(errors, "pool occupancy must remain explicitly unavailable")
    cells = payload.get("cells")
    expected = {
        (operation, concurrency)
        for operation in ("runtime_role_fixture_read", "isolated_test_write")
        for concurrency in (1, 8)
    }
    seen: set[tuple[str, int]] = set()
    if not isinstance(cells, list):
        _error(errors, "database cells must be a list")
    else:
        for cell in cells:
            if not isinstance(cell, dict):
                _error(errors, "database cell is not an object")
                continue
            key = (cell.get("operation"), cell.get("concurrency"))
            seen.add(key)
            if key not in expected or cell.get("status") != "unavailable":
                _error(errors, "database cell identity or status is invalid")
            expected_count = 100 if cell.get("operation") == "runtime_role_fixture_read" else 20
            if cell.get("target_count") != expected_count or cell.get("sample_count") != 0:
                _error(errors, "database cell count does not match the bounded contract")
            if cell.get("unavailable_reason") != "permission_denied":
                _error(errors, "database cell lacks permission-denied evidence")
            errors.extend(_validate_cell_span_contract(cell, DATABASE_TIMING_SPANS))
            if cell.get("operation") == "isolated_test_write":
                cleanup = cell.get("cleanup")
                if (
                    not isinstance(cleanup, dict)
                    or cleanup.get("status") != "not_run"
                    or cleanup.get("reason") != "permission_denied"
                ):
                    _error(errors, "unauthorized database write cleanup is not explicit")
    if seen != expected:
        _error(errors, "required database cells are missing")
    return errors


def validate_r2(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="r2_microprofile")
    if not isinstance(payload, dict):
        return errors
    if payload.get("status") != "blocked":
        _error(errors, "R2 profile must be blocked without the authorized gateway")
    if (
        payload.get("application_bucket_class") != "test-dokushodo"
        or payload.get("backup_bucket_class") != "test-dokushodo-backup"
    ):
        _error(errors, "R2 bucket classes are not the dedicated test classes")
    cells = payload.get("cells")
    expected = {
        (operation, size, concurrency)
        for operation in ("put", "head", "get")
        for size in R2_SIZES
        for concurrency in R2_CONCURRENCIES
    }
    seen: set[tuple[str, int, int]] = set()
    if not isinstance(cells, list):
        _error(errors, "R2 cells must be a list")
    else:
        for cell in cells:
            if not isinstance(cell, dict):
                _error(errors, "R2 cell is not an object")
                continue
            key = (cell.get("operation"), cell.get("payload_bytes"), cell.get("concurrency"))
            seen.add(key)
            if key not in expected or cell.get("status") != "unavailable":
                _error(errors, "R2 cell identity or status is invalid")
            if cell.get("target_count") != 20 or cell.get("sample_count") != 0:
                _error(errors, "R2 cell count does not match the bounded contract")
            if cell.get("unavailable_reason") != "test_r2_gateway_not_authorized":
                _error(errors, "R2 cell lacks gateway authorization evidence")
            errors.extend(_validate_cell_span_contract(cell, R2_TIMING_SPANS))
    if seen != expected:
        _error(errors, "required R2 cells are missing")
    cleanup = payload.get("cleanup")
    if (
        not isinstance(cleanup, dict)
        or cleanup.get("status") != "not_run"
        or cleanup.get("reason") != "test_r2_gateway_not_authorized"
    ):
        _error(errors, "R2 cleanup is not explicit")
    return errors


def validate_pipeline(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="pipeline_timing_preliminary")
    if not isinstance(payload, dict):
        return errors
    if payload.get("status") != "complete_with_unavailable_stages":
        _error(errors, "pipeline diagnostic status is invalid")
    if payload.get("warmup_runs") != 3 or payload.get("measured_runs") != 30 or payload.get("chapters_per_run") != 2:
        _error(errors, "pipeline run counts do not match the bounded contract")
    if payload.get("concurrency") != 2 or payload.get("queue_mode") != "fixture_bounded_gather":
        _error(errors, "pipeline concurrency or queue mode is not fixed")
    if payload.get("external_provider_requests") != 0:
        _error(errors, "pipeline diagnostic attempted an external provider request")
    if payload.get("worker_state") != "stopped" or payload.get("full_queue_state") != "paused":
        _error(errors, "pipeline worker or full queue state is not fail-closed")
    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != len(PIPELINE_TIMING_STAGES):
        _error(errors, "pipeline stage set is incomplete")
    else:
        seen: set[str] = set()
        for item in stages:
            if not isinstance(item, dict):
                _error(errors, "pipeline stage entry is not an object")
                continue
            stage = item.get("stage")
            seen.add(stage)
            if stage not in PIPELINE_TIMING_STAGES:
                _error(errors, "pipeline stage is outside the fixed vocabulary")
            span = item.get("span")
            errors.extend(_validate_span(span, expected_name=stage))
            if isinstance(span, dict) and span.get("available"):
                if span.get("sample_count") != 60:
                    _error(errors, "pipeline measured sample count is not two chapters times 30")
                if span.get("source") not in {"local_synthetic", "provider_mock"}:
                    _error(errors, "pipeline observed source is invalid")
        if seen != set(PIPELINE_TIMING_STAGES):
            _error(errors, "required pipeline stages are missing")
    cleanup = payload.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup.get("in_memory_rows") != 0 or cleanup.get("in_memory_objects") != 0:
        _error(errors, "pipeline synthetic cleanup proof is missing")
    return errors


def validate_remediation(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="remediation_decision")
    if not isinstance(payload, dict):
        return errors
    if payload.get("status") != "blocked" or payload.get("classification") != "mixed_or_unavailable":
        _error(errors, "remediation must remain blocked on mixed or unavailable evidence")
    if payload.get("decision") != "no_change" or payload.get("fix_applied") is not False:
        _error(errors, "speculative remediation was recorded")
    if payload.get("production_capacity_claim") != "not_established":
        _error(errors, "production capacity claim must remain not_established")
    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        _error(errors, "quantified remediation blockers are missing")
    return errors


def validate_checkpoint(payload: Any) -> list[str]:
    errors = _base_errors(payload, artifact_kind="plan_b_checkpoint")
    if not isinstance(payload, dict):
        return errors
    if payload.get("checkpoint") != "B4":
        _error(errors, "checkpoint identity is invalid")
    if payload.get("status") != "complete_with_quantified_blocker":
        _error(errors, "checkpoint status is invalid")
    if payload.get("next_phase") != "B5":
        _error(errors, "next phase is invalid")
    if payload.get("next_phase_eligibility") != "hosted_preflight_blocked":
        _error(errors, "next phase eligibility is invalid")
    if payload.get("production_capacity_claim") != "not_established":
        _error(errors, "production capacity claim must remain not_established")
    counts = payload.get("blocked_cell_counts")
    if not isinstance(counts, dict) or counts != {"reader": 15, "database": 4, "r2": 18, "security_cases": 4}:
        _error(errors, "checkpoint blocker counts are invalid")
    if (
        payload.get("provider_writes_attempted") is not False
        or payload.get("production_actions_attempted") is not False
    ):
        _error(errors, "checkpoint records an unauthorized action")
    return errors


VALIDATORS = {
    "authorization-matrix.json": validate_authorization_matrix,
    "timing-schema.json": validate_timing_schema,
    "latency-attribution-preliminary.json": validate_latency,
    "database-microprofile.json": validate_database,
    "r2-microprofile.json": validate_r2,
    "pipeline-timing-preliminary.json": validate_pipeline,
    "remediation-decision.json": validate_remediation,
    "checkpoint-B4.json": validate_checkpoint,
}


def validate_directory(root: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_ARTIFACTS:
        path = root / name
        validator = VALIDATORS[name]
        if not path.is_file():
            _error(errors, f"missing artifact: {name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            _error(errors, f"invalid JSON artifact: {name}")
            continue
        for item in validator(payload):
            _error(errors, f"{name}: {item}")
    return errors


def _self_test() -> list[str]:
    errors: list[str] = []
    parent = TimingInterval(0, 10)
    child_a = TimingInterval(1, 5)
    child_b = TimingInterval(3, 5)
    if exclusive_duration_ms(parent, (child_a, child_b)) != 3.0:
        _error(errors, "interval union self-test failed")
    valid = TimingSpan(
        name="application_total",
        source="application",
        start_offset_ms=0,
        duration_ms=1,
        sample_count=1,
    ).to_dict()
    if _validate_span(valid):
        _error(errors, "valid span self-test failed")
    invalid = dict(valid)
    invalid["duration_ms"] = -1
    if not _validate_span(invalid):
        _error(errors, "invalid span self-test failed")
    if set(TIMING_AGGREGATIONS) != {"single", "count", "mean", "p50", "p95", "p99"}:
        _error(errors, "aggregation vocabulary self-test failed")
    if "local_synthetic" not in TIMING_SOURCES:
        _error(errors, "source vocabulary self-test failed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase B4 diagnostic evidence")
    parser.add_argument("--root", type=Path, default=_REPO_ROOT / "artifacts" / "public-hosted-execution")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    errors = _self_test() if args.self_test else validate_directory(args.root)
    if errors:
        print(f"B4 diagnostics invalid: {len(errors)} bounded validation errors")
        return 1
    print("B4 diagnostics valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
