from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).parents[2] / ".github" / "workflows"
PINNED_ACTION = re.compile(r"(?:-\s*)?uses:\s+[^\s@]+@([0-9a-f]{40})(?:\s+#\s+v\S+)?$")


def _workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_ci_core_exclusions_are_all_exercised_by_extended_shards() -> None:
    source = _workflow("ci.yml")
    ignored = set(re.findall(r"--ignore=(backend/tests/[^\s]+)", source))

    assert ignored
    assert "backend-extended:" in source
    extended_section = source[source.index("backend-extended:") :]
    for test_path in ignored:
        assert test_path in extended_section, f"Ignored test {test_path} not found in backend-extended shards"

    # Contract: every backend test file in backend/tests/ (except e2e directory and test_ci_workflows.py)
    # must be either in core (not ignored) or in extended shards, and no test file is duplicated across shards.
    tests_dir = Path(__file__).parent
    all_unit_test_files = {
        f"backend/tests/{p.name}" for p in tests_dir.glob("test_*.py") if p.name != "test_ci_workflows.py"
    }

    extended_files = set(re.findall(r"backend/tests/test_[a-zA-Z0-9_]+\.py", extended_section))

    # Assert exact match between ignored set and extended files set
    assert ignored == extended_files, (
        f"Mismatch between core --ignore set and extended shard files: {ignored ^ extended_files}"
    )

    # Assert total files accounted for
    core_files = all_unit_test_files - extended_files
    assert core_files | extended_files == all_unit_test_files


def test_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    action_lines: list[str] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        action_lines.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if "uses:" in line)

    # Local reusable-workflow references (.github/workflows/...) are not
    # third-party actions and are exempt from SHA pinning.
    action_lines = [line for line in action_lines if not line.startswith("uses: ./.github/")]

    assert action_lines
    assert all(PINNED_ACTION.fullmatch(line) for line in action_lines), action_lines


def test_build_summary_fails_unless_publication_succeeds() -> None:
    source = _workflow("build.yml")

    assert "ref: ${{ github.event.workflow_run.head_sha }}" in source
    assert "BUILD_RESULT: ${{ needs.build-and-push.result }}" in source
    assert 'if [ "$BUILD_RESULT" != "success" ]; then' in source
    assert "exit 1" in source


def test_deploy_uses_published_version_and_migrates_before_start() -> None:
    source = _workflow("deploy.yml")

    # The remote SSH script must never interpolate workflow expressions: the
    # free-form version input is validated first, then passed to the script
    # only through the ssh-action envs mechanism.
    script_start = source.index("script: |")
    assert "envs: VERSION,DEPLOY_ENV" in source[:script_start]
    script = source[script_start : source.index("- name: Smoke test production deployment")]
    assert "${{" not in script
    assert r"^sha-[0-9a-f]{40}$" in source
    assert '"$DEPLOY_ENV" == "production"' in source
    assert "push:\n    tags:" not in source
    assert source.index("docker compose run --rm migrate") < source.index("docker compose up -d")


def test_gitguardian_workflow_contract() -> None:
    source = _workflow("gitguardian.yaml")

    assert "pull_request_target" not in source
    assert "push" in source
    assert "pull_request" in source
    assert re.search(r"(?m)^permissions:\s*$", source)
    assert "contents: read" in source
    assert "fetch-depth: 0" in source
    assert "secrets.GITGUARDIAN_API_KEY" in source
    for line in source.splitlines():
        if "GITGUARDIAN_API_KEY:" in line:
            assert "${{ secrets.GITGUARDIAN_API_KEY }}" in line
    for var in ("GITHUB_PUSH_BEFORE_SHA", "GITHUB_PUSH_BASE_SHA", "GITHUB_PULL_BASE_SHA", "GITHUB_DEFAULT_BRANCH"):
        assert var in source
    assert "if:" in source
    assert "github.event.pull_request.head.repo.full_name == github.repository" in source
    assert "github.event_name" in source


def test_secret_backed_opencode_workflow_restricts_commenters() -> None:
    source = _workflow("opencode.yml")

    assert 'fromJSON(\'["OWNER", "MEMBER", "COLLABORATOR"]\')' in source
    assert "github.event.comment.author_association" in source
    assert "timeout-minutes: 15" in source
    assert "npx --yes opencode-ai@1.18.11 github run" in source
    assert "anomalyco/opencode/github@" not in source


def test_ci_e2e_filter_includes_all_required_inputs() -> None:
    source = _workflow("ci.yml")
    required_filter_paths = [
        ".github/workflows/ci.yml",
        "pyproject.toml",
        "uv.lock",
        "backend/src/**",
        "backend/tests/e2e/**",
        "backend/tests/fixtures/e2e/**",
        "backend/tests/conftest.py",
        "backend/alembic/**",
        "backend/sql/**",
    ]
    for path in required_filter_paths:
        assert path in source, f"Missing {path} in E2E filter"


def test_production_monitor_contract() -> None:
    source = _workflow("production-monitor.yml")
    assert "vars.PRODUCTION_MONITOR_ENABLED == 'true'" in source
    assert "vars.PRODUCTION_BASE_URL" in source
    assert "secrets.PRODUCTION_BASE_URL" not in source
    assert "cancel-in-progress: false" in source
    assert "-TimeoutSeconds 10" in source
    assert 'echo "PRODUCTION_BASE_URL is not configured; production monitor skipped."' not in source
    assert "exit 1" in source


def test_deploy_input_flow_and_smoke_vars() -> None:
    source = _workflow("deploy.yml")
    assert "$GITHUB_OUTPUT" not in source
    assert "VERSION: ${{ inputs.version }}" in source
    assert "DEPLOY_ENV: ${{ inputs.environment }}" in source
    assert "environment: ${{ inputs.environment }}" in source
    assert "vars.PRODUCTION_BASE_URL" in source
    assert "secrets.NOVELAI_SMOKE_SESSION_COOKIE" in source
    assert "secrets.PRODUCTION_BASE_URL" not in source


def test_deploy_staging_eligibility_and_managed_gate() -> None:
    source = _workflow("deploy.yml")
    assert "needs: managed-services-check" in source
    assert "inputs.environment != 'production'" in source
    assert "needs.managed-services-check.result == 'success'" in source
    assert "!cancelled()" in source


def test_dependency_review_least_privilege() -> None:
    source = _workflow("dependency-review.yml")
    assert "contents: read" in source
    assert "pull-requests: write" not in source
    assert "pull_request_target" not in source
    assert "comment-summary-in-pr: always" not in source


def test_uv_locked_contract_in_ci_and_managed_verification() -> None:
    for name in ("ci.yml", "managed-services-verification.yml"):
        source = _workflow(name)
        assert "--frozen" not in source, f"--frozen found in {name}"
        assert "--locked" in source, f"--locked missing in {name}"


def test_build_workflow_run_trust_guards_and_concurrency() -> None:
    source = _workflow("build.yml")
    assert "concurrency:" in source
    assert "group: build-push-default-branch" in source
    assert "github.event.workflow_run.event == 'push'" in source
    assert "github.event.workflow_run.head_branch == github.event.repository.default_branch" in source
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in source
    assert "actions/attest" in source
    assert "subject-digest: ${{ steps.build.outputs.digest }}" in source
    assert "artifact-metadata: write" in source


def test_node_version_alignment() -> None:
    nvmrc = (WORKFLOWS_DIR.parent.parent / "frontend" / ".nvmrc").read_text(encoding="utf-8").strip()
    package_json = (WORKFLOWS_DIR.parent.parent / "frontend" / "package.json").read_text(encoding="utf-8")
    dockerfile = (WORKFLOWS_DIR.parent.parent / "deploy" / "frontend.Dockerfile").read_text(encoding="utf-8")

    assert nvmrc == "22"
    assert '"node": ">=22 <23"' in package_json
    assert "node:22-alpine" in dockerfile
