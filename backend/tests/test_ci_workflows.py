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
    assert all(test_path in source[source.index("backend-extended:") :] for test_path in ignored)
    assert "needs: [backend-tests, backend-extended, frontend-check]" in source


def test_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    action_lines: list[str] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        action_lines.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if "uses:" in line)

    assert action_lines
    assert all(PINNED_ACTION.fullmatch(line) for line in action_lines), action_lines


def test_build_summary_fails_unless_publication_succeeds() -> None:
    source = _workflow("build.yml")

    assert "ref: ${{ github.event.workflow_run.head_sha }}" in source
    assert "BUILD_RESULT: ${{ needs.build-and-push.result }}" in source
    assert 'if [ "$BUILD_RESULT" != "success" ]; then' in source
    assert "exit 1" in source
