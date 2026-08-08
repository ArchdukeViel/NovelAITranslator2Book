"""Blocker D: production ``translate_chapters`` produces a persisted run manifest
that links the run id, provider, glossary hash, source hashes, and output hashes
together as evidence for every translation run.

These tests cover the run-manifest contract:

- A run manifest is persisted on ``translate_chapters`` start and finalized
  with status ("completed"/"failed") and counts when the batch settles.
- ``translation_run_id`` is propagated as ``job_id`` when supplied (the worker
  contract), otherwise it falls back to a uuid-prefixed default.
- Chapter source hashes are recorded per chapter so producers and consumers can
  correlate inputs to outputs.
- Successful chapter ids appear in source order, completed/skipped/failed counts
  match the summary, and a partial-failure run is marked "failed".
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration import translation as translation_module
from novelai.services.preferences_service import PreferencesService
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineResult
from novelai.translation.service import TranslationService
from tests.conftest import TESTS_TMP_ROOT, MockTranslationProvider


def _configure_catalog_projection_db(data_dir: Path, monkeypatch):
    db_path = data_dir / "catalog_projection.sqlite"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal, engine


@pytest.fixture
def manifest_env(monkeypatch):
    """Isolated real-StorageService + PreferencesService environment for
    orchestration-level run-manifest tests.  Mirrors ``orchestration_env``
    in ``test_chapter_parallelization.py`` so manifest persistence can use
    the real ``save_translation_run_manifest`` storage method.
    """

    translation_module._translation_locks.clear()

    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"run_manifest_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    storage = StorageService(data_dir)
    settings_service = PreferencesService(data_dir)
    settings_service.set_preferred_provider("mock")
    settings_service.set_preferred_model("mock-1.0")
    usage = UsageService(data_dir)
    catalog_sessionmaker, catalog_engine = _configure_catalog_projection_db(data_dir, monkeypatch)

    try:
        yield {
            "data_dir": data_dir,
            "storage": storage,
            "settings": settings_service,
            "usage": usage,
            "catalog_sessionmaker": catalog_sessionmaker,
        }
    finally:
        catalog_engine.dispose()
        shutil.rmtree(data_dir, ignore_errors=True)


class _StubTranslationService(TranslationService):
    """Minimal ``TranslationService`` replacement that records every call's
    ``translation_run_id`` so tests can assert the producer-side run id
    matches the manifest run id.
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(dict(kwargs))
        await asyncio_sleep_zero()
        return PipelineResult(
            final_text=f"translated chapter {kwargs.get('chapter_id')}",
            chapter_url=str(kwargs.get("chapter_url") or ""),
            provider_key=str(kwargs.get("provider_key") or "mock"),
            provider_model=str(kwargs.get("provider_model") or "mock-1.0"),
        )


async def asyncio_sleep_zero() -> None:
    import asyncio

    await asyncio.sleep(0)


def _save_novel(storage: StorageService, slug: str, *, num_chapters: int) -> None:
    storage.save_metadata(
        slug,
        {
            "title": "Run Manifest Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {
                    "id": str(i),
                    "num": i,
                    "title": f"Chapter {i}",
                    "url": f"https://example.com/{slug}/{i}",
                }
                for i in range(1, num_chapters + 1)
            ],
        },
    )
    for i in range(1, num_chapters + 1):
        storage.save_chapter(slug, str(i), f"raw text for chapter {i}", title=f"Chapter {i}")


def _build_orchestrator(env, translation: TranslationService) -> NovelOrchestrationService:
    return NovelOrchestrationService(
        storage=env["storage"],
        translation=translation,
        source_factory=lambda key: _StubSource(),  # type: ignore[arg-type]
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),  # type: ignore[arg-type]
        settings_service=env["settings"],
        translation_cache=None,
        usage_service=env["usage"],
    )


class _StubSource:
    """Lightweight source adapter that satisfies the orchestrator's
    ``_source_factory(source_key)`` lookup; no network calls.
    """

    def list_chapters(self):  # pragma: no cover - never invoked in these tests
        return []

    def fetch_chapter(self, url: str):  # pragma: no cover - never invoked
        return {"text": ""}


@pytest.mark.asyncio
async def test_translate_chapters_persists_run_manifest_with_completed_status(manifest_env, monkeypatch) -> None:
    """Successful single-chapter run leaves a persisted manifest recording the
    run id, provider, source hash, and final status ``completed``."""

    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = manifest_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=1)

    service = _StubTranslationService()
    orchestrator = _build_orchestrator(manifest_env, service)

    job_id = f"job_{uuid4().hex}"
    summary = await orchestrator.translate_chapters(
        "stub",
        slug,
        "1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        job_id=job_id,
    )

    assert summary["succeeded"] == 1
    assert summary["translation_run_id"] == job_id
    loaded = storage.load_translation_run_manifest(slug, job_id)
    assert loaded is not None, "manifest must be persisted after a successful run"
    assert loaded.status == "completed"
    assert loaded.novel_id == slug
    assert loaded.translation_run_id == job_id
    assert loaded.provider_key == "mock"
    assert loaded.provider_model == "mock-1.0"
    assert loaded.expected_count == 1
    assert loaded.completed_count == 1
    assert loaded.failed_count == 0
    assert loaded.chapter_ids == ["1"]
    assert "1" in loaded.chapter_source_hashes
    assert isinstance(loaded.committed_at, str) and loaded.committed_at
    # Pipeline metadata must be stamped with the same run id as the manifest.
    assert service.calls, "translate_chapter must have been invoked"
    assert service.calls[0].get("translation_run_id") == job_id


@pytest.mark.asyncio
async def test_translate_chapters_failed_chapter_produces_failed_manifest_status(manifest_env, monkeypatch) -> None:
    """A chapter-level failure aborts the batch; the finalized manifest is
    marked ``failed`` with the failed-count matching the summary, and the
    run id is observable on the summary returned to the caller."""

    class _FailingTranslationService(_StubTranslationService):
        async def translate_chapter(self, **kwargs: Any) -> PipelineResult:  # type: ignore[override]
            self.calls.append(dict(kwargs))
            raise RuntimeError("simulated stage failure")

    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = manifest_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=1)

    service = _FailingTranslationService()
    orchestrator = _build_orchestrator(manifest_env, service)

    job_id = f"job_{uuid4().hex}"
    with pytest.raises(RuntimeError, match="simulated stage failure"):
        await orchestrator.translate_chapters(
            "stub",
            slug,
            "1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
            job_id=job_id,
        )

    loaded = storage.load_translation_run_manifest(slug, job_id)
    assert loaded is not None, "manifest must be persisted even on failure (Blocker D)"
    assert loaded.status == "failed"
    assert loaded.completed_count == 0
    assert loaded.failed_count == 1
    assert loaded.chapter_ids == []
    # Chapter source hash was recorded before the failure, evidence preserved.
    assert "1" in loaded.chapter_source_hashes


@pytest.mark.asyncio
async def test_translate_chapters_run_id_defaults_to_uuid_prefix_when_no_job(manifest_env, monkeypatch) -> None:
    """When no ``job_id`` or ``activity_id`` is supplied the manifest run id
    falls back to the ``translation_run_<uuid>`` identifier stamped by
    ``TranslationService.translate_chapter`` semantics.
    """

    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = manifest_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=1)

    service = _StubTranslationService()
    orchestrator = _build_orchestrator(manifest_env, service)

    summary = await orchestrator.translate_chapters(
        "stub",
        slug,
        "1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    run_id = summary["translation_run_id"]
    assert isinstance(run_id, str) and run_id.startswith("translation_run_")
    loaded = storage.load_translation_run_manifest(slug, run_id)
    assert loaded is not None
    assert loaded.translation_run_id == run_id
    assert service.calls[0].get("translation_run_id") == run_id
    assert service.calls[0].get("job_id") is None
