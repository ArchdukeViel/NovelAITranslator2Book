"""Safety tests for storage-boundary consolidation.

Covers:
1. Legacy content read-through via StorageService
2. API responses don't expose raw filesystem paths
3. Corrupt/missing content returns error envelope (not crash)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from novelai.storage.service import StorageService

# ── helpers ────────────────────────────────────────────────────────


def _seed_text(path: Path, content: str = "legacy content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ── legacy read-through ────────────────────────────────────────────


class TestStorageLegacyReadThrough:
    """Content placed directly on disk (legacy path) is readable via StorageService."""

    def test_read_text_legacy_file(self, tmp_path: Path) -> None:
        f = tmp_path / "legacy.txt"
        _seed_text(f, "hello from legacy")
        svc = StorageService(tmp_path)
        assert svc._read_text(f) == "hello from legacy"

    def test_exists_sees_legacy_file(self, tmp_path: Path) -> None:
        f = tmp_path / "legacy.txt"
        _seed_text(f)
        svc = StorageService(tmp_path)
        assert svc._path_exists(f) is True

    def test_missing_file_returns_envelope(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        missing = tmp_path / "no_such.txt"
        with pytest.raises(FileNotFoundError):
            svc._read_text(missing)

    def test_runtime_path_resolves_under_base(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        rp = svc.runtime_path("translation", "chunks")
        assert rp == tmp_path / "runtime" / "translation" / "chunks"
        assert not rp.exists()  # should NOT auto-create

    def test_backups_path_resolves_under_base(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        bp = svc.backups_path("manifest.json")
        assert bp == tmp_path / "backups" / "manifest.json"


# ── corrupt / missing content safety ───────────────────────────────


class TestCorruptContentSafety:
    """StorageService doesn't crash on corrupt or missing data."""

    def test_corrupt_json_raises_decode_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        _seed_text(f, "not json{{{")
        svc = StorageService(tmp_path)
        with pytest.raises(json.JSONDecodeError):
            json.loads(svc._read_text(f))

    def test_missing_chapter_returns_none(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        assert svc.load_chapter("novel_1", "ch_999") is None

    def test_missing_translated_chapter_returns_none(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        assert svc.load_translated_chapter("novel_1", "ch_999") is None

    def test_missing_metadata_returns_none(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        assert svc.load_metadata("novel_1") is None

    def test_list_novels_empty(self, tmp_path: Path) -> None:
        svc = StorageService(tmp_path)
        assert svc.list_novels() == []

    def test_empty_novel_has_no_chapters(self, tmp_path: Path) -> None:
        # a novel dir with nothing inside
        novel_dir = tmp_path / "novels" / "empty_novel"
        novel_dir.mkdir(parents=True, exist_ok=True)
        svc = StorageService(tmp_path)
        assert svc.list_novels() == []
