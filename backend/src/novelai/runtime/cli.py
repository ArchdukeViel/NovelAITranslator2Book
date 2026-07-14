from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

from novelai.config.settings import settings


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
        except Exception as exc:
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
    from novelai.runtime.container import container
    runner = getattr(container, "activity_runner", None) or container.job_runner
    activity = await runner.run_once()
    if activity is None:
        print("No pending job.")
        return
    print(f"Processed job {activity.get('id')} -> {activity.get('status')}")


async def _run_worker_forever(poll_seconds: float | None) -> None:
    from novelai.runtime.container import container
    runner = getattr(container, "activity_runner", None) or container.job_runner
    if poll_seconds is not None:
        runner.poll_seconds = max(0.05, float(poll_seconds))

    print(f"Worker started. Polling every {runner.poll_seconds:.2f}s. Press CTRL+C to stop.")
    while True:
        activity = await runner.run_once()
        if activity is None:
            await asyncio.sleep(runner.poll_seconds)
        else:
            print(f"Processed job {activity.get('id')} -> {activity.get('status')}")


def _frontend_url(
    path: str,
    *,
    base_url: str | None = None,
    host: str = "127.0.0.1",
    port: int = 3000,
) -> str:
    normalized_path = f"/{path.lstrip('/')}"
    if base_url:
        return urljoin(f"{base_url.rstrip('/')}/", normalized_path.lstrip("/"))
    return f"http://{host}:{port}{normalized_path}"


def _open_frontend_page(
    path: str,
    *,
    base_url: str | None = None,
    host: str = "127.0.0.1",
    port: int = 3000,
    open_browser: bool = True,
    label: str | None = None,
) -> str:
    url = _frontend_url(path, base_url=base_url, host=host, port=port)
    if open_browser:
        opened = webbrowser.open(url)
        if label:
            print(f"Opened {label} at {url}" if opened else f"{label} at {url}")
        else:
            print(f"Opened {url}" if opened else url)
    else:
        if label:
            print(f"{label} at {url}")
        else:
            print(url)
    return url


def _add_frontend_page_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=None,
        help="Frontend base URL to open, e.g. https://novels.example.com.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Frontend host when --base-url is not provided.")
    parser.add_argument("--port", type=int, default=3000, help="Frontend port when --base-url is not provided.")
    parser.add_argument("--no-open", action="store_true", help="Print the URL without opening a browser.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelaibook")
    subparsers = parser.add_subparsers(dest="command")

    web_parser = subparsers.add_parser("web", help="Run the backend web API")
    web_parser.add_argument("--reload", action="store_true", help="Reload the backend when Python files change.")

    adminweb_parser = subparsers.add_parser("adminweb", help="Open the admin web UI at /admin")
    _add_frontend_page_arguments(adminweb_parser)

    publicweb_parser = subparsers.add_parser("publicweb", help="Open the public reader web UI at /")
    _add_frontend_page_arguments(publicweb_parser)

    worker_parser = subparsers.add_parser("worker", help="Run queued crawl and translation jobs")
    worker_parser.add_argument("--once", action="store_true", help="Process at most one pending job and exit.")
    worker_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=settings.JOB_WORKER_POLL_SECONDS,
        help="Polling delay for continuous worker mode.",
    )

    create_user_parser = subparsers.add_parser("create-user", help="Create a password-based user (owner or user role)")
    create_user_parser.add_argument("email", help="User email address")
    create_user_parser.add_argument("password", help="User password (will be Argon2id-hashed)")
    create_user_parser.add_argument("--role", default="user", choices=["user", "owner"], help="Role to assign (default: user)")
    create_user_parser.add_argument("--display-name", default=None, help="Optional display name")

    subparsers.add_parser("doctor", help="Check launcher wiring and environment health")

    args = parser.parse_args(argv)
    command = args.command or "web"

    if command == "adminweb":
        _open_frontend_page(
            "/admin",
            base_url=args.base_url,
            host=args.host,
            port=args.port,
            open_browser=not bool(args.no_open),
        )
        return

    if command == "publicweb":
        _open_frontend_page(
            "/",
            base_url=args.base_url,
            host=args.host,
            port=args.port,
            open_browser=not bool(args.no_open),
            label="Public reader",
        )
        return

    from novelai.runtime.bootstrap import bootstrap
    bootstrap()

    if command == "web":
        from novelai.api.server import main as web_main
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

    if command == "create-user":
        # Lazy imports — argon2 is an optional dependency
        from novelai.api.auth.passwords import hash_password
        from novelai.db.engine import session_scope
        from novelai.db.models.users import User

        email = args.email.strip().lower()
        if not email:
            print("Error: email is required.", file=sys.stderr)
            raise SystemExit(1)
        if len(args.password) < 8:
            print("Error: password must be at least 8 characters.", file=sys.stderr)
            raise SystemExit(1)

        pw_hash = hash_password(args.password)
        user = User(
            email=email,
            display_name=args.display_name,
            role=args.role,
            password_hash=pw_hash,
            email_verified_at=datetime.now(UTC),
            is_active=True,
        )
        try:
            with session_scope() as session:
                session.add(user)
                session.flush()
                print(f"Created {args.role} user: id={user.id} email={user.email}")
        except Exception as exc:
            print(f"Error: failed to create user — {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
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
