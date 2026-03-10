from __future__ import annotations

import json
import logging
import shutil
from uuid import uuid4

import pytest

from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.services.translation_service import TranslationService
from novelai.sources.base import SourceAdapter
from tests.conftest import MockTranslationProvider, TESTS_TMP_ROOT


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
