from __future__ import annotations

import json
from pathlib import Path

from tools.capacity.validate_b6_private_hosted_audit import validate


def _write_set(root: Path, *, candidate_sha: str = "a" * 40) -> None:
    payloads = {
        "private-hosted-runs.json": {
            "artifact_kind": "private_hosted_runs",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
            "status": "blocked",
            "blockers": [{"area": "runner", "reason": "unavailable"}],
            "runner_policy": "github_hosted_ubuntu_required; persistent_self_hosted_forbidden",
            "runs": [],
        },
        "workflow-timing.json": {
            "artifact_kind": "workflow_timing",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
            "status": "blocked",
        },
        "protection-before.json": {
            "artifact_kind": "protection_before",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
        },
        "visibility-transition.json": {
            "artifact_kind": "visibility_transition",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
            "status": "blocked",
            "attempted": False,
            "before_visibility": "private",
            "after_visibility": "not_run",
            "visibility_change_authorized": False,
        },
        "protection-after.json": {
            "artifact_kind": "protection_after",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
            "status": "not_run",
        },
        "fork-safety.json": {
            "artifact_kind": "fork_safety",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
            "status": "not_run",
        },
        "public-main-runs.json": {
            "artifact_kind": "public_main_runs",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": candidate_sha,
            "status": "not_run",
        },
    }
    for filename, payload in payloads.items():
        (root / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_b6_validator_accepts_blocked_private_gate(tmp_path: Path) -> None:
    _write_set(tmp_path)
    assert validate(tmp_path) == []


def test_b6_validator_rejects_visibility_attempt(tmp_path: Path) -> None:
    _write_set(tmp_path)
    path = tmp_path / "visibility-transition.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["attempted"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert any("visibility transition must not be attempted" in error for error in validate(tmp_path))
