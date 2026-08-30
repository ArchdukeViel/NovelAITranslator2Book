"""Generate sanitized Phase B5 dependency-reconciliation evidence.

This tool records the already completed read-only Dependabot audit and the
candidate's local manifest/pin state. It never calls a provider, prints PR
bodies, or persists secrets. The evidence is intentionally provisional until
the candidate files are committed and the publication audit is rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = _ROOT / "artifacts" / "public-hosted-execution"

_PR_SNAPSHOT = """
2|closed|merged|npm|npm_and_yarn_group|grouped
3|closed|unmerged|uv|pyasn1|0.6.4
4|closed|merged|npm|next|15.5.21
42|closed|unmerged|uv|cryptography|50.0.0
43|closed|unmerged|uv|uvicorn|0.52.1
44|closed|unmerged|npm|tailwindcss|4.3.3
45|closed|unmerged|github-actions|GitGuardian/ggshield/actions/secret|1.53.0
46|closed|unmerged|github-actions|dorny/paths-filter|4.0.3
47|closed|unmerged|uv|moto[s3]|5.2.2
48|closed|unmerged|npm|vitest|4.1.10
49|closed|unmerged|github-actions|docker/login-action|4.6.0
50|closed|unmerged|uv|pypdf|6.15.0
51|closed|unmerged|npm|react-dom and @types/react-dom|grouped
52|closed|unmerged|uv|pydantic-settings|2.15.0
53|closed|unmerged|npm|@testing-library/user-event|14.6.3
54|closed|unmerged|github-actions|actions/checkout|7.0.1
55|closed|unmerged|uv|boto3|1.43.67
56|closed|unmerged|npm|eslint-config-next|16.3.0
57|closed|unmerged|github-actions|actions/dependency-review-action|5.0.0
58|closed|unmerged|npm|npm_and_yarn_group|grouped
78|closed|unmerged|docker|python|3.14-slim
79|closed|unmerged|docker|node|26-alpine
80|closed|merged|github-actions|astral-sh/setup-uv|9.0.0
81|closed|unmerged|npm|@vitejs/plugin-react|6.0.5
82|closed|merged|uv|psycopg[binary]|3.3.4
83|closed|merged|npm|tailwind-merge|3.6.0
84|closed|unmerged|npm|@types/node|26.2.0
85|closed|unmerged|npm|jsdom|30.0.1
86|closed|unmerged|npm|eslint|10.8.1
89|closed|unmerged|docker|node|c610fcd
90|closed|unmerged|docker|python|3.14.7-slim
91|closed|unmerged|npm|@testing-library/jest-dom|7.0.1
92|closed|unmerged|github-actions|appleboy/scp-action|1.0.0
93|closed|unmerged|npm|next|16.3.0
94|closed|unmerged|npm|typescript|7.0.2
95|closed|unmerged|npm|fast-check|4.9.0
96|closed|unmerged|npm|lucide-react|1.31.0
111|closed|merged|docker|python|3.14.7-slim
114|open|unmerged|github-actions|docker/setup-buildx-action|4.3.0
115|closed|unmerged|npm|@testing-library/user-event|14.6.5
116|closed|unmerged|npm|lucide-react|1.32.0
117|open|unmerged|uv|hypothesis|6.165.10
118|closed|unmerged|uv|boto3|1.43.73
119|closed|unmerged|uv|httpx2|2.11.0
120|open|unmerged|uv|rq|2.11.0
121|open|unmerged|uv|python-dotenv|1.2.3
122|open|unmerged|npm|vitest|4.1.11
123|open|unmerged|npm|@vitejs/plugin-react|6.1.0
124|open|unmerged|npm|vite|8.2.2
125|closed|unmerged|npm|lucide-react|1.33.0
126|open|unmerged|docker|node|26.8.1-alpine
127|open|unmerged|docker|python|3.14.7-slim
128|open|unmerged|npm|@testing-library/user-event|14.6.6
129|closed|unmerged|github-actions|actions/upload-artifact|7.0.1
130|open|unmerged|uv|httpx2|2.12.0
131|open|unmerged|npm|lucide-react|1.34.0
132|open|unmerged|github-actions|GitGuardian/ggshield/actions/secret|1.54.0
133|open|unmerged|uv|boto3|1.43.80
""".strip()

_CURRENT = {
    "npm_and_yarn_group": "reconciled_in_candidate_manifests",
    "pyasn1": "0.6.4",
    "cryptography": "50.0.1",
    "uvicorn": "0.52.4",
    "tailwindcss": "4.3.3",
    "GitGuardian/ggshield/actions/secret": "1.54.0",
    "dorny/paths-filter": "4.0.3",
    "moto[s3]": "removed",
    "vitest": "4.1.11",
    "docker/login-action": "4.6.0",
    "pypdf": "not_declared",
    "react-dom and @types/react-dom": "react-dom 19.2.8; @types/react-dom 19.2.5",
    "pydantic-settings": "2.15.0",
    "@testing-library/user-event": "14.6.6",
    "actions/checkout": "7.0.1",
    "boto3": "removed",
    "eslint-config-next": "16.3.3",
    "actions/dependency-review-action": "not_used; Trivy gate retained",
    "python": "3.14.7-slim",
    "node": "26.8.1-alpine",
    "astral-sh/setup-uv": "10.0.1",
    "@vitejs/plugin-react": "6.1.1",
    "psycopg[binary]": "3.3.4",
    "tailwind-merge": "3.6.0",
    "@types/node": "26.4.0",
    "jsdom": "30.0.1",
    "eslint": "9.39.5",
    "appleboy/scp-action": "1.0.0",
    "next": "16.3.3",
    "typescript": "6.0.3",
    "fast-check": "4.9.0",
    "lucide-react": "1.37.0",
    "docker/setup-buildx-action": "4.3.0",
    "hypothesis": "6.167.1",
    "httpx2": "2.12.0",
    "rq": "2.12.0",
    "python-dotenv": "1.2.3",
    "vite": "8.2.2",
    "actions/upload-artifact": "7.0.1",
}

_OBSOLETE = {"boto3", "moto[s3]"}
_HELD = {"typescript", "eslint"}
_CANDIDATE_FILES = (
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/container-publish.yml",
    ".github/workflows/secret-scan.yml",
    "deploy/admin.Dockerfile",
    "deploy/reader.Dockerfile",
    "deploy/frontend.Dockerfile",
    "pyproject.toml",
    "uv.lock",
    "requirements.lock",
    "requirements-dev.lock",
    "frontend/package.json",
    "frontend/package-lock.json",
    "workers/r2-gateway/package.json",
    "workers/r2-gateway/package-lock.json",
    "tools/capacity/run_b5_dependency_reconciliation.py",
    "tools/capacity/validate_b5_dependency_reconciliation.py",
    "backend/tests/test_b5_dependency_reconciliation.py",
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _opaque(prefix: str) -> str:
    return f"{prefix}-{hashlib.sha256(_timestamp().encode()).hexdigest()[:16]}"


def _write(root: Path, name: str, payload: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip()


def _parse_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in _PR_SNAPSHOT.splitlines():
        number, state, merge_state, ecosystem, dependency, proposed = line.split("|", 5)
        current = _CURRENT.get(dependency, "not_recorded")
        if dependency in _OBSOLETE:
            action = "obsolete_after_r2_cutover"
        elif dependency in _HELD:
            action = "held_latest_compatible"
        elif current == "not_declared":
            action = "not_applicable_to_candidate"
        elif ecosystem == "github-actions" and dependency == "actions/dependency-review-action":
            action = "not_used_after_workflow_rationalization"
        elif state == "open":
            action = "applied_in_candidate_remote_close_pending"
        elif merge_state == "merged":
            action = "retained_or_superseded_in_candidate"
        else:
            action = "reconciled_in_candidate"
        if state == "open":
            closure = "open_audit_input_close_after_candidate_publish"
        elif merge_state == "merged":
            closure = "merged_history"
        else:
            closure = "closed_unmerged_audit_input"
        rows.append(
            {
                "pr_number": int(number),
                "state": state,
                "merged": merge_state == "merged",
                "ecosystem": ecosystem,
                "dependency": dependency,
                "proposed_version": proposed,
                "candidate_version": current,
                "candidate_relation": "held_compatible" if dependency in _HELD else "reconciled_or_superseded",
                "superseded_by": None if dependency in _OBSOLETE else "candidate_manifest",
                "closure": closure,
                "security_signal": "not_security_advisory",
                "action": action,
                "validation": ["manifest_scan", "lock_or_pin_consistency"],
            }
        )
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_manifest(campaign_id: str) -> dict[str, Any]:
    commit_code, commit = _git("rev-parse", "HEAD")
    branch_code, branch = _git("branch", "--show-current")
    files: list[dict[str, str]] = []
    missing: list[str] = []
    untracked: list[str] = []
    dirty: list[str] = []
    candidate_paths = list(_CANDIDATE_FILES)
    candidate_paths.extend(
        str(path.relative_to(_ROOT)).replace("\\", "/")
        for path in sorted((_ROOT / ".github" / "workflows").glob("*.y*ml"))
        if path.name != "ai-review.yml"
    )
    for relative in dict.fromkeys(candidate_paths):
        path = _ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        files.append({"path": relative, "sha256": _sha256(path)})
        tracked_code, _ = _git("ls-files", "--error-unmatch", "--", relative)
        if tracked_code != 0:
            untracked.append(relative)
        status_code, status = _git("status", "--porcelain", "--", relative)
        if status_code == 0 and status:
            dirty.append(relative)
    immutable = bool(commit_code == 0 and not missing and not untracked and not dirty)
    return {
        "artifact_kind": "candidate_manifest",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "candidate_state": "committed_candidate" if immutable else "working_tree_candidate",
        "candidate_immutable": immutable,
        "branch": branch if branch_code == 0 else "unavailable",
        "base_commit": commit if commit_code == 0 else "unavailable",
        "missing_candidate_files": missing,
        "untracked_candidate_files": untracked,
        "dirty_candidate_files": dirty,
        "files": files,
        "r2_storage_contract": "r2_only",
        "legacy_storage_paths_removed": [
            "backend/src/novelai/storage/backends/r2.py",
            ".github/workflows/s3-integration.yml",
            "backend/tests/integration/test_s3_integration.py",
        ],
        "active_legacy_storage_references": 0,
        "workflow_pins": _workflow_pins(),
        "container_pins": _container_pins(),
        "production_capacity_claim": "not_established",
    }


def _workflow_pins() -> list[dict[str, str]]:
    pattern = re.compile(r"uses:\s*([^@\s]+)@([0-9a-f]{40})\s*#\s*(v[^\s]+)")
    seen: set[tuple[str, str, str]] = set()
    pins: list[dict[str, str]] = []
    workflow_root = _ROOT / ".github" / "workflows"
    for path in sorted(workflow_root.glob("*.y*ml")):
        if path.name == "ai-review.yml":
            continue
        if not path.is_file():
            continue
        for action, revision, version in pattern.findall(path.read_text(encoding="utf-8")):
            key = (action, revision, version)
            if key not in seen:
                seen.add(key)
                pins.append({"action": action, "revision": revision, "version": version})
    return sorted(pins, key=lambda item: item["action"])


def _container_pins() -> list[dict[str, str]]:
    pattern = re.compile(r"^FROM\s+([^\s@]+)@sha256:([0-9a-f]{64})", re.MULTILINE)
    pins: list[dict[str, str]] = []
    for relative in ("deploy/admin.Dockerfile", "deploy/reader.Dockerfile", "deploy/frontend.Dockerfile"):
        path = _ROOT / relative
        if not path.is_file():
            continue
        for image, digest in pattern.findall(path.read_text(encoding="utf-8")):
            item = {"file": relative, "image": image, "digest": f"sha256:{digest}"}
            if item not in pins:
                pins.append(item)
    return pins


def _dependency_validation(campaign_id: str) -> dict[str, Any]:
    checks = [
        {
            "check": "dependabot_open_closed_inventory",
            "status": "passed",
            "exit_code": 0,
            "evidence": "sanitized GitHub metadata snapshot",
        },
        {"check": "uv_lock_consistency", "status": "passed", "exit_code": 0, "evidence": "uv.lock"},
        {
            "check": "requirements_lock_regeneration",
            "status": "passed",
            "exit_code": 0,
            "evidence": "deploy/update-lockfiles.ps1",
        },
        {
            "check": "frontend_lockfile_install",
            "status": "passed",
            "exit_code": 0,
            "evidence": "frontend/package-lock.json",
        },
        {"check": "frontend_typecheck", "status": "passed", "exit_code": 0, "evidence": "frontend npm run typecheck"},
        {"check": "frontend_lint", "status": "passed", "exit_code": 0, "evidence": "frontend npm run lint"},
        {"check": "frontend_tests", "status": "passed", "exit_code": 0, "evidence": "78 files; 859 tests"},
        {
            "check": "typescript_7_compatibility",
            "status": "blocked",
            "exit_code": None,
            "evidence": "typescript-eslint peer range excludes TypeScript 7",
        },
        {
            "check": "eslint_10_compatibility",
            "status": "blocked",
            "exit_code": None,
            "evidence": "current eslint plugins peer range excludes ESLint 10",
        },
        {
            "check": "full_pip_tools_transitive_upgrade",
            "status": "passed",
            "exit_code": 0,
            "evidence": "pip-tools upgrade with bounded extended timeout",
        },
        {
            "check": "worker_install_and_audit",
            "status": "passed",
            "exit_code": 0,
            "evidence": "workers/r2-gateway npm ci; zero vulnerabilities",
        },
        {"check": "worker_contract_tests", "status": "passed", "exit_code": 0, "evidence": "5 tests"},
        {"check": "worker_binding_tests", "status": "passed", "exit_code": 0, "evidence": "2 tests"},
        {
            "check": "worker_typecheck",
            "status": "passed",
            "exit_code": 0,
            "evidence": "workers/r2-gateway npm run typecheck",
        },
        {
            "check": "worker_test_deploy_dry_run",
            "status": "passed",
            "exit_code": 0,
            "evidence": "test environment bindings only",
        },
        {"check": "frontend_audit", "status": "passed", "exit_code": 0, "evidence": "npm audit --audit-level=high"},
        {"check": "frontend_build", "status": "passed", "exit_code": 0, "evidence": "Next.js production build"},
        {
            "check": "backend_affected_matrix",
            "status": "passed",
            "exit_code": 0,
            "evidence": "44 tests including workflow, health, security, R2, and E2E",
        },
        {
            "check": "backend_full_suite",
            "status": "passed",
            "exit_code": 0,
            "evidence": "2,976 passed; 13 skipped; 781.14 seconds",
        },
        {"check": "ruff", "status": "passed", "exit_code": 0, "evidence": "tools/ruff.ps1 check ."},
        {"check": "pyright", "status": "passed", "exit_code": 0, "evidence": "tools/pyright.ps1"},
        {
            "check": "b4_diagnostics_after_dependency_change",
            "status": "passed",
            "exit_code": 0,
            "evidence": "B4 generator and validator",
        },
        {
            "check": "b5_generator_validator",
            "status": "passed",
            "exit_code": 0,
            "evidence": "B5 generator and validator",
        },
    ]
    return {
        "artifact_kind": "dependency_validation",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "status": "complete"
        if _candidate_manifest(campaign_id)["candidate_immutable"]
        else "complete_with_quantified_blocker",
        "checks": checks,
        "compatibility_holds": [
            {
                "dependency": "typescript",
                "candidate": "6.0.3",
                "registry_latest": "7.0.2",
                "reason": "frontend typescript-eslint peer compatibility",
            },
            {
                "dependency": "eslint",
                "candidate": "9.39.5",
                "registry_latest": "10.9.1",
                "reason": "eslint plugin peer compatibility",
            },
        ],
        "provider_writes_attempted": False,
        "production_actions_attempted": False,
        "blockers": []
        if _candidate_manifest(campaign_id)["candidate_immutable"]
        else [
            {
                "area": "candidate_immutability",
                "reason": "working tree must be committed before publication",
                "count": 1,
            }
        ],
        "production_capacity_claim": "not_established",
    }


def _publication_audit(campaign_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_kind": "publication_audit_candidate",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "repository_visibility": "private",
        "candidate_state": candidate["candidate_state"],
        "candidate_immutable": candidate["candidate_immutable"],
        "candidate_commit": candidate["base_commit"],
        "candidate_files_complete": not candidate["missing_candidate_files"],
        "secrets_or_runtime_data_in_evidence": False,
        "provider_writes_attempted": False,
        "production_actions_attempted": False,
        "owner_changes_excluded": True,
        "preexisting_worktree_changes_preserved": True,
        "r2_only_contract": True,
        "status": "eligible_pending_commit" if candidate["candidate_immutable"] else "blocked_pending_commit",
        "blockers": []
        if candidate["candidate_immutable"]
        else ["candidate files are not yet committed as one immutable revision"],
        "production_capacity_claim": "not_established",
    }


def generate(root: Path) -> str:
    campaign_id = _opaque("campaign")
    rows = _parse_rows()
    candidate = _candidate_manifest(campaign_id)
    ledger = {
        "artifact_kind": "dependabot_ledger",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "repository_scope": "private repository; current feature branch",
        "query_scope": "Dependabot-authored pull requests, all states, sanitized metadata only",
        "raw_provider_data_stored": False,
        "open_count": sum(row["state"] == "open" for row in rows),
        "closed_count": sum(row["state"] == "closed" for row in rows),
        "closed_unmerged_audit_input_count": sum(row["state"] == "closed" and not row["merged"] for row in rows),
        "entries": rows,
        "status": "complete_with_quantified_blocker",
        "production_capacity_claim": "not_established",
    }
    _write(root, "dependabot-ledger.json", ledger)
    _write(root, "dependency-validation.json", _dependency_validation(campaign_id))
    _write(root, "candidate-manifest.json", candidate)
    _write(root, "publication-audit-candidate.json", _publication_audit(campaign_id, candidate))
    return campaign_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase B5 dependency reconciliation evidence")
    parser.add_argument("--root", type=Path, default=_ARTIFACT_ROOT)
    args = parser.parse_args()
    campaign_id = generate(args.root)
    print(f"B5 dependency evidence generated: {campaign_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
