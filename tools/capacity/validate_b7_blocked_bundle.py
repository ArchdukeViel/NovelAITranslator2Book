"""Validate the fail-closed B7 blocked evidence bundle.

The validator checks candidate/campaign joins, exact bounded denominators, the
fixed timing-span contract, zero-attempt safety, role-boundary structure, and
redaction.  It intentionally accepts only blocked/unavailable/not-run evidence
for this preflight bundle; it cannot certify hosted capacity or recovery.
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
REQUIRED_ARTIFACTS = (
    "load-generator.json",
    "frontend-profile.json",
    "pipeline-timing.json",
    "database-microprofile.json",
    "r2-microprofile.json",
    "security-boundary.json",
    "writer-state-before.json",
    "writer-state-after.json",
    "recovery-manifest.json",
    "cleanup.json",
    "final-validation.json",
    "artifact-manifest.json",
    "handoff.json",
    "handoff.md",
)
ARTIFACT_KINDS = {name.removesuffix(".json"): name for name in REQUIRED_ARTIFACTS if name.endswith(".json")}
CAMPAIGN = re.compile(r"^camp-(?:[0-9a-f]{16}|[0-9]{8}T[0-9]{6}Z)$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^run-[0-9a-f]{16}$")
UTC_TIMESTAMP = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[^\s]+Z$")
URL = re.compile(r"(?:https?|postgres(?:ql)?|redis)://", re.IGNORECASE)
SQL = re.compile(r"\b(?:select|insert|update|delete|create|alter|drop|grant|revoke)\b", re.IGNORECASE)
PROTECTED_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
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
ALLOWED_STATUS = {"blocked", "unavailable", "not_run", "partial", "passed", "complete_with_blockers"}


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


def _load_json(root: Path, name: str, errors: list[str]) -> dict[str, Any] | None:
    path = root / name
    if not path.is_file():
        _error(errors, f"missing artifact: {name}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _error(errors, f"invalid JSON {name}: {exc.__class__.__name__}")
        return None
    if not isinstance(value, dict):
        _error(errors, f"artifact is not an object: {name}")
        return None
    errors.extend(_redaction_errors(value, name))
    return value


def _require(payload: dict[str, Any], key: str, errors: list[str], name: str) -> Any:
    if key not in payload:
        _error(errors, f"{name} missing {key}")
    return payload.get(key)


def _common_errors(
    payload: dict[str, Any],
    *,
    name: str,
    expected_kind: str,
    candidate: str,
    campaign: str,
    run_id: str,
) -> list[str]:
    errors: list[str] = []
    if payload.get("artifact_kind") != expected_kind:
        _error(errors, f"{name} artifact_kind is not {expected_kind}")
    if payload.get("schema_version") != 1:
        _error(errors, f"{name} schema_version is not 1")
    if payload.get("plan_id") != PLAN_ID or payload.get("plan_version") != PLAN_VERSION:
        _error(errors, f"{name} plan identity mismatch")
    if payload.get("candidate_sha") != candidate:
        _error(errors, f"{name} candidate mismatch")
    if payload.get("campaign_id") != campaign:
        _error(errors, f"{name} campaign mismatch")
    if payload.get("run_id") != run_id:
        _error(errors, f"{name} run mismatch")
    if payload.get("environment") != ENVIRONMENT:
        _error(errors, f"{name} environment is not non-production")
    if payload.get("target_classes") != TARGET_CLASSES:
        _error(errors, f"{name} target classes are not the exact allowlist")
    for key in ("utc_start", "utc_end"):
        value = payload.get(key)
        if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
            _error(errors, f"{name}.{key} is not a UTC timestamp")
    if payload.get("monotonic_clock") != "monotonic_ns":
        _error(errors, f"{name} monotonic clock is invalid")
    if payload.get("collection_status") not in ALLOWED_STATUS:
        _error(errors, f"{name} collection status is invalid")
    if not isinstance(payload.get("unavailable_reason"), str) or not payload.get("unavailable_reason"):
        _error(errors, f"{name} unavailable reason is missing")
    if payload.get("sample_count") != 0 or payload.get("aggregation") != "none":
        _error(errors, f"{name} blocked bundle must have zero samples and none aggregation")
    if payload.get("provenance") != ["local_preflight", "read_only_mcp"]:
        _error(errors, f"{name} provenance is invalid")
    if payload.get("production_capacity_claim") != "not_established":
        _error(errors, f"{name} makes a production capacity claim")
    if not REVISION.fullmatch(candidate):
        _error(errors, "candidate revision format is invalid")
    if not CAMPAIGN.fullmatch(campaign):
        _error(errors, "campaign format is invalid")
    if not RUN_ID.fullmatch(run_id):
        _error(errors, "run identifier format is invalid")
    return errors


def _validate_span(value: Any, name: str, expected_name: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        _error(errors, f"{name} span is not an object")
        return
    if value.get("name") != expected_name:
        _error(errors, f"{name} span name mismatch")
    try:
        TimingSpan(**value)
    except (TypeError, ValueError) as exc:
        _error(errors, f"{name} span fails timing contract: {exc}")
    if value.get("available") is not False or value.get("sample_count") != 0:
        _error(errors, f"{name} span must be unavailable with zero samples")


def _validate_span_cells(payload: dict[str, Any], *, name: str, span_names: tuple[str, ...], errors: list[str]) -> None:
    cells = payload.get("cells")
    if not isinstance(cells, list) or not cells:
        _error(errors, f"{name} cells are missing")
        return
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            _error(errors, f"{name} cell {index} is not an object")
            continue
        if cell.get("sample_count") != 0 or cell.get("status") not in {"unavailable", "blocked"}:
            _error(errors, f"{name} cell {index} is not fail-closed")
        if not isinstance(cell.get("unavailable_reason"), str) or not cell.get("unavailable_reason"):
            _error(errors, f"{name} cell {index} has no unavailable reason")
        spans = cell.get("spans")
        if not isinstance(spans, list) or len(spans) != len(span_names):
            _error(errors, f"{name} cell {index} has the wrong span count")
            continue
        for span_name, span in zip(span_names, spans, strict=True):
            _validate_span(span, f"{name} cell {index}", span_name, errors)


def _validate_load(payload: dict[str, Any], errors: list[str]) -> None:
    planned = payload.get("planned_attempts")
    if planned != {"cloudflare_tunnel": 1000, "direct_service": 500, "caddy_loopback": 500, "total": 2000}:
        _error(errors, "load-generator arithmetic is invalid")
    for key in ("attempted_attempts", "completed_attempts", "counted_slo_gate_attempts"):
        if payload.get(key) != 0:
            _error(errors, f"load-generator {key} must be zero")
    if payload.get("saturation_status") != "unavailable":
        _error(errors, "load-generator saturation must be unavailable")
    transport = payload.get("transport_status")
    if not isinstance(transport, dict) or set(transport) != {"cloudflare_tunnel", "direct_service", "caddy_loopback"}:
        _error(errors, "load-generator transport classes are incomplete")
    runner = payload.get("runner_observations")
    if not isinstance(runner, dict) or len(runner) != 6:
        _error(errors, "load-generator runner observations are incomplete")
    if (
        payload.get("retry_policy") != "none_for_counted_requests"
        or payload.get("concurrency") != 8
        or payload.get("timeout_seconds") != 20
    ):
        _error(errors, "load-generator controls are invalid")


def _validate_frontend(payload: dict[str, Any], errors: list[str]) -> None:
    plan = payload.get("public_navigation_plan")
    if not isinstance(plan, dict) or plan.get("planned_navigations") != 140 or plan.get("navigations_per_cell") != 7:
        _error(errors, "frontend public navigation arithmetic is invalid")
    cells = payload.get("cells")
    if not isinstance(cells, list) or len(cells) != 20:
        _error(errors, "frontend cell count must be 20")
        return
    seen: set[tuple[Any, ...]] = set()
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            _error(errors, f"frontend cell {index} is not an object")
            continue
        identity = (cell.get("route_class"), cell.get("device_profile"), cell.get("context"))
        if identity in seen:
            _error(errors, f"duplicate frontend cell {identity}")
        seen.add(identity)
        if cell.get("planned_navigations") != 7 or cell.get("attempted_navigations") != 0:
            _error(errors, f"frontend cell {index} denominator is invalid")
        if cell.get("status") != "blocked" or cell.get("unavailable_reason") != "isolated_reader_runtime_unavailable":
            _error(errors, f"frontend cell {index} is not blocked on runtime availability")
        metrics = cell.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != {
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
        }:
            _error(errors, f"frontend cell {index} metric set is invalid")
    protected = payload.get("protected_lane")
    if (
        not isinstance(protected, dict)
        or protected.get("status") != "blocked"
        or protected.get("planned_navigations") != 84
    ):
        _error(errors, "protected frontend lane is not explicitly blocked")
    if payload.get("public_attempted_navigations") != 0 or payload.get("field_web_vitals_claim") != "not_established":
        _error(errors, "frontend attempted count or field-vitals claim is invalid")


def _validate_pipeline(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("pipeline_timing_status") != "blocked" or payload.get("fixture_only") is not True:
        _error(errors, "pipeline status or fixture-only flag is invalid")
    if payload.get("external_provider_requests") != 0:
        _error(errors, "pipeline recorded provider requests")
    stages = payload.get("stages")
    if not isinstance(stages, list) or [item.get("stage") for item in stages if isinstance(item, dict)] != list(
        PIPELINE_TIMING_STAGES
    ):
        _error(errors, "pipeline stage vocabulary is invalid")
    else:
        for index, stage in enumerate(stages):
            if isinstance(stage, dict):
                _validate_span(stage.get("span"), f"pipeline stage {index}", str(stage.get("stage")), errors)


def _validate_database(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("database_microprofile_status") != "blocked":
        _error(errors, "database microprofile is not blocked")
    preflight = payload.get("fixture_preflight")
    if preflight != {"matching_novel_rows": 0, "matching_chapter_rows": 0, "collision": False}:
        _error(errors, "database fixture preflight is invalid")
    cells = payload.get("cells")
    if not isinstance(cells, list) or len(cells) != 4:
        _error(errors, "database microprofile must have four cells")
    else:
        _validate_span_cells(payload, name="database", span_names=DATABASE_TIMING_SPANS, errors=errors)


def _validate_r2(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("r2_microprofile_status") != "blocked" or payload.get("gateway_status") != "unavailable":
        _error(errors, "R2 microprofile status is invalid")
    cells = payload.get("cells")
    if not isinstance(cells, list) or len(cells) != 18:
        _error(errors, "R2 microprofile must have 18 cells")
    else:
        _validate_span_cells(payload, name="r2", span_names=R2_TIMING_SPANS, errors=errors)


def _validate_security(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("security_status") != "blocked" or payload.get("local_contract_status") != "passed":
        _error(errors, "security status is invalid")
    if payload.get("hosted_identity_lane_status") != "blocked":
        _error(errors, "hosted identity lane is not blocked")
    identities = payload.get("identities")
    expected = {
        "guest",
        "authenticated_user",
        "owner",
        "runtime_database_role",
        "migration_role",
        "r2_content_identity",
        "r2_recovery_identity",
        "mcp_operator_identity",
        "github_untrusted_workflow",
    }
    actual = {item.get("principal_class") for item in identities or [] if isinstance(item, dict)}
    if actual != expected:
        _error(errors, "security identity matrix is incomplete")
    cases = payload.get("authorization_cases")
    if not isinstance(cases, list) or len(cases) != 3:
        _error(errors, "security authorization cases are incomplete")


def _validate_writer(payload: dict[str, Any], phase: str, errors: list[str]) -> None:
    if payload.get("phase") != phase:
        _error(errors, f"writer {phase} phase is invalid")
    if payload.get("worker_state") != "stopped":
        _error(errors, f"writer {phase} worker state is invalid")
    if payload.get("original_queue_state") != "unknown" or payload.get("other_writers_state") != "unknown":
        _error(errors, f"writer {phase} unknown-state safety gate was not preserved")
    if (
        payload.get("proof_status") != "insufficient"
        or payload.get("profile_started") is not False
        or payload.get("write_allowed") is not False
    ):
        _error(errors, f"writer {phase} proof status is unsafe")


def _validate_recovery(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("recovery_status") != "blocked" or payload.get("recovery_started") is not False:
        _error(errors, "recovery must be blocked before start")
    if payload.get("recovery_point_id") is not None:
        _error(errors, "blocked recovery contains a recovery point")
    if payload.get("production_mutation") != "none":
        _error(errors, "recovery mutation state is invalid")
    for key in (
        "backup_timestamp_status",
        "manifest_commit_status",
        "database_snapshot_status",
        "r2_manifest_status",
        "restore_verification_status",
        "cleanup_status",
    ):
        if payload.get(key) != "not_run":
            _error(errors, f"recovery {key} must be not_run")


def _validate_cleanup(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("cleanup_status") != "blocked" or payload.get("cleanup_executed") is not False:
        _error(errors, "cleanup status is invalid")
    if payload.get("resources_created_by_run") != 0:
        _error(errors, "cleanup claims generated resources")
    if (
        payload.get("preflight_fixture_rows") != {"novel": 0, "chapter": 0}
        or payload.get("preflight_application_objects") != 0
    ):
        _error(errors, "cleanup preflight zero proof is invalid")
    if payload.get("postrun_verification_status") != "not_run":
        _error(errors, "cleanup postrun verification must be not_run")


def _validate_final(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("overall_follow_up_disposition") != "blocked":
        _error(errors, "final validation disposition is invalid")
    if payload.get("local_validation_status") != "passed" or payload.get("hosted_validation_status") != "blocked":
        _error(errors, "final validation statuses are invalid")
    if not isinstance(payload.get("blockers"), list) or not payload["blockers"]:
        _error(errors, "final validation blockers are missing")


def _validate_manifest(payload: dict[str, Any], root: Path, errors: list[str]) -> None:
    if payload.get("manifest_status") != "blocked":
        _error(errors, "artifact manifest status is invalid")
    entries = payload.get("entries")
    names = {item.get("name") for item in entries or [] if isinstance(item, dict)}
    expected = set(REQUIRED_ARTIFACTS) - {"artifact-manifest.json"}
    if not expected.issubset(names):
        _error(errors, "artifact manifest omits required artifacts")
    for item in entries or []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            _error(errors, "artifact manifest entry is invalid")
            continue
        path = root / item["name"]
        if item.get("present") != path.is_file():
            _error(errors, f"artifact manifest presence mismatch for {item['name']}")
        if path.is_file() and item.get("sha256") is not None and not isinstance(item.get("sha256"), str):
            _error(errors, f"artifact manifest digest is invalid for {item['name']}")


def _validate_handoff(payload: dict[str, Any], errors: list[str]) -> None:
    expected = {
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
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            _error(errors, f"handoff {key} is invalid")
    if (
        payload.get("workflow_urls") != []
        or not isinstance(payload.get("blocker_ids"), list)
        or not payload["blocker_ids"]
    ):
        _error(errors, "handoff hosted-run/blocker fields are invalid")


def validate(root: Path, candidate: str | None = None) -> list[str]:
    errors: list[str] = []
    baseline = _load_json(root, "baseline.json", errors)
    snapshot = _load_json(root, "b7-mcp-snapshot.json", errors)
    if baseline is None or snapshot is None:
        return errors
    resolved_candidate = candidate or str(baseline.get("baseline_revision", ""))
    campaign = str(baseline.get("campaign_id", ""))
    if baseline.get("baseline_revision") != resolved_candidate:
        _error(errors, "baseline candidate does not match requested candidate")
    if snapshot.get("candidate_revision") != resolved_candidate or snapshot.get("campaign_id") != campaign:
        _error(errors, "MCP snapshot is not joined to the bundle candidate/campaign")
    if not REVISION.fullmatch(resolved_candidate):
        _error(errors, "candidate revision is invalid")
    if not CAMPAIGN.fullmatch(campaign):
        _error(errors, "campaign is invalid")
    generated: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_ARTIFACTS:
        if name == "handoff.md":
            continue
        payload = _load_json(root, name, errors)
        if payload is not None:
            generated[name] = payload
    run_ids = {str(payload.get("run_id")) for payload in generated.values()}
    if len(run_ids) != 1:
        _error(errors, "generated artifacts do not share one run id")
        run_id = next(iter(run_ids), "")
    else:
        run_id = next(iter(run_ids))
    for name, payload in generated.items():
        expected_kind = name.removesuffix(".json").replace("-", "_")
        errors.extend(
            _common_errors(
                payload,
                name=name,
                expected_kind=expected_kind,
                candidate=resolved_candidate,
                campaign=campaign,
                run_id=run_id,
            )
        )
    if "load-generator.json" in generated:
        _validate_load(generated["load-generator.json"], errors)
    if "frontend-profile.json" in generated:
        _validate_frontend(generated["frontend-profile.json"], errors)
    if "pipeline-timing.json" in generated:
        _validate_pipeline(generated["pipeline-timing.json"], errors)
    if "database-microprofile.json" in generated:
        _validate_database(generated["database-microprofile.json"], errors)
    if "r2-microprofile.json" in generated:
        _validate_r2(generated["r2-microprofile.json"], errors)
    if "security-boundary.json" in generated:
        _validate_security(generated["security-boundary.json"], errors)
    if "writer-state-before.json" in generated:
        _validate_writer(generated["writer-state-before.json"], "before", errors)
    if "writer-state-after.json" in generated:
        _validate_writer(generated["writer-state-after.json"], "after", errors)
    if "recovery-manifest.json" in generated:
        _validate_recovery(generated["recovery-manifest.json"], errors)
    if "cleanup.json" in generated:
        _validate_cleanup(generated["cleanup.json"], errors)
    if "final-validation.json" in generated:
        _validate_final(generated["final-validation.json"], errors)
    if "artifact-manifest.json" in generated:
        _validate_manifest(generated["artifact-manifest.json"], root, errors)
    if "handoff.json" in generated:
        _validate_handoff(generated["handoff.json"], errors)
    handoff_path = root / "handoff.md"
    if not handoff_path.is_file():
        _error(errors, "missing artifact: handoff.md")
    else:
        text = handoff_path.read_text(encoding="utf-8")
        for value, label in ((resolved_candidate, "candidate"), (campaign, "campaign"), (run_id, "run")):
            if value not in text:
                _error(errors, f"handoff.md is missing {label}")
        if "Disposition: **blocked**" not in text or "production_capacity_claim`: **not_established**" not in text:
            _error(errors, "handoff.md is not fail-closed")
        if URL.search(text) or SQL.search(text) or "bearer " in text.lower():
            _error(errors, "handoff.md contains protected text")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the candidate-bound B7 blocked evidence bundle")
    parser.add_argument(
        "--root", type=Path, default=_REPO_ROOT / "artifacts" / "operations" / "reader-capacity-follow-up"
    )
    parser.add_argument("--candidate-revision", default=None)
    args = parser.parse_args()
    errors = validate(args.root, args.candidate_revision)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"B7 blocked bundle invalid: {len(errors)} error(s)")
        return 1
    print(f"VALIDATION PASSED: {args.root} (B7 blocked bundle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
