from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture()
def storage() -> Generator[StorageService]:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"atomic_recovery_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    store = StorageService(data_dir)
    yield store
    shutil.rmtree(data_dir, ignore_errors=True)


# ── Atomic write helper ─────────────────────────────────────────────────────


def test_atomic_write_replaces_target_with_complete_json(storage: StorageService) -> None:
    target = storage.base_dir / "novels" / "n1" / "metadata.json"
    storage._write_text_atomic(target, json.dumps({"title": "T"}))

    assert json.loads(target.read_text(encoding="utf-8")) == {"title": "T"}
    # No leftover temp files in the target directory.
    assert list(target.parent.glob(".*.tmp")) == []


def test_atomic_write_failure_before_replace_preserves_existing_file(
    storage: StorageService, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = storage.base_dir / "novels" / "n1" / "metadata.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"title": "old"}), encoding="utf-8")

    def _boom(*_args: object, **_kw: object) -> object:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError):
        storage._write_text_atomic(target, json.dumps({"title": "new"}))

    assert json.loads(target.read_text(encoding="utf-8")) == {"title": "old"}


def test_atomic_write_uses_unique_temp_names(
    storage: StorageService, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []
    original_replace = os.replace

    def _spy(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
        if Path(dst) == target:
            seen.append(Path(src))
        return original_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", _spy)

    target = storage.base_dir / "novels" / "n1" / "metadata.json"
    storage._write_text_atomic(target, "a")
    storage._write_text_atomic(target, "b")

    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert all(p.name.startswith(".") and p.name.endswith(".tmp") for p in seen)


# ── Metadata backup compatibility ───────────────────────────────────────────


def test_metadata_save_preserves_existing_backup_behavior(storage: StorageService) -> None:
    storage.save_metadata("bk-novel", {"title": "V1"})
    storage.save_metadata("bk-novel", {"title": "V2"})

    backup_dir = storage._novel_dir("bk-novel") / "metadata_backups"
    assert backup_dir.is_dir()
    assert len(list(backup_dir.glob("*.json"))) >= 1

    loaded = storage.load_metadata("bk-novel")
    assert loaded is not None
    assert loaded["title"] == "V2"


# ── Metadata recovery from backup ───────────────────────────────────────────


def test_load_metadata_recovers_from_latest_valid_backup(
    storage: StorageService, caplog: pytest.LogCaptureFixture
) -> None:
    storage.save_metadata("rec-novel", {"title": "Good"})
    storage.save_metadata("rec-novel", {"title": "Newer"})

    (storage._novel_dir("rec-novel") / "metadata.json").write_text("{not valid json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        loaded = storage.load_metadata("rec-novel")

    assert loaded is not None
    assert loaded["title"] == "Good"
    assert any("Recovered metadata" in record.message for record in caplog.records)
    # Recovery logging must not leak full payload text.
    assert all("Good" not in record.message for record in caplog.records)


def test_load_metadata_skips_invalid_backup_and_uses_older_valid_backup(storage: StorageService) -> None:
    novel_dir = storage.novels_dir / "skip-novel"
    novel_dir.mkdir(parents=True, exist_ok=True)
    (novel_dir / "metadata.json").write_text("{bad", encoding="utf-8")
    backup_dir = novel_dir / "metadata_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Newest backup is corrupt; older backup is valid.
    (backup_dir / "2024-03-02T00_00_00Z.json").write_text("{corrupt", encoding="utf-8")
    (backup_dir / "2024-03-01T00_00_00Z.json").write_text(
        json.dumps({"schema_version": storage.SCHEMA_VERSION, "title": "Older"}),
        encoding="utf-8",
    )

    loaded = storage.load_metadata("skip-novel")
    assert loaded is not None
    assert loaded["title"] == "Older"


def test_load_metadata_corrupt_without_backup_preserves_existing_failure_contract(
    storage: StorageService,
) -> None:
    novel_dir = storage.novels_dir / "bad-novel"
    novel_dir.mkdir(parents=True, exist_ok=True)
    (novel_dir / "metadata.json").write_text("{bad", encoding="utf-8")
    assert storage.load_metadata("bad-novel") is None


def test_list_metadata_continues_after_corrupted_novel_metadata(storage: StorageService) -> None:
    storage.save_metadata("ok-novel", {"title": "OK"})
    bad_dir = storage.novels_dir / "bad-novel"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "metadata.json").write_text("{bad", encoding="utf-8")

    result = storage.list_novels()
    assert "ok-novel" in result
    assert "bad-novel" in result


def test_temp_files_are_ignored_by_metadata_listing(storage: StorageService) -> None:
    storage.save_metadata("tmp-novel", {"title": "T"})
    novel_dir = storage._novel_dir("tmp-novel")
    (novel_dir / ".metadata.json.12345.abc.tmp").write_text("garbage", encoding="utf-8")

    history = storage.list_metadata_history("tmp-novel")
    assert any(entry["is_current"] for entry in history)
    assert all(not entry["snapshot_id"].endswith(".tmp") for entry in history)


# ── Bundle coverage ─────────────────────────────────────────────────────────


def test_chapter_bundle_write_uses_atomic_helper(
    storage: StorageService, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    original = storage._write_text_atomic

    def _spy(path: Path, content: str, **kwargs: Any) -> None:
        calls.append(path)
        original(path, content, **kwargs)

    monkeypatch.setattr(storage, "_write_text_atomic", _spy)
    storage.save_chapter("ch-novel", "c1", "Text")

    assert any(path.name == "c1.json" for path in calls)


def test_translation_bundle_write_uses_atomic_helper(
    storage: StorageService, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    original = storage._write_text_atomic

    def _spy(path: Path, content: str, **kwargs: Any) -> None:
        calls.append(path)
        original(path, content, **kwargs)

    monkeypatch.setattr(storage, "_write_text_atomic", _spy)
    storage.save_translated_chapter("tr-novel", "c1", "Translated", provider="gemini", model="m")

    assert any(path.name == "c1.json" for path in calls)
