"""Validate the sanitized Phase B6 private-hosted evidence set."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_REQUIRED = {
    "private-hosted-runs.json": "private_hosted_runs",
    "workflow-timing.json": "workflow_timing",
    "protection-before.json": "protection_before",
    "visibility-transition.json": "visibility_transition",
    "protection-after.json": "protection_after",
    "fork-safety.json": "fork_safety",
    "public-main-runs.json": "public_main_runs",
}
_SENSITIVE_KEY = re.compile(
    r"(?:secret|token|password|credential|cookie|authorization|connection[_-]?url)", re.IGNORECASE
)
_SENSITIVE_VALUE = re.compile(
    r"(?:bearer\s+|gh[pousr]_\w{20,}|sk-[A-Za-z0-9_-]{16,}|postgres(?:ql)?://)", re.IGNORECASE
)
_SAFE_CONTROL_KEYS = {
    "secret_scanning",
    "push_protection",
    "dependabot_security_updates",
    "code_scanning_default_setup",
}


def _walk_redaction(value: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if _SENSITIVE_KEY.search(str(key)) and key not in _SAFE_CONTROL_KEYS | {
                "secret_access",
                "secrets_or_runtime_data_in_evidence",
            }:
                violations.append(f"{path}.{key}")
            violations.extend(_walk_redaction(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_walk_redaction(child, f"{path}[{index}]"))
    elif isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        violations.append(path)
    return violations


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    for filename, kind in _REQUIRED.items():
        path = root / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            errors.append(f"invalid JSON {filename}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"root must be an object {filename}")
            continue
        payloads[filename] = payload
        if payload.get("artifact_kind") != kind:
            errors.append(f"wrong artifact kind {filename}")
        if payload.get("schema_version") != 1:
            errors.append(f"unsupported schema {filename}")
        if payload.get("repository_visibility") != "private":
            errors.append(f"repository visibility is not private {filename}")
        errors.extend(f"redaction violation {item}" for item in _walk_redaction(payload))

    candidate_shas = {payload.get("candidate_sha") for payload in payloads.values() if payload.get("candidate_sha")}
    if len(candidate_shas) != 1:
        errors.append("all artifacts must share one candidate SHA")
    private_runs = payloads.get("private-hosted-runs.json")
    if private_runs:
        if private_runs.get("status") not in {"complete", "blocked", "unavailable"}:
            errors.append("private-hosted-runs status is invalid")
        if private_runs.get("status") != "complete" and not private_runs.get("blockers"):
            errors.append("blocked private-hosted-runs must include blockers")
        if private_runs.get("runner_policy") != "github_hosted_ubuntu_required; persistent_self_hosted_forbidden":
            errors.append("runner policy is invalid")
        for run in private_runs.get("runs", []):
            if not isinstance(run, dict) or run.get("candidate_sha_match") is not True:
                errors.append("every recorded run must match the exact candidate SHA")
    timing = payloads.get("workflow-timing.json")
    if timing and timing.get("status") not in {"complete", "blocked", "unavailable"}:
        errors.append("workflow timing status is invalid")
    visibility = payloads.get("visibility-transition.json")
    if visibility:
        if visibility.get("attempted") is not False:
            errors.append("visibility transition must not be attempted without authority")
        if visibility.get("before_visibility") != "private" or visibility.get("after_visibility") != "not_run":
            errors.append("visibility transition state is invalid")
        if visibility.get("visibility_change_authorized") is not False:
            errors.append("visibility authorization must be false")
    for filename in ("protection-after.json", "fork-safety.json", "public-main-runs.json"):
        payload = payloads.get(filename)
        if payload and payload.get("status") != "not_run":
            errors.append(f"{filename} must remain not_run while publication is blocked")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase B6 hosted evidence")
    parser.add_argument("--root", type=Path, default=Path("artifacts/public-hosted-execution"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sample = {
            "artifact_kind": "private_hosted_runs",
            "schema_version": 1,
            "repository_visibility": "private",
            "candidate_sha": "a" * 40,
            "status": "blocked",
            "blockers": [{"reason": "runner unavailable"}],
            "runner_policy": "github_hosted_ubuntu_required; persistent_self_hosted_forbidden",
            "runs": [],
        }
        if _walk_redaction(sample):
            print("B6 validator self-test failed")
            return 1
        print("B6 validator self-test passed")
        return 0
    errors = validate(args.root)
    if errors:
        print("B6 private hosted evidence invalid")
        for error in errors:
            print(f"- {error}")
        return 1
    print("B6 private hosted evidence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
