from __future__ import annotations

import json
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from novelai.infrastructure.http.cache import FetchCacheEntry
from novelai.storage import StorageFetchCache
from novelai.storage.common import UnsupportedStorageSchemaVersionError, validate_storage_schema_version
from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "storage_contract"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _write_chapter_payload(storage: StorageService, novel_id: str, chapter_id: str, payload: dict[str, Any]) -> None:
    path = storage._novel_dir(novel_id) / storage.CHAPTERS_DIRNAME / f"{chapter_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_metadata(storage: StorageService, novel_id: str, payload: dict[str, Any]) -> None:
    path = storage._novel_dir(novel_id) / "metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ── Contract assertion helpers (test-only) ──────────────────────────────────


def assert_metadata_contract(payload: dict[str, Any]) -> None:
    assert isinstance(payload, dict)
    assert isinstance(payload.get("novel_id") or payload.get("id"), str)
    assert isinstance(payload.get("title"), str)
    chapters = payload.get("chapters")
    if chapters is not None:
        assert isinstance(chapters, list)


def assert_raw_chapter_contract(payload: dict[str, Any]) -> None:
    # load_chapter returns a flattened view; raw fields are at the top level.
    assert isinstance(payload, dict)
    assert isinstance(payload.get("id"), str)
    assert isinstance(payload.get("scraped_at"), str)
    assert isinstance(payload.get("text"), str)
    assert isinstance(payload.get("images"), list)


def assert_translation_version_contract(payload: dict[str, Any]) -> None:
    assert isinstance(payload, dict)
    assert isinstance(payload.get("chapter_id"), str)
    assert isinstance(payload.get("version_id"), str)
    assert isinstance(payload.get("version_kind"), str)
    assert isinstance(payload.get("text"), str)
    assert payload.get("provider_key") is None or isinstance(payload.get("provider_key"), str)
    assert payload.get("provider_model") is None or isinstance(payload.get("provider_model"), str)
    assert isinstance(payload.get("glossary_revision"), int)


def assert_edit_history_contract(payload: dict[str, Any]) -> None:
    assert isinstance(payload, dict)
    assert isinstance(payload.get("id"), str)
    assert isinstance(payload.get("action"), str)
    assert isinstance(payload.get("version_id"), str)
    assert isinstance(payload.get("created_at"), str)


@pytest.fixture()
def storage() -> Generator[StorageService]:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"storage_contracts_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    store = StorageService(data_dir)
    yield store
    shutil.rmtree(data_dir, ignore_errors=True)


def test_translation_chunk_output_and_provider_request_persistence(storage: StorageService) -> None:

    chunks = storage.save_translation_chunks(
        "novel1",
        [
            {
                "chunk_id": "c0001",
                "chapter_ids": ["chapter_001"],
                "paragraph_ids": ["p0001", "p0002"],
                "paragraph_hashes": ["hash_p0001", "hash_p0002"],
                "paragraph_lineage": [
                    {
                        "chapter_id": "chapter_001",
                        "paragraph_id": "p0001",
                        "paragraph_index": 1,
                        "source_hash": "hash_p0001",
                        "char_count": 12,
                    },
                    {
                        "chapter_id": "chapter_001",
                        "paragraph_id": "p0002",
                        "paragraph_index": 2,
                        "source_hash": "hash_p0002",
                        "char_count": 20,
                    },
                ],
                "source_text": "[CHAPTER chapter_001]\n[P p0001]\n本文",
                "char_count": 32,
                "provider_key": "gemini",
                "provider_model": "gemini-2.5-flash-lite",
            }
        ],
    )
    assert chunks[0]["source_text_hash"]
    assert chunks[0]["paragraph_hashes"] == ["hash_p0001", "hash_p0002"]
    assert chunks[0]["paragraph_lineage"][0]["paragraph_id"] == "p0001"
    assert chunks[0]["status"] == "pending"

    updated = storage.update_translation_chunk_status(
        "novel1",
        "c0001",
        "needs_retry",
        provider_key="gemini",
        provider_model="gemini-2.5-flash-lite",
        last_error_code="provider_rate_limited",
        attempt_count=1,
    )
    assert updated["provider_key"] == "gemini"
    assert updated["provider_model"] == "gemini-2.5-flash-lite"
    assert updated["last_error_code"] == "provider_rate_limited"

    attempt = storage.save_chunk_attempt_record(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001", "p0002"],
            "attempt_number": 1,
            "provider_key": "gemini",
            "provider_model": "gemini-2.5-flash-lite",
            "scheduler_policy": "volume_first",
            "selection_reason": "primary_available",
            "status": "failed",
            "error_code": "provider_rate_limited",
            "headers": {"authorization": "Bearer should-not-be-stored"},
        }
    )
    assert attempt["status"] == "failed"
    assert "headers" not in attempt
    assert storage.list_chunk_attempt_records(novel_id="novel1", chunk_id="c0001") == [attempt]

    output = storage.save_translation_output(
        {
            "output_id": "out_c0001",
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001", "p0002"],
            "translated_text": "Translated text.",
            "structured_paragraph_map": [
                {"chapter_id": "chapter_001", "paragraph_id": "p0001", "translated_text": "Translated text."}
            ],
            "qa_score": 0.98,
            "provider_key": "gemini",
            "provider_model": "gemini-2.5-flash-lite",
        }
    )
    loaded_output = storage.read_translation_output("novel1", output_id="out_c0001")
    assert loaded_output == output
    assert output["output_hash"]

    request = storage.save_provider_request_record(
        {
            "request_id": "req_1",
            "job_id": "job_1",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "chunk_id": "c0001",
            "provider_key": "gemini",
            "provider_model": "gemini-2.5-flash-lite",
            "source_text_hash": chunks[0]["source_text_hash"],
            "success": False,
            "normalized_provider_error_code": "provider_rate_limited",
            "retry_after_seconds": 21,
            "api_key": "should-not-be-stored",
            "headers": {"authorization": "Bearer should-not-be-stored"},
        }
    )
    assert request["normalized_provider_error_code"] == "provider_rate_limited"
    assert "api_key" not in request
    assert "headers" not in request
    assert storage.list_provider_request_records(novel_id="novel1", success=False) == [request]


def test_translation_chunk_records_without_paragraph_hashes_load_safely(storage: StorageService) -> None:
    chunks = storage.save_translation_chunks(
        "novel1",
        [
            {
                "chunk_id": "legacy_c0001",
                "chapter_ids": ["chapter_001"],
                "paragraph_ids": ["p0001"],
                "source_text": "Legacy source",
            }
        ],
    )

    assert chunks[0]["paragraph_hashes"] == []
    assert storage.read_translation_chunks("novel1")[0]["paragraph_hashes"] == []


def test_runtime_records_reject_future_schema_without_overwrite(storage: StorageService) -> None:
    path = storage._translation_runtime_dir() / "chunks.json"
    future_payload = {
        "novel1:future": {
            "schema_version": 2,
            "novel_id": "novel1",
            "chunk_id": "future",
            "status": "pending",
        }
    }
    path.write_text(json.dumps(future_payload), encoding="utf-8")

    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.read_translation_chunks("novel1")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.save_translation_chunks("novel1", [{"chunk_id": "new", "source_text": "text"}])

    assert json.loads(path.read_text(encoding="utf-8")) == future_payload


def test_translation_runtime_records_are_scoped_by_run_and_chapter(storage: StorageService) -> None:
    storage.save_translation_chunks(
        "novel1",
        [
            {
                "chunk_id": "c0001",
                "translation_run_id": "run_chapter_1",
                "chapter_ids": ["chapter_001"],
                "paragraph_ids": ["p0001"],
                "source_text": "[P p0001]\nChapter 1 text",
            },
            {
                "chunk_id": "c0001",
                "translation_run_id": "run_chapter_2",
                "chapter_ids": ["chapter_002"],
                "paragraph_ids": ["p0001"],
                "source_text": "[P p0001]\nChapter 2 text",
            },
        ],
    )

    all_chunks = storage.read_translation_chunks("novel1")
    assert len(all_chunks) == 2
    assert {chunk["runtime_key"] for chunk in all_chunks} == {
        "novel1:run_chapter_1:chapter_001:c0001",
        "novel1:run_chapter_2:chapter_002:c0001",
    }

    updated = storage.update_translation_chunk_status(
        "novel1",
        "c0001",
        "needs_retry",
        translation_run_id="run_chapter_2",
        chapter_ids=["chapter_002"],
        attempt_count=1,
    )
    assert updated["runtime_key"] == "novel1:run_chapter_2:chapter_002:c0001"

    chapter_1_chunk = storage.read_translation_chunks(
        "novel1",
        translation_run_id="run_chapter_1",
        chapter_ids=["chapter_001"],
    )[0]
    chapter_2_chunk = storage.read_translation_chunks(
        "novel1",
        translation_run_id="run_chapter_2",
        chapter_ids=["chapter_002"],
    )[0]
    assert chapter_1_chunk["status"] == "pending"
    assert chapter_2_chunk["status"] == "needs_retry"

    first_attempt = storage.save_chunk_attempt_record(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_chapter_1",
            "chapter_ids": ["chapter_001"],
            "attempt_number": 1,
            "status": "failed",
        }
    )
    second_attempt = storage.save_chunk_attempt_record(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_chapter_2",
            "chapter_ids": ["chapter_002"],
            "attempt_number": 1,
            "status": "running",
        }
    )
    assert first_attempt["attempt_id"] != second_attempt["attempt_id"]
    assert storage.list_chunk_attempt_records(
        novel_id="novel1",
        chunk_id="c0001",
        translation_run_id="run_chapter_2",
        chapter_ids=["chapter_002"],
    ) == [second_attempt]

    old_attempt = storage.save_chunk_attempt_record(
        {
            "attempt_id": "novel1:c0001:1",
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "attempt_number": 1,
            "status": "failed",
        }
    )
    scoped_attempts = storage.list_chunk_attempt_records(
        novel_id="novel1",
        chunk_id="c0001",
        translation_run_id="run_chapter_2",
        chapter_ids=["chapter_002"],
    )
    assert scoped_attempts == [second_attempt]
    assert old_attempt in storage.list_chunk_attempt_records(novel_id="novel1", chunk_id="c0001")

    first_output = storage.save_translation_output(
        {
            "output_id": "c0001:attempt_0001",
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_chapter_1",
            "chapter_ids": ["chapter_001"],
            "translated_text": "Chapter 1 translation.",
        }
    )
    second_output = storage.save_translation_output(
        {
            "output_id": "c0001:attempt_0001",
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_chapter_2",
            "chapter_ids": ["chapter_002"],
            "translated_text": "Chapter 2 translation.",
        }
    )
    assert first_output["runtime_key"] != second_output["runtime_key"]
    assert storage.read_translation_output(
        "novel1",
        chunk_id="c0001",
        translation_run_id="run_chapter_2",
        chapter_ids=["chapter_002"],
    ) == [second_output]


def test_temporary_bundle_delete_does_not_delete_canonical_chapter_data(storage: StorageService) -> None:
    storage.save_chapter("novel1", "chapter_001", "Raw chapter text", title="Chapter 1")
    storage.save_translated_chapter(
        "novel1", "chapter_001", "Final translated text", provider_key="dummy", provider_model="dummy"
    )

    storage.save_translation_bundle(
        {
            "bundle_id": "bundle_0001",
            "novel_id": "novel1",
            "chunk_ids": ["c0001"],
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "source_text_hash": "hash",
            "target_chars": 4500,
            "hard_max_chars": 7000,
            "status": "translated",
        }
    )
    assert storage.read_translation_bundle("novel1", "bundle_0001") is not None

    assert storage.delete_translation_bundle("novel1", "bundle_0001") is True

    assert storage.read_translation_bundle("novel1", "bundle_0001") is None
    chapter = storage.load_chapter("novel1", "chapter_001")
    translated = storage.load_translated_chapter("novel1", "chapter_001")
    assert chapter is not None
    assert translated is not None
    assert chapter["text"] == "Raw chapter text"
    assert translated["text"] == "Final translated text"


def test_fetch_cache_entry_and_conditional_headers(storage: StorageService) -> None:
    stored = storage.save_fetch_cache_entry(
        {
            "url": "https://ncode.syosetu.com/n0813kx/1/",
            "final_url": "https://ncode.syosetu.com/n0813kx/1/",
            "source_key": "syosetu_ncode",
            "status_code": 200,
            "headers": {"ETag": '"abc"', "Last-Modified": "Thu, 04 Jun 2026 00:00:00 GMT"},
            "body_text": "<html>chapter</html>",
            "parser_version": "syosetu-v1",
        }
    )

    assert stored["body_hash"]
    assert storage.read_fetch_cache_entry("syosetu_ncode", "https://ncode.syosetu.com/n0813kx/1/") == stored
    assert storage.fetch_cache_conditional_headers(
        "syosetu_ncode",
        "https://ncode.syosetu.com/n0813kx/1/",
    ) == {
        "If-None-Match": '"abc"',
        "If-Modified-Since": "Thu, 04 Jun 2026 00:00:00 GMT",
    }


def test_storage_fetch_cache_adapter_uses_storage_service(storage: StorageService) -> None:
    cache = StorageFetchCache(storage)
    cache.set(
        FetchCacheEntry(
            requested_url="https://example.test/chapter",
            final_url="https://example.test/chapter",
            status_code=200,
            headers={"etag": '"v2"'},
            text="cached chapter",
            body=b"cached chapter",
            source_key="generic",
            fetched_at="2026-06-04T00:00:00Z",
        )
    )

    cached = cache.get("generic", "https://example.test/chapter")

    assert cached is not None
    assert cached.text == "cached chapter"
    assert cache.conditional_headers("generic", "https://example.test/chapter") == {"If-None-Match": '"v2"'}


def test_storage_contracts_are_documented() -> None:
    # Resolve repository root robustly regardless of current working directory
    repo_root = Path(__file__).resolve().parents[2]
    doc = (repo_root / "docs" / "reference" / "data-output-structure.md").read_text(encoding="utf-8")
    required_fragments = [
        "runtime/translation/chunks.json",
        "runtime/translation/chunk_attempts.json",
        "runtime/translation/bundles.json",
        "runtime/translation/outputs.json",
        "runtime/provider_requests.json",
        "runtime/fetch_cache/index.json",
        "translation_cache.json",
        "scheduler_states.json",
    ]
    for fragment in required_fragments:
        assert fragment in doc


# ── Metadata contract ───────────────────────────────────────────────────────


def test_storage_contract_document_exists() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    doc = (repo_root / "docs" / "storage-contract.md").read_text(encoding="utf-8")
    for fragment in (
        "Novel Metadata",
        "Metadata Backups",
        "Raw Chapter Bundles",
        "Chapter Image Assets",
        "Translated Chapter Versions",
        "Translation Edit History",
        "PostgreSQL Projection Relationship",
    ):
        assert fragment in doc


def test_metadata_save_load_round_trip_preserves_fields(storage: StorageService) -> None:
    path = storage.save_metadata(
        "novel-meta-1",
        {
            "title": "Source Title",
            "translated_title": "Translated Title",
            "source_language": "ja",
            "origin_type": "web",
            "origin_uri_or_path": "https://example.test/novel",
            "document_type": "web_novel",
            "input_adapter_key": "syosetu",
            "context_group_id": "grp-1",
        },
    )
    assert path.name == "metadata.json"
    assert path.parent.name == "novel-meta-1" or path.parent.parent.name == "novels"

    loaded = storage.load_metadata("novel-meta-1")
    assert loaded is not None
    assert_metadata_contract(loaded)
    assert loaded["title"] == "Source Title"
    assert loaded["translated_title"] == "Translated Title"
    assert loaded["novel_id"] == "novel-meta-1"
    assert loaded["schema_version"] == storage.SCHEMA_VERSION


def test_metadata_additive_unknown_fields_preserved(storage: StorageService) -> None:
    storage.save_metadata("novel-meta-2", {"title": "T", "custom_additive_field": "keep-me"})
    loaded = storage.load_metadata("novel-meta-2")
    assert loaded is not None
    assert loaded.get("custom_additive_field") == "keep-me"


def test_metadata_write_rejects_legacy_source_field(storage: StorageService) -> None:
    with pytest.raises(ValueError, match="source_key"):
        storage.save_metadata("legacy-source-write", {"title": "T", "source": "syosetu"})

    assert storage.load_metadata("legacy-source-write") is None


def test_metadata_read_rejects_legacy_source_field(storage: StorageService) -> None:
    payload = {
        "schema_version": storage.SCHEMA_VERSION,
        "novel_id": "legacy-source-read",
        "title": "T",
        "source": "syosetu",
    }
    _write_metadata(storage, "legacy-source-read", payload)

    with pytest.raises(ValueError, match="source_key"):
        storage.load_metadata("legacy-source-read")


@pytest.mark.parametrize("operation", ["write", "read"])
def test_metadata_rejects_legacy_status_field(storage: StorageService, operation: str) -> None:
    payload = {
        "schema_version": storage.SCHEMA_VERSION,
        "novel_id": "legacy-status",
        "title": "T",
        "status": "ongoing",
    }
    if operation == "read":
        _write_metadata(storage, "legacy-status", payload)

    with pytest.raises(ValueError, match="publication_status"):
        if operation == "write":
            storage.save_metadata("legacy-status", payload)
        else:
            storage.load_metadata("legacy-status")


def test_unversioned_metadata_is_rejected(storage: StorageService) -> None:
    _write_metadata(storage, "current-novel-1", _load_fixture("legacy_metadata.json"))
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_metadata("current-novel-1")


def test_metadata_older_schema_is_rejected(storage: StorageService) -> None:
    payload = _load_fixture("legacy_metadata.json")
    payload["schema_version"] = 1
    _write_metadata(storage, "current-novel-1", payload)
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_metadata("current-novel-1")


def test_metadata_rejects_future_schema_without_overwrite(storage: StorageService) -> None:
    future_payload = {
        **_load_fixture("legacy_metadata.json"),
        "schema_version": storage.SCHEMA_VERSION + 1,
    }
    _write_metadata(storage, "legacy-novel-1", future_payload)
    path = storage._novel_dir("legacy-novel-1") / "metadata.json"

    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_metadata("legacy-novel-1")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.save_metadata("legacy-novel-1", {"title": "must not overwrite"})

    assert json.loads(path.read_text(encoding="utf-8")) == future_payload


@pytest.mark.parametrize("invalid_version", [0, -1, "2", True])
def test_explicit_invalid_storage_schema_versions_are_rejected(invalid_version: object) -> None:
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        validate_storage_schema_version(
            {"schema_version": invalid_version},
            current_version=2,
            artifact_type="test artifact",
        )


# ── Metadata backup contract ────────────────────────────────────────────────


def test_metadata_backup_path_pattern_and_ordering(storage: StorageService) -> None:
    storage.save_metadata("novel-backup-1", {"title": "V1", "updated_at": "2024-01-01T00:00:00Z"})
    storage.save_metadata("novel-backup-1", {"title": "V2", "updated_at": "2024-02-01T00:00:00Z"})

    backup_dir = storage._novel_dir("novel-backup-1") / "metadata_backups"
    assert backup_dir.is_dir()
    backups = sorted(backup_dir.glob("*.json"), key=lambda p: p.name, reverse=True)
    assert backups, "expected at least one timestamped backup"

    history = storage.list_metadata_history("novel-backup-1")
    assert history[0]["is_current"] is True
    assert any(not entry["is_current"] for entry in history)


def test_metadata_backup_retention_bounded(storage: StorageService) -> None:
    for index in range(7):
        storage.save_metadata(
            "novel-retention-1",
            {"title": f"V{index}", "updated_at": f"2024-03-{index + 1:02d}T00:00:00Z"},
        )
    backup_dir = storage._novel_dir("novel-retention-1") / "metadata_backups"
    backups = list(backup_dir.glob("*.json"))
    assert len(backups) <= 6  # 5 retention + current snapshot headroom


# ── Raw chapter bundle contract ─────────────────────────────────────────────


def test_raw_chapter_save_load_round_trip(storage: StorageService) -> None:
    path = storage.save_chapter(
        "novel-ch-1",
        "chapter_001",
        "Raw chapter text.",
        title="Chapter One",
        source_key="syosetu",
        source_url="https://example.test/1",
        images=[],
        source_blocks=[{"type": "line", "text": "Raw chapter text."}],
    )
    assert path.name == "chapter_001.json"

    loaded = storage.load_chapter("novel-ch-1", "chapter_001")
    assert loaded is not None
    assert_raw_chapter_contract(loaded)
    assert loaded["text"] == "Raw chapter text."
    assert loaded["source_key"] == "syosetu"
    assert len(loaded["source_blocks"]) == 1
    assert loaded["source_blocks"][0]["text"] == "Raw chapter text."

    # Paragraphs are preserved in the stored raw bundle even though load_chapter
    # does not surface them in its flattened return.
    stored = storage._load_chapter_bundle("novel-ch-1", "chapter_001")
    assert stored is not None
    assert stored["raw"]["paragraphs"] == ["Raw chapter text."]


def test_raw_chapter_provenance_fields(storage: StorageService) -> None:
    storage.save_chapter(
        "novel-ch-2",
        "chapter_002",
        "Provenance text.",
        origin_type="web",
        document_type="web_novel",
        input_adapter_key="syosetu",
        context_group_id="grp-x",
    )
    loaded = storage.load_chapter("novel-ch-2", "chapter_002")
    assert loaded is not None
    for field in ("origin_type", "document_type", "input_adapter_key", "context_group_id"):
        assert loaded[field] is not None, field


def test_unversioned_chapter_bundle_is_rejected(storage: StorageService) -> None:
    _write_chapter_payload(storage, "current-novel-1", "chapter-1", _load_fixture("legacy_chapter_bundle.json"))
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_chapter("current-novel-1", "chapter-1")


def test_chapter_rejects_future_schema_without_overwrite(storage: StorageService) -> None:
    future_payload = {
        **_load_fixture("legacy_chapter_bundle.json"),
        "schema_version": storage.SCHEMA_VERSION + 1,
    }
    _write_chapter_payload(storage, "legacy-novel-1", "legacy-ch-1", future_payload)
    path = storage._chapter_path("legacy-novel-1", "legacy-ch-1")

    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_chapter("legacy-novel-1", "legacy-ch-1")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.save_chapter("legacy-novel-1", "legacy-ch-1", "must not overwrite")

    assert json.loads(path.read_text(encoding="utf-8")) == future_payload


def test_glossary_noncurrent_shapes_are_rejected_and_preserved(storage: StorageService) -> None:
    path = storage._novel_dir("current-novel-1") / "glossary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy_entries = [{"source": "猫", "target": "cat"}]
    path.write_text(json.dumps(legacy_entries), encoding="utf-8")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_glossary("current-novel-1")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.save_glossary("current-novel-1", [])
    assert json.loads(path.read_text(encoding="utf-8")) == legacy_entries

    future_payload = {
        "schema_version": storage.SCHEMA_VERSION + 1,
        "entries": legacy_entries,
    }
    path.write_text(json.dumps(future_payload), encoding="utf-8")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_glossary("current-novel-1")
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.save_glossary("current-novel-1", [])

    assert json.loads(path.read_text(encoding="utf-8")) == future_payload


def test_current_storage_writers_emit_supported_schema_versions(storage: StorageService) -> None:
    metadata_path = storage.save_metadata("versioned-novel", {"title": "Versioned"})
    chapter_path = storage.save_chapter("versioned-novel", "1", "Raw text")
    glossary_path = storage.save_glossary("versioned-novel", [{"source": "猫", "target": "cat"}])
    runtime_record = storage.save_translation_chunks(
        "versioned-novel",
        [{"chunk_id": "c0001", "source_text": "Raw text"}],
    )[0]

    assert json.loads(metadata_path.read_text(encoding="utf-8"))["schema_version"] == storage.SCHEMA_VERSION
    assert json.loads(chapter_path.read_text(encoding="utf-8"))["schema_version"] == storage.SCHEMA_VERSION
    assert json.loads(glossary_path.read_text(encoding="utf-8"))["schema_version"] == storage.SCHEMA_VERSION
    assert runtime_record["schema_version"] == 1


# ── Image asset and manifest contract ───────────────────────────────────────


def test_image_asset_save_and_clear(storage: StorageService) -> None:
    manifest = storage.save_chapter_image_asset(
        "novel-img-1",
        "chapter_001",
        image_index=0,
        content=b"\x89PNG\r\n\x1a\nfake-bytes",
        source_url="https://img.test/a.png",
        content_type="image/png",
    )
    assert manifest["content_type"] == "image/png"
    assert manifest["size_bytes"] == len(b"\x89PNG\r\n\x1a\nfake-bytes")
    assert isinstance(manifest["sha256"], str) and manifest["sha256"]
    assert manifest["local_path"].endswith("0000.png")

    resolved = storage.resolve_asset_path("novel-img-1", manifest["local_path"])
    assert resolved is not None and resolved.exists()

    storage.clear_chapter_image_assets("novel-img-1", "chapter_001")
    assert resolved.exists() is False


def test_image_manifest_download_error_preserved(storage: StorageService) -> None:
    storage.save_chapter(
        "novel-img-2",
        "chapter_002",
        "Text with image.",
        images=[{"source_url": "https://img.test/b.png", "download_error": "404"}],
    )
    loaded = storage.load_chapter("novel-img-2", "chapter_002")
    assert loaded is not None
    images = loaded["images"]
    assert any(image.get("download_error") == "404" for image in images)


# ── Translation version contract ────────────────────────────────────────────


def test_translated_chapter_save_load_round_trip(storage: StorageService) -> None:
    path = storage.save_translated_chapter(
        "novel-tr-1",
        "chapter_001",
        "Translated text.",
        provider_key="gemini",
        provider_model="gemini-2.5-flash",
    )
    assert path.name == "chapter_001.json"

    loaded = storage.load_translated_chapter("novel-tr-1", "chapter_001")
    assert loaded is not None
    assert_translation_version_contract(loaded)
    assert loaded["text"] == "Translated text."
    assert loaded["provider_key"] == "gemini"


def test_translation_version_listing_and_activation(storage: StorageService) -> None:
    storage.save_translated_chapter("novel-tr-2", "chapter_001", "V1 text", provider_key="gemini", provider_model="m1")
    storage.save_translated_chapter("novel-tr-2", "chapter_001", "V2 text", provider_key="gemini", provider_model="m2")

    versions = storage.list_translated_chapter_versions("novel-tr-2", "chapter_001")
    assert len(versions) == 2
    assert all(isinstance(v["version_id"], str) for v in versions)
    active = [v for v in versions if v["active"]]
    assert len(active) == 1
    assert active[0]["text"] == "V2 text"

    first_id = versions[0]["version_id"]
    assert storage.activate_translated_chapter_version("novel-tr-2", "chapter_001", first_id)
    versions = storage.list_translated_chapter_versions("novel-tr-2", "chapter_001")
    assert len(versions) == 2  # older versions preserved
    assert next(v for v in versions if v["version_id"] == first_id)["active"] is True


def test_current_schema_rejects_legacy_translation_version_fields(storage: StorageService) -> None:
    _write_chapter_payload(
        storage,
        "current-novel-1",
        "chapter-1",
        {
            "schema_version": storage.SCHEMA_VERSION,
            "id": "chapter-1",
            "translation_versions": [
                {
                    "id": "v1",
                    "kind": "machine_translation",
                    "provider": "gemini",
                    "model": "gemini-3.1-flash-lite",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "text": "legacy",
                }
            ],
            "active_translation_version_id": "v1",
        },
    )

    with pytest.raises(ValueError, match="version_id"):
        storage.load_translated_chapter("current-novel-1", "chapter-1")


def test_current_schema_rejects_duplicate_translation_version_ids(storage: StorageService) -> None:
    version = {
        "version_id": "v1",
        "version_kind": "machine_translation",
        "provider_key": "gemini",
        "provider_model": "gemini-3.1-flash-lite",
        "glossary_revision": 0,
        "created_at": "2026-01-01T00:00:00+00:00",
        "text": "canonical",
    }
    _write_chapter_payload(
        storage,
        "current-novel-2",
        "chapter-1",
        {
            "schema_version": storage.SCHEMA_VERSION,
            "id": "chapter-1",
            "translation_versions": [version, dict(version)],
            "active_translation_version_id": "v1",
        },
    )

    with pytest.raises(ValueError, match="Duplicate translation version_id"):
        storage.load_translated_chapter("current-novel-2", "chapter-1")


def test_unversioned_translation_fixture_is_rejected(storage: StorageService) -> None:
    _write_chapter_payload(storage, "current-novel-1", "chapter-1", _load_fixture("legacy_translation_bundle.json"))
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_translated_chapter("current-novel-1", "chapter-1")


# ── Edit history contract ───────────────────────────────────────────────────


def test_edit_history_save_and_load(storage: StorageService) -> None:
    storage.save_translated_chapter("novel-ed-1", "chapter_001", "Base text", provider_key="gemini", provider_model="m")
    storage.save_edited_translation(
        "novel-ed-1",
        "chapter_001",
        "Edited text",
        editor="human",
        note="fix",
        glossary_revision=0,
    )

    history = storage.load_translation_edit_history("novel-ed-1", "chapter_001")
    assert len(history) == 1
    assert_edit_history_contract(history[0])
    assert history[0]["action"] == "manual_edit"
    assert history[0]["editor"] == "human"
    assert history[0]["note"] == "fix"

    edited = storage.load_translated_chapter("novel-ed-1", "chapter_001")
    assert edited is not None
    assert edited["text"] == "Edited text"


def test_unversioned_edit_history_fixture_is_rejected(storage: StorageService) -> None:
    _write_chapter_payload(storage, "current-novel-1", "chapter-1", _load_fixture("legacy_edit_history.json"))
    with pytest.raises(UnsupportedStorageSchemaVersionError):
        storage.load_translation_edit_history("current-novel-1", "chapter-1")
