"""Tests for malformed artifact recovery (Task 8).

Functions tested:
  - _load_chapter_bundle: truncated JSON → None, empty file → None, array → None
  - load_chapter_state: truncated JSON → None, empty file → None
  - load_glossary: malformed JSON → [], empty file → []
  - _read_json_file: malformed JSON → {} + WARNING, empty/whitespace → {} + DEBUG
  - BackupManager._load_manifest: corrupted manifest → {}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from novelai.services.backup_manager import BackupManager
from novelai.storage.chapters import _load_chapter_bundle
from novelai.storage.glossary import load_glossary
from novelai.storage.jobs import load_chapter_state
from novelai.storage.runtime_contracts import _read_json_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeStorage:
    """Minimal StorageService-like object for testing storage functions."""

    def __init__(self, tmp_path: Path) -> None:
        self.base_dir = tmp_path
        self._novels_root = tmp_path / "novels"
        self._novels_root.mkdir(parents=True, exist_ok=True)

    def _novel_dir(self, novel_id: str) -> Path:
        d = self._novels_root / novel_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _chapter_path(self, novel_id: str, chapter_id: str) -> Path:
        return self._novel_dir(novel_id) / "chapters" / f"{chapter_id}.json"

    def _get_state_dir(self, novel_id: str) -> Path:
        d = self._novel_dir(novel_id) / "states"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _normalize_media_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def _load_legacy_raw_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        return None

    def _load_legacy_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        return None

    def _path_exists(self, path: Path) -> bool:
        return path.exists()

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")


def _make_storage(tmp_path):
    """Create a _FakeStorage for _read_json_file tests."""
    return _FakeStorage(tmp_path)


# ---------------------------------------------------------------------------
# _load_chapter_bundle
# ---------------------------------------------------------------------------

class TestLoadChapterBundle:
    """_load_chapter_bundle: truncated JSON → None, empty file → None, array → None."""

    def test_truncated_json_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch1"
        path = storage._chapter_path(novel_id, chapter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"id": "ch1", "title": "Truncated...', encoding="utf-8")
        result = _load_chapter_bundle(storage, novel_id, chapter_id)
        assert result is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch2"
        path = storage._chapter_path(novel_id, chapter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        result = _load_chapter_bundle(storage, novel_id, chapter_id)
        assert result is None

    def test_array_instead_of_dict_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch3"
        path = storage._chapter_path(novel_id, chapter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(["a", "b"]), encoding="utf-8")
        result = _load_chapter_bundle(storage, novel_id, chapter_id)
        assert result is None

    def test_valid_dict_returns_data(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch4"
        path = storage._chapter_path(novel_id, chapter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"id": "ch4", "title": "Good"}
        path.write_text(json.dumps(data), encoding="utf-8")
        result = _load_chapter_bundle(storage, novel_id, chapter_id)
        assert result is not None
        assert result["id"] == "ch4"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        result = _load_chapter_bundle(storage, "nonexistent", "ch1")
        assert result is None


# ---------------------------------------------------------------------------
# load_chapter_state
# ---------------------------------------------------------------------------

class TestLoadChapterState:
    """load_chapter_state: truncated JSON → None, empty file → None."""

    def test_truncated_json_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch1"
        state_dir = storage._get_state_dir(novel_id)
        path = state_dir / f"{chapter_id}.json"
        path.write_text('{"chapter_id": "ch1", "current_state": "scraped",', encoding="utf-8")
        result = load_chapter_state(storage, novel_id, chapter_id)
        assert result is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch2"
        state_dir = storage._get_state_dir(novel_id)
        path = state_dir / f"{chapter_id}.json"
        path.write_text("", encoding="utf-8")
        result = load_chapter_state(storage, novel_id, chapter_id)
        assert result is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        result = load_chapter_state(storage, "nonexistent", "ch1")
        assert result is None

    def test_valid_state_returns_data(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        chapter_id = "ch3"
        state_dir = storage._get_state_dir(novel_id)
        path = state_dir / f"{chapter_id}.json"
        data = {
            "chapter_id": chapter_id,
            "current_state": "scraped",
            "transitions": [],
            "last_updated": "2025-01-01T00:00:00",
            "error_count": 0,
            "retry_count": 0,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        result = load_chapter_state(storage, novel_id, chapter_id)
        assert result is not None
        assert result["chapter_id"] == chapter_id


# ---------------------------------------------------------------------------
# load_glossary
# ---------------------------------------------------------------------------

class TestLoadGlossary:
    """load_glossary: malformed JSON → [], empty file → []."""

    def test_malformed_json_returns_empty_list(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        path = storage._novel_dir(novel_id) / "glossary.json"
        path.write_text('{"entries": [{"source": "broken"', encoding="utf-8")
        result = load_glossary(storage, novel_id)
        assert result == []

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        path = storage._novel_dir(novel_id) / "glossary.json"
        path.write_text("", encoding="utf-8")
        result = load_glossary(storage, novel_id)
        assert result == []

    def test_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        result = load_glossary(storage, "nonexistent")
        assert result == []

    def test_valid_glossary_dict_format(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        path = storage._novel_dir(novel_id) / "glossary.json"
        data = {"entries": [{"source": "foo", "target": "bar"}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        result = load_glossary(storage, novel_id)
        assert result == [{"source": "foo", "target": "bar"}]

    def test_valid_glossary_list_format(self, tmp_path: Path) -> None:
        storage = _FakeStorage(tmp_path)
        novel_id = "test-novel"
        path = storage._novel_dir(novel_id) / "glossary.json"
        data = [{"source": "foo", "target": "bar"}]
        path.write_text(json.dumps(data), encoding="utf-8")
        result = load_glossary(storage, novel_id)
        assert result == [{"source": "foo", "target": "bar"}]


# ---------------------------------------------------------------------------
# _read_json_file
# ---------------------------------------------------------------------------

class TestReadJsonFile:
    """_read_json_file: malformed → {} + WARNING, empty → {} + DEBUG."""

    def test_malformed_json_returns_default_and_logs_warning(
        self, tmp_path: Path, caplog: Any
    ) -> None:
        path = tmp_path / "test.json"
        path.write_text("{broken", encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            result = _read_json_file(_make_storage(tmp_path), path, {})
        assert result == {}
        assert any("Corrupt JSON file" in msg for msg in caplog.messages)

    def test_empty_file_returns_default_and_logs_debug(
        self, tmp_path: Path, caplog: Any
    ) -> None:
        path = tmp_path / "test.json"
        path.write_text("", encoding="utf-8")
        with caplog.at_level(logging.DEBUG):
            result = _read_json_file(_make_storage(tmp_path), path, {})
        assert result == {}
        assert any("Empty/whitespace file" in msg for msg in caplog.messages)

    def test_whitespace_file_returns_default_and_logs_debug(
        self, tmp_path: Path, caplog: Any
    ) -> None:
        path = tmp_path / "test.json"
        path.write_text("   \n\n  ", encoding="utf-8")
        with caplog.at_level(logging.DEBUG):
            result = _read_json_file(_make_storage(tmp_path), path, {})
        assert result == {}
        assert any("Empty/whitespace file" in msg for msg in caplog.messages)

    def test_missing_file_returns_default(self, tmp_path: Path) -> None:
        result = _read_json_file(_make_storage(tmp_path), tmp_path / "nonexistent.json", {})
        assert result == {}

    def test_valid_json_returns_parsed(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        result = _read_json_file(_make_storage(tmp_path), path, {})
        assert result == {"key": "value"}

    def test_oserror_silent(self, tmp_path: Path) -> None:
        """OSError branch is silent — no log."""
        result = _read_json_file(_make_storage(tmp_path), tmp_path / "nonexistent_dir" / "file.json", {})
        assert result == {}


# ---------------------------------------------------------------------------
# BackupManager._load_manifest (corrupted manifest → {})
# ---------------------------------------------------------------------------

class TestBackupManagerLoadManifest:
    """BackupManager._load_manifest: corrupted manifest → {}."""

    def test_corrupted_manifest_returns_empty(self, tmp_path: Path) -> None:
        mgr = BackupManager(tmp_path)
        mgr._backup_manifest.parent.mkdir(parents=True, exist_ok=True)
        mgr._backup_manifest.write_text("{broken", encoding="utf-8")
        result = mgr._load_manifest()
        assert result == {}

    def test_empty_manifest_returns_empty(self, tmp_path: Path) -> None:
        mgr = BackupManager(tmp_path)
        mgr._backup_manifest.parent.mkdir(parents=True, exist_ok=True)
        mgr._backup_manifest.write_text("", encoding="utf-8")
        result = mgr._load_manifest()
        assert result == {}

    def test_missing_manifest_returns_empty(self, tmp_path: Path) -> None:
        mgr = BackupManager(tmp_path)
        result = mgr._load_manifest()
        assert result == {}

    def test_valid_manifest_returns_entries(self, tmp_path: Path) -> None:
        mgr = BackupManager(tmp_path)
        mgr._backup_manifest.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "b1": {
                "timestamp": "2025-01-01T00:00:00Z",
                "novel_id": "test-novel",
                "size_bytes": 100,
                "compressed": True,
                "files_count": 3,
                "description": None,
            }
        }
        mgr._backup_manifest.write_text(json.dumps(data), encoding="utf-8")
        result = mgr._load_manifest()
        assert "b1" in result
        assert result["b1"]["novel_id"] == "test-novel"
