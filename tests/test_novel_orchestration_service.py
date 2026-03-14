from __future__ import annotations

import json
import logging
import shutil
from typing import Any
from uuid import uuid4

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.pipeline.context import PipelineResult
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from tests.conftest import TESTS_TMP_ROOT, MockTranslationProvider


class StubSource(SourceAdapter):
    def __init__(self) -> None:
        self.requested_max_chapters: list[int | None] = []
        self.chapter_payloads: dict[str, dict[str, object]] = {}
        self.assets: dict[str, dict[str, object]] = {}

    @property
    def key(self) -> str:
        return "stub"

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        self.requested_max_chapters.append(max_chapter)
        return {
            "source": "syosetu_ncode",
            "source_url": f"https://ncode.syosetu.com/{url}/",
            "title": "Original Novel",
            "author": "Original Author",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{url}/1"},
                {"id": "2", "num": 2, "title": "Chapter Two", "url": f"https://example.com/{url}/2"},
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return f"chapter from {url}"

    async def fetch_chapter_payload(self, url: str) -> dict[str, object]:
        payload = self.chapter_payloads.get(url)
        if payload is not None:
            return payload
        return {"text": await self.fetch_chapter(url), "images": []}

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> dict[str, object]:
        asset = self.assets.get(url)
        if asset is not None:
            return asset
        return {
            "url": url,
            "content": b"asset-bytes",
            "content_type": "image/png",
        }


class UnusedTranslationService(TranslationService):
    pass


class StubTranslationService(TranslationService):
    def __init__(self, *, final_text: str = "translated", fail: bool = False) -> None:
        self.final_text = final_text
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("provider failure")
        return PipelineResult(
            final_text=self.final_text,
            chapter_url=str(kwargs.get("chapter_url") or ""),
            provider_key="mock",
            provider_model="mock-1.0",
        )


@pytest.fixture
def orchestration_env():
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"orchestrator_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    storage = StorageService(data_dir)
    settings = PreferencesService(data_dir)
    settings.set_provider_key("mock")
    settings.set_provider_model("mock-1.0")
    cache = TranslationCache(data_dir)
    usage = UsageService(data_dir)

    yield {
        "data_dir": data_dir,
        "storage": storage,
        "settings": settings,
        "cache": cache,
        "usage": usage,
    }

    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_scrape_metadata_translates_title_author_and_chapter_titles(orchestration_env) -> None:
    provider = MockTranslationProvider(key="mock", model="mock-1.0")
    source = StubSource()
    storage = orchestration_env["storage"]

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")
    metadata_path = storage.base_dir / "novels" / "novel-1" / "metadata.json"

    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert metadata["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert metadata_path.exists()
    stored = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert stored["translated_title"] == "[TRANSLATED] Original Novel"
    assert stored["translated_author"] == "[TRANSLATED] Original Author"
    assert stored["authors"]["translated"] == "[TRANSLATED] Original Author"
    assert orchestration_env["usage"].summary(all_days=True)["total_requests"] == 4


@pytest.mark.asyncio
async def test_scrape_metadata_passes_max_chapter_to_source(orchestration_env) -> None:
    provider = MockTranslationProvider(key="mock", model="mock-1.0")
    source = StubSource()

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update", max_chapter=46)

    assert source.requested_max_chapters == [46]


@pytest.mark.asyncio
async def test_scrape_metadata_logs_missing_openai_key_only_once(orchestration_env, caplog) -> None:
    provider = MockTranslationProvider(key="dummy", model="dummy")
    source = StubSource()
    settings = orchestration_env["settings"]
    settings.set_provider_key("openai")
    settings.set_provider_model("gpt-5.4")
    settings.clear_api_key()

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with caplog.at_level(logging.WARNING, logger="novelai.services.novel_orchestration_service"):
        await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")
        await orchestrator.scrape_metadata("syosetu_ncode", "novel-2", mode="update")

    warnings = [
        record.message
        for record in caplog.records
        if "OpenAI API key missing; falling back to dummy provider for metadata translation." in record.message
    ]

    assert warnings == ["OpenAI API key missing; falling back to dummy provider for metadata translation."]


@pytest.mark.asyncio
async def test_scrape_chapters_downloads_and_stores_image_assets(orchestration_env) -> None:
    source = StubSource()
    chapter_url = "https://example.com/novel-1/1"
    source.chapter_payloads[chapter_url] = {
        "text": "Before\n\n[Image: Scene illustration]\n\nAfter",
        "images": [
            {
                "index": 0,
                "placeholder": "[Image: Scene illustration]",
                "original_url": "https://assets.example.com/scene.jpg",
                "alt": "Scene illustration",
            }
        ],
    }
    source.assets["https://assets.example.com/scene.jpg"] = {
        "url": "https://assets.example.com/scene.jpg",
        "content": b"scene-bytes",
        "content_type": "image/jpeg",
    }

    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": chapter_url},
            ],
        },
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_chapters("stub", "novel-1", "1", mode="update")

    chapter = storage.load_chapter("novel-1", "1")
    assert chapter is not None
    assert chapter["text"] == "Before\n\n[Image: Scene illustration]\n\nAfter"
    assert chapter["images"][0]["local_path"] == "assets/images/1/0000.jpg"
    assert "download_error" not in chapter["images"][0]

    export_images = storage.load_chapter_export_images("novel-1", "1")
    assert export_images[0]["asset_path"] is not None


@pytest.mark.asyncio
async def test_scrape_chapters_records_download_error_for_html_asset_response(orchestration_env) -> None:
    source = StubSource()
    chapter_url = "https://example.com/novel-1/1"
    source.chapter_payloads[chapter_url] = {
        "text": "[Image: Blocked image]",
        "images": [
            {
                "index": 0,
                "placeholder": "[Image: Blocked image]",
                "original_url": "https://assets.example.com/blocked.jpg",
                "alt": "Blocked image",
            }
        ],
    }
    source.assets["https://assets.example.com/blocked.jpg"] = {
        "url": "https://assets.example.com/blocked.jpg",
        "content": b"<html>blocked</html>",
        "content_type": "text/html; charset=utf-8",
    }

    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": chapter_url},
            ],
        },
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_chapters("stub", "novel-1", "1", mode="update")

    chapter = storage.load_chapter("novel-1", "1")
    assert chapter is not None
    assert chapter["images"][0]["download_error"] == "Asset response was HTML instead of image content."
    assert chapter["images"][0].get("local_path") is None


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_missing_source_language(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="missing_source_language"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_when_nothing_to_translate(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_translated_chapter("novel-1", "1", "already translated", provider="mock", model="mock-1.0")

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="nothing_to_translate"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_translate_chapters_attempts_checkpoint_restore_after_error_state(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.update_chapter_state("novel-1", "1", ChapterState.SEGMENTED, error="old failure")
    storage.create_checkpoint("novel-1", "1", "resume")

    restore_calls: list[tuple[str, str, str]] = []
    original_restore = storage.restore_from_checkpoint

    def _tracking_restore(novel_id: str, chapter_id: str, checkpoint_name: str) -> bool:
        restore_calls.append((novel_id, chapter_id, checkpoint_name))
        return original_restore(novel_id, chapter_id, checkpoint_name)

    storage.restore_from_checkpoint = _tracking_restore  # type: ignore[method-assign]

    translation = StubTranslationService(final_text="translated ok")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "novel-1", "1", force=True)

    assert restore_calls
    assert restore_calls[-1] == ("novel-1", "1", "resume")
    translated = storage.load_translated_chapter("novel-1", "1")
    assert translated is not None
    assert translated["text"] == "translated ok"


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_pending_glossary_terms(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_glossary(
        "novel-1",
        [{"source": "英雄", "target": "hero", "status": "pending", "locked": True}],
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="pending_glossary_terms"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_missing_ocr_review(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_chapter_media_state(
        "novel-1",
        "1",
        ocr_required=True,
        ocr_text="OCR text",
        ocr_status="pending",
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="missing_ocr_review"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_translate_chapters_allows_when_ocr_reviewed(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_chapter_media_state(
        "novel-1",
        "1",
        ocr_required=True,
        ocr_text="Corrected OCR text",
        ocr_status="reviewed",
    )

    translation = StubTranslationService(final_text="translated ok")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "novel-1", "1")

    translated = storage.load_translated_chapter("novel-1", "1")
    assert translated is not None
    assert translated["text"] == "translated ok"


@pytest.mark.asyncio
async def test_retranslate_chapter_forces_single_chapter_translation(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
                {"id": "2", "num": 2, "title": "Chapter Two", "url": "https://example.com/novel-1/2"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text 1", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_chapter("novel-1", "2", "raw text 2", source_key="stub", source_url="https://example.com/novel-1/2")
    storage.save_translated_chapter("novel-1", "1", "old translation", provider="mock", model="mock-1.0")

    translation = StubTranslationService(final_text="new translation")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.retranslate_chapter("stub", "novel-1", "1")

    assert len(translation.calls) == 1
    assert str(translation.calls[0].get("chapter_url")) == "https://example.com/novel-1/1"
    translated_1 = storage.load_translated_chapter("novel-1", "1")
    translated_2 = storage.load_translated_chapter("novel-1", "2")
    assert translated_1 is not None
    assert translated_1["text"] == "new translation"
    assert translated_2 is None


@pytest.mark.asyncio
async def test_ingest_ocr_candidates_updates_media_state_from_images(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter(
        "novel-1",
        "1",
        "Body text",
        source_key="stub",
        source_url="https://example.com/novel-1/1",
        images=[
            {
                "index": 0,
                "placeholder": "[Image: inscription]",
                "original_url": "https://assets.example.com/inscription.jpg",
                "alt": "Ancient inscription",
            }
        ],
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.ingest_ocr_candidates("novel-1", "1")

    assert summary["selected"] == 1
    assert summary["updated"] == 1
    assert summary["skipped_no_images"] == 0
    assert summary["skipped_reviewed"] == 0
    assert summary["failed"] == []

    media = storage.load_chapter_media_state("novel-1", "1")
    assert media is not None
    assert media["ocr_required"] is True
    assert media["ocr_status"] == "pending"
    assert isinstance(media["ocr_text"], str)
    assert "Ancient inscription" in media["ocr_text"]


@pytest.mark.asyncio
async def test_ingest_ocr_candidates_skips_reviewed_when_not_overwriting(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter(
        "novel-1",
        "1",
        "Body text",
        source_key="stub",
        source_url="https://example.com/novel-1/1",
        images=[
            {
                "index": 0,
                "placeholder": "[Image: inscription]",
                "original_url": "https://assets.example.com/inscription.jpg",
                "alt": "Ancient inscription",
            }
        ],
    )
    storage.save_chapter_media_state(
        "novel-1",
        "1",
        ocr_required=True,
        ocr_text="Hand reviewed OCR",
        ocr_status="reviewed",
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.ingest_ocr_candidates("novel-1", "1", overwrite=False)

    assert summary["selected"] == 1
    assert summary["updated"] == 0
    assert summary["skipped_reviewed"] == 1

    media = storage.load_chapter_media_state("novel-1", "1")
    assert media is not None
    assert media["ocr_status"] == "reviewed"
    assert media["ocr_text"] == "Hand reviewed OCR"


@pytest.mark.asyncio
async def test_ingest_ocr_candidates_skips_chapter_without_images(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "Body text", source_key="stub", source_url="https://example.com/novel-1/1")

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.ingest_ocr_candidates("novel-1", "1")

    assert summary["selected"] == 1
    assert summary["updated"] == 0
    assert summary["skipped_no_images"] == 1

    media = storage.load_chapter_media_state("novel-1", "1")
    assert media is not None
    assert media["ocr_required"] is False
    assert media["ocr_status"] == "skipped"
