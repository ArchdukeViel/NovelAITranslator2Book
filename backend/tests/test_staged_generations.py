"""Storage-stage generation tests (DEBT-GEN-01, Section 4 pre-activation)."""

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


def _stage_active_snapshot(storage: StorageService, generation_id: str) -> None:
    """Stage metadata+chapter_index+source_state so Section 4 validation passes."""
    storage.stage_generation_metadata(
        "novel-1",
        generation_id,
        {"title": "T", "source_novel_id": "novel-1"},
    )
    storage.stage_generation_chapter_index(
        "novel-1",
        generation_id,
        [{"id": "1", "chapter_id": "1", "title": "T", "url": "u"}],
    )
    storage.stage_generation_source_state("novel-1", generation_id, {"chapters": []})
    storage.stage_generation_chapter(
        "novel-1",
        generation_id,
        "1",
        {"id": "1", "raw": {"text": "x"}},
    )


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
    _stage_active_snapshot(storage, "gen-200")

    activated = storage.activate_generation("novel-1", "gen-200")
    assert activated.status == "committed"
    assert activated.activated_at is not None

    active_current = storage.get_active_generation("novel-1")
    assert active_current is not None
    assert active_current.generation_id == "gen-200"
    assert active_current.status == "committed"


def test_stage_snapshot_files_are_files_not_directories(storage: StorageService):
    """Regression: staged snapshot entries must be regular files.

    Writing through the stage-dir helper used to create a *directory* at the
    file path, which made the subsequent atomic rename fail on Windows
    (WinError 5 Access denied).
    """
    storage.create_generation_stage("novel-1", "gen-300")
    g_dir = storage.base_dir / "novels" / "novel-1" / "generations" / "gen-300"

    # Each snapshot stage can be written repeatedly and must produce a file.
    for _ in range(2):
        storage.stage_generation_source_state("novel-1", "gen-300", {"chapters": []})
        storage.stage_generation_chapter_index("novel-1", "gen-300", [{"id": "1"}])
        storage.stage_generation_metadata(
            "novel-1",
            "gen-300",
            {"title": "T", "source_novel_id": "novel-1"},
        )

    assert (g_dir / "source_state.json").is_file()
    assert (g_dir / "chapter_index.json").is_file()
    assert (g_dir / "metadata.json").is_file()

    # Chapter and image staging must also land as files.
    storage.stage_generation_chapter("novel-1", "gen-300", "1", {"id": "1", "raw": {"text": "x"}})
    assert (g_dir / "chapters" / "0001.json").is_file()
    stored = storage.stage_generation_image(
        "novel-1",
        "gen-300",
        "1",
        image_index=0,
        content=b"\x89PNG",
        source_url="https://example.test/img.png",
    )
    # The logical local_path is generation-agnostic.  After activation the
    # reader API can resolve it through the active generation layout.
    storage.commit_generation("novel-1", "gen-300")
    resolved = storage.resolve_asset_path("novel-1", stored["local_path"])
    assert resolved is not None and resolved.is_file()

    manifest = storage.load_generation_manifest("novel-1", "gen-300")
    assert manifest is not None
    assert manifest.source_state_hash
    assert manifest.chapter_index_hash
    assert manifest.metadata_hash
    assert manifest.chapter_ids == ["1"]


def test_pre_activation_validation_aborts_when_stage_incomplete(storage: StorageService):
    """Sections 4 + 5: a stage missing ``metadata.json`` must not become active.

    ``commit_generation`` runs the deterministic validation function and
    raises before touching the active pointer when membership, identity, or
    hash invariants fail. The previous active pointer remains untouched so
    readers continue to see the legacy layout / previous generation.
    """
    storage.create_generation_stage("novel-1", "gen-empty")
    storage.stage_generation_chapter_index("novel-1", "gen-empty", [{"id": "1"}])
    storage.stage_generation_chapter(
        "novel-1",
        "gen-empty",
        "1",
        {"id": "1", "raw": {"text": "x"}},
    )

    with pytest.raises(RuntimeError):
        storage.commit_generation("novel-1", "gen-empty")

    assert storage.get_active_generation("novel-1") is None


def test_skip_validation_bypasses_validation_for_recovery_paths(storage: StorageService):
    """Operators can opt out of validation via ``skip_validation=True``.

    Mirrors the rollback recovery path: the operator already inspected the
    stage manually and accepts the partial / legacy shape, so the strict
    default must yield to explicit consent.
    """
    storage.create_generation_stage("novel-1", "gen-recovery")
    manifest = storage.commit_generation(
        "novel-1",
        "gen-recovery",
        skip_validation=True,
    )
    assert manifest.status == "committed"
    assert manifest.activated_at is not None
    active = storage.get_active_generation("novel-1")
    assert active is not None
    assert active.generation_id == "gen-recovery"
