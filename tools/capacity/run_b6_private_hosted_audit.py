"""Capture sanitized Phase B6 private-hosted and repository-control evidence.

This tool uses the authenticated ``gh`` CLI only for read-only GitHub API
queries. It never reads or emits secret values, workflow outputs, provider
responses, or repository contents. A hosted job that fails before receiving a
runner is recorded as blocked evidence, not as a passing workflow.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ARTIFACT_ROOT = _ROOT / "artifacts" / "public-hosted-execution"
_REQUIRED_WORKFLOWS = (
    "CI",
    "CodeQL",
    "Secret Scan",
    "Security Static Analysis",
    "Dependency Review",
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _opaque(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _write(root: Path, name: str, payload: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _gh_json(endpoint: str) -> tuple[bool, Any]:
    """Return parsed API data without retaining command output on failure."""

    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            cwd=_ROOT,
            capture_output=True,
            check=False,
            timeout=45,
        )
    except OSError, subprocess.TimeoutExpired:
        return False, None
    if result.returncode != 0:
        return False, None
    try:
        stdout = result.stdout
        if not isinstance(stdout, bytes):
            return False, None
        return True, json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return False, None


def _duration(started: str | None, completed: str | None) -> float | None:
    if not started or not completed:
        return None
    try:
        begin = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(max(0.0, (end - begin).total_seconds()), 3)


def _runner_class(labels: list[str]) -> str:
    if "self-hosted" in labels:
        return "self_hosted"
    if any(label.startswith("ubuntu-") for label in labels):
        return "github_hosted_ubuntu"
    return "unknown"


def _job_snapshot(job: dict[str, Any]) -> dict[str, Any]:
    labels = [str(label) for label in job.get("labels", []) if isinstance(label, str)]
    steps = job.get("steps") or []
    step_snapshots: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        step_snapshots.append(
            {
                "index": index,
                "status": step.get("status", "unavailable"),
                "conclusion": step.get("conclusion"),
                "duration_seconds": _duration(step.get("started_at"), step.get("completed_at")),
            }
        )
    return {
        "job_id": job.get("id"),
        "name": job.get("name", "unavailable"),
        "status": job.get("status", "unavailable"),
        "conclusion": job.get("conclusion"),
        "labels": labels,
        "runner_class": _runner_class(labels),
        "runner_assigned": bool(job.get("runner_name")),
        "steps_count": len(steps),
        "duration_seconds": _duration(job.get("started_at"), job.get("completed_at")),
        "steps": step_snapshots,
    }


def _run_snapshot(repo: str, run: dict[str, Any], candidate_sha: str) -> dict[str, Any]:
    run_id = run.get("id")
    jobs_ok, jobs_data = _gh_json(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    raw_jobs = jobs_data.get("jobs", []) if jobs_ok and isinstance(jobs_data, dict) else []
    jobs = [_job_snapshot(job) for job in raw_jobs if isinstance(job, dict)]
    created = run.get("created_at")
    started = run.get("run_started_at")
    return {
        "run_id": run_id,
        "workflow_name": run.get("name", "unavailable"),
        "workflow_id": run.get("workflow_id"),
        "event": run.get("event", "unavailable"),
        "head_branch": run.get("head_branch", "unavailable"),
        "head_sha": run.get("head_sha", "unavailable"),
        "candidate_sha_match": run.get("head_sha") == candidate_sha,
        "status": run.get("status", "unavailable"),
        "conclusion": run.get("conclusion"),
        "created_at": created,
        "run_started_at": started,
        "updated_at": run.get("updated_at"),
        "queue_wait_seconds": _duration(created, started),
        "run_duration_seconds": _duration(started, run.get("updated_at")),
        "jobs_available": jobs_ok,
        "jobs": jobs,
        "url": run.get("html_url"),
    }


def _check_snapshot(check: dict[str, Any], candidate_sha: str) -> dict[str, Any]:
    return {
        "name": check.get("name", "unavailable"),
        "status": check.get("status", "unavailable"),
        "conclusion": check.get("conclusion"),
        "started_at": check.get("started_at"),
        "completed_at": check.get("completed_at"),
        "candidate_sha": candidate_sha,
        "app": (check.get("app") or {}).get("slug", "unavailable"),
    }


def _runs_artifact(repo: str, pr_number: int, candidate_sha: str, campaign_id: str) -> dict[str, Any]:
    runs_ok, runs_data = _gh_json(f"repos/{repo}/actions/runs?head_sha={candidate_sha}&per_page=100")
    raw_runs = runs_data.get("workflow_runs", []) if runs_ok and isinstance(runs_data, dict) else []
    runs = [_run_snapshot(repo, run, candidate_sha) for run in raw_runs if isinstance(run, dict)]

    checks_ok, checks_data = _gh_json(f"repos/{repo}/commits/{candidate_sha}/check-runs?per_page=100")
    raw_checks = checks_data.get("check_runs", []) if checks_ok and isinstance(checks_data, dict) else []
    checks = [_check_snapshot(check, candidate_sha) for check in raw_checks if isinstance(check, dict)]

    by_workflow: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_workflow.setdefault(str(run["workflow_name"]), []).append(run)
    workflow_disposition: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for workflow in _REQUIRED_WORKFLOWS:
        matches = by_workflow.get(workflow, [])
        conclusions = [item.get("conclusion") for item in matches]
        if not matches:
            status = "unavailable"
            blockers.append({"workflow": workflow, "reason": "no candidate run returned by GitHub"})
        elif all(conclusion == "success" for conclusion in conclusions):
            status = "passed"
        else:
            status = "blocked"
            blockers.append(
                {
                    "workflow": workflow,
                    "reason": "candidate job failed or completed without a passing conclusion",
                    "run_count": len(matches),
                }
            )
        workflow_disposition.append({"workflow": workflow, "status": status, "run_count": len(matches)})

    all_jobs = [job for run in runs for job in run.get("jobs", [])]
    runner_classes = sorted({job.get("runner_class") for job in all_jobs})
    if any(not job.get("runner_assigned") for job in all_jobs):
        blockers.append(
            {
                "area": "hosted_runner_assignment",
                "reason": "one or more candidate jobs completed with zero assigned runner and zero steps",
                "count": sum(not job.get("runner_assigned") for job in all_jobs),
            }
        )
    return {
        "artifact_kind": "private_hosted_runs",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "repository": repo,
        "repository_visibility": "private",
        "pr_number": pr_number,
        "candidate_sha": candidate_sha,
        "candidate_runs_query_available": runs_ok,
        "candidate_checks_query_available": checks_ok,
        "runs": runs,
        "checks": checks,
        "workflow_disposition": workflow_disposition,
        "runner_policy": "github_hosted_ubuntu_required; persistent_self_hosted_forbidden",
        "runner_classes_observed": runner_classes,
        "persistent_self_hosted_runner_count": 0,
        "status": "complete" if not blockers and runs else "blocked",
        "blockers": blockers,
        "production_capacity_claim": "not_established",
    }


def _api_summary(repo: str, endpoint: str, transform: Any) -> dict[str, Any]:
    ok, data = _gh_json(f"repos/{repo}/{endpoint}")
    if not ok:
        return {"status": "unavailable", "reason": "read_only_endpoint_unavailable"}
    try:
        value = transform(data)
    except AttributeError, TypeError:
        return {"status": "unavailable", "reason": "read_only_endpoint_shape_unavailable"}
    return {"status": "available", "value": value}


def _rulesets_summary(repo: str) -> dict[str, Any]:
    ok, data = _gh_json(f"repos/{repo}/rulesets?per_page=100")
    if not ok or not isinstance(data, list):
        return {"status": "unavailable", "reason": "read_only_endpoint_unavailable"}
    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ruleset_id = item.get("id")
        detail_ok, detail = (
            _gh_json(f"repos/{repo}/rulesets/{ruleset_id}") if isinstance(ruleset_id, int) else (False, None)
        )
        source = detail if detail_ok and isinstance(detail, dict) else item
        bypass_actors = source.get("bypass_actors")
        rows.append(
            {
                "id": ruleset_id,
                "name": item.get("name"),
                "target": item.get("target"),
                "enforcement": item.get("enforcement"),
                "detail_available": detail_ok,
                "bypass_actors_count": len(bypass_actors) if isinstance(bypass_actors, list) else None,
                "conditions_present": bool(source.get("conditions")),
            }
        )
    return {"status": "available", "value": rows}


def _protection_artifact(repo: str, candidate_sha: str, campaign_id: str) -> dict[str, Any]:
    protection_ok, protection = _gh_json(f"repos/{repo}/branches/main/protection")
    repo_ok, repository = _gh_json(f"repos/{repo}")
    if not repo_ok or not isinstance(repository, dict):
        repository = {}
    if not protection_ok or not isinstance(protection, dict):
        protection = {}
    required_checks = protection.get("required_status_checks") or {}
    checks = required_checks.get("checks") or []
    review = protection.get("required_pull_request_reviews") or {}
    enforce_admins = protection.get("enforce_admins") or {}
    return {
        "artifact_kind": "protection_before",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "repository": repo,
        "repository_visibility": "private"
        if repository.get("private")
        else repository.get("visibility", "unavailable"),
        "candidate_sha": candidate_sha,
        "branch": "main",
        "branch_protection_available": protection_ok,
        "branch_protection": {
            "required_status_checks": {
                "strict": required_checks.get("strict"),
                "contexts": required_checks.get("contexts") or [],
                "checks": [
                    {"context": item.get("context"), "app_id_present": item.get("app_id") is not None}
                    for item in checks
                    if isinstance(item, dict)
                ],
            },
            "required_pull_request_reviews": {
                "required_approving_review_count": review.get("required_approving_review_count"),
                "require_code_owner_reviews": review.get("require_code_owner_reviews"),
                "require_last_push_approval": review.get("require_last_push_approval"),
                "dismiss_stale_reviews": review.get("dismiss_stale_reviews"),
            },
            "required_conversation_resolution": (protection.get("required_conversation_resolution") or {}).get(
                "enabled"
            ),
            "enforce_admins": enforce_admins.get("enabled"),
            "required_linear_history": (protection.get("required_linear_history") or {}).get("enabled"),
            "allow_force_pushes": (protection.get("allow_force_pushes") or {}).get("enabled"),
            "allow_deletions": (protection.get("allow_deletions") or {}).get("enabled"),
            "restrictions_present": protection.get("restrictions") is not None,
        },
        "merge_policy": {
            key: repository.get(key)
            for key in (
                "allow_squash_merge",
                "allow_merge_commit",
                "allow_rebase_merge",
                "allow_auto_merge",
                "delete_branch_on_merge",
                "use_squash_pr_title_as_default",
                "use_squash_pr_body_as_default",
            )
            if isinstance(repository.get(key), bool)
        },
        "rulesets": _rulesets_summary(repo),
        "actions_permissions": _api_summary(
            repo,
            "actions/permissions",
            lambda data: {
                "enabled": data.get("enabled"),
                "allowed_actions": data.get("allowed_actions"),
                "sha_pinning_required": data.get("sha_pinning_required"),
            },
        ),
        "workflow_permissions": _api_summary(
            repo,
            "actions/permissions/workflow",
            lambda data: {
                "default_workflow_permissions": data.get("default_workflow_permissions"),
                "can_approve_pull_request_reviews": data.get("can_approve_pull_request_reviews"),
            },
        ),
        "selected_actions": _api_summary(
            repo,
            "actions/permissions/selected-actions",
            lambda data: {
                "github_owned_allowed": data.get("github_owned_allowed"),
                "verified_allowed": data.get("verified_allowed"),
                "patterns_count": len(data.get("patterns") or []),
            },
        ),
        "runners": _api_summary(
            repo,
            "actions/runners?per_page=100",
            lambda data: {
                "total_count": data.get("total_count"),
                "busy_count": sum(bool(item.get("busy")) for item in data.get("runners", []) if isinstance(item, dict)),
                "labels": sorted(
                    {
                        label.get("name")
                        for item in data.get("runners", [])
                        if isinstance(item, dict)
                        for label in item.get("labels", [])
                        if isinstance(label, dict) and isinstance(label.get("name"), str)
                    }
                ),
            },
        ),
        "environments": _api_summary(
            repo,
            "environments?per_page=100",
            lambda data: {
                "total_count": data.get("total_count"),
                "names": sorted(
                    item.get("name")
                    for item in data.get("environments", [])
                    if isinstance(item, dict) and item.get("name")
                ),
            },
        ),
        "fork_approval": _api_summary(
            repo,
            "actions/permissions/fork-pr-contributor-approval",
            lambda data: {
                "approval_policy": data.get("approval_policy"),
                "approval_policy_present": isinstance(data.get("approval_policy"), str),
            },
        ),
        "packages": _api_summary(
            repo,
            "packages?per_page=100",
            lambda data: {
                "count": len(data) if isinstance(data, list) else None,
                "package_types": sorted(
                    {
                        item.get("package_type")
                        for item in data
                        if isinstance(item, dict) and isinstance(item.get("package_type"), str)
                    }
                )
                if isinstance(data, list)
                else [],
            },
        ),
        "oidc": _api_summary(
            repo,
            "actions/oidc/customization/sub",
            lambda data: {
                "use_default": data.get("use_default"),
                "include_claim_keys_count": len(data.get("include_claim_keys") or []),
            },
        ),
        "apps": _api_summary(
            repo,
            "installation",
            lambda data: {
                "installation_present": isinstance(data, dict),
                "app_slug_present": isinstance(data.get("app_slug"), str),
            },
        ),
        "hooks": _api_summary(
            repo,
            "hooks?per_page=100",
            lambda data: (
                {
                    "count": len(data),
                    "active_count": sum(bool(item.get("active")) for item in data if isinstance(item, dict)),
                }
                if isinstance(data, list)
                else {"count": 0, "active_count": 0}
            ),
        ),
        "deployments": _api_summary(
            repo,
            "deployments?per_page=100",
            lambda data: {
                "count": len(data) if isinstance(data, list) else None,
                "environment_count": len(
                    {
                        item.get("environment")
                        for item in data
                        if isinstance(item, dict) and isinstance(item.get("environment"), str)
                    }
                )
                if isinstance(data, list)
                else None,
            },
        ),
        "pages": _api_summary(
            repo, "pages", lambda data: {"status": data.get("status"), "https": data.get("https_enforced")}
        ),
        "security_controls": {
            name: _api_summary(repo, endpoint, lambda data: {"enabled": data.get("enabled")})
            for name, endpoint in {
                "secret_scanning": "secret-scanning",
                "push_protection": "secret-scanning/push-protection",
                "dependabot_security_updates": "dependabot/security-updates",
                "code_scanning_default_setup": "code-scanning/default-setup",
            }.items()
        },
        "status": "complete" if protection_ok else "blocked",
        "blockers": [] if protection_ok else ["main branch protection endpoint unavailable"],
        "production_capacity_claim": "not_established",
    }


def _timing_artifact(private_runs: dict[str, Any], campaign_id: str) -> dict[str, Any]:
    runs = private_runs.get("runs", [])
    workflow_rows: list[dict[str, Any]] = []
    for run in runs:
        jobs = run.get("jobs", [])
        durations = [
            job.get("duration_seconds") for job in jobs if isinstance(job.get("duration_seconds"), (int, float))
        ]
        workflow_rows.append(
            {
                "run_id": run.get("run_id"),
                "workflow_name": run.get("workflow_name"),
                "candidate_sha": private_runs.get("candidate_sha"),
                "queue_wait_seconds": run.get("queue_wait_seconds"),
                "run_duration_seconds": run.get("run_duration_seconds"),
                "critical_path_job_seconds": round(max(durations), 3) if durations else None,
                "job_count": len(jobs),
                "jobs": [
                    {
                        "job_id": job.get("job_id"),
                        "name": job.get("name"),
                        "runner_class": job.get("runner_class"),
                        "runner_assigned": job.get("runner_assigned"),
                        "status": job.get("status"),
                        "conclusion": job.get("conclusion"),
                        "duration_seconds": job.get("duration_seconds"),
                        "steps_count": job.get("steps_count"),
                        "steps": job.get("steps", []),
                    }
                    for job in jobs
                ],
            }
        )
    return {
        "artifact_kind": "workflow_timing",
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "repository_visibility": "private",
        "candidate_sha": private_runs.get("candidate_sha"),
        "runs": workflow_rows,
        "status": private_runs.get("status", "blocked"),
        "blockers": private_runs.get("blockers", []),
        "production_capacity_claim": "not_established",
    }


def _simple_gate(kind: str, campaign_id: str, candidate_sha: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "artifact_kind": kind,
        "schema_version": 1,
        "campaign_id": campaign_id,
        "captured_at_utc": _timestamp(),
        "repository_visibility": "private",
        "candidate_sha": candidate_sha,
        "status": status,
        "attempted": False,
        "reason": reason,
        "production_capacity_claim": "not_established",
    }


def generate(repo: str, pr_number: int, candidate_sha: str, root: Path) -> str:
    campaign_id = _opaque("campaign")
    private_runs = _runs_artifact(repo, pr_number, candidate_sha, campaign_id)
    protection = _protection_artifact(repo, candidate_sha, campaign_id)
    _write(root, "private-hosted-runs.json", private_runs)
    _write(root, "workflow-timing.json", _timing_artifact(private_runs, campaign_id))
    _write(root, "protection-before.json", protection)
    _write(
        root,
        "visibility-transition.json",
        {
            **_simple_gate(
                "visibility_transition",
                campaign_id,
                candidate_sha,
                "blocked",
                "repository visibility authority was not supplied; current authorization covers branch Git operations only",
            ),
            "before_visibility": "private",
            "after_visibility": "not_run",
            "visibility_change_authorized": False,
            "owner_surface_acceptance": False,
        },
    )
    _write(
        root,
        "protection-after.json",
        _simple_gate(
            "protection_after",
            campaign_id,
            candidate_sha,
            "not_run",
            "no visibility transition was authorized or attempted",
        ),
    )
    _write(
        root,
        "fork-safety.json",
        {
            **_simple_gate(
                "fork_safety",
                campaign_id,
                candidate_sha,
                "not_run",
                "benign external fork PR was not separately authorized",
            ),
            "fork_created": False,
            "secret_access": False,
            "provider_calls": False,
        },
    )
    _write(
        root,
        "public-main-runs.json",
        _simple_gate(
            "public_main_runs",
            campaign_id,
            candidate_sha,
            "not_run",
            "repository remains private and candidate has not been merged to main",
        ),
    )
    return campaign_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture sanitized Phase B6 hosted evidence")
    parser.add_argument("--repo", required=True, help="owner/repository")
    parser.add_argument("--pr", required=True, type=int, help="private candidate pull request number")
    parser.add_argument("--candidate-sha", required=True, help="exact candidate commit SHA")
    parser.add_argument("--root", type=Path, default=_DEFAULT_ARTIFACT_ROOT)
    args = parser.parse_args()
    campaign_id = generate(args.repo, args.pr, args.candidate_sha, args.root)
    print(f"B6 private hosted evidence generated: {campaign_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
