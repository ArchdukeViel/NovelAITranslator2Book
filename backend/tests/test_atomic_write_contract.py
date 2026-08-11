from __future__ import annotations

import os
from pathlib import Path

import pytest

import novelai.utils as utils
from novelai.services.pipeline.checkpoint import Checkpoint, CheckpointManager
from novelai.storage.backends.filesystem import FilesystemBackend
from novelai.utils.filesystem import replace_with_retry


# ── Matrix A: First write ──────────────────────────────────────────────────
def test_atomic_write_first_write(tmp_path: Path) -> None:
    target = tmp_path / "new_target.txt"

    utils.atomic_write(target, "NEW")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "NEW"
    assert list(tmp_path.glob("*.tmp")) == []


# ── Matrix B: Normal replacement ──────────────────────────────────────────
def test_atomic_write_normal_replacement(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("OLD", encoding="utf-8")

    utils.atomic_write(target, "NEW")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "NEW"
    assert list(tmp_path.glob("*.tmp")) == []


# ── Matrix C: Transient PermissionError ───────────────────────────────────
def test_atomic_write_transient_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("OLD", encoding="utf-8")

    attempts = 0
    real_replace = os.replace
    sleep_calls: list[float] = []

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise PermissionError("Locked transiently")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda s: sleep_calls.append(s))

    utils.atomic_write(target, "NEW")

    assert attempts == 3
    assert len(sleep_calls) == 2
    assert target.read_text(encoding="utf-8") == "NEW"
    assert list(tmp_path.glob("*.tmp")) == []


# ── Matrix D: Persistent PermissionError (Principal Test) ──────────────────
def test_atomic_write_persistent_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("OLD", encoding="utf-8")

    attempts = 0
    sleep_calls: list[float] = []

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        raise PermissionError("Locked permanently")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda s: sleep_calls.append(s))

    with pytest.raises(PermissionError):
        utils.atomic_write(target, "NEW")

    assert attempts == 8
    assert len(sleep_calls) == 7
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "OLD"
    assert list(tmp_path.glob("*.tmp")) == []


# ── Matrix E: Non-Permission OSError ──────────────────────────────────────
def test_atomic_write_non_permission_os_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("OLD", encoding="utf-8")

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("Disk full or invalid device")

    monkeypatch.setattr(os, "replace", mock_replace)

    with pytest.raises(OSError, match="Disk full"):
        utils.atomic_write(target, "NEW")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "OLD"
    assert list(tmp_path.glob("*.tmp")) == []


# ── Matrix F: Bounded retry count & parameter validation ──────────────────
def test_replace_with_retry_bounded_and_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "src.tmp"
    dst = tmp_path / "dst.txt"
    src.write_text("SRC", encoding="utf-8")

    attempts = 0
    sleep_calls: list[float] = []

    def mock_replace(s: str | Path, d: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda s: sleep_calls.append(s))

    with pytest.raises(PermissionError):
        replace_with_retry(src, dst, attempts=5)

    assert attempts == 5
    assert len(sleep_calls) == 4


def test_replace_with_retry_attempts_validation(tmp_path: Path) -> None:
    src = tmp_path / "src.tmp"
    dst = tmp_path / "dst.txt"

    with pytest.raises(ValueError, match="attempts must be >= 1"):
        replace_with_retry(src, dst, attempts=0)

    with pytest.raises(ValueError, match="attempts must be >= 1"):
        replace_with_retry(src, dst, attempts=-1)


def test_replace_with_retry_single_attempt_no_sleep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "src.tmp"
    dst = tmp_path / "dst.txt"
    src.write_text("SRC", encoding="utf-8")

    attempts = 0
    sleep_calls: list[float] = []

    def mock_replace(s: str | Path, d: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda s: sleep_calls.append(s))

    with pytest.raises(PermissionError):
        replace_with_retry(src, dst, attempts=1)

    assert attempts == 1
    assert len(sleep_calls) == 0


# ── FilesystemBackend Retry & CAS Safety ────────────────────────────────────
def test_filesystem_backend_persistent_permission_error_preserves_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FilesystemBackend(tmp_path)
    backend.save("file.txt", b"OLD")

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda _s: None)

    with pytest.raises(PermissionError):
        backend.save("file.txt", b"NEW")

    assert backend.load("file.txt") == b"OLD"
    assert {p.name for p in tmp_path.iterdir()} == {"file.txt"}


def test_filesystem_backend_cas_persistent_failure_preserves_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FilesystemBackend(tmp_path)
    backend.save("file.txt", b"OLD")

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda _s: None)

    with pytest.raises(PermissionError):
        backend.compare_and_swap("file.txt", b"OLD", b"NEW")

    assert backend.load("file.txt") == b"OLD"
    assert {p.name for p in tmp_path.iterdir()} == {"file.txt"}


# ── CheckpointStore failure safety & temp cleanup ─────────────────────────
def test_checkpoint_save_failure_preserves_checkpoint_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = CheckpointManager(tmp_path)
    cp = Checkpoint("ch1", segments_completed=5, segments_total=10)
    manager.save(cp)

    initial_loaded = manager.load("ch1")
    assert initial_loaded is not None
    assert initial_loaded.segments_completed == 5

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda _s: None)

    cp_updated = Checkpoint("ch1", segments_completed=8, segments_total=10)
    manager.save(cp_updated)

    # Checkpoint was preserved as original 5
    loaded = manager.load("ch1")
    assert loaded is not None
    assert loaded.segments_completed == 5
    # Warning logged
    assert any("Failed to write checkpoint ch1" in record.message for record in caplog.records)
    # Directory contains only the committed checkpoint file
    assert {p.name for p in tmp_path.iterdir()} == {"ch1.json"}
