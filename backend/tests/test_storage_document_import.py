from __future__ import annotations

import shutil
from collections.abc import Generator
from uuid import uuid4

import pytest

from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def storage() -> Generator[StorageService]:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"storage_doc_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    store = StorageService(data_dir)
    yield store
    shutil.rmtree(data_dir, ignore_errors=True)


def test_metadata_defaults_include_translation_profiles(storage: StorageService) -> None:
    storage.save_metadata(
        "novel1",
        {
            "title": "Imported",
            "origin_type": "url",
            "origin_uri_or_path": "https://example.com/story",
            "document_type": "web_novel",
            "input_adapter_key": "web",
        },
    )

    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["origin_type"] == "url"
    assert loaded["document_type"] == "web_novel"
    assert loaded["input_adapter_key"] == "web"
    assert set(loaded["translation_profiles"]) == {
        "glossary_extraction",
        "glossary_translation",
        "glossary_review",
        "body_translation",
        "ocr",
        "polish",
    }
    assert loaded["translation_profiles"]["body_translation"] == {
        "provider_key": None,
        "provider_model": None,
    }


def test_metadata_rejects_legacy_translation_profile_fields(storage: StorageService) -> None:
    with pytest.raises(ValueError, match="Unsupported workflow profile fields"):
        storage.save_metadata(
            "novel1",
            {
                "title": "Imported",
                "translation_profiles": {
                    "body_translation": {
                        "provider": "gemini",
                        "model": "legacy",
                    }
                },
            },
        )


def test_save_and_load_chapter_round_trips_document_unit_fields(storage: StorageService) -> None:
    storage.save_chapter(
        "novel1",
        "1",
        "Imported text",
        title="Unit 1",
        input_adapter_key="web",
        origin_type="url",
        origin_uri_or_path="https://example.com/story",
        document_type="web_novel",
        unit_type="chapter",
        import_order=1,
        context_group_id="book-a",
        region_metadata=[{"page": 1}],
        ocr_artifacts=[{"engine": "manual"}],
    )

    loaded = storage.load_chapter("novel1", "1")

    assert loaded is not None
    assert loaded["input_adapter_key"] == "web"
    assert loaded["origin_type"] == "url"
    assert loaded["document_type"] == "web_novel"
    assert loaded["unit_type"] == "chapter"
    assert loaded["import_order"] == 1
    assert loaded["context_group_id"] == "book-a"
    assert loaded["region_metadata"] == [{"page": 1}]
    assert loaded["ocr_artifacts"] == [{"engine": "manual"}]
