"""Capture sanitized read-only MCP observations for the B7 follow-up.

The Supabase and Cloudflare MCP servers run outside the repository runtime.
This command is the narrow handoff between those read-only observations and
the checked-in evidence contract: callers provide only bounded scalar values,
and the command rejects fixture collisions, candidate drift, production-like
bucket classes, and protected data before writing the snapshot.

It intentionally records provider posture and aggregate database state, not
reader samples or provider billing.  A successful snapshot is not a capacity
result; B7 remains blocked until the data-plane, writer-state, and timing
contracts are independently satisfied.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"^[0-9a-f]{40}$")
_CAMPAIGN = re.compile(r"^camp-[0-9]{8}T[0-9]{6}Z$")
_UTC = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[^\s]+Z$")

_UNAVAILABLE_REASONS = frozenset(
    {
        "provider_metric_unavailable",
        "pooler_metric_unavailable",
        "r2_metric_unavailable",
        "runtime_state_unavailable",
        "cloudflare_tunnel_unavailable",
        "target_not_configured",
        "endpoint_unavailable",
    }
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _nonnegative(value: Any, *, name: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be a non-negative number or omitted")
    return value


def _count(values: Mapping[str, Any], name: str) -> int | None:
    value = values.get(name)
    checked = _nonnegative(value, name=name)
    if checked is None:
        return None
    if not isinstance(checked, int):
        raise ValueError(f"{name} must be an integer")
    return checked


def _state(values: Mapping[str, Any], name: str, default: str = "unavailable") -> str:
    value = values.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty state")
    return value.strip().lower()


def _optional_metric(values: Mapping[str, Any], name: str, *, unavailable_reason: str) -> dict[str, Any]:
    value = values.get(name)
    if value is None:
        if unavailable_reason not in _UNAVAILABLE_REASONS:
            raise ValueError("unsupported unavailable reason")
        return {"status": "unavailable", "unavailable_reason": unavailable_reason}
    return {"status": "observed", "value": _nonnegative(value, name=name)}


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    revision = completed.stdout.strip().lower()
    if not _SHA.fullmatch(revision):
        raise ValueError("git HEAD is not a full commit SHA")
    return revision


def _read_baseline(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("baseline must be a JSON object")
    campaign_id = payload.get("campaign_id")
    revision = payload.get("baseline_revision")
    if not isinstance(campaign_id, str) or not _CAMPAIGN.fullmatch(campaign_id):
        raise ValueError("baseline campaign_id is not an opaque campaign identifier")
    if not isinstance(revision, str) or not _SHA.fullmatch(revision.lower()):
        raise ValueError("baseline_revision is not a full commit SHA")
    return payload


def _require_zero(values: Mapping[str, Any], name: str) -> int:
    value = _count(values, name)
    if value is None:
        raise ValueError(f"{name} is required for the collision gate")
    if value != 0:
        raise ValueError(f"{name} is non-zero; refusing to produce a seed-eligible snapshot")
    return value


def build_snapshot(
    *,
    baseline: Mapping[str, Any],
    candidate_revision: str,
    captured_at_utc: str,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a sanitized snapshot from bounded MCP scalar observations."""

    if not _SHA.fullmatch(candidate_revision.lower()):
        raise ValueError("candidate_revision must be a full commit SHA")
    if not _UTC.fullmatch(captured_at_utc):
        raise ValueError("captured_at_utc must be a UTC timestamp")

    campaign_id = baseline.get("campaign_id")
    baseline_revision = str(baseline.get("baseline_revision", "")).lower()
    if not isinstance(campaign_id, str) or not _CAMPAIGN.fullmatch(campaign_id):
        raise ValueError("baseline campaign_id is invalid")
    if not _SHA.fullmatch(baseline_revision):
        raise ValueError("baseline_revision is invalid")

    fixture_novel_rows = _require_zero(values, "fixture_novel_rows")
    fixture_chapter_rows = _require_zero(values, "fixture_chapter_rows")
    application_objects = _require_zero(values, "application_prefix_objects")
    backup_objects = _require_zero(values, "backup_prefix_objects")

    approved_bucket_count = _count(values, "approved_test_bucket_classes")
    if approved_bucket_count != 2:
        raise ValueError("the two dedicated test bucket classes must be proven")

    security_findings = _count(values, "security_advisor_findings")
    performance_findings = _count(values, "performance_advisor_findings")
    public_tables = _count(values, "public_tables")
    public_tables_rls = _count(values, "public_tables_rls")
    security_definer_functions = _count(values, "public_security_definer_functions")
    activity_total = _count(values, "activity_total")
    activity_active = _count(values, "activity_active")
    activity_idle = _count(values, "activity_idle")
    activity_null_state = _count(values, "activity_null_state")
    migration_rows = _count(values, "migration_rows")

    writer_state = _state(values, "other_writers_state", "unknown")
    queue_state = _state(values, "original_queue_state", "unknown")
    worker_state = _state(values, "worker_state", "unknown")
    tunnel_state = _state(values, "tunnel_status")
    reader_runtime_state = _state(values, "reader_runtime_state")
    r2_window_state = _state(values, "r2_exact_window_status")
    ruleset_state = _state(values, "ruleset_status")
    candidate_join = "matched" if baseline_revision == candidate_revision.lower() else "mismatch"

    blockers: list[dict[str, str]] = []

    def blocker(blocker_id: str, target: str, reason: str, next_action: str) -> None:
        blockers.append(
            {
                "blocker_id": blocker_id,
                "target": target,
                "reason": reason,
                "next_action": next_action,
            }
        )

    if candidate_join != "matched":
        blocker(
            "blk-b7-candidate-mismatch",
            "candidate_join",
            "MCP snapshot candidate does not match the safety baseline",
            "recapture the baseline and MCP snapshot at one frozen candidate",
        )
    if writer_state not in {"stopped", "paused"}:
        blocker(
            "blk-b7-writer-state",
            "other_writers",
            "other writer state is not independently stopped",
            "obtain an approved runtime writer-state proof before any fixture write",
        )
    if queue_state not in {"stopped", "paused"}:
        blocker(
            "blk-b7-queue-state",
            "original_translation_queue",
            "original translation queue is not independently paused",
            "obtain an approved runtime queue-state proof before profiling",
        )
    if worker_state != "stopped":
        blocker(
            "blk-b7-worker-state",
            "translation_worker",
            "translation worker is not proven stopped",
            "stop the dedicated worker and recapture the safety baseline",
        )
    if tunnel_state != "ready":
        blocker(
            "blk-b7-tunnel",
            "cloudflare_tunnel",
            "isolated Cloudflare tunnel is not ready",
            "start the disposable quick tunnel and prove isolated liveness HTTP 200",
        )
    if reader_runtime_state != "ready":
        blocker(
            "blk-b7-reader-runtime",
            "isolated_reader_runtime",
            "isolated reader runtime is not ready",
            "restore disposable Compose observation and prove isolated liveness",
        )
    if r2_window_state != "observed":
        blocker(
            "blk-b7-r2-analytics",
            "r2_exact_bucket_window",
            "Cloudflare R2 exact bucket/window analytics are unavailable",
            "collect provider-supported exact-window R2 metrics or retain unavailable evidence",
        )
    if ruleset_state != "observed":
        blocker(
            "blk-b7-cloudflare-rulesets",
            "cloudflare_rulesets",
            "Cloudflare ruleset posture endpoint is unavailable",
            "resolve a supported read-only ruleset endpoint before security sign-off",
        )

    snapshot = {
        "artifact_kind": "b7_mcp_snapshot",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": captured_at_utc,
        "candidate_revision": candidate_revision.lower(),
        "baseline_revision": baseline_revision,
        "candidate_join": candidate_join,
        "source": "mcp_read_only",
        "target_classes": {
            "database": "dedicated_test_project",
            "application_bucket": "dedicated_test_application_bucket",
            "backup_bucket": "dedicated_test_backup_bucket",
        },
        "supabase": {
            "project_class": "dedicated_test",
            "advisor_status": "observed"
            if security_findings is not None and performance_findings is not None
            else "partial",
            "security_advisor_findings": security_findings,
            "performance_advisor_findings": performance_findings,
            "fixture_preflight": {
                "novel_rows": fixture_novel_rows,
                "chapter_rows": fixture_chapter_rows,
                "collision": False,
            },
            "migration_rows": migration_rows,
            "public_tables": public_tables,
            "public_tables_rls": public_tables_rls,
            "public_security_definer_functions": security_definer_functions,
            "activity": {
                "session_count": activity_total,
                "active_count": activity_active,
                "idle_count": activity_idle,
                "null_state_count": activity_null_state,
            },
            "pg_stat_statements": {
                "status": _state(values, "pg_stat_statements_status"),
                "statement_rows": _count(values, "pg_stat_statements_rows"),
                "total_calls": _count(values, "pg_stat_statements_calls"),
                "total_exec_time_ms": _nonnegative(
                    values.get("pg_stat_statements_exec_time_ms"), name="pg_stat_statements_exec_time_ms"
                ),
                "total_rows": _count(values, "pg_stat_statements_total_rows"),
            },
            "pool_occupancy": {
                "status": _state(values, "pool_occupancy_status", "unavailable"),
                "unavailable_reason": "pooler_metric_unavailable",
            },
        },
        "cloudflare": {
            "zone": {
                "status": _state(values, "zone_status", "unavailable"),
                "paused": bool(values.get("zone_paused", False)),
            },
            "dns": {
                "record_count": _count(values, "dns_record_count"),
                "proxied_count": _count(values, "dns_proxied_count"),
                "caa_count": _count(values, "dns_caa_count"),
            },
            "dnssec_status": _state(values, "dnssec_status"),
            "minimum_tls_version": str(values.get("minimum_tls_version", "unavailable")),
            "ssl_mode": str(values.get("ssl_mode", "unavailable")),
            "tunnel": {
                "status": tunnel_state,
                "connection_count": _count(values, "tunnel_connection_count"),
                "route_status": _state(values, "tunnel_route_status"),
                "ingress_count": _count(values, "tunnel_ingress_count"),
            },
            "rulesets": {"status": ruleset_state},
            "r2": {
                "approved_test_bucket_classes": approved_bucket_count,
                "application_prefix_objects": application_objects,
                "backup_prefix_objects": backup_objects,
                "exact_bucket_window_status": r2_window_state,
            },
        },
        "safety": {
            "production_data_plane_mutation": False,
            "provider_mutations_attempted": False,
            "raw_provider_response_stored": False,
            "worker_state": worker_state,
            "original_queue_state": queue_state,
            "other_writers_state": writer_state,
            "reader_runtime_state": reader_runtime_state,
            "profile_eligible": not blockers,
            "production_capacity_claim": "not_established",
            "blockers": blockers,
        },
        "posture_recommendations": [
            "enable DNSSEC only through a separately authorized provider change",
            "raise minimum TLS after origin certificate compatibility is verified",
            "consider strict origin TLS only after the origin certificate is proven",
            "do not treat unavailable ruleset or exact-window metrics as secure or billed",
        ],
    }
    return snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-path",
        type=Path,
        default=_REPO_ROOT / "artifacts/operations/reader-capacity-follow-up/baseline.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "artifacts/operations/reader-capacity-follow-up/b7-mcp-snapshot.json",
    )
    parser.add_argument("--candidate-revision", default=None)
    parser.add_argument("--captured-at-utc", default=None)
    parser.add_argument("--security-advisor-findings", type=int, default=None)
    parser.add_argument("--performance-advisor-findings", type=int, default=None)
    parser.add_argument("--fixture-novel-rows", type=int, required=True)
    parser.add_argument("--fixture-chapter-rows", type=int, required=True)
    parser.add_argument("--migration-rows", type=int, default=None)
    parser.add_argument("--public-tables", type=int, default=None)
    parser.add_argument("--public-tables-rls", type=int, default=None)
    parser.add_argument("--public-security-definer-functions", type=int, default=None)
    parser.add_argument("--activity-total", type=int, default=None)
    parser.add_argument("--activity-active", type=int, default=None)
    parser.add_argument("--activity-idle", type=int, default=None)
    parser.add_argument("--activity-null-state", type=int, default=None)
    parser.add_argument("--pg-stat-statements-status", default="unavailable")
    parser.add_argument("--pg-stat-statements-rows", type=int, default=None)
    parser.add_argument("--pg-stat-statements-calls", type=int, default=None)
    parser.add_argument("--pg-stat-statements-exec-time-ms", type=float, default=None)
    parser.add_argument("--pg-stat-statements-total-rows", type=int, default=None)
    parser.add_argument("--pool-occupancy-status", default="unavailable")
    parser.add_argument("--approved-test-bucket-classes", type=int, default=0)
    parser.add_argument("--application-prefix-objects", type=int, required=True)
    parser.add_argument("--backup-prefix-objects", type=int, required=True)
    parser.add_argument("--zone-status", default="unavailable")
    parser.add_argument("--zone-paused", action="store_true")
    parser.add_argument("--dns-record-count", type=int, default=None)
    parser.add_argument("--dns-proxied-count", type=int, default=None)
    parser.add_argument("--dns-caa-count", type=int, default=None)
    parser.add_argument("--dnssec-status", default="unavailable")
    parser.add_argument("--minimum-tls-version", default="unavailable")
    parser.add_argument("--ssl-mode", default="unavailable")
    parser.add_argument("--tunnel-status", default="unavailable")
    parser.add_argument("--tunnel-connection-count", type=int, default=None)
    parser.add_argument("--tunnel-route-status", default="unavailable")
    parser.add_argument("--tunnel-ingress-count", type=int, default=None)
    parser.add_argument("--ruleset-status", default="unavailable")
    parser.add_argument("--r2-exact-window-status", default="unavailable")
    parser.add_argument("--worker-state", default="unknown")
    parser.add_argument("--original-queue-state", default="unknown")
    parser.add_argument("--other-writers-state", default="unknown")
    parser.add_argument("--reader-runtime-state", default="unavailable")
    return parser


def main() -> int:
    args = _parser().parse_args()
    baseline = _read_baseline(args.baseline_path)
    candidate = args.candidate_revision or _git_revision()
    captured = args.captured_at_utc or _timestamp()
    values = vars(args)
    payload = build_snapshot(
        baseline=baseline,
        candidate_revision=candidate,
        captured_at_utc=captured,
        values=values,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"B7 MCP snapshot written: {args.output} "
        f"status={'ready' if payload['safety']['profile_eligible'] else 'blocked'} "
        f"blockers={len(payload['safety']['blockers'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
