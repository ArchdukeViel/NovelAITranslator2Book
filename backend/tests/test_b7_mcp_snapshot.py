from __future__ import annotations

import json
import re

import pytest
from tools.capacity.capture_b7_mcp_snapshot import build_snapshot
from tools.capacity.validate_b7_mcp_snapshot import validate_snapshot

SHA = "a" * 40
CAMPAIGN = "camp-20260831T010203Z"
BASELINE = {"campaign_id": CAMPAIGN, "baseline_revision": SHA}


def _values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "security_advisor_findings": 0,
        "performance_advisor_findings": 101,
        "fixture_novel_rows": 0,
        "fixture_chapter_rows": 0,
        "migration_rows": 1,
        "public_tables": 37,
        "public_tables_rls": 37,
        "public_security_definer_functions": 1,
        "activity_total": 12,
        "activity_active": 1,
        "activity_idle": 4,
        "activity_null_state": 7,
        "pg_stat_statements_status": "unavailable",
        "pool_occupancy_status": "unavailable",
        "approved_test_bucket_classes": 2,
        "application_prefix_objects": 0,
        "backup_prefix_objects": 0,
        "zone_status": "active",
        "dns_record_count": 3,
        "dns_proxied_count": 3,
        "dns_caa_count": 0,
        "dnssec_status": "disabled",
        "minimum_tls_version": "1.0",
        "ssl_mode": "full",
        "tunnel_status": "down",
        "tunnel_connection_count": 0,
        "tunnel_route_status": "observed",
        "tunnel_ingress_count": 2,
        "ruleset_status": "unavailable",
        "r2_exact_window_status": "unavailable",
        "worker_state": "stopped",
        "original_queue_state": "unknown",
        "other_writers_state": "unknown",
        "reader_runtime_state": "unavailable",
    }
    values.update(overrides)
    return values


def test_snapshot_is_sanitized_and_fail_closed() -> None:
    payload = build_snapshot(
        baseline=BASELINE,
        candidate_revision=SHA,
        captured_at_utc="2026-08-31T01:02:03Z",
        values=_values(),
    )

    assert payload["artifact_kind"] == "b7_mcp_snapshot"
    assert payload["candidate_join"] == "matched"
    assert payload["supabase"]["fixture_preflight"] == {
        "novel_rows": 0,
        "chapter_rows": 0,
        "collision": False,
    }
    assert payload["cloudflare"]["r2"]["application_prefix_objects"] == 0
    assert payload["cloudflare"]["tunnel"]["status"] == "down"
    assert payload["safety"]["profile_eligible"] is False
    blocker_ids = {item["blocker_id"] for item in payload["safety"]["blockers"]}
    assert {"blk-b7-writer-state", "blk-b7-tunnel", "blk-b7-r2-analytics"} <= blocker_ids
    raw = json.dumps(payload)
    assert not re.search(r"(?i)(postgres(?:ql)?://|https?://|bearer |password|api[_-]?key|query_text)", raw)
    assert "production_capacity_claim" in raw
    assert validate_snapshot(payload) == []


def test_candidate_drift_is_a_blocker() -> None:
    payload = build_snapshot(
        baseline=BASELINE,
        candidate_revision="b" * 40,
        captured_at_utc="2026-08-31T01:02:03Z",
        values=_values(),
    )

    assert payload["candidate_join"] == "mismatch"
    assert any(item["blocker_id"] == "blk-b7-candidate-mismatch" for item in payload["safety"]["blockers"])


def test_fixture_collision_refuses_snapshot() -> None:
    with pytest.raises(ValueError, match="refusing to produce"):
        build_snapshot(
            baseline=BASELINE,
            candidate_revision=SHA,
            captured_at_utc="2026-08-31T01:02:03Z",
            values=_values(fixture_novel_rows=1),
        )
