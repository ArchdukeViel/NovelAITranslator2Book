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

    from collections import Counter

    extended_occurrences = re.findall(r"backend/tests/test_[a-zA-Z0-9_]+\.py", extended_section)
    extended_counts = Counter(extended_occurrences)
    duplicates = {path: count for path, count in extended_counts.items() if count > 1}
    assert not duplicates, f"Extended test files must appear exactly once: {duplicates}"

    extended_files = set(extended_occurrences)

    # Assert exact match between ignored set and extended files set
    assert ignored == extended_files, (
        f"Mismatch between core --ignore set and extended shard files: {ignored ^ extended_files}"
    )

    # Assert total files accounted for
    core_files = all_unit_test_files - extended_files
    assert core_files | extended_files == all_unit_test_files


def test_ci_setup_uv_pin_is_consistent() -> None:
    """All setup-uv uses in ci.yml must reference the exact same commit SHA.

    Catches partial replacements that leave stale pins in some jobs (e.g. a
    corrected backend-lint pin while e2e-tests still references the old SHA).
    """
    source = _workflow("ci.yml")

    pins = re.findall(r"astral-sh/setup-uv@([0-9a-f]{40})", source)

    assert pins
    assert len(set(pins)) == 1, f"setup-uv uses inconsistent commit pins: {sorted(set(pins))}"
    assert set(pins) == {"c771a70e6277c0a99b617c7a806ffedaca235ff9"}


def test_s3_integration_has_execution_policy() -> None:
    """The real S3 integration suite must have an automated execution policy.

    The file is marked ``slow``/``integration`` and therefore intentionally
    excluded from the normal core/extended runs; this contract keeps it wired
    to the scheduled MinIO workflow so it cannot silently become manual-only.
    """
    source = _workflow("s3-integration.yml")

    assert "test_s3_integration.py" in source
    assert "schedule" in source
    assert "workflow_dispatch" in source
    assert "TEST_S3_ENDPOINT" in source
    assert "TEST_S3_BUCKET" in source
    assert "minio" in source


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
    assert "envs: VERSION,DEPLOY_ENV,ADMIN_IMAGE,READER_IMAGE,FRONTEND_IMAGE" in source[:script_start]
    script = source[script_start : source.index("- name: Smoke test production deployment")]
    assert "${{" not in script
    assert r"^sha-[0-9a-f]{40}$" in source
    assert "DEPLOY_ENV" in source
    assert "push:\n    tags:" not in source
    assert source.index("COMPOSE_PROFILES=migration") < source.index('"${COMPOSE[@]}" up -d')
    assert "--wait --wait-timeout 180" in source
    assert "--pull never" in source
    assert "release.env" in source
    assert "PREVIOUS_RELEASE" in source
    assert "docker image prune" not in source
    assert '"c7a8b9d0e1f2"' in source

    # Exact SCP action pin and checkout contracts
    assert "appleboy/scp-action@917f8b81dfc1ccd331fef9e2d61bdc6c8be94634" in source
    # replace() is not a GitHub Actions expression function: the checkout ref
    # must be derived by the validated "Resolve deployment ref" shell step.
    assert "replace(inputs.version" not in source
    assert "ref: ${{ steps.deploy-ref.outputs.ref }}" in source
    assert "- name: Resolve deployment ref" in source
    assert "id: deploy-ref" in source

    # Sigstore provenance, registry login, digest resolution, and release directory contracts
    assert "docker/login-action@371161bbe7024a29a25c5e19bfcbc0804fe9ad2c" in source
    assert "ADMIN_IMAGE=" in source
    assert "READER_IMAGE=" in source
    assert "FRONTEND_IMAGE=" in source
    assert "sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6" in source
    assert "cosign verify-attestation" in source
    assert "https://slsa.dev/provenance/v1" in source
    assert "gh attestation verify" not in source
    # OCI references must be lowercase: buildx pushes the GHCR repository path
    # lowercased, so the deploy step must normalize before digest resolution.
    assert 'GHCR_BASE="ghcr.io/${{ github.repository }}"' in source
    assert "${GHCR_BASE,,}" in source
    # Multi-platform images are OCI indexes; the top-level digest is absent
    # from the index payload, so it must be read via imagetools --format.
    assert 'docker buildx imagetools inspect "${ADMIN_REF}" --format' in source
    assert "{{.Manifest.Digest}}" in source
    assert "$(docker manifest inspect" not in source
    assert "packages: read" in source
    assert 'RELEASE_DIR="/opt/novelai/releases/$VERSION"' in source
    assert 'CURRENT_LINK="/opt/novelai/current"' in source


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


def test_ci_docker_filter_includes_all_required_inputs() -> None:
    source = _workflow("ci.yml")
    required_docker_paths = [
        "deploy/**",
        ".dockerignore",
        "readme.md",
    ]
    for path in required_docker_paths:
        assert path in source, f"Missing {path} in Docker filter"


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
    assert "VERSION: ${{ inputs.version }}" in source
    assert "DEPLOY_ENV: ${{ inputs.environment }}" in source
    assert "environment: ${{ inputs.environment }}" in source
    assert "vars.PRODUCTION_BASE_URL" in source
    assert "secrets.NOVELAI_SMOKE_SESSION_COOKIE" in source
    assert "secrets.PRODUCTION_BASE_URL" not in source

    # The "Resolve deployment ref" step writes only a regex-validated checkout
    # ref to GITHUB_OUTPUT (one write: the sha- tag suffix); the
    # free-form version input itself is never emitted.
    assert source.count("$GITHUB_OUTPUT") == 1
    resolve_section = source[source.index("- name: Resolve deployment ref") : source.index("- uses: actions/checkout")]
    assert 'echo "ref=${VERSION#sha-}" >> "$GITHUB_OUTPUT"' in resolve_section
    assert 'echo "ref=$GITHUB_SHA" >> "$GITHUB_OUTPUT"' not in resolve_section
    assert 'default: "latest"' not in source
    assert "latest or sha-" not in source


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
    assert "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25" in source
    assert "scan-type: fs" in source
    assert "scanners: vuln,misconfig" in source
    assert "severity: HIGH,CRITICAL" in source
    assert 'TRIVY_INCLUDE_DEV_DEPS: "true"' in source
    assert 'exit-code: "1"' in source


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
    assert "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25" in source
    assert "exit-code: '1'" in source
    assert "zizmor: ignore[dangerous-triggers]" in source
    assert 'IMAGE_NAME="ghcr.io/${REPOSITORY,,}/${IMAGE}"' in source
    assert "image-ref: ${{ steps.image-ref.outputs.ref }}" in source
    assert "sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6" in source
    assert "cosign attest" in source
    assert "cosign verify-attestation" in source
    assert "actions/attest" not in source
    assert "attestations: write" not in source


def test_admin_image_pins_fixed_postgresql_client() -> None:
    dockerfile = (WORKFLOWS_DIR.parent.parent / "deploy" / "admin.Dockerfile").read_text(encoding="utf-8")

    assert "CVE-2026-6473" in dockerfile
    assert "postgresql-client-17=17.11-1.pgdg13+2" in dockerfile


def test_node_version_alignment() -> None:
    nvmrc = (WORKFLOWS_DIR.parent.parent / "frontend" / ".nvmrc").read_text(encoding="utf-8").strip()
    package_json = (WORKFLOWS_DIR.parent.parent / "frontend" / "package.json").read_text(encoding="utf-8")
    dockerfile = (WORKFLOWS_DIR.parent.parent / "deploy" / "frontend.Dockerfile").read_text(encoding="utf-8")

    assert nvmrc == "22"
    assert '"node": ">=22 <23"' in package_json
    assert "node:22-alpine" in dockerfile
    assert "sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32" in dockerfile
    assert "/usr/local/lib/node_modules/npm" in dockerfile
    assert "/usr/local/bin/npm" in dockerfile


def test_dependabot_python_ignore_policy() -> None:
    dependabot_file = WORKFLOWS_DIR.parent / "dependabot.yml"
    source = dependabot_file.read_text(encoding="utf-8")
    assert 'dependency-name: "python"' in source
    assert 'update-types: ["version-update:semver-minor", "version-update:semver-major"]' in source


def test_production_compose_contract() -> None:
    compose_file = WORKFLOWS_DIR.parent.parent / "deploy" / "compose.yml"
    source = compose_file.read_text(encoding="utf-8")
    # Scanner-safe interpolation: no required-variable error text that
    # GitGuardian could mistake for a hard-coded credential. Presence of
    # DATABASE_RESTORE_PASSWORD is enforced by the deploy.yml preflight.
    assert "POSTGRES_PASSWORD: ${DATABASE_RESTORE_PASSWORD}" in source
    assert ":?Set DATABASE_RESTORE_PASSWORD" not in source
    assert "build:" not in source
    # Every third-party image must be digest-pinned with a well-formed
    # sha256 digest. Wrong digests fail `docker compose pull` on any host;
    # the deploy workflow is the only place that exercises the pins.
    pinned = re.findall(r"image: ([a-z0-9.-]+:[a-z0-9._-]+@sha256:[0-9a-f]{64})\s*$", source, re.M)
    assert {"redis:7.4.2-alpine", "postgres:17.4-alpine", "caddy:2.9.1-alpine"} == {ref.split("@")[0] for ref in pinned}
    assert len(pinned) == 3
    # Public-service images use ${VAR:-ghcr.io/...} interpolation and must
    # never be digest-pinned by CI: their digests change on every build, so
    # a pin would hard-fail the deploy.
    assert not re.search(r"image: \$\{[^}]*\}@sha256:[0-9a-f]{64}", source)


def test_caddy_staging_http_contract() -> None:
    repo_root = WORKFLOWS_DIR.parent.parent
    compose_source = (repo_root / "deploy" / "compose.yml").read_text(encoding="utf-8")
    caddy_start = compose_source.index("  caddy:")
    caddy_end = compose_source.index("\n  frontend:", caddy_start) + 1
    caddy_service = compose_source[caddy_start:caddy_end]
    assert "SITE_DOMAIN: ${SITE_DOMAIN:-localhost}" in caddy_service
    assert "env_file:" not in caddy_service

    caddyfile = (repo_root / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert caddyfile.splitlines()[0] == "http://{$SITE_DOMAIN:localhost} {"
    assert "Strict-Transport-Security" not in caddyfile


def test_ci_and_static_analysis_security_contracts() -> None:
    ci = _workflow("ci.yml")
    assert "contents: read\n  pull-requests: read" in ci
    assert ci.count("dorny/paths-filter@") == 2
    assert ci.count("persist-credentials: false") >= 7

    static = _workflow("static-analysis.yml")
    for job_name in ("Analyze (actions)", "Analyze (python)", "Analyze (javascript-typescript)"):
        assert f"name: {job_name}" in static
    assert "zizmor==1.29.0" in static
    assert "--offline" in static
    assert "--format=github" in static
    assert "--min-severity=medium" in static
    assert "S102,S307,S324,S501,S506,S602,S605,S608,S609" in static
    assert "node-version: 22" in static
    assert "npm ci" in static


def test_compose_private_http_health_and_migration_contract() -> None:
    compose = (WORKFLOWS_DIR.parent.parent / "deploy" / "compose.yml").read_text(encoding="utf-8")
    caddy_start = compose.index("  caddy:")
    frontend_start = compose.index("\n  frontend:") + 1
    caddy = compose[caddy_start:frontend_start]
    assert '"${PUBLIC_BIND_ADDRESS:-127.0.0.1}:${PUBLIC_HTTP_PORT:-80}:80"' in caddy
    assert "443:443" not in caddy
    assert "condition: service_healthy" in caddy
    assert "healthcheck:" in caddy
    assert "stop_grace_period" in caddy
    assert "profiles:\n      - migration" in compose
    assert "condition: service_completed_successfully" not in compose
    assert "healthcheck:" in compose[frontend_start:]
    assert "stop_grace_period" in compose[frontend_start:]
    assert "headers={'Host': '${SITE_DOMAIN:-localhost}'}" in compose
    assert "localhost:8000/health/live" in compose
    assert "localhost:8001/health/live" in compose


def test_deploy_actions_consume_deploy_port() -> None:
    deploy = _workflow("deploy.yml")
    # The target SSH port must be configurable per environment; production
    # keeps the default 22 unless overridden, staging sets DEPLOY_PORT=2222.
    assert "DEPLOY_PORT: ${{ vars.DEPLOY_PORT || '22' }}" in deploy
    # Both remote actions (SCP and SSH) must pass the configured port; a
    # missing port input silently falls back to 22 and hits the wrong port.
    assert deploy.count("port: ${{ env.DEPLOY_PORT }}") == 2
    scp_index = deploy.index("appleboy/scp-action")
    ssh_index = deploy.index("appleboy/ssh-action")
    assert deploy[scp_index : scp_index + 500].count("port: ${{ env.DEPLOY_PORT }}") == 1
    assert deploy[ssh_index : ssh_index + 500].count("port: ${{ env.DEPLOY_PORT }}") == 1


def test_deploy_tailscale_private_network_step() -> None:
    deploy = _workflow("deploy.yml")
    # The deploy job reaches the staging host over the private tailnet; the
    # GitHub-hosted runner joins as an ephemeral node before any transfer.
    tailscale_index = deploy.index("tailscale/github-action@")
    assert "authkey: ${{ env.TS_AUTHKEY }}" in deploy
    assert "ping: ${{ env.DEPLOY_HOST }}" in deploy
    assert deploy.count("TS_AUTHKEY: ${{ secrets.TS_AUTHKEY }}") == 1
    # The step must run before both remote actions.
    assert tailscale_index < deploy.index("appleboy/scp-action")
    assert tailscale_index < deploy.index("appleboy/ssh-action")
    # No untagged public-tunnel remnant may exist.
    assert "ngrok" not in deploy
    assert "pinggy" not in deploy


def test_deploy_restore_password_preflight() -> None:
    deploy = _workflow("deploy.yml")
    script_start = deploy.index("script: |")
    script = deploy[script_start : deploy.index("- name: Smoke test production deployment")]
    assert "${{" not in script
    assert "grep -Eq '^DATABASE_RESTORE_PASSWORD=.+$'" in script
    assert "restore-db (recovery) profile" in script
