"""Regression coverage for immutable generation carry-forward and rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from novelai.storage.backends.filesystem import FilesystemBackend
from novelai.storage.service import StorageService


class FailingCopyBackend(FilesystemBackend):
    """Filesystem backend that fails on one deterministic copy call."""

    def __init__(self, base_dir: Path) -> None:
        super().__init__(base_dir)
        self.copy_calls = 0
        self.fail_on_call: int | None = None

    def copy_object(self, source: str | Path, destination: str | Path) -> None:
        self.copy_calls += 1
        if self.fail_on_call == self.copy_calls:
            raise OSError("injected immutable-copy failure")
        super().copy_object(source, destination)


def _stage_generation(storage: StorageService, generation_id: str) -> None:
    novel_id = "novel-copy-reuse"
    chapter_ids = ["1", "2"]
    storage.create_generation_stage(
        novel_id,
        generation_id,
        source_key="test_source",
        source_work_id=novel_id,
        mode="update",
        expected_chapters=len(chapter_ids),
    )
    storage.stage_generation_metadata(
        novel_id,
        generation_id,
        {"title": "Copy Reuse", "source_novel_id": novel_id},
    )
    storage.stage_generation_source_state(
        novel_id,
        generation_id,
        {"ordered_episode_ids": chapter_ids},
    )
    storage.stage_generation_chapter_index(
        novel_id,
        generation_id,
        [{"id": chapter_id, "chapter_id": chapter_id, "title": f"Chapter {chapter_id}"} for chapter_id in chapter_ids],
    )


def _stage_and_commit_initial_generation(storage: StorageService) -> None:
    novel_id = "novel-copy-reuse"
    _stage_generation(storage, "gen-A")
    for chapter_id in ("1", "2"):
        storage.stage_generation_chapter(
            novel_id,
            "gen-A",
            chapter_id,
            {"id": chapter_id, "raw": {"text": f"raw {chapter_id}", "images": []}},
        )
    storage.commit_generation(
        novel_id,
        "gen-A",
        chapter_dispositions={"1": "fetched_new", "2": "fetched_new"},
    )


def test_failed_copy_keeps_active_generation_and_retry_succeeds(tmp_path: Path) -> None:
    """A copy failure rolls back only the stage and leaves the active pointer intact."""
    backend = FailingCopyBackend(tmp_path)
    storage = StorageService(tmp_path, backend=backend)
    novel_id = "novel-copy-reuse"
    _stage_and_commit_initial_generation(storage)

    _stage_generation(storage, "gen-B")
    backend.fail_on_call = backend.copy_calls + 2
    with pytest.raises(OSError, match="injected immutable-copy failure"):
        storage.seed_generation_from_active(novel_id, "gen-B", ["1", "2"])

    storage.rollback_generation(novel_id, "gen-B", reason="copy failure regression")
    assert storage.resolve_active_generation_id(novel_id) == "gen-A"
    assert not (tmp_path / "novels" / novel_id / "generations" / "gen-B").exists()

    _stage_generation(storage, "gen-B")
    backend.fail_on_call = None
    copied_chapters, copied_assets = storage.seed_generation_from_active(novel_id, "gen-B", ["1", "2"])
    assert (copied_chapters, copied_assets) == (2, 0)
    storage.commit_generation(
        novel_id,
        "gen-B",
        chapter_dispositions={"1": "carried_unselected", "2": "carried_unselected"},
        starting_active_generation_id="gen-A",
    )

    assert storage.resolve_active_generation_id(novel_id) == "gen-B"
    chapter_one = storage.load_chapter(novel_id, "1")
    chapter_two = storage.load_chapter(novel_id, "2")
    assert chapter_one is not None
    assert chapter_two is not None
    assert chapter_one["text"] == "raw 1"
    assert chapter_two["text"] == "raw 2"
    assert backend.copy_calls >= 4
