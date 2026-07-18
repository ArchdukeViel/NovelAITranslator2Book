from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from novelai import __main__ as package_main
from novelai.runtime import cli


def _patch_bootstrap(monkeypatch, fn):
    """Patch the bootstrap function. novelai.runtime.bootstrap is re-exported
    as a function in __init__.py, so we need to patch the actual module."""
    import importlib
    mod = importlib.import_module("novelai.runtime.bootstrap")
    monkeypatch.setattr(mod, "bootstrap", fn)


def test_cli_default_runs_web(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    _patch_bootstrap(monkeypatch, lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr("novelai.api.server.main", lambda *, reload=False: calls.append(("web", reload)), raising=False)

    cli.main([])

    assert calls == [("bootstrap", None), ("web", False)]


def test_cli_web_reload_runs_web_main(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    _patch_bootstrap(monkeypatch, lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr("novelai.api.server.main", lambda *, reload=False: calls.append(("web", reload)), raising=False)

    cli.main(["web", "--reload"])

    assert calls == [("bootstrap", None), ("web", True)]


def test_cli_adminweb_opens_admin_frontend(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, object]] = []
    _patch_bootstrap(monkeypatch, lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.append(("open", url)) or True)

    cli.main(["adminweb"])

    assert calls == [("open", "http://127.0.0.1:3000/admin")]
    assert "Opened http://127.0.0.1:3000/admin" in capsys.readouterr().out


def test_cli_publicweb_prints_public_frontend_when_no_open(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[str, object]] = []
    _patch_bootstrap(monkeypatch, lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.append(("open", url)) or True)

    cli.main(["publicweb", "--base-url", "https://novels.example.com", "--no-open"])

    assert calls == []
    assert urlparse(capsys.readouterr().out.split("Public reader at ")[1].strip()).hostname == "novels.example.com"


def test_cli_worker_once_runs_one_job(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []

    class StubRunner:
        async def run_once(self) -> dict[str, str]:
            calls.append("run_once")
            return {"id": "job-1", "status": "completed"}

    _patch_bootstrap(monkeypatch, lambda: calls.append("bootstrap"))
    monkeypatch.setattr("novelai.runtime.container.container", SimpleNamespace(job_runner=StubRunner()), raising=False)

    cli.main(["worker", "--once"])

    assert "bootstrap" in calls


def test_cli_doctor_exits_zero_when_checks_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []
    _patch_bootstrap(monkeypatch, lambda: calls.append("bootstrap"))
    monkeypatch.setattr("novelai.runtime.cli._doctor_check", lambda: (0, ["Result: PASS"]), raising=False)

    cli.main(["doctor"])

    output = capsys.readouterr().out
    assert calls == ["bootstrap"]
    assert "Result: PASS" in output


def test_cli_doctor_exits_nonzero_when_checks_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_bootstrap(monkeypatch, lambda: None)
    monkeypatch.setattr("novelai.runtime.cli._doctor_check", lambda: (2, ["Result: WARN"]), raising=False)

    with pytest.raises(SystemExit) as exc:
        cli.main(["doctor"])

    assert exc.value.code == 1


def test_package_main_routes_web_and_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str] | bool]] = []
    monkeypatch.setattr(package_main, "cli_main", lambda argv: calls.append(("cli", list(argv))))
    monkeypatch.setattr(package_main, "web_main", lambda *, reload=False: calls.append(("web", reload)))

    package_main.main(["--interface", "cli", "doctor"])
    package_main.main(["--interface", "web"])
    package_main.main(["--reload"])

    assert calls == [
        ("cli", ["doctor"]),
        ("web", False),
        ("web", True),
    ]


def test_pyproject_console_scripts_use_web_only_modules() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert scripts["novelaibook"] == "novelai.runtime.cli:main"
    assert scripts["novelai"] == "novelai.__main__:main"
    assert "novelaibook-gui" not in scripts
