from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from tests.conftest import TESTS_ROOT, TESTS_TMP_ROOT, cleanup_test_artifacts


def _workspace_test_root() -> Path:
    root = TESTS_TMP_ROOT.parent.parent / "project_layout" / uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_cleanup_test_artifacts_removes_known_directories():
    root = _workspace_test_root()
    try:
        project_root = root / "project"
        tests_root = project_root / "tests"
        from tests.conftest import _XDIST_WORKER_ID

        for path in [
            project_root / ".pytest_cache",
            tests_root / ".pytest_cache",
            tests_root / ".tmp" / "fixtures" / _XDIST_WORKER_ID,
            project_root / "tests_tmp",
            project_root / "pytest-cache-files-abcd1234",
        ]:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("x", encoding="utf-8")

        removed, warnings = cleanup_test_artifacts(
            project_root=project_root,
            tests_root=tests_root,
            include_pytest_managed=True,
        )

        assert not warnings
        assert {str(path.relative_to(project_root)).replace("\\", "/") for path in removed} == {
            ".pytest_cache",
            "tests/.pytest_cache",
            f"tests/.tmp/fixtures/{_XDIST_WORKER_ID}",
            "tests_tmp",
            "pytest-cache-files-abcd1234",
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_xdist_worker_temp_isolation():
    from tests.conftest import _XDIST_WORKER_ID, TESTS_RUNTIME_ROOT, TESTS_TMP_ROOT

    assert TESTS_TMP_ROOT.name == _XDIST_WORKER_ID
    assert TESTS_RUNTIME_ROOT.name == _XDIST_WORKER_ID
    assert TESTS_TMP_ROOT.parent == TESTS_ROOT / ".tmp" / "fixtures"
    assert TESTS_RUNTIME_ROOT.parent == TESTS_ROOT / ".tmp" / "runtime"


def test_deployment_files_have_one_canonical_frontend_dockerfile() -> None:
    project_root = Path(__file__).resolve().parents[2]

    assert (project_root / "deploy" / "frontend.Dockerfile").is_file()
    assert not (project_root / "frontend" / "Dockerfile").exists()
