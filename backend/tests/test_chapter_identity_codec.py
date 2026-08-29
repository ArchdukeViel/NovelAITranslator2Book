"""Physical chapter-id codec tests (PR-41 Blocker B).

Logical chapter IDs (e.g. Kakuyomu's ``kakuyomu:<episode-id>``) contain
characters that are invalid in Windows file names. ``encode_physical_stem`` /
``decode_physical_stem`` plus the storage-layer call sites must guarantee
reversible, filesystem-safe names while preserving legacy numeric naming.
"""

from __future__ import annotations

from pathlib import Path

from novelai.core.chapter_state import ChapterState
from novelai.core.security import decode_physical_stem, encode_physical_stem
from novelai.storage.service import StorageService

KAKUYOMU_ID = "kakuyomu:16818093075570329555"


def test_encode_decode_round_trip() -> None:
    for logical in (
        "1",
        "abc",
        KAKUYOMU_ID,
        "chapter_2.5",
        "novel:作品:123",
        "100%",
        "a*b?<x>|y",
        "名前:123",
        "a/b",
        "a\\b",
    ):
        encoded = encode_physical_stem(logical)
        assert "/" not in encoded
        assert "\\" not in encoded
        assert ":" not in encoded
        assert "\x00" not in encoded
        assert decode_physical_stem(encoded) == logical


def test_encode_numeric_passthrough() -> None:
    assert encode_physical_stem("123") == "123"


def test_decode_legacy_names_unchanged() -> None:
    # Zero-padded numeric stems are handled by the numeric branch in callers.
    assert decode_physical_stem("0001") == "0001"
    # Plain safe names pass through.
    assert decode_physical_stem("abc") == "abc"
    # POSIX-era raw names containing reserved characters are not decodable
    # (re-encoding does not reproduce them) and must resolve to themselves.
    assert decode_physical_stem("kakuyomu:123") == "kakuyomu:123"


def test_storage_chapter_round_trip(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    novel_id = "16818093075570329555"  # Kakuyomu work id (numeric)
    path = storage.save_chapter(
        novel_id,
        KAKUYOMU_ID,
        "hello",
        source_key="kakuyomu",
        source_url="https://kakuyomu.jp/works/w/episodes/e",
    )
    assert path.as_posix() == f"r2:chapter/{novel_id}/{KAKUYOMU_ID}"
    chapter = storage.load_chapter(novel_id, KAKUYOMU_ID)
    assert chapter is not None
    assert chapter["id"] == KAKUYOMU_ID
    assert chapter["text"] == "hello"
    assert storage.list_stored_chapters(novel_id) == [KAKUYOMU_ID]


def test_storage_numeric_zero_pad_preserved(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    path = storage.save_chapter("n", "7", "text")
    assert path.as_posix() == "r2:chapter/n/7"
    assert storage.list_stored_chapters("n") == ["7"]
    chapter = storage.load_chapter("n", "7")
    assert chapter is not None
    assert chapter["text"] == "text"


def test_chapter_state_with_kakuyomu_id(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    storage.update_chapter_state("n", KAKUYOMU_ID, ChapterState.SCRAPED)
    state = storage.load_chapter_state("n", KAKUYOMU_ID)
    assert state is not None
    assert state["chapter_id"] == KAKUYOMU_ID
    assert state["current_state"] == ChapterState.SCRAPED
    assert storage.get_chapters_by_state("n", ChapterState.SCRAPED) == [KAKUYOMU_ID]


def test_checkpoint_with_kakuyomu_id(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    storage.save_chapter("n", KAKUYOMU_ID, "raw text")
    storage.save_translated_chapter("n", KAKUYOMU_ID, "translated text")
    storage.update_chapter_state("n", KAKUYOMU_ID, ChapterState.TRANSLATED)

    checkpoint_path = storage.create_checkpoint("n", KAKUYOMU_ID, "manual")
    assert "kakuyomu%3A16818093075570329555__manual.json" in checkpoint_path.name

    infos = storage.list_checkpoints("n", KAKUYOMU_ID)
    assert len(infos) == 1
    assert infos[0]["checkpoint_name"] == "manual"

    storage.save_translated_chapter("n", KAKUYOMU_ID, "changed text")
    assert storage.restore_from_checkpoint("n", KAKUYOMU_ID, "manual") is True
    translated = storage.load_translated_chapter("n", KAKUYOMU_ID)
    assert translated is not None
    assert translated["text"] == "translated text"


def test_chapter_images_with_kakuyomu_id(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    storage.save_metadata("n", {"title": "Kakuyomu novel", "chapters": []})
    asset = storage.save_chapter_image_asset(
        "n",
        KAKUYOMU_ID,
        image_index=0,
        content=b"\x89PNG",
        content_type="image/png",
    )
    assert asset["storage_key"].startswith("novels/1/assets/")
    assert storage.r2_backend.head(asset["storage_key"]).logical_sha256 == asset["sha256"]
    assert "local_path" not in asset

    storage.save_chapter("n", KAKUYOMU_ID, "text with image", images=[asset])
    chapter = storage.load_chapter("n", KAKUYOMU_ID)
    assert chapter is not None
    assert chapter["images"][0]["storage_key"] == asset["storage_key"]
