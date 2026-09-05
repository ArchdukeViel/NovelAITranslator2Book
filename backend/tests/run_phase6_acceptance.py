"""Forwarding stub for tools/capacity/run_phase6_acceptance.py."""

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "tools" / "capacity" / "run_phase6_acceptance.py"
    runpy.run_path(str(target), run_name="__main__")
