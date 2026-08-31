"""Validate the sanitized read-only MCP snapshot used by B7."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
CAMPAIGN = re.compile(r"^camp-[0-9]{8}T[0-9]{6}Z$")
UTC = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[^\s]+Z$")
PROTECTED_KEYS = {
    "api_key",
    "authorization",
    "connection_string",
    "connection_url",
    "cookie",
    "hostname",
    "object_key",
    "password",
    "project_id",
    "query",
    "query_text",
    "secret",
    "sql",
    "token",
    "tunnel_id",
}
PROTECTED_TEXT = re.compile(r"(?i)(?:postgres(?:ql)?://|https?://|bearer\s|password\s*[:=]|api[_-]?key\s*[:=])")
STATES = {"active", "disabled", "down", "enabled", "full", "observed", "off", "on", "partial", "ready", "unavailable"}


def _errors(value: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in PROTECTED_KEYS:
                found.append(f"protected field: {path}.{normalized}")
            found.extend(_errors(child, f"{path}.{normalized}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str) and PROTECTED_TEXT.search(value):
        found.append(f"protected text: {path}")
    return found


def _require(payload: dict[str, Any], path: str, errors: list[str]) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            errors.append(f"missing field: {path}")
            return None
        current = current[part]
    return current


def _nonnegative(value: Any, path: str, errors: list[str], *, optional: bool = True) -> None:
    if value is None and optional:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        errors.append(f"non-negative number required: {path}")


def _state(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or value not in STATES:
        errors.append(f"unsupported state: {path}")


def validate_snapshot(payload: Any) -> list[str]:
    """Return semantic validation errors; an empty list means valid."""

    if not isinstance(payload, dict):
        return ["snapshot must be an object"]
    errors = _errors(payload)
    if payload.get("artifact_kind") != "b7_mcp_snapshot":
        errors.append("artifact_kind must be b7_mcp_snapshot")
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field, pattern in (("campaign_id", CAMPAIGN), ("candidate_revision", SHA), ("baseline_revision", SHA)):
        value = payload.get(field)
        if not isinstance(value, str) or not pattern.fullmatch(value):
            errors.append(f"{field} has the wrong opaque format")
    captured = payload.get("captured_at_utc")
    if not isinstance(captured, str) or not UTC.fullmatch(captured):
        errors.append("captured_at_utc must be a UTC timestamp")
    if payload.get("source") != "mcp_read_only":
        errors.append("source must be mcp_read_only")
    if payload.get("candidate_join") not in {"matched", "mismatch"}:
        errors.append("candidate_join is invalid")

    target_classes = payload.get("target_classes")
    expected_targets = {
        "database": "dedicated_test_project",
        "application_bucket": "dedicated_test_application_bucket",
        "backup_bucket": "dedicated_test_backup_bucket",
    }
    if target_classes != expected_targets:
        errors.append("target classes are not the approved non-production classes")

    supabase = payload.get("supabase")
    if not isinstance(supabase, dict) or supabase.get("project_class") != "dedicated_test":
        errors.append("Supabase target is not the dedicated test class")
    else:
        for field in (
            "security_advisor_findings",
            "performance_advisor_findings",
            "migration_rows",
            "public_tables",
            "public_tables_rls",
            "public_security_definer_functions",
        ):
            _nonnegative(supabase.get(field), f"supabase.{field}", errors)
        fixture = supabase.get("fixture_preflight")
        if (
            not isinstance(fixture, dict)
            or fixture.get("novel_rows") != 0
            or fixture.get("chapter_rows") != 0
            or fixture.get("collision") is not False
        ):
            errors.append("Supabase fixture collision proof is not zero and explicit")
        activity = supabase.get("activity")
        if not isinstance(activity, dict):
            errors.append("Supabase activity aggregate is missing")
        else:
            for field in ("session_count", "active_count", "idle_count", "null_state_count"):
                _nonnegative(activity.get(field), f"supabase.activity.{field}", errors)
        statements = supabase.get("pg_stat_statements")
        if not isinstance(statements, dict):
            errors.append("pg_stat_statements status is missing")
        else:
            _state(statements.get("status"), "supabase.pg_stat_statements.status", errors)
            for field in ("statement_rows", "total_calls", "total_exec_time_ms", "total_rows"):
                _nonnegative(statements.get(field), f"supabase.pg_stat_statements.{field}", errors)
        pool = supabase.get("pool_occupancy")
        if not isinstance(pool, dict):
            errors.append("pool occupancy status is missing")
        else:
            _state(pool.get("status"), "supabase.pool_occupancy.status", errors)

    cloudflare = payload.get("cloudflare")
    if not isinstance(cloudflare, dict):
        errors.append("Cloudflare observation is missing")
    else:
        zone = cloudflare.get("zone")
        if not isinstance(zone, dict):
            errors.append("Cloudflare zone observation is missing")
        else:
            _state(zone.get("status"), "cloudflare.zone.status", errors)
            if not isinstance(zone.get("paused"), bool):
                errors.append("cloudflare.zone.paused must be boolean")
        dns = cloudflare.get("dns")
        if not isinstance(dns, dict):
            errors.append("Cloudflare DNS aggregate is missing")
        else:
            for field in ("record_count", "proxied_count", "caa_count"):
                _nonnegative(dns.get(field), f"cloudflare.dns.{field}", errors)
        for field in ("dnssec_status",):
            _state(cloudflare.get(field), f"cloudflare.{field}", errors)
        tunnel = cloudflare.get("tunnel")
        if not isinstance(tunnel, dict):
            errors.append("Cloudflare tunnel observation is missing")
        else:
            for field in ("status", "route_status"):
                _state(tunnel.get(field), f"cloudflare.tunnel.{field}", errors)
            for field in ("connection_count", "ingress_count"):
                _nonnegative(tunnel.get(field), f"cloudflare.tunnel.{field}", errors)
        rulesets = cloudflare.get("rulesets")
        if not isinstance(rulesets, dict):
            errors.append("Cloudflare ruleset observation is missing")
        else:
            _state(rulesets.get("status"), "cloudflare.rulesets.status", errors)
        r2 = cloudflare.get("r2")
        if not isinstance(r2, dict):
            errors.append("Cloudflare R2 observation is missing")
        else:
            if r2.get("approved_test_bucket_classes") != 2:
                errors.append("R2 approved test bucket class count must be 2")
            if r2.get("application_prefix_objects") != 0 or r2.get("backup_prefix_objects") != 0:
                errors.append("R2 prefix collision proof is not zero")
            _state(r2.get("exact_bucket_window_status"), "cloudflare.r2.exact_bucket_window_status", errors)

    safety = payload.get("safety")
    if not isinstance(safety, dict):
        errors.append("safety section is missing")
    else:
        for field in ("worker_state", "original_queue_state", "other_writers_state", "reader_runtime_state"):
            value = safety.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"safety.{field} must be a non-empty state")
        for field in (
            "production_data_plane_mutation",
            "provider_mutations_attempted",
            "raw_provider_response_stored",
            "profile_eligible",
        ):
            if not isinstance(safety.get(field), bool):
                errors.append(f"safety.{field} must be boolean")
        if (
            safety.get("production_data_plane_mutation") is not False
            or safety.get("provider_mutations_attempted") is not False
            or safety.get("raw_provider_response_stored") is not False
        ):
            errors.append("snapshot records an unauthorized or unsafe operation")
        if safety.get("production_capacity_claim") != "not_established":
            errors.append("production capacity claim must remain not_established")
        blockers = safety.get("blockers")
        if not isinstance(blockers, list):
            errors.append("safety blockers must be a list")
        elif safety.get("profile_eligible") is False and not blockers:
            errors.append("blocked snapshot must include blockers")
        elif safety.get("profile_eligible") is True and blockers:
            errors.append("eligible snapshot cannot include blockers")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8-sig"))
    errors = validate_snapshot(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"VALIDATION PASSED: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
