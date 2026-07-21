"""Test fixtures and utilities for integration tests."""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState
from novelai.db.model_registry import register_database_models
from novelai.glossary.glossary import Glossary
from novelai.providers.base import TranslationProvider
from novelai.runtime.container import Container
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.storage.service import StorageService
from novelai.translation.service import TranslationService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = Path(__file__).resolve().parent
TESTS_TMP_ROOT = TESTS_ROOT / ".tmp" / "fixtures"
TESTS_RUNTIME_ROOT = TESTS_ROOT / ".tmp" / "runtime"
COLLECTION_RUNTIME_ROOT = TESTS_RUNTIME_ROOT / "collection"


def pytest_configure() -> None:
    """Isolate module-level application bootstrap before test collection.

    Some API test modules import the production ASGI app, whose module-level
    construction initializes filesystem-backed services. Autouse fixtures run
    after collection, so establish the same fail-closed test environment here.
    """
    COLLECTION_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ["NOVEL_LIBRARY_DIR"] = str(COLLECTION_RUNTIME_ROOT)
    os.environ["ENV"] = "test"
    os.environ["STORAGE_BACKEND"] = "filesystem"
    os.environ["WEB_RATE_LIMITER_BACKEND"] = "memory"
    os.environ.pop("ALLOWED_HOSTS", None)
    os.environ.pop("CSRF_TRUSTED_ORIGINS", None)
    os.environ.pop("PROVIDER_GEMINI_API_KEY", None)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("REDIS_URL", None)
    settings.NOVEL_LIBRARY_DIR = COLLECTION_RUNTIME_ROOT
    settings.ENV = "test"
    settings.STORAGE_BACKEND = "filesystem"
    settings.WEB_RATE_LIMITER_BACKEND = "memory"
    settings.ALLOWED_HOSTS = []
    settings.CSRF_TRUSTED_ORIGINS = []
    settings.PROVIDER_DEFAULT = "dummy"
    settings.PROVIDER_GEMINI_API_KEY = None
    settings.DATABASE_URL = None


def _force_remove_tree(path: Path) -> None:
    """Remove a directory tree even when Windows leaves read-only temp paths behind.

    Uses a subprocess with a timeout to prevent indefinite hangs on locked files.
    """
    import sys as _sys

    def on_error(func: Any, target: str, exc_info: Any) -> None:
        with contextlib.suppress(Exception):
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        with contextlib.suppress(Exception):
            func(target)

    try:
        subprocess.run(
            [_sys.executable, "-c",
             f"import shutil; shutil.rmtree(r'{path}', onerror=lambda f, t, e: None)"],
            timeout=10, capture_output=True, check=False,
        )
    except (subprocess.TimeoutExpired, Exception):
        shutil.rmtree(path, onerror=on_error, ignore_errors=True)


def cleanup_test_artifacts(
    project_root: Path = PROJECT_ROOT,
    tests_root: Path = TESTS_ROOT,
    *,
    include_pytest_managed: bool = False,
) -> tuple[list[Path], list[str]]:
    """Remove test-generated cache and temp directories.

    .tmp/runtime/ is intentionally NOT cleaned here. It's recreated each
    session by isolate_tests_from_runtime_library and may contain locked
    files on Windows that cause indefinite hangs during session teardown.
    """
    removed: list[Path] = []
    warnings: list[str] = []
    extra_test_output_roots = (
        project_root / ".pipeline_test_runs",
        project_root / ".pipeline_verify",
        project_root / ".pytest_tmp",
        tests_root / ".cache",
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
    runtime_container._preferences = None
    runtime_container._usage = None
    runtime_container._translation = None
    runtime_container._export = None
    runtime_container._orchestrator = None
    runtime_container._auth_email = None


@pytest.fixture(scope="session", autouse=True)
def auto_cleanup_test_outputs() -> Iterator[None]:
    """Clean test-generated filesystem output before and after the test session."""
    cleanup_test_artifacts(include_pytest_managed=True)
    yield
    cleanup_test_artifacts(include_pytest_managed=True)


@pytest.fixture(scope="session", autouse=True)
def register_orm_models() -> None:
    """Register all ORM models with SQLAlchemy before any test runs.

    Replaces scattered side-effect imports of individual model modules.
    """
    register_database_models()


@pytest.fixture(scope="session", autouse=True)
def isolate_tests_from_runtime_library() -> Iterator[None]:
    """Route any implicit runtime writes into a disposable test library."""
    TESTS_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    runtime_dir = TESTS_RUNTIME_ROOT / f"session_{uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)

    previous_novel_library_dir = settings.NOVEL_LIBRARY_DIR
    previous_provider_default = settings.PROVIDER_DEFAULT
    previous_storage_backend = settings.STORAGE_BACKEND
    previous_rate_limiter_backend = settings.WEB_RATE_LIMITER_BACKEND
    previous_allowed_hosts = settings.ALLOWED_HOSTS
    previous_csrf_trusted_origins = settings.CSRF_TRUSTED_ORIGINS
    previous_gemini_api_key = settings.PROVIDER_GEMINI_API_KEY
    previous_database_url = settings.DATABASE_URL
    previous_env_novel_library = os.environ.get("NOVEL_LIBRARY_DIR")
    previous_env_storage_backend = os.environ.get("STORAGE_BACKEND")
    previous_env_rate_limiter_backend = os.environ.get("WEB_RATE_LIMITER_BACKEND")
    previous_env_allowed_hosts = os.environ.get("ALLOWED_HOSTS")
    previous_env_csrf_trusted_origins = os.environ.get("CSRF_TRUSTED_ORIGINS")
    previous_env_gemini_api_key = os.environ.get("PROVIDER_GEMINI_API_KEY")
    previous_env_database_url = os.environ.get("DATABASE_URL")
    previous_env = os.environ.get("ENV")
    previous_settings_env = settings.ENV

    os.environ["NOVEL_LIBRARY_DIR"] = str(runtime_dir)
    os.environ["ENV"] = "test"
    os.environ["STORAGE_BACKEND"] = "filesystem"
    os.environ["WEB_RATE_LIMITER_BACKEND"] = "memory"
    os.environ.pop("ALLOWED_HOSTS", None)
    os.environ.pop("CSRF_TRUSTED_ORIGINS", None)
    os.environ.pop("PROVIDER_GEMINI_API_KEY", None)
    os.environ.pop("DATABASE_URL", None)

    settings.NOVEL_LIBRARY_DIR = runtime_dir
    settings.ENV = "test"
    settings.STORAGE_BACKEND = "filesystem"
    settings.WEB_RATE_LIMITER_BACKEND = "memory"
    settings.ALLOWED_HOSTS = []
    settings.CSRF_TRUSTED_ORIGINS = []
    settings.PROVIDER_DEFAULT = "dummy"
    settings.PROVIDER_GEMINI_API_KEY = None
    settings.DATABASE_URL = None
    _reset_global_container()

    try:
        yield
    finally:
        _reset_global_container()
        settings.NOVEL_LIBRARY_DIR = previous_novel_library_dir
        settings.ENV = previous_settings_env
        settings.STORAGE_BACKEND = previous_storage_backend
        settings.WEB_RATE_LIMITER_BACKEND = previous_rate_limiter_backend
        settings.ALLOWED_HOSTS = previous_allowed_hosts
        settings.CSRF_TRUSTED_ORIGINS = previous_csrf_trusted_origins
        settings.PROVIDER_DEFAULT = previous_provider_default
        settings.PROVIDER_GEMINI_API_KEY = previous_gemini_api_key
        settings.DATABASE_URL = previous_database_url

        if previous_env_novel_library is None:
            os.environ.pop("NOVEL_LIBRARY_DIR", None)
        else:
            os.environ["NOVEL_LIBRARY_DIR"] = previous_env_novel_library

        if previous_env_storage_backend is None:
            os.environ.pop("STORAGE_BACKEND", None)
        else:
            os.environ["STORAGE_BACKEND"] = previous_env_storage_backend

        if previous_env_rate_limiter_backend is None:
            os.environ.pop("WEB_RATE_LIMITER_BACKEND", None)
        else:
            os.environ["WEB_RATE_LIMITER_BACKEND"] = previous_env_rate_limiter_backend

        if previous_env_allowed_hosts is None:
            os.environ.pop("ALLOWED_HOSTS", None)
        else:
            os.environ["ALLOWED_HOSTS"] = previous_env_allowed_hosts

        if previous_env_csrf_trusted_origins is None:
            os.environ.pop("CSRF_TRUSTED_ORIGINS", None)
        else:
            os.environ["CSRF_TRUSTED_ORIGINS"] = previous_env_csrf_trusted_origins

        if previous_env_gemini_api_key is None:
            os.environ.pop("PROVIDER_GEMINI_API_KEY", None)
        else:
            os.environ["PROVIDER_GEMINI_API_KEY"] = previous_env_gemini_api_key

        if previous_env_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_env_database_url

        if previous_env is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = previous_env

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
        self.source_key = source_key
        self.call_count = 0
        self.chapters_data: dict[str, str] = {}

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

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
        self.settings_service = PreferencesService(self.data_dir)

        # Create mock components
        self.mock_provider = MockTranslationProvider()
        self.mock_source = MockSourceAdapter()
        self.mock_glossary = MockGlossary()
        self.translation_service = self._create_translation_service()
        self.container = self._create_container()

    def _create_translation_service(self) -> TranslationService:
        """Create a translation service wired to fixture mocks."""
        from novelai.translation.pipeline.pipeline import TranslationPipeline
        from novelai.translation.pipeline.stages.fetch import FetchStage
        from novelai.translation.pipeline.stages.parse import ParseStage
        from novelai.translation.pipeline.stages.post_process import PostProcessStage
        from novelai.translation.pipeline.stages.segment import SmartSegmentStage
        from novelai.translation.pipeline.stages.translate import TranslateStage
        from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage

        pipeline = TranslationPipeline(
            stages=[
                FetchStage(),
                ParseStage(),
                SmartSegmentStage(),
                TranslateStage(
                    provider_factory=lambda key: self.mock_provider,
                    cache=self.cache,
                    settings_service=self.settings_service,
                    usage_service=self.usage_service,
                    storage=self.storage,
                ),
                TranslationQAStage(),
                PostProcessStage(glossary=self.mock_glossary),
            ]
        )
        return TranslationService(pipeline=pipeline)

    def _create_container(self) -> Container:
        """Create a container for the test environment."""
        return Container(
            _storage=self.storage,
            _translation_cache=self.cache,
            _preferences=self.settings_service,
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
        TESTS_ROOT / ".pytest_cache",
    ]

    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                print(f"✓ Cleaned up: {cache_dir}")
            except Exception as e:
                print(f"⚠ Could not clean {cache_dir}: {e}")
