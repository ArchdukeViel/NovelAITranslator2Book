from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.admin import router as admin_router
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session
from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.services.cache.translation_cache import CacheEntry, TranslationCacheService, make_cache_key
from novelai.services.glossary_repository import GlossaryRepository
from novelai.translation.pipeline.context import PipelineContext
from novelai.translation.pipeline.stages.translate import TranslateStage

_TMP = Path(__file__).resolve().parent / ".tmp" / "advanced_caching"


@pytest.fixture()
def cache_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    yield d
    # Clean up
    try:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


class TestCacheKey:
    def test_make_cache_key_deterministic_and_unique(self) -> None:
        key1 = make_cache_key("hello", "ja", "en", "hash1")
        key2 = make_cache_key("hello", "ja", "en", "hash1")
        assert key1 == key2
        assert len(key1) == 64

        # Changing any field changes the key
        assert make_cache_key("hello2", "ja", "en", "hash1") != key1
        assert make_cache_key("hello", "zh", "en", "hash1") != key1
        assert make_cache_key("hello", "ja", "fr", "hash1") != key1
        assert make_cache_key("hello", "ja", "en", "hash2") != key1


class TestTranslationCacheService:
    def test_get_returns_none_on_miss(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        assert service.get("nonexistent") is None

    def test_set_and_get(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        entry = CacheEntry(
            key="testkey",
            source_text="hello",
            translated_text="こんにちは",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=datetime.now(UTC).isoformat(),
            ttl_seconds=0,
            novel_id="novel1",
        )
        service.set("testkey", entry)
        retrieved = service.get("testkey")
        assert retrieved is not None
        assert retrieved.translated_text == "こんにちは"
        assert retrieved.novel_id == "novel1"

    def test_ttl_expiry(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        # Expired entry
        entry = CacheEntry(
            key="expiredkey",
            source_text="hello",
            translated_text="こんにちは",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=(datetime.now(UTC) - timedelta(seconds=10)).isoformat(),
            ttl_seconds=5,
        )
        service.set("expiredkey", entry)
        assert service.get("expiredkey") is None

        # Non-expired entry
        entry2 = CacheEntry(
            key="validkey",
            source_text="hello",
            translated_text="こんにちは",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=datetime.now(UTC).isoformat(),
            ttl_seconds=100,
        )
        service.set("validkey", entry2)
        assert service.get("validkey") is not None

    def test_cache_disabled(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        entry = CacheEntry(
            key="testkey",
            source_text="hello",
            translated_text="こんにちは",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=datetime.now(UTC).isoformat(),
            ttl_seconds=0,
        )

        original_enabled = settings.TRANSLATION_CACHE_ENABLED
        try:
            settings.TRANSLATION_CACHE_ENABLED = False
            service.set("testkey", entry)
            assert service.get("testkey") is None
        finally:
            settings.TRANSLATION_CACHE_ENABLED = original_enabled

    def test_invalidate_by_novel_id(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        entry1 = CacheEntry(
            key="key1",
            source_text="hello",
            translated_text="こんにちは",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=datetime.now(UTC).isoformat(),
            novel_id="novel1",
        )
        entry2 = CacheEntry(
            key="key2",
            source_text="world",
            translated_text="世界",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=datetime.now(UTC).isoformat(),
            novel_id="novel2",
        )
        service.set("key1", entry1)
        service.set("key2", entry2)

        assert service.get("key1") is not None
        assert service.get("key2") is not None

        # Invalidate novel1
        count = service.invalidate("novel1")
        assert count == 1
        assert service.get("key1") is None
        assert service.get("key2") is not None

    def test_stats(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        assert service.stats()["hits"] == 0
        assert service.stats()["misses"] == 0

        service.get("nonexistent")
        assert service.stats()["misses"] == 1

        entry = CacheEntry(
            key="key1",
            source_text="hello",
            translated_text="こんにちは",
            source_language="en",
            target_language="ja",
            glossary_hash="hash1",
            provider_key="dummy",
            provider_model="dummy",
            created_at=datetime.now(UTC).isoformat(),
        )
        service.set("key1", entry)
        service.get("key1")
        assert service.stats()["hits"] == 1
        assert service.stats()["total_entries"] == 1
        assert service.stats()["total_size_bytes"] > 0

    def test_eviction(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)
        original_max = settings.TRANSLATION_CACHE_MAX_ENTRIES
        try:
            settings.TRANSLATION_CACHE_MAX_ENTRIES = 2
            for i in range(3):
                entry = CacheEntry(
                    key=f"key{i}",
                    source_text=f"text{i}",
                    translated_text=f"trans{i}",
                    source_language="en",
                    target_language="ja",
                    glossary_hash="hash1",
                    provider_key="dummy",
                    provider_model="dummy",
                    created_at=datetime.now(UTC).isoformat(),
                )
                service.set(f"key{i}", entry)
                # Sleep briefly to ensure distinct mtimes
                import time
                time.sleep(0.01)

            # The oldest entry (key0) should be evicted
            assert service.get("key0") is None
            assert service.get("key1") is not None
            assert service.get("key2") is not None
        finally:
            settings.TRANSLATION_CACHE_MAX_ENTRIES = original_max


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_translate_stage_cache_hit_and_miss(self, cache_dir: Path) -> None:
        service = TranslationCacheService(cache_dir=cache_dir)

        # Mock provider factory
        class MockProvider:
            key = "mock"
            def available_models(self):
                return ["mock-model"]
            async def translate(self, prompt, model, request=None):
                return {"text": "translated: " + prompt, "metadata": {}}

        def mock_provider_factory(key):
            return MockProvider()

        # Mock storage so persisted chunk states don't short-circuit the cache check
        from unittest.mock import MagicMock

        from novelai.storage.service import StorageService
        mock_storage = MagicMock(spec=StorageService)
        mock_storage.load_chunk_states.return_value = []
        mock_storage.read_translation_output.return_value = []
        mock_storage.load_scheduler_state.return_value = None

        stage = TranslateStage(
            provider_factory=mock_provider_factory,
            cache_service=service,
            storage=mock_storage,
        )

        context = PipelineContext(
            chapter_url="https://example.com/chapter1",
            novel_id="novel123",
            chapter_id="chapter1",
            provider_key="mock",
            provider_model="mock-model",
        )
        context.chunks = ["hello"]

        # First run: cache miss
        res_context = await stage.run(context)
        assert res_context.translations == ["translated: hello"]
        assert service.stats()["hits"] == 0
        assert service.stats()["misses"] == 1

        # Second run: cache hit
        context2 = PipelineContext(
            chapter_url="https://example.com/chapter1",
            novel_id="novel123",
            chapter_id="chapter1",
            provider_key="mock",
            provider_model="mock-model",
        )
        context2.chunks = ["hello"]
        res_context2 = await stage.run(context2)
        assert res_context2.translations == ["translated: hello"]
        assert service.stats()["hits"] == 1


class TestGlossaryInvalidation:
    def test_glossary_update_invalidates_cache(self, cache_dir: Path) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
        session = Session()

        try:
            # Create novel
            novel = Novel(slug="test-novel", title="Test Novel", language="ja", status="ongoing")
            session.add(novel)
            session.flush()

            # Set up cache service
            service = TranslationCacheService(cache_dir=cache_dir)
            entry = CacheEntry(
                key="key1",
                source_text="hello",
                translated_text="こんにちは",
                source_language="en",
                target_language="ja",
                glossary_hash="hash1",
                provider_key="dummy",
                provider_model="dummy",
                created_at=datetime.now(UTC).isoformat(),
                novel_id=str(novel.id),
            )
            service.set("key1", entry)
            assert service.get("key1") is not None

            # Mock GlossaryService invalidation call via GlossaryRepository
            repo = GlossaryRepository(session)

            # Patch TranslationCacheService in GlossaryService to use our test cache_dir
            original_init = TranslationCacheService.__init__
            def patched_init(self_service, *args, **kwargs):
                kwargs.setdefault("cache_dir", cache_dir)
                original_init(self_service, *args, **kwargs)

            TranslationCacheService.__init__ = patched_init
            try:
                # Create an approved glossary entry, which increments revision and invalidates cache
                repo.create_glossary_entry(
                    novel_id=novel.id,
                    canonical_term="term",
                    term_type="other",
                    status="approved",
                )
                session.commit()
            finally:
                TranslationCacheService.__init__ = original_init

            # Cache should be invalidated
            assert service.get("key1") is None

        finally:
            session.close()
            Base.metadata.drop_all(engine)


class TestManualInvalidationEndpoint:
    def test_manual_invalidation_endpoint(self, cache_dir: Path) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
        db_session = Session()

        try:
            app = FastAPI()
            app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
            current: dict = {"user": SessionUser(user_id=None, email=None, role="guest")}

            def _user_override():
                return current["user"]

            def _db_override():
                yield db_session

            app.dependency_overrides[get_current_user] = _user_override
            app.dependency_overrides[get_db_session] = _db_override
            app.state.current_user = current
            app.include_router(auth_router)
            app.include_router(admin_router, prefix="/api")

            # Set up cache service
            service = TranslationCacheService(cache_dir=cache_dir)
            entry = CacheEntry(
                key="key1",
                source_text="hello",
                translated_text="こんにちは",
                source_language="en",
                target_language="ja",
                glossary_hash="hash1",
                provider_key="dummy",
                provider_model="dummy",
                created_at=datetime.now(UTC).isoformat(),
                novel_id="novel123",
            )
            service.set("key1", entry)
            assert service.get("key1") is not None

            # Patch TranslationCacheService to use our test cache_dir
            original_init = TranslationCacheService.__init__
            def patched_init(self_service, *args, **kwargs):
                kwargs.setdefault("cache_dir", cache_dir)
                original_init(self_service, *args, **kwargs)

            TranslationCacheService.__init__ = patched_init
            try:
                client = TestClient(app, raise_server_exceptions=True)
                # Authenticate as owner
                current["user"] = SessionUser(user_id=1, email="owner@example.com", role="owner")
                # Get CSRF token
                token_resp = client.get("/api/auth/csrf")
                csrf_token = token_resp.json()["csrf_token"]
                response = client.post(
                    "/api/admin/novels/novel123/cache/invalidate",
                    headers={"X-CSRF-Token": csrf_token},
                )
                assert response.status_code == 200
                assert response.json() == {"status": "success", "invalidated": 1}
            finally:
                TranslationCacheService.__init__ = original_init

            # Cache should be invalidated
            assert service.get("key1") is None

        finally:
            db_session.close()
            Base.metadata.drop_all(engine)
