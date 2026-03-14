from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedDocument, ImportedUnit
from novelai.pipeline.context import PipelineResult
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from tests.conftest import TESTS_TMP_ROOT, MockTranslationProvider


class StubDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "text"

    def probe(self, source: str | Path) -> bool:
        return True

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        units = [
            ImportedUnit(
                unit_id="1",
                import_order=1,
                title="Part 1",
                text="勇者 Aria entered the city. 勇者 Aria returned victorious.",
                source_ref=str(source),
                unit_type="chapter",
                context_group_id="stub-doc",
            ),
        ]
        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file",
            origin_uri_or_path=str(source),
            document_type="text",
            title="Imported Story",
            source_language="Japanese",
            units=tuple(units),
        )


class StubTranslationService(TranslationService):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def translate_chapter(self, **kwargs: object) -> PipelineResult:
        self.calls.append(kwargs)
        return PipelineResult(
            final_text="[TRANSLATED] Imported",
            chapter_url=str(kwargs.get("chapter_url") or ""),
            provider_key="mock",
            provider_model="mock-1.0",
        )


@pytest.fixture
def env() -> dict[str, object]:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"doc_orch_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    yield {
        "data_dir": data_dir,
        "storage": StorageService(data_dir),
        "settings": PreferencesService(data_dir),
        "cache": TranslationCache(data_dir),
        "usage": UsageService(data_dir),
    }
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_import_document_persists_units_and_metadata(env: dict[str, object]) -> None:
    translation = StubTranslationService()
    orchestrator = NovelOrchestrationService(
        storage=env["storage"],
        translation=translation,
        input_adapter_factory=lambda key: StubDocumentAdapter(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=env["settings"],
        translation_cache=env["cache"],
        usage_service=env["usage"],
    )

    metadata = await orchestrator.import_document("text", "novel-1", "C:/story.txt")
    chapter = env["storage"].load_chapter("novel-1", "1")

    assert metadata["document_type"] == "text"
    assert metadata["input_adapter_key"] == "text"
    assert chapter is not None
    assert chapter["input_adapter_key"] == "text"
    assert chapter["text"].startswith("勇者")


@pytest.mark.asyncio
async def test_translate_chapters_uses_imported_raw_text_without_source_adapter(env: dict[str, object]) -> None:
    translation = StubTranslationService()
    orchestrator = NovelOrchestrationService(
        storage=env["storage"],
        translation=translation,
        input_adapter_factory=lambda key: StubDocumentAdapter(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=env["settings"],
        translation_cache=env["cache"],
        usage_service=env["usage"],
    )
    await orchestrator.import_document("text", "novel-1", "C:/story.txt")

    await orchestrator.translate_chapters("imported", "novel-1", "1")

    assert translation.calls
    assert translation.calls[0]["raw_text"] == "勇者 Aria entered the city. 勇者 Aria returned victorious."
    translated = env["storage"].load_translated_chapter("novel-1", "1")
    assert translated is not None
    assert translated["text"] == "[TRANSLATED] Imported"


@pytest.mark.asyncio
async def test_extract_glossary_terms_builds_pending_candidates(env: dict[str, object]) -> None:
    translation = StubTranslationService()
    orchestrator = NovelOrchestrationService(
        storage=env["storage"],
        translation=translation,
        input_adapter_factory=lambda key: StubDocumentAdapter(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=env["settings"],
        translation_cache=env["cache"],
        usage_service=env["usage"],
    )
    await orchestrator.import_document("text", "novel-1", "C:/story.txt")

    summary = await orchestrator.extract_glossary_terms("novel-1")
    entries = env["storage"].load_glossary("novel-1")

    assert summary["added"] >= 1
    assert any(entry.get("status") == "pending" for entry in entries)
    assert any(entry.get("context_summary") for entry in entries)
