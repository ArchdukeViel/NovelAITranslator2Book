"""Test fixtures and utilities for integration tests."""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from novelai.runtime.container import Container
from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState
from novelai.glossary.glossary import Glossary
from novelai.providers.base import TranslationProvider
from novelai.services.preferences_service import PreferencesService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = Path(__file__).resolve().parent
TESTS_TMP_ROOT = TESTS_ROOT / ".tmp" / "fixtures"
TESTS_RUNTIME_ROOT = TESTS_ROOT / ".tmp" / "runtime"


def _force_remove_tree(path: Path) -> None:
    """Remove a directory tree even when Windows leaves read-only temp paths behind."""

    def on_error(func: Any, target: str, exc_info: Any) -> None:
        with contextlib.suppress(Exception):
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        func(target)

    shutil.rmtree(path, onerror=on_error)


def cleanup_test_artifacts(
    project_root: Path = PROJECT_ROOT,
    tests_root: Path = TESTS_ROOT,
    *,
    include_pytest_managed: bool = False,
) -> tuple[list[Path], list[str]]:
    """Remove test-generated cache and temp directories."""
    removed: list[Path] = []
    warnings: list[str] = []
    extra_test_output_roots = (
        project_root / ".pipeline_test_runs",
        project_root / ".pipeline_verify",
        project_root / ".pytest_tmp",
        tests_root / ".cache",
        tests_root / ".tmp" / "runtime",
    )

    paths_to_remove = [
        project_root / ".pytest_cache",
        tests_root / ".tmp" / "fixtures",
        project_root / "tests_tmp",
    ]
    if include_pytest_managed:
        paths_to_remove.extend(
            [
                tests_root / ".pytest_cache",
                tests_root / ".tmp",
            ]
        )

    for path in paths_to_remove:
        if not path.exists():
            continue
        try:
            _force_remove_tree(path)
            removed.append(path)
        except Exception as exc:
            warnings.append(f"{path}: {exc}")

    for path in project_root.glob("pytest-cache-files-*"):
        if not path.is_dir():
            continue
        try:
            _force_remove_tree(path)
            removed.append(path)
        except Exception as exc:
            warnings.append(f"{path}: {exc}")

    for path in extra_test_output_roots:
        if not path.exists():
            continue
        try:
            _force_remove_tree(path)
            removed.append(path)
        except Exception as exc:
            warnings.append(f"{path}: {exc}")

    return removed, warnings


def _reset_global_container() -> None:
    """Clear cached singletons on the shared runtime container."""
    from novelai.runtime.container import container as runtime_container

    runtime_container._storage = None
    runtime_container._translation_cache = None
    runtime_container._settings = None
    runtime_container._preferences = None
    runtime_container._usage = None
    runtime_container._translation = None
    runtime_container._export = None
    runtime_container._orchestrator = None


@pytest.fixture(scope="session", autouse=True)
def auto_cleanup_test_outputs() -> Iterator[None]:
    """Clean test-generated filesystem output before and after the test session."""
    cleanup_test_artifacts(include_pytest_managed=True)
    yield
    cleanup_test_artifacts(include_pytest_managed=True)


@pytest.fixture(scope="session", autouse=True)
def isolate_tests_from_runtime_library() -> Iterator[None]:
    """Route any implicit runtime writes into a disposable test library."""
    TESTS_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    runtime_dir = TESTS_RUNTIME_ROOT / f"session_{uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)

    previous_data_dir = settings.NOVEL_LIBRARY_DIR
    previous_provider_default = settings.PROVIDER_DEFAULT
    previous_api_key = settings.PROVIDER_OPENAI_API_KEY
    previous_env_novel_library = os.environ.get("NOVEL_LIBRARY_DIR")
    previous_env_data_dir = os.environ.get("DATA_DIR")
    previous_env_api_key = os.environ.get("PROVIDER_OPENAI_API_KEY")

    os.environ["NOVEL_LIBRARY_DIR"] = str(runtime_dir)
    os.environ["DATA_DIR"] = str(runtime_dir)
    os.environ.pop("PROVIDER_OPENAI_API_KEY", None)

    settings.NOVEL_LIBRARY_DIR = runtime_dir
    settings.PROVIDER_DEFAULT = "dummy"
    settings.PROVIDER_OPENAI_API_KEY = None
    _reset_global_container()

    try:
        yield
    finally:
        _reset_global_container()
        settings.NOVEL_LIBRARY_DIR = previous_data_dir
        settings.PROVIDER_DEFAULT = previous_provider_default
        settings.PROVIDER_OPENAI_API_KEY = previous_api_key

        if previous_env_novel_library is None:
            os.environ.pop("NOVEL_LIBRARY_DIR", None)
        else:
            os.environ["NOVEL_LIBRARY_DIR"] = previous_env_novel_library

        if previous_env_data_dir is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = previous_env_data_dir

        if previous_env_api_key is None:
            os.environ.pop("PROVIDER_OPENAI_API_KEY", None)
        else:
            os.environ["PROVIDER_OPENAI_API_KEY"] = previous_env_api_key

        if runtime_dir.exists():
            _force_remove_tree(runtime_dir)


class MockTranslationProvider(TranslationProvider):
    """Mock translation provider for testing."""

    def __init__(self, key: str = "mock", model: str = "mock-1.0") -> None:
        super().__init__()
        self._key = key
        self.model = model
        self.call_count = 0
        self.last_request = None
        self.should_fail = False
        self.failure_message = "Mock provider error"

    @property
    def key(self) -> str:
        """Return provider key."""
        return self._key

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Mock translation that returns a simple transformation."""
        self.call_count += 1

        if self.should_fail:
            raise Exception(self.failure_message)

        # Simple mock translation: add [TRANSLATED] prefix
        self.last_request = kwargs.get("request")
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

    def __init__(self, source_key: str = "mock_source") -> None:
        self._source_key = source_key
        self.call_count = 0
        self.chapters_data: dict[str, str] = {}

    @property
    def key(self) -> str:
        """Return source key."""
        return self._source_key

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        """Mock metadata fetching."""
        self.call_count += 1
        novel_id = url
        return {
            "novel_id": novel_id,
            "title": f"Test Novel {novel_id}",
            "translated_title": f"Test 翻訳 {novel_id}",
            "author": "Test Author",
            "chapters": [
                {
                    "id": str(i),
                    "title": f"Chapter {i}",
                    "url": f"http://example.com/{novel_id}/{i}",
                }
                for i in range(1, 4)
            ],
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

    def __init__(self) -> None:
        self.translations = {
            "test": "TEST_TRANSLATED",
            "example": "EXAMPLE_TRANSLATED",
        }

    def translate(self, text: str) -> str:
        """Mock glossary translation."""
        for original, translated in self.translations.items():
            text = text.replace(original, f"{translated}")
        return text

    def add_term(
        self,
        source: str,
        target: str,
        notes: str | None = None,
        *,
        locked: bool = True,
    ) -> None:
        """Add a translation term."""
        self.translations[source] = target


class TestFixture:
    """Test fixture providing isolated test environment."""

    def __init__(self) -> None:
        """Initialize test fixture with temporary storage."""
        TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.data_dir = TESTS_TMP_ROOT / f"fixture_{uuid4().hex}"
        self.data_dir.mkdir(parents=True, exist_ok=False)

        # Create services
        self.storage = StorageService(self.data_dir)
        self.cache = TranslationCache(self.data_dir)
        self.usage_service = UsageService(self.data_dir)
        self.preferences_service = PreferencesService(self.data_dir)
        self.settings_service = PreferencesService(self.data_dir)

        # Create mock components
        self.mock_provider = MockTranslationProvider()
        self.mock_source = MockSourceAdapter()
        self.mock_glossary = MockGlossary()
        self.translation_service = self._create_translation_service()
        self.container = self._create_container()

    def _create_translation_service(self) -> TranslationService:
        """Create a translation service wired to fixture mocks."""
        from novelai.pipeline.pipeline import TranslationPipeline
        from novelai.pipeline.stages.fetch import FetchStage
        from novelai.pipeline.stages.parse import ParseStage
        from novelai.pipeline.stages.post_process import PostProcessStage
        from novelai.pipeline.stages.segment import SegmentStage
        from novelai.pipeline.stages.translate import TranslateStage

        pipeline = TranslationPipeline(
            stages=[
                FetchStage(),
                ParseStage(),
                SegmentStage(),
                TranslateStage(
                    provider_factory=lambda key: self.mock_provider,
                    cache=self.cache,
                    settings_service=self.settings_service,
                    usage_service=self.usage_service,
                ),
                PostProcessStage(glossary=self.mock_glossary),
            ]
        )
        return TranslationService(pipeline=pipeline)

    def _create_container(self) -> Container:
        """Create a container for the test environment."""
        return Container(
            _storage=self.storage,
            _translation_cache=self.cache,
            _settings=self.settings_service,
            _preferences=self.preferences_service,
            _usage=self.usage_service,
            _translation=self.translation_service,
        )

    def cleanup(self) -> None:
        """Clean up test resources."""
        shutil.rmtree(self.data_dir, ignore_errors=True)

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

    def add_test_metadata(self, novel_id: str) -> dict[str, Any]:
        """Add test metadata to storage."""
        metadata = {
            "novel_id": novel_id,
            "title": f"Test Novel {novel_id}",
            "translated_title": f"Test 翻訳 {novel_id}",
            "author": "Test Author",
            "description": "A test novel",
            "chapters": [
                {
                    "id": str(i),
                    "title": f"Chapter {i}",
                    "url": f"http://example.com/{novel_id}/{i}",
                }
                for i in range(1, 6)
            ],
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

    def get_storage_stats(self) -> dict[str, Any]:
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

    def __init__(self) -> None:
        """Initialize mock pipeline."""
        self.stages = []
        self.executed_stages: list[str] = []

    def add_stage(self, stage: object) -> MockPipeline:
        """Add stage to pipeline."""
        self.stages.append(stage)
        return self

    async def run(self, context: Any) -> Any:
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


# Auto-cleanup fixture

@pytest.fixture(scope="session", autouse=True)
def cleanup_pytest_cache():
    """Auto-clean pytest cache artifacts after all tests complete."""
    yield
    removed, warnings = cleanup_test_artifacts()
    for path in removed:
        print(f"cleaned: {path}")
    for warning in warnings:
        print(f"cleanup-warning: {warning}")
    return

    # Cleanup after all tests finish
    cache_dirs = [
        Path(".pytest_cache"),
        Path("tests/.pytest_cache"),
    ]

    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                print(f"✓ Cleaned up: {cache_dir}")
            except Exception as e:
                print(f"⚠ Could not clean {cache_dir}: {e}")

