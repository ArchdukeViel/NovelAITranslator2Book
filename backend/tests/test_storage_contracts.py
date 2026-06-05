from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.infrastructure.http.cache import FetchCacheEntry
from novelai.storage import StorageFetchCache
from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture()
def storage() -> StorageService:
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
                "source_text": "[CHAPTER chapter_001]\n[P p0001]\n本文",
                "char_count": 32,
                "provider_key": "gemini",
                "provider_model": "gemini-2.5-flash-lite",
            }
        ],
    )
    assert chunks[0]["source_text_hash"]
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


def test_temporary_bundle_delete_does_not_delete_canonical_chapter_data(storage: StorageService) -> None:
    storage.save_chapter("novel1", "chapter_001", "Raw chapter text", title="Chapter 1")
    storage.save_translated_chapter("novel1", "chapter_001", "Final translated text", provider="dummy", model="dummy")

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
    doc = Path("docs/reference/DATA_OUTPUT_STRUCTURE.md").read_text(encoding="utf-8")
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
