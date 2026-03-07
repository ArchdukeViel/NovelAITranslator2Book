from __future__ import annotations

import json
import shutil
from uuid import uuid4

import pytest

from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from tests.conftest import MockTranslationProvider, TESTS_TMP_ROOT


class StubSource(SourceAdapter):
    @property
    def key(self) -> str:
        return "stub"

    async def fetch_metadata(self, url: str) -> dict[str, object]:
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


class UnusedTranslationService:
    pass


@pytest.fixture
def orchestration_env():
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"orchestrator_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    storage = StorageService(data_dir)
    settings = SettingsService(data_dir)
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
