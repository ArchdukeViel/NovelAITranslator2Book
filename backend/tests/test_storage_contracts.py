"""Cross-cutting R2 storage invariants."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.db.engine import session_scope
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.storage.artifacts import R2ArtifactRepository
from novelai.storage.backends.r2 import InMemoryR2Storage
from novelai.storage.content_addressing import canonical_json_bytes, deterministic_gzip
from novelai.storage.service import StorageService


@pytest.fixture
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path)


def test_storage_contracts_are_documented() -> None:
    document = Path(__file__).resolve().parents[2] / "docs" / "STORAGE.md"
    assert document.exists()
    contents = document.read_text(encoding="utf-8")
    assert "Cloudflare R2" in contents
    assert "PostgreSQL" in contents


def test_canonical_json_and_gzip_are_deterministic() -> None:
    payload = {"z": [2, 1], "a": "text"}
    first = canonical_json_bytes(payload)
    second = canonical_json_bytes({"a": "text", "z": [2, 1]})
    assert first == second
    assert deterministic_gzip(first) == deterministic_gzip(second)
    assert json.loads(first.decode("utf-8")) == payload


def test_metadata_is_mutable_postgres_truth_not_an_r2_metadata_object(storage: StorageService) -> None:
    novel_id = f"contract-{uuid4().hex}"
    metadata = {"title": "Contract novel", "custom": {"field": True}, "chapters": []}
    storage.save_metadata(novel_id, metadata)
    loaded = storage.load_metadata(novel_id)
    assert loaded is not None
    assert loaded["custom"] == {"field": True}
    keys = storage.list_keys_under(f"novels/{novel_id}")
    assert not any(key.endswith("metadata.json") for key in keys)


def test_immutable_artifacts_are_idempotent_and_conflict_on_same_key_changes() -> None:
    backend = InMemoryR2Storage()
    repository = R2ArtifactRepository(backend)
    first = repository.put_json(
        storage_novel_id="1",
        kind="chapters",
        identity="c1",
        payload={"raw": {"text": "same"}},
    )
    second = repository.put_json(
        storage_novel_id="1",
        kind="chapters",
        identity="c1",
        payload={"raw": {"text": "same"}},
    )
    assert first.key == second.key
    assert second.created is False


def test_translation_text_is_not_stored_in_postgres_version_projection(storage: StorageService) -> None:
    novel_id = f"translation-contract-{uuid4().hex}"
    storage.save_metadata(novel_id, {"title": "Translation contract", "chapters": []})
    storage.save_translated_chapter(novel_id, "c1", "translated text", provider_key="gemini", provider_model="m")
    versions = storage.list_translated_chapter_versions(novel_id, "c1")
    assert versions and all("text" in version for version in versions)
    with session_scope() as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one()
        chapter = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="c1").one()
        assert chapter.translation_versions_json
        assert all("text" not in version for version in chapter.translation_versions_json)
    assert storage.load_translated_chapter(novel_id, "c1")["text"] == "translated text"


def test_r2_runtime_paths_are_outside_application_namespace(storage: StorageService) -> None:
    runtime_path = storage.runtime_path("checkpoints", "novel")
    assert runtime_path.is_absolute()
    assert storage.list_keys_under("runtime") == []
