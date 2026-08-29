from __future__ import annotations

import math
from pathlib import Path
from typing import Any

REQUIRED_ROUTES = {"health_live", "catalog", "detail", "chapter", "search"}
TOPOLOGIES = {"direct_service", "caddy_loopback", "cloudflare_tunnel"}
VALID_STATUSES = {"passed", "failed", "unavailable"}

CAPACITY_TOOLS = Path(__file__).parents[2] / "tools" / "capacity"


def _required_cell_key(cell: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(cell.get("topology")),
        str(cell.get("route")),
        str(cell.get("cache_state")),
    )


def validate_profile_contract(payload: dict[str, Any]) -> bool:
    required_keys = {"schema_version", "campaign_id", "cells"}
    if not required_keys.issubset(payload.keys()):
        return False
    if payload.get("schema_version") != 1:
        return False
    if not isinstance(payload["campaign_id"], str) or not payload["campaign_id"]:
        return False
    cells = payload["cells"]
    if not isinstance(cells, list):
        return False

    required_keys_seen: set[tuple[str, str, str]] = set()
    for cell in cells:
        if not isinstance(cell, dict):
            return False
        cell_keys = {
            "campaign_id",
            "topology",
            "route",
            "cache_state",
            "max_attempts_per_cell",
            "sample_target",
            "attempted_count",
            "sample_count",
            "valid_latency_count",
            "unavailable_fields",
            "p95_ms",
            "status",
        }
        if not cell_keys.issubset(cell.keys()):
            return False
        if cell["campaign_id"] != payload["campaign_id"]:
            return False
        if cell["topology"] not in TOPOLOGIES or cell["route"] not in REQUIRED_ROUTES:
            continue
        if cell["cache_state"] not in {"warm", "cold", "unknown"}:
            return False
        if cell["status"] not in VALID_STATUSES:
            return False
        if not isinstance(cell["unavailable_fields"], list):
            return False
        if (
            not isinstance(cell["max_attempts_per_cell"], int)
            or cell["max_attempts_per_cell"] < 1
            or cell["attempted_count"] > cell["max_attempts_per_cell"]
        ):
            return False
        if cell["status"] == "unavailable":
            if not cell["unavailable_fields"]:
                return False
            if cell["sample_count"] != 0 or cell["valid_latency_count"] != 0:
                return False
            if cell["p95_ms"] is not None:
                return False
            if cell["cache_state"] == "unknown" and "cold_cache_control_unavailable" not in cell["unavailable_fields"]:
                return False
        else:
            if cell["cache_state"] == "unknown":
                return False
            if cell["sample_count"] < cell["sample_target"]:
                return False
            if cell["valid_latency_count"] != cell["sample_count"]:
                return False
            if not isinstance(cell["p95_ms"], (int, float)) or not math.isfinite(cell["p95_ms"]):
                return False
        key = _required_cell_key(cell)
        if key in required_keys_seen:
            return False
        required_keys_seen.add(key)

    for topology in TOPOLOGIES:
        for route in REQUIRED_ROUTES:
            warm_key = (topology, route, "warm")
            if warm_key not in required_keys_seen:
                return False
            cold_keys = {
                (topology, route, "cold"),
                (topology, route, "unknown"),
            }
            if not required_keys_seen.intersection(cold_keys):
                return False
    return True


def _cell(*, topology: str, route: str, cache_state: str, status: str) -> dict[str, Any]:
    unavailable = (
        []
        if status != "unavailable"
        else ["cold_cache_control_unavailable" if cache_state == "unknown" else "target_not_configured"]
    )
    samples = 50 if status != "unavailable" else 0
    return {
        "campaign_id": "test-camp",
        "topology": topology,
        "route": route,
        "cache_state": cache_state,
        "max_attempts_per_cell": 60,
        "sample_target": 50,
        "attempted_count": samples,
        "sample_count": samples,
        "valid_latency_count": samples,
        "unavailable_fields": unavailable,
        "p95_ms": None if status == "unavailable" else 12.0,
        "status": status,
    }


def test_profile_contract_validation():
    valid = {
        "schema_version": 1,
        "campaign_id": "test-camp",
        "cells": [
            _cell(
                topology=topology,
                route=route,
                cache_state=cache_state,
                status="unavailable" if cache_state == "unknown" else "passed",
            )
            for topology in TOPOLOGIES
            for route in REQUIRED_ROUTES
            for cache_state in ("warm", "unknown")
        ],
    }
    assert validate_profile_contract(valid) is True

    invalid = {"schema_version": 2}
    assert validate_profile_contract(invalid) is False


def test_profile_contract_rejects_missing_or_duplicate_required_cells():
    payload = {
        "schema_version": 1,
        "campaign_id": "test-camp",
        "cells": [
            _cell(
                topology=topology,
                route=route,
                cache_state=cache_state,
                status="unavailable" if cache_state == "unknown" else "passed",
            )
            for topology in TOPOLOGIES
            for route in REQUIRED_ROUTES
            for cache_state in ("warm", "unknown")
        ],
    }
    payload["cells"].pop()
    assert validate_profile_contract(payload) is False

    duplicate = dict(payload)
    duplicate["cells"] = list(payload["cells"])
    duplicate["cells"].append(
        _cell(
            topology="direct_service",
            route="health_live",
            cache_state="warm",
            status="passed",
        )
    )
    assert validate_profile_contract(duplicate) is False


def test_profile_contract_rejects_fake_unavailable_or_unknown_samples():
    payload = {
        "schema_version": 1,
        "campaign_id": "test-camp",
        "cells": [
            _cell(
                topology=topology,
                route=route,
                cache_state=cache_state,
                status="unavailable" if cache_state == "unknown" else "passed",
            )
            for topology in TOPOLOGIES
            for route in REQUIRED_ROUTES
            for cache_state in ("warm", "unknown")
        ],
    }
    payload["cells"][0]["sample_count"] = 1
    assert validate_profile_contract(payload) is False

    payload["cells"][0]["sample_count"] = 0
    payload["cells"][0]["valid_latency_count"] = 0
    payload["cells"][0]["p95_ms"] = None
    payload["cells"][0]["status"] = "unavailable"
    payload["cells"][0]["cache_state"] = "unknown"
    payload["cells"][0]["unavailable_fields"] = ["target_not_configured"]
    assert validate_profile_contract(payload) is False


def test_reader_runner_contract_uses_cloudflare_gate_and_explicit_caddy_binding():
    runner = (CAPACITY_TOOLS / "run_reader_profile.ps1").read_text(encoding="utf-8")
    preflight = (CAPACITY_TOOLS / "run_reader_follow_up_preflight.ps1").read_text(encoding="utf-8")

    assert "[string]$CloudflareBaseUrl" in runner
    assert '[string]$SloGateTopology = "cloudflare_tunnel"' in runner
    assert '[string]$SloGateTopology = "cloudflare_tunnel"' in preflight
    assert 'env = "READER_CLOUDFLARE_BASE_URL"' in runner
    assert '"cloudflare_tunnel"' in preflight
    assert "[string]$CaddyHostHeader" in runner
    assert 'Get-EnvValue "READER_CADDY_HOST_HEADER"' in runner
    assert '"--host-header", $HostHeader' in runner
    assert '"caddy_host_binding_unavailable"' in runner
    assert "if ($baselineFixtureId -ne $fixtureId)" in runner
    assert '"^fixture-[0-9a-f]{16}$"' in preflight
    assert '"disposable_reader_reset_or_explicit_unavailable"' in preflight


def test_reader_runner_keeps_cold_sample_target_separate_from_warm_target():
    runner = (CAPACITY_TOOLS / "run_reader_profile.ps1").read_text(encoding="utf-8")

    assert "$WarmSamples $summary" in runner
    assert "$ColdSamples $coldSummary" in runner
    assert '"disposable_reader_reset"' in runner
    assert '"--skip-warmup"' in runner
    assert '"cold_cache_control_unavailable"' in runner


def test_reader_runner_uses_the_isolated_reset_helper_contract():
    runner = (CAPACITY_TOOLS / "run_reader_profile.ps1").read_text(encoding="utf-8")
    reset = (CAPACITY_TOOLS / "reset_reader_cache.ps1").read_text(encoding="utf-8")

    assert "[string]$ColdResetScript" in runner
    assert "[string]$ColdResetComposeProject" in runner
    assert "[string]$ColdResetComposeEnvFile" in runner
    assert "Invoke-ColdReset" in runner
    assert "-ComposeProject" in runner
    assert "-ComposeEnvFile" in runner
    assert "[string]$ComposeEnvFile" in reset
    assert "--env-file" in reset
    preflight = (CAPACITY_TOOLS / "run_reader_follow_up_preflight.ps1").read_text(encoding="utf-8")
    assert "function Get-PowerShellCommand" in preflight
    assert "& $validatorShell" in preflight
    assert "redis-cli FLUSHDB" in reset
    assert "restart reader" in reset
    assert '"^reader-capacity-test-[A-Za-z0-9_-]+$"' in reset
