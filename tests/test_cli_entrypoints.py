from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

from novelai import __main__ as package_main
from novelai.interfaces import cli


def test_cli_default_runs_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class StubTUIApp:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(cli, "TUIApp", StubTUIApp)

    cli.main([])

    assert calls == ["bootstrap", "run"]


def test_cli_gui_runs_desktop_main(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    desktop_module = ModuleType("novelai.interfaces.desktop.app")

    def _desktop_main() -> None:
        calls.append("desktop")

    desktop_module.main = _desktop_main  # type: ignore[attr-defined]
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append("bootstrap"))
    monkeypatch.setitem(sys.modules, "novelai.interfaces.desktop.app", desktop_module)

    cli.main(["gui"])

    assert calls == ["bootstrap", "desktop"]


def test_cli_gui_missing_dependency_shows_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failing_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "novelai.interfaces.desktop.app":
            raise ModuleNotFoundError("No module named 'PySide6'", name="PySide6")
        return _orig_import(name, globals, locals, fromlist, level)

    calls: list[str] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append("bootstrap"))
    _orig_import = __import__
    monkeypatch.setattr("builtins.__import__", _failing_import)

    with pytest.raises(SystemExit, match="Desktop GUI dependency 'PySide6' is not installed"):
        cli.main(["gui"])

    assert calls == ["bootstrap"]


def test_cli_web_runs_web_main(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "bootstrap", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(cli, "web_main", lambda: calls.append("web"))

    cli.main(["web"])

    assert calls == ["bootstrap", "web"]


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


def test_package_main_routes_interfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(package_main, "cli_main", lambda argv: calls.append(("cli", list(argv))))
    monkeypatch.setattr(package_main, "web_main", lambda: calls.append(("web", [])))

    package_main.main(["--interface", "cli", "translate-chapters", "src", "nov", "1"])
    package_main.main(["--interface", "tui", "status"])
    package_main.main(["--interface", "gui", "status"])
    package_main.main(["--interface", "web"])

    assert calls[0] == ("cli", ["translate-chapters", "src", "nov", "1"])
    assert calls[1] == ("cli", ["tui", "status"])
    assert calls[2] == ("cli", ["gui", "status"])
    assert calls[3] == ("web", [])


def test_pyproject_console_scripts_use_canonical_modules() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert scripts["novelaibook"] == "novelai.interfaces.cli:main"
    assert scripts["novelaibook-gui"] == "novelai.interfaces.desktop.app:main"
    assert scripts["novelai"] == "novelai.__main__:main"


def test_egg_info_entry_points_do_not_reference_legacy_modules() -> None:
    entry_points = Path(__file__).resolve().parents[1] / "src" / "novel_ai.egg-info" / "entry_points.txt"
    if not entry_points.exists():
        pytest.skip("egg-info metadata not present in this checkout")

    content = entry_points.read_text(encoding="utf-8")
    assert "novelai.app.cli:main" not in content
    assert "novelai.desktop.app:main" not in content
    assert "novelaibook = novelai.interfaces.cli:main" in content
    assert "novelaibook-gui = novelai.interfaces.desktop.app:main" in content