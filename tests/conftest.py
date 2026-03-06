"""Test fixtures and utilities for integration tests."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

from novelai.app.container import Container
from novelai.core.chapter_state import ChapterState
from novelai.glossary.glossary import Glossary
from novelai.providers.base import TranslationProvider
from novelai.services.preferences_service import PreferencesService
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter


class MockTranslationProvider(TranslationProvider):
    """Mock translation provider for testing."""

    def __init__(self, key: str = "mock", model: str = "mock-1.0"):
        super().__init__()
        self._key = key
        self.model = model
        self.call_count = 0
        self.should_fail = False
        self.failure_message = "Mock provider error"

    @property
    def key(self) -> str:
        """Return provider key."""
        return self._key

    async def translate(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """Mock translation that returns a simple transformation."""
        self.call_count += 1

        if self.should_fail:
            raise Exception(self.failure_message)

        # Simple mock translation: add [TRANSLATED] prefix
        return {
            "text": f"[TRANSLATED] {prompt}",
            "metadata": {
                "usage": {
                    "total_tokens": len(prompt.split()),
                },
            },
        }

    def configure(self, **kwargs: Any) -> None:
        """Mock configuration."""
        pass


class MockSourceAdapter(SourceAdapter):
    """Mock source adapter for testing."""

    def __init__(self, source_key: str = "mock_source"):
        self._source_key = source_key
        self.call_count = 0
        self.chapters_data: Dict[str, str] = {}

    @property
    def key(self) -> str:
        """Return source key."""
        return self._source_key

    async def fetch_metadata(self, novel_id: str) -> Dict[str, Any]:
        """Mock metadata fetching."""
        self.call_count += 1
        return {
            "novel_id": novel_id,
            "title": f"Test Novel {novel_id}",
            "translated_title": f"Test 翻訳 {novel_id}",
            "author": "Test Author",
            "chapters": [f"ch{i}" for i in range(1, 4)],
        }

    async def fetch_chapter(self, url: str) -> str:
        """Mock chapter fetching."""
        self.call_count += 1
        if url in self.chapters_data:
            return self.chapters_data[url]
        return f"Test chapter content for {url}"

    def add_chapter(self, url: str, content: str) -> None:
        """Add test chapter content."""
        self.chapters_data[url] = content


class MockGlossary(Glossary):
    """Mock glossary for testing."""

    def __init__(self):
        self.translations = {
            "test": "TEST_TRANSLATED",
            "example": "EXAMPLE_TRANSLATED",
        }

    def translate(self, text: str) -> str:
        """Mock glossary translation."""
        for original, translated in self.translations.items():
            text = text.replace(original, f"{translated}")
        return text

    def add_term(self, term: str, translation: str) -> None:
        """Add a translation term."""
        self.translations[term] = translation


class TestFixture:
    """Test fixture providing isolated test environment."""

    def __init__(self):
        """Initialize test fixture with temporary storage."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)

        # Create services
        self.storage = StorageService(self.data_dir)
        self.cache = TranslationCache()
        self.usage_service = UsageService()
        self.preferences_service = PreferencesService()
        self.settings_service = SettingsService()
        self.translation_service = TranslationService()

        # Create mock components
        self.mock_provider = MockTranslationProvider()
        self.mock_source = MockSourceAdapter()
        self.mock_glossary = MockGlossary()

    def _create_container(self) -> Container:
        """Create a container for the test environment."""
        container = Container()
        # The container is singleton and uses the default services
        # For testing, use the individual services directly
        return container

    def cleanup(self) -> None:
        """Clean up test resources."""
        self.tmpdir.cleanup()

    def add_test_chapters(
        self, novel_id: str, count: int = 5, content_prefix: str = "Chapter"
    ) -> list[str]:
        """Add test chapters to storage."""
        chapter_ids = []
        for i in range(1, count + 1):
            chapter_id = f"ch{i}"
            chapter_ids.append(chapter_id)

            # Save raw chapter
            self.storage.save_chapter(
                novel_id,
                chapter_id,
                f"{content_prefix} {i} content",
                title=f"Chapter {i}",
                source_key="test_source",
            )

            # Save translated chapter
            self.storage.save_translated_chapter(
                novel_id,
                chapter_id,
                f"[TRANSLATED] {content_prefix} {i} content",
                provider="test_provider",
            )

            # Add state
            self.storage.update_chapter_state(novel_id, chapter_id, ChapterState.TRANSLATED)

        return chapter_ids

    def add_test_metadata(self, novel_id: str) -> Dict[str, Any]:
        """Add test metadata to storage."""
        metadata = {
            "novel_id": novel_id,
            "title": f"Test Novel {novel_id}",
            "translated_title": f"Test 翻訳 {novel_id}",
            "author": "Test Author",
            "description": "A test novel",
            "chapters": [f"ch{i}" for i in range(1, 6)],
        }
        self.storage.save_metadata(novel_id, metadata)
        return metadata

    def set_provider_failure(
        self, should_fail: bool = True, message: str = "Test failure"
    ) -> None:
        """Configure mock provider to fail on next call."""
        self.mock_provider.should_fail = should_fail
        self.mock_provider.failure_message = message

    def add_source_chapter(self, url: str, content: str) -> None:
        """Add chapter content to mock source."""
        self.mock_source.add_chapter(url, content)

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about stored data."""
        novels = self.storage.list_novels()
        stats = {
            "novel_count": len(novels),
            "data_dir_size": sum(
                f.stat().st_size
                for f in self.data_dir.rglob("*")
                if f.is_file()
            ),
            "novels": {},
        }

        for novel_id in novels:
            raw_chapters = self.storage.query_chapters(novel_id).count()
            metadata = self.storage.load_metadata(novel_id)
            progress = self.storage.get_scraping_progress(novel_id)

            stats["novels"][novel_id] = {
                "chapters_stored": raw_chapters,
                "metadata_title": metadata.get("title") if metadata else None,
                "progress": progress,
            }

        return stats


class MockPipeline:
    """Mock pipeline for unit testing stages in isolation."""

    def __init__(self):
        """Initialize mock pipeline."""
        self.stages = []
        self.executed_stages: list[str] = []

    def add_stage(self, stage) -> MockPipeline:
        """Add stage to pipeline."""
        self.stages.append(stage)
        return self

    async def run(self, context):
        """Run all stages."""
        for stage in self.stages:
            self.executed_stages.append(stage.__class__.__name__)
            context = await stage.run(context)
        return context

    def reset(self) -> None:
        """Reset execution history."""
        self.executed_stages = []


# Convenience factory functions

def create_test_fixture() -> TestFixture:
    """Create a new isolated test fixture."""
    return TestFixture()


def create_mock_container() -> Container:
    """Create a container with all mocked services."""
    fixture = TestFixture()
    return fixture.container
