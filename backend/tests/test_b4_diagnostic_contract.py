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


def test_generated_b4_evidence_validates_without_provider_access(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    generator = _load_tool("b4_generator", root / "tools" / "capacity" / "run_b4_local_diagnostics.py")
    validator = _load_tool("b4_validator", root / "tools" / "capacity" / "validate_b4_diagnostics.py")

    campaign_id = generator.generate(tmp_path)

    assert campaign_id.startswith("campaign-")
    assert validator.validate_directory(tmp_path) == []


def test_b4_validator_rejects_protected_text_and_missing_artifacts(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    validator = _load_tool("b4_validator_redaction", root / "tools" / "capacity" / "validate_b4_diagnostics.py")

    assert validator._redaction_errors({"sql": "SELECT private_value"})
    errors = validator.validate_directory(tmp_path)

    assert len(errors) == len(validator.REQUIRED_ARTIFACTS)
    assert all("missing artifact" in error for error in errors)
