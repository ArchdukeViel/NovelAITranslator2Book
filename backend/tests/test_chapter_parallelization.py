"""Tests for chapter-level parallelization in translation orchestration.

These tests cover REQ-1 through REQ-4 of the chapter-parallelization spec:
- REQ-1.1..REQ-1.4: bounded concurrency via TRANSLATION_CHAPTER_CONCURRENCY
- REQ-3.3:        per-chapter progress reporting in the orchestrator summary
- REQ-4.1..REQ-4.4: deterministic test coverage for the four guarantees
  (concurrent execution, stable output ordering, partial-failure isolation,
  sequential behaviour when concurrency is 1).
"""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineResult
from novelai.translation.service import TranslationService

from tests.conftest import MockTranslationProvider, TESTS_TMP_ROOT
from tests.test_novel_orchestration_service import StubSource


def _configure_catalog_projection_db(data_dir: Path, monkeypatch):
    db_path = data_dir / "catalog_projection.sqlite"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal, engine


@pytest.fixture
def orchestration_env(monkeypatch):
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"orchestrator_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    storage = StorageService(data_dir)
    settings_service = PreferencesService(data_dir)
    settings_service.set_provider_key("mock")
    settings_service.set_provider_model("mock-1.0")
    cache = TranslationCache(data_dir)
    usage = UsageService(data_dir)
    catalog_sessionmaker, catalog_engine = _configure_catalog_projection_db(data_dir, monkeypatch)

    try:
        yield {
            "data_dir": data_dir,
            "storage": storage,
            "settings": settings_service,
            "cache": cache,
            "usage": usage,
            "catalog_sessionmaker": catalog_sessionmaker,
        }
    finally:
        catalog_engine.dispose()
        shutil.rmtree(data_dir, ignore_errors=True)


class _TimingTranslationService(TranslationService):
    """Translation service stub that records per-chapter start/end times.

    - ``sleep_seconds`` is applied to every chapter so concurrent tests
      can observe overlapping windows.
    - ``fail_chapter_id`` causes the named chapter to raise ``RuntimeError``
      after its sleep; the rest of the chapters succeed.
    - ``per_chapter_delay`` overrides the global sleep for a specific chapter
      (used to make early chapters finish later than later ones).
    """

    def __init__(
        self,
        *,
        sleep_seconds: float = 0.1,
        fail_chapter_id: str | None = None,
        per_chapter_delay: dict[str, float] | None = None,
    ) -> None:
        self.sleep_seconds = sleep_seconds
        self.fail_chapter_id = fail_chapter_id
        self.per_chapter_delay: dict[str, float] = dict(per_chapter_delay or {})
        self.calls: list[dict[str, Any]] = []
        self.start_times: dict[str, float] = {}
        self.end_times: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        chapter_id = str(kwargs.get("chapter_id") or "")
        async with self._lock:
            self.calls.append(kwargs)
            self.start_times[chapter_id] = time.perf_counter()
        try:
            delay = self.per_chapter_delay.get(chapter_id, self.sleep_seconds)
            if delay > 0:
                await asyncio.sleep(delay)
            if self.fail_chapter_id and chapter_id == self.fail_chapter_id:
                raise RuntimeError(f"simulated failure for chapter {chapter_id}")
            return PipelineResult(
                final_text=f"translated chapter {chapter_id}",
                chapter_url=str(kwargs.get("chapter_url") or ""),
                provider_key=str(kwargs.get("provider_key") or "mock"),
                provider_model=str(kwargs.get("provider_model") or "mock-1.0"),
            )
        finally:
            async with self._lock:
                self.end_times[chapter_id] = time.perf_counter()


def _save_novel(storage, slug: str, *, num_chapters: int) -> None:
    storage.save_metadata(
        slug,
        {
            "title": "Parallel Test Novel",
            "source": "stub",
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
    storage = env["storage"]
    return NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=env["settings"],
        translation_cache=env["cache"],
        usage_service=env["usage"],
    )


@pytest.mark.asyncio
async def test_chapter_translations_run_concurrently_when_concurrency_above_one(
    orchestration_env, monkeypatch
) -> None:
    """REQ-4.1: with concurrency > 1, chapters overlap in wall time."""
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    monkeypatch.setattr(settings, "TRANSLATION_CHAPTER_CONCURRENCY", 3)
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=3)
    service = _TimingTranslationService(sleep_seconds=0.2)
    orchestrator = _build_orchestrator(orchestration_env, service)

    summary = await orchestrator.translate_chapters(
        "stub",
        slug,
        "1;2;3",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    assert summary["succeeded"] == 3
    assert summary["failed"] == 0
    starts = [service.start_times[cid] for cid in ("1", "2", "3")]
    ends = [service.end_times[cid] for cid in ("1", "2", "3")]
    overlaps = 0
    for i in range(3):
        for j in range(i + 1, 3):
            if starts[i] < ends[j] and starts[j] < ends[i]:
                overlaps += 1
    assert overlaps >= 1, f"expected overlapping execution, starts={starts} ends={ends}"
    # Wall clock should be one chapter's worth of sleep, not three.
    assert (max(ends) - min(starts)) < 3 * 0.2 + 0.15


@pytest.mark.asyncio
async def test_chapter_translation_output_remains_in_source_order_under_concurrency(
    orchestration_env, monkeypatch
) -> None:
    """REQ-4.2: completion order may vary; output is keyed by chapter_id."""
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    monkeypatch.setattr(settings, "TRANSLATION_CHAPTER_CONCURRENCY", 4)
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=4)
    # Chapter 1 is the slowest so chapter 4 finishes first.
    service = _TimingTranslationService(
        sleep_seconds=0.05,
        per_chapter_delay={"1": 0.30, "2": 0.20, "3": 0.10},
    )
    orchestrator = _build_orchestrator(orchestration_env, service)

    summary = await orchestrator.translate_chapters(
        "stub",
        slug,
        "1;2;3;4",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    # Progress map must be keyed in source order regardless of completion order.
    assert list(summary["chapter_progress"].keys()) == ["1", "2", "3", "4"]
    for cid in ("1", "2", "3", "4"):
        translated = storage.load_translated_chapter(slug, cid)
        assert translated is not None, f"chapter {cid} not stored on disk"
        assert translated["text"] == f"translated chapter {cid}"


@pytest.mark.asyncio
async def test_chapter_failure_does_not_erase_successful_outputs(
    orchestration_env, monkeypatch
) -> None:
    """REQ-4.3: a failure in one chapter does not clobber siblings."""
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    monkeypatch.setattr(settings, "TRANSLATION_CHAPTER_CONCURRENCY", 3)
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=3)
    service = _TimingTranslationService(sleep_seconds=0.05, fail_chapter_id="2")
    orchestrator = _build_orchestrator(orchestration_env, service)

    with pytest.raises(RuntimeError, match="simulated failure for chapter 2"):
        await orchestrator.translate_chapters(
            "stub",
            slug,
            "1;2;3",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )

    # The two non-failing chapters must be persisted before the exception
    # bubbles up to the caller.
    ch1 = storage.load_translated_chapter(slug, "1")
    ch3 = storage.load_translated_chapter(slug, "3")
    assert ch1 is not None and ch1["text"] == "translated chapter 1"
    assert ch3 is not None and ch3["text"] == "translated chapter 3"
    # Chapter 2 must not be persisted (it raised mid-flight).
    assert storage.load_translated_chapter(slug, "2") is None


@pytest.mark.asyncio
async def test_chapter_concurrency_one_runs_sequentially(
    orchestration_env, monkeypatch
) -> None:
    """REQ-4.4: with concurrency = 1, chapters finish in source order, no overlap."""
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    monkeypatch.setattr(settings, "TRANSLATION_CHAPTER_CONCURRENCY", 1)
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    _save_novel(storage, slug, num_chapters=3)
    service = _TimingTranslationService(sleep_seconds=0.1)
    orchestrator = _build_orchestrator(orchestration_env, service)

    summary = await orchestrator.translate_chapters(
        "stub",
        slug,
        "1;2;3",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    assert summary["succeeded"] == 3
    # Sequential: each chapter's end time must be <= the next chapter's start.
    for a, b in (("1", "2"), ("2", "3")):
        assert service.end_times[a] <= service.start_times[b] + 0.01, (
            f"chapter {a} ended at {service.end_times[a]} but chapter {b} "
            f"started at {service.start_times[b]}"
        )
    # Wall clock must be at least the sum of the per-chapter sleeps.
    wall_time = service.end_times["3"] - service.start_times["1"]
    assert wall_time >= 3 * 0.1 - 0.02
