"""Validate the sanitized Phase B5 dependency evidence contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ARTIFACTS = (
    "dependabot-ledger.json",
    "dependency-validation.json",
    "candidate-manifest.json",
    "publication-audit-candidate.json",
)


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _base(payload: Any, kind: str, errors: list[str]) -> None:
    if not isinstance(payload, dict):
        _error(errors, f"{kind} is not an object")
        return
    if payload.get("artifact_kind") != kind:
        _error(errors, f"artifact kind mismatch for {kind}")
    if payload.get("schema_version") != 1:
        _error(errors, f"schema version mismatch for {kind}")
    if not isinstance(payload.get("campaign_id"), str) or not payload["campaign_id"].startswith("campaign-"):
        _error(errors, f"campaign id missing for {kind}")
    if not isinstance(payload.get("captured_at_utc"), str) or not payload["captured_at_utc"].endswith("Z"):
        _error(errors, f"timestamp missing for {kind}")


def _redaction_errors(value: Any, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) != "secrets_or_runtime_data_in_evidence" and re.search(
                r"secret|token|password|credential|connection.?url|raw.?response|body", str(key), re.IGNORECASE
            ):
                _error(errors, f"protected field present: {path}.{key}")
            errors.extend(_redaction_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_redaction_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str) and re.search(
        r"(postgres(ql)?://|Bearer\s+|AKIA[0-9A-Z]{16}|-----BEGIN|SELECT\s+.+FROM)", value, re.IGNORECASE
    ):
        _error(errors, f"protected text present: {path}")
    return errors


def validate_ledger(payload: Any) -> list[str]:
    errors: list[str] = []
    _base(payload, "dependabot_ledger", errors)
    if not isinstance(payload, dict):
        return errors
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != 58:
        _error(errors, "Dependabot ledger must contain the complete 58-PR audit")
        return errors
    numbers: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            _error(errors, "ledger entry is not an object")
            continue
        number = entry.get("pr_number")
        if not isinstance(number, int) or number in numbers:
            _error(errors, "ledger PR number is missing or duplicated")
        numbers.add(number)
        required = {
            "state",
            "merged",
            "ecosystem",
            "dependency",
            "proposed_version",
            "candidate_version",
            "closure",
            "security_signal",
            "action",
            "validation",
        }
        if not required.issubset(entry):
            _error(errors, f"ledger entry {number} is incomplete")
        if entry.get("state") not in {"open", "closed"} or not isinstance(entry.get("merged"), bool):
            _error(errors, f"ledger entry {number} state is invalid")
        if entry.get("security_signal") != "not_security_advisory":
            _error(errors, f"ledger entry {number} security classification is not explicit")
        if not isinstance(entry.get("validation"), list) or not entry["validation"]:
            _error(errors, f"ledger entry {number} validation is missing")
    if (
        payload.get("open_count") != 14
        or payload.get("closed_count") != 44
        or payload.get("closed_unmerged_audit_input_count") != 38
    ):
        _error(errors, "Dependabot state counts do not match the complete audit")
    obsolete = [entry for entry in entries if entry.get("dependency") in {"boto3", "moto[s3]"}]
    if len(obsolete) != 4 or any(entry.get("action") != "obsolete_after_r2_cutover" for entry in obsolete):
        _error(errors, "all legacy S3 dependency proposals must be obsolete after R2 cutover")
    held = [entry for entry in entries if entry.get("dependency") in {"typescript", "eslint"}]
    if len(held) != 2 or any(entry.get("action") != "held_latest_compatible" for entry in held):
        _error(errors, "incompatible major updates must be explicitly held")
    return errors


def validate_dependency(payload: Any) -> list[str]:
    errors: list[str] = []
    _base(payload, "dependency_validation", errors)
    if not isinstance(payload, dict):
        return errors
    if payload.get("status") not in {"complete", "complete_with_quantified_blocker"}:
        _error(errors, "dependency validation status is invalid")
    checks = payload.get("checks")
    if not isinstance(checks, list):
        _error(errors, "dependency checks are missing")
    else:
        names = {item.get("check") for item in checks if isinstance(item, dict)}
        required = {
            "dependabot_open_closed_inventory",
            "uv_lock_consistency",
            "requirements_lock_regeneration",
            "frontend_lockfile_install",
            "frontend_typecheck",
            "frontend_lint",
            "frontend_tests",
            "typescript_7_compatibility",
            "eslint_10_compatibility",
            "full_pip_tools_transitive_upgrade",
            "worker_install_and_audit",
            "worker_contract_tests",
            "worker_binding_tests",
            "worker_typecheck",
            "worker_test_deploy_dry_run",
            "frontend_audit",
            "frontend_build",
            "backend_affected_matrix",
            "backend_full_suite",
            "ruff",
            "pyright",
            "b4_diagnostics_after_dependency_change",
            "b5_generator_validator",
        }
        if names != required:
            _error(errors, "dependency check set is incomplete or unexpected")
        for item in checks:
            if not isinstance(item, dict) or item.get("status") not in {"passed", "blocked", "unavailable"}:
                _error(errors, "dependency check status is invalid")
    holds = payload.get("compatibility_holds")
    if not isinstance(holds, list) or {item.get("dependency") for item in holds if isinstance(item, dict)} != {
        "typescript",
        "eslint",
    }:
        _error(errors, "compatibility holds are incomplete")
    if (
        payload.get("provider_writes_attempted") is not False
        or payload.get("production_actions_attempted") is not False
    ):
        _error(errors, "dependency validation records an unauthorized action")
    if not isinstance(payload.get("blockers"), list):
        _error(errors, "dependency blocker list is invalid")
    elif payload.get("status") == "complete_with_quantified_blocker" and not payload["blockers"]:
        _error(errors, "quantified dependency blockers are missing")
    elif payload.get("status") == "complete" and payload["blockers"]:
        _error(errors, "complete dependency evidence cannot retain blockers")
    return errors


def validate_candidate(payload: Any) -> list[str]:
    errors: list[str] = []
    _base(payload, "candidate_manifest", errors)
    if not isinstance(payload, dict):
        return errors
    if payload.get("r2_storage_contract") != "r2_only" or payload.get("active_legacy_storage_references") != 0:
        _error(errors, "candidate does not prove the R2-only storage contract")
    for key in ("workflow_pins", "container_pins", "files"):
        if not isinstance(payload.get(key), list) or not payload[key]:
            _error(errors, f"candidate {key} are missing")
    if payload.get("production_capacity_claim") != "not_established":
        _error(errors, "candidate production capacity claim is invalid")
    missing = payload.get("missing_candidate_files")
    if not isinstance(missing, list):
        _error(errors, "candidate missing-file list is invalid")
    return errors


def validate_publication(payload: Any) -> list[str]:
    errors: list[str] = []
    _base(payload, "publication_audit_candidate", errors)
    if not isinstance(payload, dict):
        return errors
    if payload.get("repository_visibility") != "private" or payload.get("r2_only_contract") is not True:
        _error(errors, "publication audit target is not private and R2-only")
    if payload.get("secrets_or_runtime_data_in_evidence") is not False:
        _error(errors, "publication audit permits protected data")
    if (
        payload.get("provider_writes_attempted") is not False
        or payload.get("production_actions_attempted") is not False
    ):
        _error(errors, "publication audit records an unauthorized action")
    if payload.get("production_capacity_claim") != "not_established":
        _error(errors, "publication production capacity claim is invalid")
    return errors


VALIDATORS = {
    "dependabot-ledger.json": validate_ledger,
    "dependency-validation.json": validate_dependency,
    "candidate-manifest.json": validate_candidate,
    "publication-audit-candidate.json": validate_publication,
}


def validate_directory(root: Path) -> list[str]:
    errors: list[str] = []
    payloads: dict[str, Any] = {}
    for name in REQUIRED_ARTIFACTS:
        path = root / name
        if not path.is_file():
            _error(errors, f"missing artifact: {name}")
            continue
        try:
            payloads[name] = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            _error(errors, f"invalid JSON artifact: {name}")
    for name, payload in payloads.items():
        errors.extend(f"{name}: {error}" for error in VALIDATORS[name](payload))
        errors.extend(f"{name}: {error}" for error in _redaction_errors(payload))
    campaigns = {payload.get("campaign_id") for payload in payloads.values() if isinstance(payload, dict)}
    if len(campaigns) != 1:
        _error(errors, "B5 artifacts do not share one campaign id")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase B5 dependency evidence")
    parser.add_argument("--root", type=Path, default=_ROOT / "artifacts" / "public-hosted-execution")
    args = parser.parse_args()
    errors = validate_directory(args.root)
    if errors:
        print(f"B5 dependency evidence invalid: {len(errors)} errors")
        return 1
    print("B5 dependency evidence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
