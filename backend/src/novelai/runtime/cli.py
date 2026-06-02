from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

from novelai.config.settings import settings
from novelai.api.server import main as web_main
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container


def _expected_launcher_path() -> Path:
    launcher_name = "novelaibook.exe" if sys.platform.startswith("win") else "novelaibook"
    python_dir = Path(sys.executable).resolve().parent
    if sys.platform.startswith("win"):
        scripts_dir = python_dir / "Scripts"
        if scripts_dir.exists():
            return scripts_dir / launcher_name
        return python_dir / launcher_name
    bin_dir = python_dir.parent / "bin"
    if bin_dir.exists():
        return bin_dir / launcher_name
    return python_dir / launcher_name


def _doctor_check() -> tuple[int, list[str]]:
    warnings = 0
    lines: list[str] = []
    expected = _expected_launcher_path()
    resolved = shutil.which("novelaibook")

    lines.append("NovelAIBook Doctor")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Expected launcher: {expected}")
    lines.append(f"Resolved launcher: {resolved or 'not found on PATH'}")

    if not expected.exists():
        warnings += 1
        lines.append("WARN: Expected launcher does not exist in the current environment.")

    if resolved is None:
        warnings += 1
        lines.append("WARN: 'novelaibook' is not available on PATH.")
    else:
        expected_text = str(expected.resolve())
        resolved_text = str(Path(resolved).resolve())
        if resolved_text.casefold() != expected_text.casefold():
            warnings += 1
            lines.append(
                "WARN: PATH points to a different launcher than the active Python environment. "
                "This can run stale entrypoint code."
            )

        try:
            probe = subprocess.run(
                [resolved, "--help"],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except Exception as exc:  # noqa: BLE001
            warnings += 1
            lines.append(f"WARN: Failed to execute launcher probe: {exc}")
        else:
            if probe.returncode != 0:
                warnings += 1
                output = (probe.stderr or probe.stdout or "").strip().replace("\n", " ")
                lines.append(f"WARN: Launcher probe failed with exit code {probe.returncode}. Output: {output[:220]}")

    if warnings:
        lines.append("Result: WARN")
        lines.append("Fix: python -m pip install -e .")
    else:
        lines.append("Result: PASS")
    return warnings, lines


async def _run_worker_once() -> None:
    job = await container.job_runner.run_once()
    if job is None:
        print("No pending jobs.")
        return
    print(f"Processed job {job.get('id')} -> {job.get('status')}")


async def _run_worker_forever(poll_seconds: float | None) -> None:
    if poll_seconds is not None:
        container.job_runner.poll_seconds = max(0.05, float(poll_seconds))

    print(f"Worker started. Polling every {container.job_runner.poll_seconds:.2f}s. Press CTRL+C to stop.")
    while True:
        job = await container.job_runner.run_once()
        if job is None:
            await asyncio.sleep(container.job_runner.poll_seconds)
        else:
            print(f"Processed job {job.get('id')} -> {job.get('status')}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelaibook")
    subparsers = parser.add_subparsers(dest="command")

    web_parser = subparsers.add_parser("web", help="Run the backend web API")
    web_parser.add_argument("--reload", action="store_true", help="Reload the backend when Python files change.")

    worker_parser = subparsers.add_parser("worker", help="Run queued crawl and translation jobs")
    worker_parser.add_argument("--once", action="store_true", help="Process at most one pending job and exit.")
    worker_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=settings.JOB_WORKER_POLL_SECONDS,
        help="Polling delay for continuous worker mode.",
    )

    subparsers.add_parser("doctor", help="Check launcher wiring and environment health")

    args = parser.parse_args(argv)
    command = args.command or "web"

    bootstrap()

    if command == "web":
        web_main(reload=bool(getattr(args, "reload", False)))
        return

    if command == "worker":
        try:
            if bool(args.once):
                asyncio.run(_run_worker_once())
            else:
                asyncio.run(_run_worker_forever(args.poll_seconds))
        except KeyboardInterrupt:
            print("Worker stopped.")
        return

    if command == "doctor":
        warnings, lines = _doctor_check()
        print("\n".join(lines))
        if warnings:
            raise SystemExit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
