from pathlib import Path

import pytest

from novelai.storage.generations import GenerationManifest
from novelai.storage.service import StorageService


@pytest.fixture
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path)


def test_generation_manifest_dataclass():
    m = GenerationManifest(generation_id="gen-1", novel_id="novel-1")
    assert m.generation_id == "gen-1"
    assert m.status == "staging"
    assert m.activated_at is None
    d = m.to_dict()
    m2 = GenerationManifest.from_dict(d)
    assert m2.generation_id == "gen-1"


def test_create_and_record_staged_generation(storage: StorageService):
    manifest = storage.create_generation_stage("novel-1", "gen-100")
    assert manifest.status == "staging"

    updated = storage.record_staged_chapter(
        "novel-1",
        "gen-100",
        chapter_id="1",
        version_id="v1",
        source_hash="hash123",
    )
    assert "1" in updated.chapter_ids
    assert updated.translation_versions["1"] == "v1"
    assert updated.source_hashes["1"] == "hash123"
    assert updated.status == "staging"  # Still staging before activation


def test_activate_generation_atomic_write(storage: StorageService):
    storage.create_generation_stage("novel-1", "gen-200")
    storage.record_staged_chapter("novel-1", "gen-200", "1", "v1", "hash1")

    activated = storage.activate_generation("novel-1", "gen-200")
    assert activated.status == "active"
    assert activated.activated_at is not None

    active_current = storage.get_active_generation("novel-1")
    assert active_current is not None
    assert active_current.generation_id == "gen-200"
    assert active_current.status == "active"
