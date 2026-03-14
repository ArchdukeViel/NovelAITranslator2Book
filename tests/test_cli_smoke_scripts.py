from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _venv_launcher() -> Path:
    root = Path(__file__).resolve().parents[1]
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "novelaibook.exe"
    return root / ".venv" / "bin" / "novelaibook"


def _run_launcher(args: list[str]) -> subprocess.CompletedProcess[str]:
    launcher = _venv_launcher()
    if not launcher.exists():
        pytest.skip(f"launcher not found: {launcher}")
    return subprocess.run(
        [str(launcher), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_venv_launcher_help_succeeds() -> None:
    result = _run_launcher(["--help"])

    assert result.returncode == 0
    assert "usage: novelaibook" in result.stdout.lower()


@pytest.mark.parametrize("subcommand", ["tui", "gui", "doctor"])
def test_venv_launcher_subcommand_help_succeeds(subcommand: str) -> None:
    result = _run_launcher([subcommand, "--help"])

    assert result.returncode == 0
    assert f"usage: novelaibook {subcommand}" in result.stdout.lower()


def test_venv_launcher_doctor_outputs_status() -> None:
    result = _run_launcher(["doctor"])

    # doctor may return non-zero when PATH points to stale launcher; output must be actionable.
    assert "novelaibook doctor" in result.stdout.lower()
    assert "result:" in result.stdout.lower()
    assert "fix: python -m pip install -e ." in result.stdout.lower()
