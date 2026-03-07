from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from novelai.services.storage_service import StorageService
from tests.conftest import cleanup_test_artifacts


def _workspace_test_root() -> Path:
    root = Path("tests/.tmp/project_layout") / uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_build_export_path_defaults_to_novel_library():
    root = _workspace_test_root()
    try:
        storage = StorageService(root / "novel_library")
        storage.save_metadata("novel1", {"title": "Test Novel"})

        export_path = storage.build_export_path("novel1", "epub")

        expected_path = (
            root.resolve()
            / "novel_library"
            / "novels"
            / "novel1"
            / "full_novel.epub"
        )
        assert export_path == expected_path
        assert export_path.parent.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_export_path_supports_custom_output_dir():
    root = _workspace_test_root()
    try:
        storage = StorageService(root / "novel_library")
        custom_output = root / "custom-output"

        export_path = storage.build_export_path("novel1", "pdf", custom_output)

        assert export_path == custom_output / "novel1.pdf"
        assert custom_output.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cleanup_test_artifacts_removes_known_directories():
    root = _workspace_test_root()
    try:
        project_root = root / "project"
        tests_root = project_root / "tests"
        for path in [
            project_root / ".pytest_cache",
            tests_root / ".pytest_cache",
            tests_root / ".tmp" / "fixtures",
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
            "tests/.tmp/fixtures",
            "tests/.tmp",
            "tests_tmp",
            "pytest-cache-files-abcd1234",
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)
