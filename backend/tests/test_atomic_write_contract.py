from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

import novelai.utils as utils
from novelai.services.pipeline.checkpoint import Checkpoint, CheckpointManager
from novelai.storage.backends.filesystem import FilesystemBackend
from novelai.utils.filesystem import replace_with_retry


# ── Matrix A: First write ──────────────────────────────────────────────────
def test_atomic_write_first_write() -> None:
    dirpath = Path(tempfile.mkdtemp())
    target = dirpath / "new_target.txt"

    utils.atomic_write(target, "NEW")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "NEW"
    assert list(dirpath.glob("*.tmp")) == []


# ── Matrix B: Normal replacement ──────────────────────────────────────────
def test_atomic_write_normal_replacement() -> None:
    dirpath = Path(tempfile.mkdtemp())
    target = dirpath / "target.txt"
    target.write_text("OLD", encoding="utf-8")

    utils.atomic_write(target, "NEW")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "NEW"
    assert list(dirpath.glob("*.tmp")) == []


# ── Matrix C: Transient PermissionError ───────────────────────────────────
def test_atomic_write_transient_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    dirpath = Path(tempfile.mkdtemp())
    target = dirpath / "target.txt"
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
    assert list(dirpath.glob("*.tmp")) == []


# ── Matrix D: Persistent PermissionError (Principal Test) ──────────────────
def test_atomic_write_persistent_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    dirpath = Path(tempfile.mkdtemp())
    target = dirpath / "target.txt"
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
    assert list(dirpath.glob("*.tmp")) == []


# ── Matrix E: Non-Permission OSError ──────────────────────────────────────
def test_atomic_write_non_permission_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    dirpath = Path(tempfile.mkdtemp())
    target = dirpath / "target.txt"
    target.write_text("OLD", encoding="utf-8")

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("Disk full or invalid device")

    monkeypatch.setattr(os, "replace", mock_replace)

    with pytest.raises(OSError, match="Disk full"):
        utils.atomic_write(target, "NEW")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "OLD"
    assert list(dirpath.glob("*.tmp")) == []


# ── Matrix F: Bounded retry count & no real sleeps ─────────────────────────
def test_replace_with_retry_bounded_and_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    src = Path(tempfile.mkdtemp()) / "src.tmp"
    dst = Path(tempfile.mkdtemp()) / "dst.txt"
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


# ── FilesystemBackend Retry & CAS Safety ────────────────────────────────────
def test_filesystem_backend_persistent_permission_error_preserves_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dirpath = Path(tempfile.mkdtemp())
    backend = FilesystemBackend(dirpath)
    backend.save("file.txt", b"OLD")

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda _s: None)

    with pytest.raises(PermissionError):
        backend.save("file.txt", b"NEW")

    assert backend.load("file.txt") == b"OLD"
    assert list(dirpath.glob("*.tmp")) == []


def test_filesystem_backend_cas_persistent_failure_preserves_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dirpath = Path(tempfile.mkdtemp())
    backend = FilesystemBackend(dirpath)
    backend.save("file.txt", b"OLD")

    def mock_replace(src: str | Path, dst: str | Path) -> None:
        raise PermissionError("Locked")

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr("novelai.utils.filesystem.time.sleep", lambda _s: None)

    with pytest.raises(PermissionError):
        backend.compare_and_swap("file.txt", b"OLD", b"NEW")

    assert backend.load("file.txt") == b"OLD"
    assert list(dirpath.glob("*.tmp")) == []


# ── CheckpointStore failure safety & temp cleanup ─────────────────────────
def test_checkpoint_save_failure_preserves_checkpoint_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    dirpath = Path(tempfile.mkdtemp())
    manager = CheckpointManager(dirpath)
    cp = Checkpoint("ch1", segments_completed=5, segments_total=10)
    manager.save(cp)

    assert manager.load("ch1") is not None
    assert manager.load("ch1").segments_completed == 5  # type: ignore[union-attr]

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
    # Temp files cleaned up
    assert list(dirpath.glob("*.tmp")) == []
