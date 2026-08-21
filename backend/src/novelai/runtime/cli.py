from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
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

    runner = container.activity_runner
    activity = await runner.run_once()
    if activity is None:
        print("No pending job.")
        return
    print(f"Processed job {activity.get('activity_id')} -> {activity.get('status')}")


async def _run_worker_forever(poll_seconds: float | None) -> None:
    from novelai.runtime.container import container

    runner = container.activity_runner
    if poll_seconds is not None:
        runner.poll_seconds = max(0.05, float(poll_seconds))

    print(f"Worker started. Polling every {runner.poll_seconds:.2f}s. Press CTRL+C to stop.")
    while True:
        activity = await runner.run_once()
        if activity is None:
            await asyncio.sleep(runner.poll_seconds)
        else:
            print(f"Processed job {activity.get('activity_id')} -> {activity.get('status')}")


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


def _build_backup_r2_storage():
    from novelai.storage.backends.r2 import R2Storage

    return R2Storage(
        bucket=settings.R2_BACKUP_BUCKET,
        endpoint_url=settings.R2_BACKUP_ENDPOINT or settings.R2_ENDPOINT,
        region=settings.R2_REGION,
        access_key_id=(
            settings.R2_BACKUP_ACCESS_KEY_ID.get_secret_value() if settings.R2_BACKUP_ACCESS_KEY_ID else None
        ),
        secret_access_key=(
            settings.R2_BACKUP_SECRET_ACCESS_KEY.get_secret_value() if settings.R2_BACKUP_SECRET_ACCESS_KEY else None
        ),
    )


def _print_r2_inventory() -> None:
    from novelai.runtime.container import container
    from novelai.storage.r2_cutover import inventory_bucket

    application = inventory_bucket(container.storage.r2_backend)
    backup = inventory_bucket(_build_backup_r2_storage())
    print(
        json.dumps(
            {
                "application": {
                    "bucket": application.bucket,
                    "object_count": application.object_count,
                    "bytes_total": application.bytes_total,
                },
                "backup": {
                    "bucket": backup.bucket,
                    "object_count": backup.object_count,
                    "bytes_total": backup.bytes_total,
                },
            },
            sort_keys=True,
        )
    )


def _run_r2_reset(*, execute: bool, writers_frozen: bool, identities_verified: bool, confirmation: str | None) -> None:
    from novelai.runtime.container import container
    from novelai.storage.r2_cutover import R2CutoverService

    result = R2CutoverService(
        application=container.storage.r2_backend,
        backup=_build_backup_r2_storage(),
    ).reset(
        writers_frozen=writers_frozen,
        identities_verified=identities_verified,
        confirmation=confirmation,
        dry_run=not execute,
    )
    print(json.dumps(asdict(result), sort_keys=True, default=list))


def _run_r2_gc(*, execute: bool, grace_days: int) -> None:
    from novelai.db.engine import session_scope
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel
    from novelai.runtime.container import container
    from novelai.storage.r2_cutover import R2GarbageCollector

    referenced: set[str] = set()
    protected: set[str] = set()
    exact_artifact_keys: set[str] = set()
    with session_scope() as session:
        for novel in session.query(Novel).all():
            if novel.active_generation_storage_key:
                protected.add(novel.active_generation_storage_key)
        for chapter in session.query(Chapter).all():
            for key in (chapter.raw_storage_key, chapter.translated_storage_key, chapter.media_storage_key):
                if key:
                    referenced.add(key)
                    exact_artifact_keys.add(key)

    # Raw chapter manifests can contain exact content-addressed asset keys.
    # Mark those nested references too, otherwise an image reused by a live
    # chapter could be swept merely because its small asset key is not a
    # dedicated PostgreSQL column.
    def _mark_nested_keys(value: object) -> None:
        if isinstance(value, dict):
            for item in value.values():
                _mark_nested_keys(item)
        elif isinstance(value, list):
            for item in value:
                _mark_nested_keys(item)
        elif isinstance(value, str) and value.startswith("novels/"):
            referenced.add(value)

    for key in exact_artifact_keys:
        with contextlib.suppress(FileNotFoundError, RuntimeError):
            _mark_nested_keys(container.storage.load_r2_json_artifact(key))
    result = R2GarbageCollector(container.storage.r2_backend).collect(
        referenced_keys=referenced,
        protected_keys=protected,
        grace_period=timedelta(days=grace_days),
        dry_run=not execute,
    )
    print(json.dumps(asdict(result), sort_keys=True, default=list))


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
    create_user_parser.add_argument(
        "--role", default="user", choices=["user", "owner"], help="Role to assign (default: user)"
    )
    create_user_parser.add_argument("--display-name", default=None, help="Optional display name")

    subparsers.add_parser("doctor", help="Check launcher wiring and environment health")

    subparsers.add_parser("r2-inventory", help="Inventory both canonical R2 buckets")

    reset_parser = subparsers.add_parser("r2-reset", help="Plan or explicitly execute the two-bucket R2 reset")
    reset_parser.add_argument("--execute", action="store_true", help="Execute after all safety gates pass")
    reset_parser.add_argument("--writers-frozen", action="store_true", help="Confirm all writers are frozen")
    reset_parser.add_argument(
        "--identities-verified", action="store_true", help="Confirm the identity manifest is verified"
    )
    reset_parser.add_argument("--confirm", default=None, help="Exact reset confirmation token")

    gc_parser = subparsers.add_parser("r2-gc", help="Mark and sweep unreferenced R2 objects")
    gc_parser.add_argument("--execute", action="store_true", help="Delete eligible objects; default is dry-run")
    gc_parser.add_argument("--grace-days", type=int, default=7, help="Minimum age of an unreferenced object")

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

    if command == "r2-inventory":
        from novelai.runtime.bootstrap import bootstrap

        bootstrap()
        _print_r2_inventory()
        return

    if command == "r2-reset":
        from novelai.runtime.bootstrap import bootstrap

        bootstrap()
        _run_r2_reset(
            execute=bool(args.execute),
            writers_frozen=bool(args.writers_frozen),
            identities_verified=bool(args.identities_verified),
            confirmation=args.confirm,
        )
        return

    if command == "r2-gc":
        if args.grace_days < 0:
            raise SystemExit("--grace-days cannot be negative")
        from novelai.runtime.bootstrap import bootstrap

        bootstrap()
        _run_r2_gc(execute=bool(args.execute), grace_days=args.grace_days)
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
