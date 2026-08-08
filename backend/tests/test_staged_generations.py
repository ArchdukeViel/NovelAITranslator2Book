"""Storage-stage generation tests (DEBT-GEN-01, Section 4 pre-activation)."""

from pathlib import Path

import pytest

from novelai.storage.generations import GenerationManifest, _parse_active_generation_id
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
    manifest = storage.create_generation_stage("novel-1", "gen-100", expected_chapters=1)
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
    storage.create_generation_stage("novel-1", "gen-200", expected_chapters=1)
    storage.record_staged_chapter("novel-1", "gen-200", "1", "v1", "hash1")
    _stage_active_snapshot(storage, "gen-200")

    activated = storage.activate_generation("novel-1", "gen-200", chapter_dispositions={"1": "fetched_new"})
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
    storage.create_generation_stage("novel-1", "gen-300", expected_chapters=1)
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
    storage.commit_generation("novel-1", "gen-300", chapter_dispositions={"1": "fetched_new"})
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
    storage.create_generation_stage("novel-1", "gen-empty", expected_chapters=1)
    storage.stage_generation_chapter_index("novel-1", "gen-empty", [{"id": "1"}])
    storage.stage_generation_chapter(
        "novel-1",
        "gen-empty",
        "1",
        {"id": "1", "raw": {"text": "x"}},
    )

    with pytest.raises(RuntimeError):
        storage.commit_generation("novel-1", "gen-empty", chapter_dispositions={"1": "fetched_new"})

    assert storage.get_active_generation("novel-1") is None


def test_recovery_activation_requires_consent_and_bypasses_validation(storage: StorageService):
    """Recovery-only activation is a separately named API with explicit
    reason/evidence; the normal commit path never skips validation."""
    storage.create_generation_stage("novel-1", "gen-recovery", expected_chapters=1)

    # The recovery API requires explicit operator consent.
    with pytest.raises(ValueError, match="reason"):
        storage.commit_generation_recovery("novel-1", "gen-recovery", reason="", evidence="")
    with pytest.raises(ValueError, match="evidence"):
        storage.commit_generation_recovery("novel-1", "gen-recovery", reason="manual", evidence="")

    manifest = storage.commit_generation_recovery(
        "novel-1",
        "gen-recovery",
        reason="operator inspected stage manually",
        evidence="stage incomplete by design; validated by operator",
    )
    assert manifest.status == "committed"
    assert manifest.activated_at is not None
    active = storage.get_active_generation("novel-1")
    assert active is not None
    assert active.generation_id == "gen-recovery"


def test_normal_commit_never_accepts_committed_manifest(storage: StorageService):
    """Section 4: only ``status == staging`` may pass the normal commit path;
    an already-committed manifest is rejected, never re-activated."""
    storage.create_generation_stage("novel-1", "gen-recommit", expected_chapters=1)
    storage.commit_generation_recovery(
        "novel-1",
        "gen-recommit",
        reason="setup",
        evidence="test fixture",
    )
    with pytest.raises(RuntimeError, match="manifest_status_staging"):
        storage.commit_generation("novel-1", "gen-recommit", chapter_dispositions={})


def test_atomic_write_survives_transient_windows_file_lock(monkeypatch, storage: StorageService):
    """Windows WinError-5 flake: a briefly held destination handle must not
    fail the atomic rename. The bounded retry recovers deterministically."""
    import os

    real_replace = os.replace
    calls = {"count": 0}

    def flaky_replace(src, dst):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr("os.replace", flaky_replace)
    storage.save_metadata("novel-win", {"title": "Windows", "source_novel_id": "novel-win"})

    meta = storage.load_metadata("novel-win")
    assert meta is not None
    assert meta["title"] == "Windows"
    # The transient lock was retried (at least two PermissionErrors absorbed
    # plus the successful replaces).
    assert calls["count"] >= 3


# ---------------------------------------------------------------------------
# S9 — Active generation ID parsing and pointer-corruption resilience
# ---------------------------------------------------------------------------


def test_parse_active_generation_id_handles_all_corrupt_and_valid_cases():
    """_parse_active_generation_id maps missing, empty, malformed bytes, non-dict
    JSON, non-string IDs, and whitespace-only IDs to None, and returns the valid
    trimmed ID string for valid pointer payloads."""
    assert _parse_active_generation_id(None) is None
    assert _parse_active_generation_id(b"") is None
    assert _parse_active_generation_id(b"invalid json {") is None
    assert _parse_active_generation_id(b"[1, 2, 3]") is None
    assert _parse_active_generation_id(b'"string_json"') is None
    assert _parse_active_generation_id(b'{"active_generation_id": ""}') is None
    assert _parse_active_generation_id(b'{"active_generation_id": "   "}') is None
    assert _parse_active_generation_id(b'{"active_generation_id": 12345}') is None
    assert _parse_active_generation_id(b'{"active_generation_id": null}') is None
    assert _parse_active_generation_id(b'{"active_generation_id": "gen-valid-123"}') == "gen-valid-123"


def test_resolve_active_generation_id_recovers_from_corrupt_pointer_file(storage: StorageService):
    """When active_generation.json on disk is corrupted or empty,
    resolve_active_generation_id returns None without crashing."""
    novel_id = "novel-corrupt-pointer"
    pointer_path = storage._generations_dir(novel_id) / "active_generation.json"
    pointer_path.parent.mkdir(parents=True, exist_ok=True)

    # Corrupt pointer file with invalid JSON
    pointer_path.write_bytes(b"CORRUPTED_BYTES_{{")
    assert storage.resolve_active_generation_id(novel_id) is None
    assert storage.get_active_generation(novel_id) is None

    # Empty pointer file
    pointer_path.write_bytes(b"")
    assert storage.resolve_active_generation_id(novel_id) is None
    assert storage.get_active_generation(novel_id) is None
