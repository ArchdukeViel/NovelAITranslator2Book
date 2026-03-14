from __future__ import annotations

import shutil
from uuid import uuid4

import pytest

from novelai.services.storage_service import StorageService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def storage() -> StorageService:
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
            "origin_type": "file",
            "origin_uri_or_path": "C:/books/imported.epub",
            "document_type": "epub",
            "input_adapter_key": "epub",
        },
    )

    loaded = storage.load_metadata("novel1")

    assert loaded is not None
    assert loaded["origin_type"] == "file"
    assert loaded["document_type"] == "epub"
    assert loaded["input_adapter_key"] == "epub"
    assert set(loaded["translation_profiles"]) == {
        "glossary_extraction",
        "glossary_translation",
        "glossary_review",
        "body_translation",
        "ocr",
        "polish",
    }


def test_save_and_load_chapter_round_trips_document_unit_fields(storage: StorageService) -> None:
    storage.save_chapter(
        "novel1",
        "1",
        "Imported text",
        title="Unit 1",
        input_adapter_key="text",
        origin_type="file",
        origin_uri_or_path="C:/books/chapter1.txt",
        document_type="text",
        unit_type="section",
        import_order=1,
        context_group_id="book-a",
        region_metadata=[{"page": 1}],
        ocr_artifacts=[{"engine": "manual"}],
    )

    loaded = storage.load_chapter("novel1", "1")

    assert loaded is not None
    assert loaded["input_adapter_key"] == "text"
    assert loaded["origin_type"] == "file"
    assert loaded["document_type"] == "text"
    assert loaded["unit_type"] == "section"
    assert loaded["import_order"] == 1
    assert loaded["context_group_id"] == "book-a"
    assert loaded["region_metadata"] == [{"page": 1}]
    assert loaded["ocr_artifacts"] == [{"engine": "manual"}]
