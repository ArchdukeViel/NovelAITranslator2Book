"""Focused tests for the provider-free B7 blocked evidence bundle."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_tool(name: str) -> ModuleType:
    path = Path(__file__).parents[2] / "tools" / "capacity" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs(tmp_path: Path) -> tuple[Path, Path, str]:
    candidate = "a" * 40
    baseline = {
        "campaign_id": "camp-20260831T000000Z",
        "interval_start": "2026-08-31T00:00:00Z",
        "baseline_revision": candidate,
    }
    mcp = {"candidate_revision": candidate, "campaign_id": baseline["campaign_id"]}
    baseline_path = tmp_path / "baseline.json"
    mcp_path = tmp_path / "b7-mcp-snapshot.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    mcp_path.write_text(json.dumps(mcp), encoding="utf-8")
    return baseline_path, mcp_path, candidate


def test_generator_emits_complete_fail_closed_bundle(tmp_path: Path) -> None:
    capture = _load_tool("capture_b7_blocked_bundle")
    validate = _load_tool("validate_b7_blocked_bundle")
    baseline_path, mcp_path, candidate = _inputs(tmp_path)

    capture.generate(
        tmp_path,
        baseline_path,
        mcp_path,
        candidate,
        "2026-08-31T00:01:00Z",
    )

    assert validate.validate(tmp_path, candidate) == []
    assert (tmp_path / "frontend-profile.json").is_file()
    assert (tmp_path / "handoff.json").is_file()
    assert (tmp_path / "handoff.md").is_file()


def test_validator_rejects_nonzero_blocked_attempts(tmp_path: Path) -> None:
    capture = _load_tool("capture_b7_blocked_bundle")
    validate = _load_tool("validate_b7_blocked_bundle")
    baseline_path, mcp_path, candidate = _inputs(tmp_path)
    capture.generate(tmp_path, baseline_path, mcp_path, candidate, "2026-08-31T00:01:00Z")

    path = tmp_path / "load-generator.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["attempted_attempts"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate.validate(tmp_path, candidate)
    assert any("load-generator attempted_attempts must be zero" in error for error in errors)


def test_generator_rejects_mcp_candidate_drift(tmp_path: Path) -> None:
    capture = _load_tool("capture_b7_blocked_bundle")
    baseline_path, mcp_path, candidate = _inputs(tmp_path)
    mcp_path.write_text(
        json.dumps({"candidate_revision": "b" * 40, "campaign_id": "camp-20260831T000000Z"}),
        encoding="utf-8",
    )

    try:
        capture.generate(tmp_path, baseline_path, mcp_path, candidate, "2026-08-31T00:01:00Z")
    except ValueError as exc:
        assert "MCP snapshot is not joined" in str(exc)
    else:
        raise AssertionError("candidate drift must refuse bundle generation")
