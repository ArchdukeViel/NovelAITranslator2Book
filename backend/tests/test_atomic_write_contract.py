"""Runtime-file atomic-write tests.

Canonical novel artifacts are R2 objects and are covered by the R2 backend
tests; these cases cover only disposable local runtime files.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import novelai.utils as utils
from novelai.services.pipeline.checkpoint import Checkpoint, CheckpointManager
from novelai.utils.filesystem import replace_with_retry


def test_atomic_write_first_write(tmp_path: Path) -> None:
    target = tmp_path / "new_target.txt"
    utils.atomic_write(target, "NEW")
    assert target.read_text(encoding="utf-8") == "NEW"
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_retries_transient_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("OLD", encoding="utf-8")
    attempts = 0
    sleep_calls: list[float] = []
    real_replace = os.replace

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise PermissionError("Locked transiently")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", sleep_calls.append)
    utils.atomic_write(target, "NEW")
    assert attempts == 3
    assert len(sleep_calls) == 2
    assert target.read_text(encoding="utf-8") == "NEW"


def test_replace_with_retry_validates_attempts(tmp_path: Path) -> None:
    src = tmp_path / "src.tmp"
    dst = tmp_path / "dst.txt"
    for attempts in (0, -1):
        with pytest.raises(ValueError, match="attempts must be >= 1"):
            replace_with_retry(src, dst, attempts=attempts)


def test_checkpoint_runtime_write_failure_preserves_previous_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = CheckpointManager(tmp_path)
    manager.save(Checkpoint("ch1", segments_completed=5, segments_total=10))

    def fail_replace(_src: str | Path, _dst: str | Path) -> None:
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", fail_replace)
    manager.save(Checkpoint("ch1", segments_completed=8, segments_total=10))

    loaded = manager.load("ch1")
    assert loaded is not None and loaded.segments_completed == 5
    assert any("Failed to write checkpoint ch1" in record.message for record in caplog.records)
