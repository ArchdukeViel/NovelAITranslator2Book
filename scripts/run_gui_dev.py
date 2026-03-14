from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from watchfiles import run_process


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _target() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    subprocess.run(
        [sys.executable, "-m", "novelai.interfaces.cli", "gui"],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
    )


if __name__ == "__main__":
    run_process(str(PROJECT_ROOT / "src"), target=_target)
