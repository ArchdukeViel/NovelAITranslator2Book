"""Forwarding stub for tools/benchmarks/run_hosted_benchmark.py."""

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "tools" / "benchmarks" / "run_hosted_benchmark.py"
    runpy.run_path(str(target), run_name="__main__")
