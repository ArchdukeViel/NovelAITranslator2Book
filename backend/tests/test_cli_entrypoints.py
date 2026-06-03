from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from novelai import __main__ as package_main
from novelai.runtime import cli


def test_cli_default_runs_web(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr(cli, "web_main", lambda *, reload=False: calls.append(("web", reload)))

    cli.main([])

    assert calls == [("bootstrap", None), ("web", False)]


def test_cli_web_reload_runs_web_main(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr(cli, "web_main", lambda *, reload=False: calls.append(("web", reload)))

    cli.main(["web", "--reload"])

    assert calls == [("bootstrap", None), ("web", True)]


def test_cli_adminweb_opens_admin_frontend(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.append(("open", url)) or True)

    cli.main(["adminweb"])

    assert calls == [("open", "http://127.0.0.1:3000/admin")]
    assert "Opened http://127.0.0.1:3000/admin" in capsys.readouterr().out


def test_cli_publicweb_prints_public_frontend_when_no_open(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append(("bootstrap", None)))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.append(("open", url)) or True)

    cli.main(["publicweb", "--base-url", "https://novels.example.com", "--no-open"])

    assert calls == []
    assert "https://novels.example.com/" in capsys.readouterr().out


def test_cli_worker_once_runs_one_job(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []

    class StubRunner:
        async def run_once(self) -> dict[str, str]:
            calls.append("run_once")
            return {"id": "job-1", "status": "completed"}

    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(cli, "container", SimpleNamespace(job_runner=StubRunner()))

    cli.main(["worker", "--once"])

    assert calls == ["bootstrap", "run_once"]
    assert "Processed job job-1 -> completed" in capsys.readouterr().out


def test_cli_doctor_exits_zero_when_checks_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(cli, "_doctor_check", lambda: (0, ["Result: PASS"]))

    cli.main(["doctor"])

    output = capsys.readouterr().out
    assert calls == ["bootstrap"]
    assert "Result: PASS" in output


def test_cli_doctor_exits_nonzero_when_checks_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "bootstrap", lambda: None)
    monkeypatch.setattr(cli, "_doctor_check", lambda: (2, ["Result: WARN"]))

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


def test_legacy_cli_import_is_resolved_by_compat_layer() -> None:
    import importlib

    legacy_cli = importlib.import_module("novelai.interfaces.cli")

    assert legacy_cli is cli


def test_legacy_web_import_is_resolved_by_compat_layer() -> None:
    import importlib

    legacy_app = importlib.import_module("novelai.interfaces.web.app")
    canonical_app = importlib.import_module("novelai.api.app")

    assert legacy_app is canonical_app


def test_legacy_pipeline_and_service_imports_are_resolved_by_compat_layer() -> None:
    import importlib

    legacy_pipeline = importlib.import_module("novelai.pipeline.pipeline")
    canonical_pipeline = importlib.import_module("novelai.translation.pipeline.pipeline")
    legacy_storage = importlib.import_module("novelai.services.storage_service")
    canonical_storage = importlib.import_module("novelai.storage.service")

    assert legacy_pipeline is canonical_pipeline
    assert legacy_storage is canonical_storage
