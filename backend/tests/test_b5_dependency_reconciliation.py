from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_tool(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b5_generator_and_validator_are_provider_free(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    generator = _load_tool("b5_generator", root / "tools" / "capacity" / "run_b5_dependency_reconciliation.py")
    validator = _load_tool("b5_validator", root / "tools" / "capacity" / "validate_b5_dependency_reconciliation.py")

    campaign_id = generator.generate(tmp_path)

    assert campaign_id.startswith("campaign-")
    assert validator.validate_directory(tmp_path) == []


def test_b5_validator_rejects_protected_fields(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    generator = _load_tool(
        "b5_generator_redaction", root / "tools" / "capacity" / "run_b5_dependency_reconciliation.py"
    )
    validator = _load_tool(
        "b5_validator_redaction", root / "tools" / "capacity" / "validate_b5_dependency_reconciliation.py"
    )

    generator.generate(tmp_path)
    payload = {"token": "must-not-be-recorded"}

    assert validator._redaction_errors(payload)
