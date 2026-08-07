"""PR-41 Section 6/7 production-path tests.

Two production contracts asserted by exercising the orchestrator +
storage paths directly:

1. Raw generation byte-immutability across translation: the activated
   raw generation's chapters/* and assets/images/* tree must be
   byte-identical before and after a translation pass.
2. Carried-forward image assets survive prior-generation deletion:
   the new generation's bundle can resolve an image that was copied
   from the prior generation without falling back to the legacy root.
3. A missing ``local_path`` inside an otherwise complete stage is
   rejected by the pre-activation validator (no silent fallback to
   the legacy root).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from novelai.storage.service import StorageService


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_files(directory: Path) -> dict[Path, str]:
    out: dict[Path, str] = {}
    if not directory.exists():
        return out
    for path in directory.rglob("*"):
        if path.is_file():
            out[path] = _hash_file(path)
    return out


def _write_minimal_generation(storage: StorageService, novel_id: str, generation_id: str) -> str | None:
    """Stage + commit a minimal raw generation with a chapter bundle and an image.
    Returns the asset's logical local_path so callers can resolve it."""
    storage.create_generation_stage(
        novel_id,
        generation_id,
        source_key="kakuyomu",
        source_work_id=novel_id,
        mode="full",
        expected_chapters=1,
    )
    storage.stage_generation_metadata(
        novel_id,
        generation_id,
        {"title": "Stable Identity", "source_novel_id": novel_id},
    )
    storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
    storage.stage_generation_chapter_index(
        novel_id,
        generation_id,
        [{"id": "1", "chapter_id": "1", "title": "Hello", "url": "u"}],
    )
    # Image is staged via the canonical API so the chapter bundle records it.
    stored_image = storage.stage_generation_image(
        novel_id,
        generation_id,
        "1",
        image_index=0,
        content=b"\x89PNG-binary-content",
        source_url="https://example.test/img.png",
        content_type="image/png",
    )
    storage.stage_generation_chapter(
        novel_id,
        generation_id,
        "1",
        {
            "id": "1",
            "raw": {
                "text": "Hello",
                "images": [
                    {
                        "local_path": stored_image["local_path"],
                        "content_type": "image/png",
                        "size_bytes": stored_image["size_bytes"],
                        "sha256": stored_image["sha256"],
                    }
                ],
            },
        },
    )
    storage.commit_generation(novel_id, generation_id)
    return stored_image["local_path"]


def _chapter_image_path_for(storage: StorageService, novel_id: str, generation_id: str, local_path: str) -> Path:
    """Resolve a stage-local asset path to a file Path inside the novel library."""
    return storage.base_dir / "novels" / novel_id / "generations" / generation_id / local_path


def test_active_raw_generation_byte_immutability_under_translation(tmp_path: Path) -> None:
    """Section 6 evidence: the committed raw generation is byte-identical after translation."""
    storage = StorageService(tmp_path)
    novel_id = "novel-immut"
    local_path = _write_minimal_generation(storage, novel_id, "gen-A")

    active = storage.get_active_generation(novel_id)
    assert active is not None
    assert active.generation_id == "gen-A"

    gen_dir = storage.base_dir / "novels" / novel_id / "generations" / "gen-A"
    # Confirm the staged image is on disk so we exercise the asset
    # validation path during the before/after comparison.
    if local_path:
        assert _chapter_image_path_for(storage, novel_id, "gen-A", local_path).is_file()
    before_hashes = _walk_files(gen_dir)

    # Production translation write path: the overlay contract guarantees
    # the raw ``chapters/<id>.json`` bundle is never modified.
    storage.save_translated_chapter(
        novel_id,
        "1",
        "Bonjour",
        provider_key="mock",
        provider_model="mock-model",
        confidence_score=0.9,
        glossary_revision=0,
    )

    after_hashes = _walk_files(gen_dir)

    # Section 6: every file in the raw generation is byte-identical.
    assert before_hashes.keys() == after_hashes.keys(), (
        "raw generation file set changed during translation: "
        f"+added={set(after_hashes) - set(before_hashes)}, "
        f"-removed={set(before_hashes) - set(after_hashes)}"
    )
    for path, expected in before_hashes.items():
        assert after_hashes[path] == expected, f"raw generation file mutated during translation: {path}"

    # The translation is still readable to readers.
    translated = storage.load_translated_chapter(novel_id, "1")
    assert translated is not None
    assert translated["text"] == "Bonjour"

    # Carry forward: an additional translation pass must keep the raw
    # generation immutable too.
    storage.save_translated_chapter(
        novel_id,
        "1",
        "Bonjour v2",
        provider_key="mock",
        provider_model="mock-model",
        confidence_score=0.95,
        glossary_revision=0,
    )
    final_hashes = _walk_files(gen_dir)
    assert final_hashes == before_hashes


def test_carried_image_survives_prior_generation_deletion(tmp_path: Path) -> None:
    """Section 7 evidence: deletion of generation A leaves B able to resolve its image."""
    storage = StorageService(tmp_path)
    novel_id = "novel-image"

    asset_local_path = _write_minimal_generation(storage, novel_id, "gen-A")
    assert isinstance(asset_local_path, str) and asset_local_path.strip()
    asset_a = storage.base_dir / "novels" / novel_id / "generations" / "gen-A" / asset_local_path
    assert asset_a.is_file()

    # --- Generation B: carries the chapter forward from A ---
    storage.create_generation_stage(
        novel_id,
        "gen-B",
        source_key="kakuyomu",
        source_work_id=novel_id,
        mode="full",
        expected_chapters=1,
    )
    storage.stage_generation_metadata(novel_id, "gen-B", {"title": "Stable Identity", "source_novel_id": novel_id})
    storage.stage_generation_chapter_index(
        novel_id, "gen-B", [{"id": "1", "chapter_id": "1", "title": "Hello", "url": "u"}]
    )
    storage.stage_generation_source_state(novel_id, "gen-B", {"chapters": []})
    storage.seed_generation_from_active(novel_id, "gen-B", ["1"])
    storage.commit_generation(
        novel_id, "gen-B", starting_active_generation_id=storage.resolve_active_generation_id(novel_id)
    )

    gen_b_dir = storage.base_dir / "novels" / novel_id / "generations" / "gen-B"

    # The asset must be inside gen-B after seeding, not just in gen-A.
    asset_b = gen_b_dir / asset_local_path
    assert asset_b.is_file(), "seed_generation_from_active must copy image assets"

    # Delete generation A outright and confirm the carry-forward path
    # does not silently fall back to the legacy novel root.
    gen_a_dir = storage.base_dir / "novels" / novel_id / "generations" / "gen-A"
    if gen_a_dir.exists():
        shutil.rmtree(gen_a_dir)

    # resolve_asset_path must locate the image inside gen-B only.
    resolved = storage.resolve_asset_path(novel_id, asset_local_path)
    assert resolved is not None
    assert resolved.is_file()
    assert resolved.resolve() == asset_b.resolve()


def test_missing_active_generation_image_fails_validation(tmp_path: Path) -> None:
    """A missing image inside an otherwise complete stage is rejected."""
    from novelai.storage.generations import validate_generation_activation

    storage = StorageService(tmp_path)
    novel_id = "novel-image-missing"

    storage.create_generation_stage(
        novel_id,
        "gen-miss",
        source_key="kakuyomu",
        source_work_id=novel_id,
        mode="full",
        expected_chapters=1,
    )
    storage.stage_generation_metadata(novel_id, "gen-miss", {"title": "T", "source_novel_id": novel_id})
    storage.stage_generation_source_state(novel_id, "gen-miss", {"chapters": []})
    storage.stage_generation_chapter_index(
        novel_id, "gen-miss", [{"id": "1", "chapter_id": "1", "title": "T", "url": "u"}]
    )
    storage.stage_generation_chapter(
        novel_id,
        "gen-miss",
        "1",
        {
            "id": "1",
            "raw": {
                "text": "x",
                "images": [
                    {
                        "local_path": "assets/images/kakuyomu%3A1/9999.jpg",
                        "content_type": "image/jpeg",
                        "size_bytes": 1,
                        "sha256": "x",
                    }
                ],
            },
        },
    )

    result = validate_generation_activation(storage, novel_id, "gen-miss")
    assert not result.is_valid
    failed_names = {check.name for check in result.failed_checks()}
    assert "every_referenced_image_resolves_inside_stage" in failed_names
