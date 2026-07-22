from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL, settings
from novelai.core.chapter_state import ChapterState
from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedDocument, ImportedUnit
from novelai.providers.base import TranslationProvider
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration import crawler as crawler_module
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineResult, PipelineState, paragraph_source_hash
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.post_process import PostProcessStage
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.service import TranslationService
from tests.conftest import TESTS_TMP_ROOT, MockTranslationProvider


class StubSource(SourceAdapter):
    source_key = "stub"

    def __init__(self) -> None:
        self.requested_max_chapters: list[int | None] = []
        self.chapter_payloads: dict[str, dict[str, object]] = {}
        self.assets: dict[str, dict[str, object]] = {}

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        self.requested_max_chapters.append(max_chapter)
        return {
            "source_key": "syosetu_ncode",
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

    async def fetch_chapter_payload(self, url: str, *, on_retry=None) -> dict[str, object]:
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
        units = (
            ImportedUnit(
                unit_id="1",
                import_order=1,
                title="Part 1",
                text="Hero Aria entered the city.",
                source_ref=str(source),
                unit_type="chapter",
                context_group_id="stub-doc",
            ),
            ImportedUnit(
                unit_id="2",
                import_order=2,
                title="Part 2",
                text="Hero Aria returned.",
                source_ref=str(source),
                unit_type="chapter",
                context_group_id="stub-doc",
            ),
        )
        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file",
            origin_uri_or_path=str(source),
            document_type="text",
            title="Imported Story",
            source_language="Japanese",
            units=units,
        )


class StubTranslationService(TranslationService):
    def __init__(
        self,
        *,
        final_text: str = "translated",
        fail: bool = False,
        paragraph_prefix: str | None = None,
    ) -> None:
        self.final_text = final_text
        self.fail = fail
        self.paragraph_prefix = paragraph_prefix
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("provider failure")
        if self.paragraph_prefix is not None:
            raw_text = str(kwargs.get("raw_text") or "")
            paragraphs = [part.strip() for part in raw_text.split("\n\n") if part.strip()]
            paragraph_map = [
                {
                    "chapter_id": str(kwargs.get("chapter_id") or "1"),
                    "paragraph_id": f"p{index:04d}",
                    "translated_text": f"{self.paragraph_prefix}{part}",
                }
                for index, part in enumerate(paragraphs, start=1)
            ]
            raw = json.dumps(
                {
                    "translated_text": "\n\n".join(item["translated_text"] for item in paragraph_map),
                    "paragraph_map": paragraph_map,
                }
            )
            return PipelineResult(
                final_text="\n\n".join(item["translated_text"] for item in paragraph_map),
                chapter_url=str(kwargs.get("chapter_url") or ""),
                provider_key="mock",
                provider_model="mock-1.0",
                translations=[raw],
                metadata={"raw_provider_translations": [raw]},
            )
        return PipelineResult(
            final_text=self.final_text,
            chapter_url=str(kwargs.get("chapter_url") or ""),
            provider_key="mock",
            provider_model="mock-1.0",
        )


class RuntimeSimulationTranslationService(TranslationService):
    def __init__(self, storage: StorageService, *, fail_chapter_once: str | None = None) -> None:
        self.storage = storage
        self.fail_chapter_once = fail_chapter_once
        self.failed_chapters: set[str] = set()
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(kwargs)
        novel_id = str(kwargs.get("novel_id") or "novel1")
        chapter_id = str(kwargs.get("chapter_id") or "1")
        job_id = kwargs.get("job_id") if isinstance(kwargs.get("job_id"), str) else None
        activity_id = kwargs.get("activity_id") if isinstance(kwargs.get("activity_id"), str) else None
        translation_run_id = job_id or activity_id or f"manual_sim_{len(self.calls):04d}"
        provider_key = str(kwargs.get("provider_key") or "mock")
        provider_model = str(kwargs.get("provider_model") or "mock-1.0")
        chunk_id = "c0001"
        is_failure = self.fail_chapter_once == chapter_id and chapter_id not in self.failed_chapters
        source_text = (
            "[P p0001]\nsmall retry paragraph"
            if not is_failure and chapter_id == self.fail_chapter_once
            else str(kwargs.get("raw_text") or f"[P p0001]\nchapter {chapter_id} full text")
        )
        status = "needs_retry" if is_failure else "translated"
        attempt_number = 2 if is_failure else 1

        self.storage.save_translation_chunks(
            novel_id,
            [
                {
                    "chunk_id": chunk_id,
                    "novel_id": novel_id,
                    "translation_run_id": translation_run_id,
                    "chapter_ids": [chapter_id],
                    "paragraph_ids": ["p0001"],
                    "source_text": source_text,
                    "status": status,
                    "attempt_count": attempt_number,
                    "provider_key": provider_key,
                    "provider_model": provider_model,
                }
            ],
        )
        self.storage.save_chunk_attempt_record(
            {
                "chunk_id": chunk_id,
                "novel_id": novel_id,
                "translation_run_id": translation_run_id,
                "chapter_ids": [chapter_id],
                "paragraph_ids": ["p0001"],
                "attempt_number": attempt_number,
                "provider_key": provider_key,
                "provider_model": provider_model,
                "status": "failed" if is_failure else "succeeded",
                "error_code": "simulated_full_chunk_failure" if is_failure else None,
            }
        )
        chunk_state = {
            "chunk_id": chunk_id,
            "novel_id": novel_id,
            "translation_run_id": translation_run_id,
            "chapter_ids": [chapter_id],
            "paragraph_ids": ["p0001"],
            "provider_key": provider_key,
            "provider_model": provider_model,
            "attempt_number": attempt_number,
            "status": status,
            "error_code": "simulated_full_chunk_failure" if is_failure else None,
        }
        self.storage.upsert_chunk_state(chunk_state)
        event = {
            "job_id": job_id,
            "activity_id": activity_id,
            "translation_run_id": translation_run_id,
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "chunk_id": chunk_id,
            "stage_name": "RuntimeSimulation",
            "status_before": "running",
            "status_after": "failed" if is_failure else "translated",
            "error_code": "simulated_full_chunk_failure" if is_failure else None,
        }
        if is_failure:
            self.failed_chapters.add(chapter_id)
            failed_context = PipelineState(
                chapter_url=str(kwargs.get("chapter_url") or ""),
                job_id=job_id,
                activity_id=activity_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                provider_key=provider_key,
                provider_model=provider_model,
                metadata={"translation_run_id": translation_run_id},
            )
            failed_context.chunk_states[chunk_id] = chunk_state
            failed_context.pipeline_events.append(event)
            error = RuntimeError("simulated full chunk failure")
            error.pipeline_context = failed_context  # type: ignore[attr-defined]
            error.pipeline_events = [event]  # type: ignore[attr-defined]
            error.details = {"chunk_id": chunk_id, "attempt_number": attempt_number}  # type: ignore[attr-defined]
            raise error

        translated = f"translated chapter {chapter_id}"
        self.storage.save_translation_output(
            {
                "output_id": f"{chunk_id}:attempt_{attempt_number:04d}",
                "chunk_id": chunk_id,
                "novel_id": novel_id,
                "translation_run_id": translation_run_id,
                "chapter_ids": [chapter_id],
                "paragraph_ids": ["p0001"],
                "translated_text": translated,
                "provider_key": provider_key,
                "provider_model": provider_model,
                "attempt_number": attempt_number,
                "qa_status": status,
            }
        )
        return PipelineResult(
            final_text=translated,
            chapter_url=str(kwargs.get("chapter_url") or ""),
            job_id=job_id,
            activity_id=activity_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            provider_key=provider_key,
            provider_model=provider_model,
            pipeline_events=[event],
            chunk_states={chunk_id: chunk_state},
            metadata={"translation_run_id": translation_run_id},
        )


class _BootstrapCandidate:
    def __init__(self, source: str, context_summary: str | None = None, notes: str | None = None) -> None:
        self.source = source
        self.context_summary = context_summary
        self.notes = notes


class RunIdCaptureStage(PipelineStage):
    def __init__(self) -> None:
        self.run_ids: list[str] = []

    async def run(self, context: PipelineState) -> PipelineState:
        run_id = context.metadata.get("translation_run_id")
        if isinstance(run_id, str):
            self.run_ids.append(run_id)
        context.final_text = "translated"
        return context


class GlossarySchemaCaptureProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="mock", model="mock-1.0")
        self.last_kwargs: dict[str, Any] = {}

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.last_kwargs = kwargs
        return {
            "text": json.dumps(
                {
                    "terms": [
                        {"source": "魔導具"},
                        {"source": "王都"},
                    ]
                },
                ensure_ascii=False,
            ),
            "metadata": {
                "usage": {
                    "total_tokens": 42,
                },
            },
        }


class PromptInjectionCaptureProvider(TranslationProvider):
    def __init__(self) -> None:
        self.user_prompts: list[str] = []

    @property
    def key(self) -> str:
        return "mock"

    def available_models(self) -> list[str]:
        return ["mock-1.0"]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        request = kwargs.get("request")
        user_prompt = getattr(request, "user_prompt", "") if request is not None else ""
        self.user_prompts.append(str(user_prompt))
        return {
            "text": "[CHAPTER 1]\n[P p0001]\nTranslated Pocott.",
            "metadata": {"usage": {"total_tokens": 3}},
        }


class GeminiFallbackProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="gemini", model=GEMINI_DEFAULT_MODEL)
        self.models_seen: list[str | None] = []

    def available_models(self) -> list[str]:
        return [GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.models_seen.append(model)
        if model == GEMINI_DEFAULT_MODEL:
            raise RuntimeError("quota exceeded")
        source_text = prompt
        if "<source_text>" in prompt and "</source_text>" in prompt:
            source_text = prompt.split("<source_text>", 1)[1].split("</source_text>", 1)[0].strip()
        return {
            "text": f"[{model}] {source_text}",
            "metadata": {
                "usage": {
                    "total_tokens": 11,
                },
            },
        }


class PartialGeminiTitleProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="gemini", model=GEMINI_DEFAULT_MODEL)
        self.models_seen: list[str | None] = []

    def available_models(self) -> list[str]:
        return [GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.models_seen.append(model)
        source_text = prompt
        if "<source_text>" in prompt and "</source_text>" in prompt:
            source_text = prompt.split("<source_text>", 1)[1].split("</source_text>", 1)[0].strip()
        if model == GEMINI_DEFAULT_MODEL and source_text == "第10話　初スカート、お披露目":
            return {"text": "Episode", "metadata": {"usage": {"total_tokens": 3}}}
        if source_text == "第10話　初スカート、お披露目":
            return {"text": "Episode 10: First Skirt Reveal", "metadata": {"usage": {"total_tokens": 8}}}
        return {"text": f"[{model}] {source_text}", "metadata": {"usage": {"total_tokens": 11}}}


class PartialTitleSource(StubSource):
    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        self.requested_max_chapters.append(max_chapter)
        return {
            "source_key": "novel18_syosetu",
            "source_url": f"https://novel18.syosetu.com/{url}/",
            "title": "TS刑事　如月真琴の憂鬱",
            "author": "Ayas_hi",
            "chapters": [
                {
                    "id": "10",
                    "num": 10,
                    "title": "第10話　初スカート、お披露目",
                    "url": f"https://example.com/{url}/10",
                },
            ],
        }


class SynopsisSource(StubSource):
    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        metadata = await super().fetch_metadata(url, max_chapter=max_chapter)
        metadata["synopsis"] = "Original Synopsis"
        return metadata


class BatchMetadataProvider(MockTranslationProvider):
    def __init__(
        self,
        *,
        invalid_batch_json: bool = False,
        omit_ids: set[str] | None = None,
        duplicate_first_id: bool = False,
        fenced_batch_json: bool = False,
        commentary_batch_json: bool = False,
    ) -> None:
        super().__init__(key="mock", model="mock-1.0")
        self.invalid_batch_json = invalid_batch_json
        self.omit_ids = omit_ids or set()
        self.duplicate_first_id = duplicate_first_id
        self.fenced_batch_json = fenced_batch_json
        self.commentary_batch_json = commentary_batch_json
        self.prompts: list[str] = []

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        self.prompts.append(prompt)
        if self.invalid_batch_json and "<metadata_items>" in prompt:
            return {"text": "NOT JSON", "metadata": {"usage": {"total_tokens": 5}}}

        if "<metadata_items>" in prompt:
            payload = json.loads(prompt.split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0].strip())
            items = [
                {"id": item["id"], "translation": f"[TRANSLATED] {item['source_text']}"}
                for item in payload["items"]
                if item["id"] not in self.omit_ids
            ]
            if self.duplicate_first_id and items:
                duplicate = dict(items[0])
                duplicate["translation"] = f"{duplicate['translation']} duplicate"
                items.append(duplicate)
            text = json.dumps({"items": items})
            if self.fenced_batch_json:
                text = f"```json\n{text}\n```"
            if self.commentary_batch_json:
                text = f"Here is the JSON:\n{text}\nDone."
            return {"text": text, "metadata": {"usage": {"total_tokens": 7}}}

        return {"text": f"[TRANSLATED] {prompt}", "metadata": {"usage": {"total_tokens": 3}}}


class FailingMetadataProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="mock", model="mock-1.0")

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        raise RuntimeError("metadata provider failed " + ("x" * 800))


def _configure_catalog_projection_db(data_dir, monkeypatch):
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
    settings = PreferencesService(data_dir)
    settings.set_preferred_provider("mock")
    settings.set_preferred_model("mock-1.0")
    cache = TranslationCache(data_dir)
    usage = UsageService(data_dir)
    catalog_sessionmaker, catalog_engine = _configure_catalog_projection_db(data_dir, monkeypatch)

    try:
        yield {
            "data_dir": data_dir,
            "storage": storage,
            "settings": settings,
            "cache": cache,
            "usage": usage,
            "catalog_sessionmaker": catalog_sessionmaker,
        }
    finally:
        catalog_engine.dispose()
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_scrape_write_paths_refresh_catalog_projection(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    source = StubSource()
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="novel-1").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 0

    await orchestrator.scrape_chapters("syosetu_ncode", "novel-1", "all")
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="novel-1").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 0


@pytest.mark.asyncio
async def test_scrape_metadata_bootstraps_glossary_candidates_nonfatally(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    source = StubSource()
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    result = await orchestrator.scrape_metadata("syosetu_ncode", "bootstrap-novel", mode="update")

    assert result["bootstrap_candidate_count"] > 0
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="bootstrap-novel").one()
        assert novel.glossary_status == "glossary_pending"
        entries = GlossaryRepository(session).list_glossary_entries_for_novel(novel.id)
        assert entries
        assert {entry.status for entry in entries} == {"candidate"}


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.integers(min_value=0, max_value=3))
async def test_scrape_metadata_bootstrap_exception_isolation(orchestration_env, candidate_count: int) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    source = StubSource()
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Bootstrap Exception",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug,
            title="Bootstrap Exception",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch.object(crawler_module, "extract_candidate_glossary_terms", side_effect=RuntimeError("boom")):
        result = await orchestrator.scrape_metadata("syosetu_ncode", slug, mode="update")

    assert result["bootstrap_candidate_count"] == 0
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug=slug).one()
        assert novel.glossary_status == "glossary_skipped"


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.sampled_from(["glossary_ready", "glossary_pending", "glossary_skipped"]))
async def test_bootstrap_invocation_gate(orchestration_env, glossary_status: str) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Bootstrap Gate",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug,
            title="Bootstrap Gate",
            language="ja",
            publication_status="ongoing",
            glossary_status=glossary_status,
        )
        session.add(novel)
        session.commit()

    calls: list[list[str]] = []

    def _extract(texts, max_terms=50):
        calls.append(list(texts))
        return [_BootstrapCandidate("Pocott", "Pocott", "note")]

    source = StubSource()
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch.object(crawler_module, "extract_candidate_glossary_terms", side_effect=_extract):
        result = await crawler_module.bootstrap_glossary_if_needed(orchestrator, slug, {"title": "Bootstrap Gate"})

    if glossary_status == "glossary_ready":
        assert result == 0
        # extract runs before status check — calls populated regardless
    else:
        assert result == 1
        assert calls


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.integers(min_value=1, max_value=3))
async def test_bootstrap_produces_pending_status(orchestration_env, candidate_count: int) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Bootstrap Pending",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug,
            title="Bootstrap Pending",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()

    candidates = [_BootstrapCandidate(f"Term {index}", f"Term {index}", None) for index in range(candidate_count)]

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch.object(crawler_module, "extract_candidate_glossary_terms", return_value=candidates):
        added = await crawler_module.bootstrap_glossary_if_needed(orchestrator, slug, {"title": "Bootstrap Pending"})

    assert added == candidate_count
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug=slug).one()
        assert novel.glossary_status == "glossary_pending"
        entries = GlossaryRepository(session).list_glossary_entries_for_novel(novel.id)
        assert len(entries) == candidate_count


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.sampled_from(["glossary_pending", "glossary_ready", "glossary_skipped"]), st.booleans())
async def test_translate_guard_glossary_gate_properties(
    orchestration_env, glossary_status: str, skip_glossary_gate: bool
) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Guard Novel",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug, title="Guard Novel", language="ja", publication_status="ongoing", glossary_status=glossary_status
        )
        session.add(novel)
        session.flush()
        if glossary_status == "glossary_pending":
            GlossaryRepository(session).create_glossary_entry(
                novel_id=novel.id,
                canonical_term="Pocott",
                term_type="place",
                status="candidate",
            )
        session.commit()

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    issues = orchestrator._preflight_translation(
        novel_id=slug,
        source_key="stub",
        meta={"chapters": [{"id": "1", "title": "Chapter One", "url": f"https://example.com/{slug}/1"}]},
        selected_numbers=[1],
        force=False,
        source_language="Japanese",
        target_language="English",
        glossary=None,
        skip_glossary_gate=skip_glossary_gate,
    )

    gate_issues = [issue for issue in issues if issue.code == "glossary_gate_pending"]
    if glossary_status == "glossary_pending" and not skip_glossary_gate:
        assert len(gate_issues) == 1
        assert gate_issues[0].details is not None
        assert gate_issues[0].details["glossary_status"] == "glossary_pending"
        assert gate_issues[0].details["glossary_pending_count"] == 1
        assert gate_issues[0].details["glossary_review_url"] == f"/admin/novels/{slug}/glossary"
    else:
        assert gate_issues == []


@pytest.mark.asyncio
async def test_import_write_paths_refresh_catalog_projection(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        input_adapter_factory=lambda key: StubDocumentAdapter(),
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.import_document("text", "imported-novel", "C:/story.txt")
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="imported-novel").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 0


@pytest.mark.asyncio
async def test_translation_write_path_refreshes_catalog_projection(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "translated-novel",
        {
            "title": "Translated Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"},
                {"id": "2", "num": 2, "title": "Chapter 2", "url": "https://example.com/2"},
            ],
        },
    )
    storage.save_chapter("translated-novel", "1", "raw text", title="Chapter 1")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(final_text="translated body"),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        "stub",
        "translated-novel",
        "1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="translated-novel").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 1
        assert novel.latest_chapter_id == "1"
        assert novel.latest_chapter_number == 1
        assert novel.latest_chapter_title == "Chapter 1"
        assert novel.latest_chapter_updated_at is not None


@pytest.mark.asyncio
async def test_translate_chapters_passes_provider_lock_to_translation_service(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "locked-novel",
        {
            "title": "Locked Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"},
            ],
        },
    )
    storage.save_chapter("locked-novel", "1", "raw text", title="Chapter 1")
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        "stub",
        "locked-novel",
        "1",
        provider_key="gemini",
        provider_model=GEMINI_DEFAULT_MODEL,
        source_language="Japanese",
        allow_cross_provider_fallback=False,
    )

    assert translation.calls[0]["provider_key"] == "gemini"
    assert translation.calls[0]["provider_model"] == GEMINI_DEFAULT_MODEL
    assert translation.calls[0]["allow_cross_provider_fallback"] is False


@pytest.mark.asyncio
async def test_translate_chapters_passes_platform_db_novel_id_to_translation_service(
    orchestration_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "glossary-owned",
        {
            "title": "Glossary Owned",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter("glossary-owned", "1", "Pocott arrives.", title="Chapter 1")
    with SessionLocal() as session:
        novel = Novel(
            slug="glossary-owned",
            title="Glossary Owned",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()
        platform_novel_id = novel.id
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "glossary-owned", "1", source_language="Japanese")

    assert translation.calls[0]["platform_novel_id"] == platform_novel_id


@pytest.mark.asyncio
async def test_translate_chapters_does_not_treat_source_id_as_platform_novel_id(
    orchestration_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "16817330655991571532",
        {
            "title": "Source ID Only",
            "source_key": "kakuyomu",
            "source_language": "Japanese",
            "source_novel_id": "16817330655991571532",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter("16817330655991571532", "1", "Pocott arrives.", title="Chapter 1")
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "16817330655991571532", "1", source_language="Japanese")

    assert translation.calls[0]["platform_novel_id"] is None


@pytest.mark.asyncio
async def test_translate_chapters_injects_approved_db_glossary_through_real_pipeline(
    orchestration_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "glossary-pipeline",
        {
            "title": "Glossary Pipeline",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter(
        "glossary-pipeline",
        "1",
        "Pocott and SMOKE_REVIEWING_CANDIDATE arrive.",
        title="Chapter 1",
    )
    with SessionLocal() as session:
        novel = Novel(
            slug="glossary-pipeline",
            title="Glossary Pipeline",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
            # start at 6 — creating an approved entry below increments it to 7
            glossary_revision=6,
        )
        session.add(novel)
        session.flush()
        repo = GlossaryRepository(session)
        approved = repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term="Pocott",
            term_type="place",
            approved_translation="Pocott",
            status="approved",
        )
        repo.add_glossary_alias(
            entry_id=approved.id,
            novel_id=novel.id,
            alias_text="Pokot",
            alias_type="banned",
        )
        repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term="SMOKE_REVIEWING_CANDIDATE",
            term_type="other",
            approved_translation="Do Not Inject",
            status="candidate",
        )
        session.commit()
    provider = PromptInjectionCaptureProvider()
    translate_stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=orchestration_env["cache"],
        settings_service=orchestration_env["settings"],
        usage_service=orchestration_env["usage"],
        storage=storage,
    )
    translation = TranslationService(
        TranslationPipeline(
            [
                FetchStage(),
                ParseStage(),
                SmartSegmentStage(),
                translate_stage,
                PostProcessStage(),
            ]
        )
    )
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "glossary-pipeline", "1", source_language="Japanese")

    prompt = provider.user_prompts[0]
    assert prompt.count("GLOSSARY FOR THIS NOVEL") == 1
    assert "- Pocott => Pocott" in prompt
    assert 'Pocott: avoid "Pokot"' in prompt
    assert "SMOKE_REVIEWING_CANDIDATE =>" not in prompt
    assert "Do Not Inject" not in prompt
    outputs = storage.read_translation_output(
        "glossary-pipeline",
        chunk_id="c0001",
        chapter_ids=["1"],
    )
    output = outputs[-1]
    assert output["glossary_hash"]
    assert output["glossary_revision"] == 7
    assert output["glossary_injected_term_count"] == 1
    translated = storage.load_translated_chapter("glossary-pipeline", "1")
    assert translated is not None
    assert translated["glossary_revision"] == 7
    assert translated["glossary_injected_term_count"] == 1


@pytest.mark.asyncio
async def test_retranslate_chapter_preserves_platform_db_novel_id(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "retry-glossary",
        {
            "title": "Retry Glossary",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter("retry-glossary", "1", "Pocott arrives.", title="Chapter 1")
    with SessionLocal() as session:
        novel = Novel(
            slug="retry-glossary",
            title="Retry Glossary",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()
        platform_novel_id = novel.id
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.retranslate_chapter("stub", "retry-glossary", "1", source_language="Japanese")

    assert translation.calls[0]["platform_novel_id"] == platform_novel_id


@pytest.mark.asyncio
async def test_runtime_orchestration_sim_scopes_full_failure_and_small_retry(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "runtime-scope-novel",
        {
            "title": "Runtime Scope Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"},
                {"id": "2", "num": 2, "title": "Chapter 2", "url": "https://example.com/2"},
            ],
        },
    )
    storage.save_chapter("runtime-scope-novel", "1", "[P p0001]\nchapter one", title="Chapter 1")
    storage.save_chapter(
        "runtime-scope-novel",
        "2",
        "[P p0001]\nchapter two first paragraph\n\n[P p0002]\nchapter two second paragraph",
        title="Chapter 2",
    )
    translation = RuntimeSimulationTranslationService(storage, fail_chapter_once="2")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        "stub",
        "runtime-scope-novel",
        "1",
        provider_key="mock",
        provider_model="mock-1.0",
        job_id="job_chapter_1",
        activity_id="activity_chapter_1",
        source_language="Japanese",
    )
    with pytest.raises(RuntimeError, match="simulated full chunk failure"):
        await orchestrator.translate_chapters(
            "stub",
            "runtime-scope-novel",
            "2",
            provider_key="mock",
            provider_model="mock-1.0",
            job_id="job_chapter_2_full",
            activity_id="activity_chapter_2_full",
            source_language="Japanese",
        )
    await orchestrator.translate_chapters(
        "stub",
        "runtime-scope-novel",
        "2",
        provider_key="mock",
        provider_model="mock-1.0",
        job_id="job_chapter_2_small_retry",
        activity_id="activity_chapter_2_small_retry",
        force=True,
        source_language="Japanese",
    )

    chapter_1_chunk = storage.read_translation_chunks(
        "runtime-scope-novel",
        translation_run_id="job_chapter_1",
        chapter_ids=["1"],
    )[0]
    chapter_2_full_chunk = storage.read_translation_chunks(
        "runtime-scope-novel",
        translation_run_id="job_chapter_2_full",
        chapter_ids=["2"],
    )[0]
    chapter_2_retry_chunk = storage.read_translation_chunks(
        "runtime-scope-novel",
        translation_run_id="job_chapter_2_small_retry",
        chapter_ids=["2"],
    )[0]
    assert {
        chapter_1_chunk["runtime_key"],
        chapter_2_full_chunk["runtime_key"],
        chapter_2_retry_chunk["runtime_key"],
    } == {
        "runtime-scope-novel:job_chapter_1:1:c0001",
        "runtime-scope-novel:job_chapter_2_full:2:c0001",
        "runtime-scope-novel:job_chapter_2_small_retry:2:c0001",
    }
    assert chapter_2_full_chunk["status"] == "needs_retry"
    assert chapter_2_retry_chunk["status"] == "translated"
    assert chapter_2_retry_chunk["attempt_count"] == 1

    full_attempt = storage.list_chunk_attempt_records(
        novel_id="runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_2_full",
        chapter_ids=["2"],
    )[0]
    retry_attempt = storage.list_chunk_attempt_records(
        novel_id="runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_2_small_retry",
        chapter_ids=["2"],
    )[0]
    assert full_attempt["attempt_number"] == 2
    assert full_attempt["status"] == "failed"
    assert retry_attempt["attempt_number"] == 1
    assert retry_attempt["status"] == "succeeded"

    chapter_1_output = storage.read_translation_output(
        "runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_1",
        chapter_ids=["1"],
    )[0]
    retry_output = storage.read_translation_output(
        "runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_2_small_retry",
        chapter_ids=["2"],
    )[0]
    assert chapter_1_output["translated_text"] == "translated chapter 1"
    assert retry_output["translated_text"] == "translated chapter 2"
    assert chapter_1_output["runtime_key"] != retry_output["runtime_key"]

    retry_states = storage.load_chunk_states(
        novel_id="runtime-scope-novel",
        chapter_id="2",
        translation_run_id="job_chapter_2_small_retry",
    )
    full_states = storage.load_chunk_states(
        novel_id="runtime-scope-novel",
        chapter_id="2",
        translation_run_id="job_chapter_2_full",
    )
    assert retry_states[0]["attempt_number"] == 1
    assert retry_states[0]["status"] == "translated"
    assert full_states[0]["attempt_number"] == 2
    assert full_states[0]["status"] == "needs_retry"

    assert storage.list_pipeline_events(job_id="job_chapter_1")
    assert storage.list_pipeline_events(job_id="job_chapter_2_full")
    assert storage.list_pipeline_events(job_id="job_chapter_2_small_retry")
    runtime_dir = storage._translation_runtime_dir()
    trace_dir = storage._trace_dir()
    assert (runtime_dir / "chunks.json").exists()
    assert (runtime_dir / "chunk_attempts.json").exists()
    assert (runtime_dir / "outputs.json").exists()
    assert (trace_dir / "chunk_states.json").exists()
    assert (trace_dir / "pipeline_events.json").exists()


@pytest.mark.asyncio
async def test_translation_service_generates_isolated_manual_run_ids() -> None:
    capture = RunIdCaptureStage()
    service = TranslationService(TranslationPipeline([capture]))

    first = await service.translate_chapter(source_adapter=None, chapter_url="manual-1")
    second = await service.translate_chapter(source_adapter=None, chapter_url="manual-2")
    stable = await service.translate_chapter(
        source_adapter=None,
        chapter_url="stable",
        job_id="job_stable",
        activity_id="activity_stable",
    )

    assert first.metadata["translation_run_id"].startswith("translation_run_")
    assert second.metadata["translation_run_id"].startswith("translation_run_")
    assert first.metadata["translation_run_id"] != second.metadata["translation_run_id"]
    assert stable.metadata["translation_run_id"] == "job_stable"
    assert capture.run_ids == [
        first.metadata["translation_run_id"],
        second.metadata["translation_run_id"],
        "job_stable",
    ]


def test_gemini_model_candidates_default_to_stable_flash_lite() -> None:
    candidates = model_candidates("gemini", None, [GEMINI_FALLBACK_MODEL])

    assert len(candidates) >= 1
    assert candidates[0] == GEMINI_DEFAULT_MODEL
    # When no requested_model is given, the first supported model is included
    # as an additional candidate after defaults and fallbacks.
    assert GEMINI_FALLBACK_MODEL in candidates
    assert not candidates[0].endswith("-preview")


def test_gemini_model_candidates_preserve_explicit_override() -> None:
    candidates = model_candidates("gemini", GEMINI_FALLBACK_MODEL, [GEMINI_DEFAULT_MODEL])

    assert candidates[:2] == [GEMINI_FALLBACK_MODEL, GEMINI_DEFAULT_MODEL]


@pytest.mark.asyncio
async def test_scrape_metadata_translates_title_author_and_chapter_titles(orchestration_env) -> None:
    provider = BatchMetadataProvider()
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

    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert metadata["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert metadata["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    stored = storage.load_metadata("novel-1")
    assert stored is not None
    index_entry = storage._load_index()["novel-1"]
    folder_name = index_entry["folder_name"]
    assert folder_name == stored["folder_name"]
    assert folder_name == "translated-original-novel"
    metadata_path = storage._folder_path(folder_name) / "metadata.json"
    assert metadata_path.exists()
    assert stored["translated_title"] == "[TRANSLATED] Original Novel"
    assert stored["translated_author"] == "[TRANSLATED] Original Author"
    assert stored["metadata_translation_status"] == "completed"
    assert stored["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert stored["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert stored["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert stored["authors"]["translated"] == "[TRANSLATED] Original Author"
    assert provider.call_count == 2
    assert orchestration_env["usage"].summary(all_days=True)["total_requests"] == 2


@pytest.mark.asyncio
async def test_scrape_metadata_batches_title_author_and_synopsis(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    source = SynopsisSource()
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["translated_synopsis"] == "[TRANSLATED] Original Synopsis"
    stored = orchestration_env["storage"].load_metadata("novel-1")
    assert stored["translated_synopsis"] == "[TRANSLATED] Original Synopsis"
    assert stored["metadata_translation_status"] == "completed"
    first_batch = json.loads(provider.prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert [item["id"] for item in first_batch["items"]] == ["novel_title", "author", "synopsis"]


@pytest.mark.asyncio
async def test_scrape_metadata_retranslates_source_identical_previous_metadata(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "translated_title": "Original Novel",
            "author": "Original Author",
            "translated_author": "Original Author",
            "chapters": [
                {
                    "id": "1",
                    "title": "Chapter One",
                    "translated_title": "Chapter One",
                },
                {
                    "id": "2",
                    "title": "Chapter Two",
                    "translated_title": "Chapter Two",
                },
            ],
        },
    )

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

    assert provider.call_count == 2
    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert metadata["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"


@pytest.mark.asyncio
async def test_scrape_metadata_falls_back_between_gemini_models(orchestration_env) -> None:
    provider = GeminiFallbackProvider()
    source = StubSource()
    settings = orchestration_env["settings"]
    settings.set_preferred_provider("gemini")
    settings.set_preferred_model(GEMINI_DEFAULT_MODEL)
    settings.set_api_key("gemini-key", provider_key="gemini")
    orchestration_env["cache"].set(
        "metadata:chapter_title:English:第10話　初スカート、お披露目",
        "gemini",
        GEMINI_DEFAULT_MODEL,
        "Episode",
    )

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert provider.models_seen[:2] == [GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL]
    assert metadata["translated_title"] == f"[{GEMINI_FALLBACK_MODEL}] Original Novel"
    assert metadata["metadata_translation_status"] == "completed"


@pytest.mark.asyncio
async def test_scrape_metadata_retries_incomplete_chapter_title_translation(orchestration_env) -> None:
    provider = PartialGeminiTitleProvider()
    source = PartialTitleSource()
    settings = orchestration_env["settings"]
    settings.set_preferred_provider("gemini")
    settings.set_preferred_model(GEMINI_DEFAULT_MODEL)
    settings.set_api_key("gemini-key", provider_key="gemini")

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("novel18_syosetu", "n0813kx", mode="update")

    assert metadata["metadata_translation_status"] == "completed"
    assert metadata["chapters"][0]["translated_title"] == "Episode 10: First Skirt Reveal"
    assert GEMINI_DEFAULT_MODEL in provider.models_seen


@pytest.mark.asyncio
async def test_metadata_chapter_titles_batch_by_default_size(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [{"id": str(index), "num": index, "title": f"Chapter {index}"} for index in range(1, 31)],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    batch_prompts = [prompt for prompt in provider.prompts if "<metadata_items>" in prompt]
    assert len(batch_prompts) == 2
    first_batch = json.loads(batch_prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    second_batch = json.loads(batch_prompts[1].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert len(first_batch["items"]) == 25
    assert len(second_batch["items"]) == 5
    assert translated["chapters"][29]["translated_title"] == "[TRANSLATED] Chapter 30"


@pytest.mark.asyncio
async def test_metadata_chapter_title_batch_deduplicates_exact_repeated_titles(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [
            {"id": "1", "num": 1, "title": "Interlude"},
            {"id": "2", "num": 2, "title": "Interlude"},
            {"id": "3", "num": 3, "title": "Finale"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    batch = json.loads(provider.prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert [item["source_text"] for item in batch["items"]] == ["Interlude", "Finale"]
    assert [chapter["translated_title"] for chapter in translated["chapters"]] == [
        "[TRANSLATED] Interlude",
        "[TRANSLATED] Interlude",
        "[TRANSLATED] Finale",
    ]


@pytest.mark.asyncio
async def test_metadata_batch_skips_reusable_and_cached_fields(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    cache = orchestration_env["cache"]
    cache.set("metadata:chapter_title:English:Cached Chapter", "mock", "mock-1.0", "Cached Translation")
    metadata = {
        "source_key": "syosetu_ncode",
        "title": "Original Novel",
        "translated_title": "Translated Novel",
        "metadata_translation_prompt_version": "metadata-literal-v3",
        "chapters": [
            {"id": "1", "num": 1, "title": "Cached Chapter"},
            {"id": "2", "num": 2, "title": "Needs Batch"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=cache,
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata, existing_metadata=metadata)

    assert provider.call_count == 1
    batch = json.loads(provider.prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert [item["source_text"] for item in batch["items"]] == ["Needs Batch"]
    assert translated["translated_title"] == "Translated Novel"
    assert translated["chapters"][0]["translated_title"] == "Cached Translation"
    assert translated["chapters"][1]["translated_title"] == "[TRANSLATED] Needs Batch"


@pytest.mark.asyncio
async def test_metadata_invalid_batch_json_falls_back_to_individual_translation(orchestration_env) -> None:
    provider = BatchMetadataProvider(invalid_batch_json=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "title": "Original Novel",
        "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["translated_title"] == "[TRANSLATED] Original Novel"
    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert provider.call_count == 8


@pytest.mark.asyncio
async def test_metadata_batch_fenced_json_is_extracted(orchestration_env) -> None:
    provider = BatchMetadataProvider(fenced_batch_json=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "title": "Original Novel",
        "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["translated_title"] == "[TRANSLATED] Original Novel"
    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_metadata_batch_commentary_with_single_json_object_is_extracted(orchestration_env) -> None:
    provider = BatchMetadataProvider(commentary_batch_json=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_metadata_duplicate_batch_item_id_falls_back_safely(orchestration_env) -> None:
    provider = BatchMetadataProvider(duplicate_first_id=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [
            {"id": "1", "num": 1, "title": "Chapter One"},
            {"id": "2", "num": 2, "title": "Chapter Two"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert translated["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert provider.call_count == 5


@pytest.mark.asyncio
async def test_metadata_missing_batch_item_id_falls_back_safely(orchestration_env) -> None:
    provider = BatchMetadataProvider(omit_ids={"chapter:2"})
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [
            {"id": "1", "num": 1, "title": "Chapter One"},
            {"id": "2", "num": 2, "title": "Chapter Two"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert translated["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert provider.call_count == 5


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
async def test_scrape_metadata_missing_gemini_key_never_calls_dummy_provider(orchestration_env) -> None:
    provider = MockTranslationProvider(key="dummy", model="dummy")
    source = StubSource()
    settings = orchestration_env["settings"]
    settings.set_preferred_provider("gemini")
    settings.set_preferred_model("gemini-2.0-flash")
    settings.clear_api_key("gemini")

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert provider.call_count == 0
    assert metadata["metadata_translation_status"] == "unavailable"
    assert metadata["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert "metadata_translation_error" not in metadata
    assert "translated_title" not in metadata


@pytest.mark.asyncio
async def test_scrape_metadata_failed_translation_preserves_source_fields_without_fake_translations(
    orchestration_env,
) -> None:
    provider = FailingMetadataProvider()
    source = SynopsisSource()

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")
    stored = orchestration_env["storage"].load_metadata("novel-1")

    assert metadata["title"] == "Original Novel"
    assert metadata["author"] == "Original Author"
    assert metadata["synopsis"] == "Original Synopsis"
    assert metadata["chapters"][0]["title"] == "Chapter One"
    assert metadata["metadata_translation_status"] == "failed"
    assert metadata["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert len(metadata["metadata_translation_error"]) <= 500
    assert "translated_title" not in metadata
    assert "translated_author" not in metadata
    assert "translated_synopsis" not in metadata
    assert "translated_title" not in metadata["chapters"][0]
    assert stored["metadata_translation_status"] == "failed"
    assert stored["metadata_translation_error"] == metadata["metadata_translation_error"]
    assert stored["chapters"][1]["title"] == "Chapter Two"


def test_estimate_translation_requests_counts_metadata_and_body_chunks(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "title": "Original Novel",
            "author": "Original Author",
            "synopsis": "Original Synopsis",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One"},
                {"id": "2", "num": 2, "title": "Chapter Two"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "a" * 3000)
    storage.save_chapter("novel-1", "2", "\n\n".join(["b" * 3000, "c" * 3000]))
    provider = MockTranslationProvider(key="mock", model="mock-1.0")
    translation = StubTranslationService()
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["metadata_requests"]["title"] == 1
    assert estimate["metadata_requests"]["author"] == 1
    assert estimate["metadata_requests"]["synopsis"] == 1
    assert estimate["metadata_requests"]["novel_fields"] == 1
    assert estimate["metadata_requests"]["chapter_titles"] == 1
    assert estimate["metadata_requests"]["unique_chapter_titles"] == 2
    assert estimate["metadata_requests"]["chapter_title_batch_size"] == 25
    assert estimate["metadata_requests"]["metadata_batching"] is True
    assert estimate["metadata_requests"]["total"] == 2
    assert estimate["body_requests"]["estimated_chunks"] == 2
    assert estimate["body_requests"]["chapters_with_text"] == 2
    assert estimate["body_requests"]["chapters_missing_text"] == []
    assert estimate["body_requests"]["per_chapter"] == [
        {"chapter_id": "1", "source_chars": 3000, "paragraphs": 1, "chunks": 1},
        {"chapter_id": "2", "source_chars": 6002, "paragraphs": 2, "chunks": 1},
    ]
    assert estimate["total_estimated_requests"] == 4
    assert estimate["assumptions"]["provider_calls"] is False
    assert estimate["assumptions"]["metadata_batching"] is True
    assert estimate["assumptions"]["adaptive_chunking"] is True
    assert estimate["assumptions"]["adaptive_soft_target_chars"] == 5800
    assert estimate["assumptions"]["adaptive_hard_max_chars"] == 7000
    assert estimate["assumptions"]["conditional_overlap"] is True
    assert estimate["assumptions"]["default_overlap_paragraphs"] == 0
    assert estimate["assumptions"]["unsafe_boundary_overlap_paragraphs"] == 1
    assert estimate["assumptions"]["boundary_context_chars"] == 160
    assert estimate["assumptions"]["paragraph_hash_lineage"] is True
    assert estimate["assumptions"]["delta_retranslation_enabled"] is True
    assert estimate["assumptions"]["delta_require_structured_paragraph_map"] is True
    assert estimate["assumptions"]["delta_force_full_on_unsafe"] is True
    assert provider.call_count == 0
    assert translation.calls == []


def test_estimate_translation_requests_uses_adaptive_body_chunk_count(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000]))
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["body_requests"]["estimated_chunks"] == 2
    assert estimate["body_requests"]["per_chapter"] == [
        {"chapter_id": "1", "source_chars": 12006, "paragraphs": 4, "chunks": 2}
    ]
    assert estimate["assumptions"]["adaptive_chunking"] is True


def _save_delta_fixture(
    storage: StorageService,
    *,
    old_paragraphs: list[str],
    new_paragraphs: list[str],
    novel_id: str = "novel-delta",
) -> None:
    storage.save_metadata(
        novel_id,
        {
            "source_key": "syosetu_ncode",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
        },
    )
    storage.save_chapter(novel_id, "1", "\n\n".join(new_paragraphs))
    old_lineage = [
        {
            "chapter_id": "1",
            "paragraph_id": f"p{index:04d}",
            "paragraph_index": index,
            "source_hash": paragraph_source_hash(text),
            "char_count": len(text),
        }
        for index, text in enumerate(old_paragraphs, start=1)
    ]
    storage.save_translation_chunks(
        novel_id,
        [
            {
                "chunk_id": "c0001",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in old_lineage],
                "paragraph_hashes": [item["source_hash"] for item in old_lineage],
                "paragraph_lineage": old_lineage,
                "source_text": "\n\n".join(old_paragraphs),
                "status": "translated",
            }
        ],
    )


def _delta_estimate(orchestration_env, *, old_paragraphs: list[str], new_paragraphs: list[str]) -> dict[str, Any]:
    storage = orchestration_env["storage"]
    _save_delta_fixture(storage, old_paragraphs=old_paragraphs, new_paragraphs=new_paragraphs)
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )
    return orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-delta",
        chapters="all",
    )


def test_estimate_translation_requests_delta_identical_has_no_windows(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["A.", "B.", "C."])

    assert estimate["body_requests"]["estimated_chunks"] == 1
    assert estimate["delta"]["available"] is True
    assert estimate["delta"]["delta_body_requests"] == 0
    assert estimate["delta"]["unchanged_paragraphs"] == 3
    assert estimate["delta"]["changed_windows"] == []
    assert estimate["total_estimated_requests"] == estimate["metadata_requests"]["total"] + 1


def test_estimate_translation_requests_delta_changed_paragraph_has_padded_window(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["A.", "Bee.", "C."]
    )

    assert estimate["delta"]["changed_paragraphs"] == 1
    assert estimate["delta"]["delta_body_requests"] == 1
    assert estimate["delta"]["changed_windows"] == [
        {
            "chapter_id": "1",
            "start_paragraph_index": 1,
            "end_paragraph_index": 3,
            "paragraph_hashes": [
                paragraph_source_hash("A."),
                paragraph_source_hash("Bee."),
                paragraph_source_hash("C."),
            ],
            "estimated_chunks": 1,
        }
    ]


def test_estimate_translation_requests_delta_inserted_paragraph_has_window(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "C."], new_paragraphs=["A.", "B.", "C."])

    assert estimate["delta"]["inserted_paragraphs"] == 1
    assert estimate["delta"]["changed_windows"][0]["start_paragraph_index"] == 1
    assert estimate["delta"]["changed_windows"][0]["end_paragraph_index"] == 3


def test_estimate_translation_requests_delta_deleted_paragraph_has_conservative_window(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["A.", "C."])

    assert estimate["delta"]["deleted_paragraphs"] == 1
    assert estimate["delta"]["delta_body_requests"] == 1
    assert estimate["delta"]["changed_windows"][0]["chapter_id"] == "1"


def test_estimate_translation_requests_delta_repeated_hashes_are_ambiguous(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env, old_paragraphs=["A.", "X.", "X.", "C."], new_paragraphs=["A.", "X.", "X.", "C."]
    )

    assert estimate["delta"]["ambiguous_paragraphs"] == 2
    assert estimate["delta"]["unchanged_paragraphs"] == 2
    assert estimate["delta"]["delta_body_requests"] == 1


def test_estimate_translation_requests_delta_moved_paragraph_is_ambiguous(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["B.", "A.", "C."])

    assert estimate["delta"]["ambiguous_paragraphs"] >= 1
    assert estimate["delta"]["unchanged_paragraphs"] < 3
    assert estimate["delta"]["delta_body_requests"] == 1


def test_estimate_translation_requests_delta_overlapping_windows_merge(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env,
        old_paragraphs=["A.", "B.", "C.", "D.", "E."],
        new_paragraphs=["A.", "Bee.", "C.", "Dee.", "E."],
    )

    assert estimate["delta"]["changed_paragraphs"] == 2
    assert len(estimate["delta"]["changed_windows"]) == 1
    assert estimate["delta"]["changed_windows"][0]["start_paragraph_index"] == 1
    assert estimate["delta"]["changed_windows"][0]["end_paragraph_index"] == 5


def test_estimate_translation_requests_delta_missing_old_lineage_unavailable(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "syosetu_ncode",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-delta",
        chapters="all",
    )

    assert estimate["delta"]["available"] is False
    assert estimate["delta"]["delta_body_requests"] == estimate["body_requests"]["estimated_chunks"]


def test_estimate_translation_requests_delta_older_records_without_hashes_unavailable(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "syosetu_ncode",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.")
    storage.save_translation_chunks(
        "novel-delta",
        [{"chunk_id": "legacy_c0001", "chapter_ids": ["1"], "paragraph_ids": ["p0001"], "source_text": "A."}],
    )
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-delta",
        chapters="all",
    )

    assert estimate["delta"]["available"] is False
    assert "falling back to full body estimate" in " ".join(estimate["delta"]["notes"])


def test_estimate_translation_requests_delta_uses_active_segmentation_for_window_chunks(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "b" * 3000, "c" * 3000, "d" * 3000, "C."],
    )

    assert estimate["body_requests"]["estimated_chunks"] == 2
    assert estimate["delta"]["delta_body_requests"] == 2


def _save_delta_execution_fixture(
    storage: StorageService,
    *,
    old_paragraphs: list[str],
    new_paragraphs: list[str],
    old_translations: list[str] | None = None,
    structured: bool = True,
    translated_chapter_text: str | None = None,
) -> None:
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "\n\n".join(new_paragraphs))
    old_lineage = [
        {
            "chapter_id": "1",
            "paragraph_id": f"p{index:04d}",
            "paragraph_index": index,
            "source_hash": paragraph_source_hash(text),
            "char_count": len(text),
        }
        for index, text in enumerate(old_paragraphs, start=1)
    ]
    storage.save_translation_chunks(
        "novel-delta",
        [
            {
                "chunk_id": "c0001",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in old_lineage],
                "paragraph_hashes": [item["source_hash"] for item in old_lineage],
                "paragraph_lineage": old_lineage,
                "source_text": "\n\n".join(old_paragraphs),
                "status": "translated",
            }
        ],
    )
    if structured:
        translations = old_translations or [f"old:{text}" for text in old_paragraphs]
        storage.save_translation_output(
            {
                "output_id": "old_c0001",
                "chunk_id": "c0001",
                "novel_id": "novel-delta",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in old_lineage],
                "paragraph_hashes": [item["source_hash"] for item in old_lineage],
                "paragraph_lineage": old_lineage,
                "translated_text": "\n\n".join(translations),
                "structured_paragraph_map": [
                    {
                        "chapter_id": "1",
                        "paragraph_id": item["paragraph_id"],
                        "translated_text": translations[index],
                    }
                    for index, item in enumerate(old_lineage)
                ],
            }
        )
    if translated_chapter_text is not None:
        storage.save_translated_chapter(
            "novel-delta", "1", translated_chapter_text, provider_key="mock", provider_model="mock-1.0"
        )


async def _run_delta_translate(
    orchestration_env, translation: StubTranslationService
) -> tuple[StorageService, StubTranslationService]:
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )
    return storage, translation


@pytest.mark.asyncio
async def test_delta_disabled_preserves_full_translation_behavior(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(final_text="full translation")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full translation"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "delta_disabled"


@pytest.mark.asyncio
async def test_delta_unchanged_chapter_reuses_whole_old_output(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(final_text="full translation")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole chapter"
    assert translation.calls == []
    assert saved["confidence_details"]["delta"]["mode"] == "whole_chapter_unchanged"


@pytest.mark.asyncio
async def test_delta_changed_paragraph_translates_window_and_reassembles(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(paragraph_prefix="new:")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new:A.\n\nnew:Bee.\n\nnew:C."
    assert len(translation.calls) == 1
    assert translation.calls[0]["json_output"] is True
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]


@pytest.mark.asyncio
async def test_delta_inserted_paragraph_reassembles_correctly(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "C."],
        new_paragraphs=["A.", "B.", "C."],
        old_translations=["old:A.", "old:C."],
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(paragraph_prefix="new:"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new:A.\n\nnew:B.\n\nnew:C."


@pytest.mark.asyncio
async def test_delta_deleted_paragraph_reassembles_without_stale_translation(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(paragraph_prefix="new:"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    text = saved["text"]
    assert "old:B." not in text
    assert text == "new:A.\n\nnew:C."


@pytest.mark.asyncio
async def test_delta_ambiguous_region_falls_back_to_full_translation(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "X.", "X.", "C."],
        new_paragraphs=["A.", "X.", "X.", "C."],
        old_translations=["old:A.", "old:X1", "old:X2", "old:C."],
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(final_text="full fallback")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full fallback"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "ambiguous_or_moved_region"


@pytest.mark.asyncio
async def test_delta_missing_lineage_falls_back_to_full_translation(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.")

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(final_text="full fallback"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full fallback"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "missing_lineage"


@pytest.mark.asyncio
async def test_delta_missing_structured_map_falls_back_for_changed_chapter(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        structured=False,
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(final_text="full fallback"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full fallback"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "missing_structured_paragraph_map"


@pytest.mark.asyncio
async def test_delta_window_missing_structured_output_falls_back(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(final_text="plain window"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "plain window"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"


@pytest.mark.asyncio
async def test_force_retranslate_bypasses_delta_reuse(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
    )
    storage = orchestration_env["storage"]
    translation = StubTranslationService(final_text="forced full")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        force=True,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved["text"] == "forced full"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "force_full_translation"


def test_estimate_translation_requests_counts_batched_unique_chapter_titles(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "chapters": [
                {"id": str(index), "num": index, "title": "Repeated" if index <= 10 else f"Chapter {index}"}
                for index in range(1, 31)
            ],
        },
    )
    for index in range(1, 31):
        storage.save_chapter("novel-1", str(index), "text")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["metadata_requests"]["unique_chapter_titles"] == 21
    assert estimate["metadata_requests"]["chapter_titles"] == 1
    assert estimate["metadata_requests"]["total"] == 1
    assert estimate["body_requests"]["estimated_chunks"] == 30


def test_estimate_translation_requests_reports_missing_raw_chapter_text(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "kakuyomu",
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One"},
                {"id": "2", "num": 2, "title": "Chapter Two"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "available text")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="kakuyomu",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["body_requests"]["estimated_chunks"] == 1
    assert estimate["body_requests"]["chapters_with_text"] == 1
    assert estimate["body_requests"]["chapters_missing_text"] == ["2"]
    assert estimate["body_requests"]["per_chapter"][0]["chapter_id"] == "1"


def test_estimate_translation_requests_can_exclude_or_include_translated_chapters(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "title": "Original Novel",
            "metadata_translation_prompt_version": "metadata-literal-v2",
            "translated_title": "Translated Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "translated_title": "Translated One"},
                {"id": "2", "num": 2, "title": "Chapter Two", "translated_title": "Translated Two"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "already translated text")
    storage.save_chapter("novel-1", "2", "pending text")
    storage.save_translated_chapter("novel-1", "1", "Translated body", provider_key="mock", provider_model="mock-1.0")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    excluded = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )
    included = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
        include_already_translated=True,
    )

    assert excluded["chapters_selected"] == 2
    assert excluded["chapters_included"] == 1
    assert excluded["body_requests"]["chapters_skipped_translated"] == ["1"]
    assert excluded["body_requests"]["per_chapter"] == [
        {"chapter_id": "2", "source_chars": len("pending text"), "paragraphs": 1, "chunks": 1}
    ]
    assert included["chapters_included"] == 2
    assert included["body_requests"]["chapters_skipped_translated"] == []
    assert [item["chapter_id"] for item in included["body_requests"]["per_chapter"]] == ["1", "2"]


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
    storage.save_translated_chapter(
        "novel-1", "1", "already translated", provider_key="mock", provider_model="mock-1.0"
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

    with pytest.raises(RuntimeError, match="nothing_to_translate"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_extract_glossary_llm_mode_enforces_json_schema(orchestration_env) -> None:
    provider = GlossarySchemaCaptureProvider()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-llm",
        {
            "title": "Glossary LLM Novel",
            "source_language": "Japanese",
            "input_adapter_key": "web",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-llm/1"},
            ],
        },
    )
    storage.save_chapter("novel-llm", "1", "魔導具は王都で使われる。")

    settings = orchestration_env["settings"]
    settings.set_llm_step_config("glossary_extraction", provider="mock", model="mock-1.0")

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.extract_glossary_terms(
        "novel-llm",
        config={
            "mode": "llm",
            "provider": "mock",
            "model": "mock-1.0",
        },
    )

    assert summary["config"]["mode"] == "llm"
    assert summary["config"]["llm_candidates"] == 2
    json_schema = provider.last_kwargs.get("json_schema")
    assert isinstance(json_schema, dict)
    assert json_schema.get("required") == ["terms"]
    assert "terms" in (json_schema.get("properties") or {})

    glossary = storage.load_glossary("novel-llm")
    sources = {str(entry.get("source")) for entry in glossary if isinstance(entry, dict)}
    assert "魔導具" in sources
    assert "王都" in sources


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

    with patch(
        "novelai.services.novel_orchestration_service.safely_refresh_catalog_projection_after_storage_write"
    ) as refresh_projection:
        await orchestrator.translate_chapters("stub", "novel-1", "1", force=True)

    assert restore_calls
    assert restore_calls[-1] == ("novel-1", "1", "resume")
    refresh_projection.assert_called_once_with(
        "novel-1",
        storage,
        context="checkpoint_restore",
    )
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
async def test_translate_chapters_preflight_blocks_pending_db_glossary_status(orchestration_env) -> None:
    source = StubSource()
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "glossary-gate",
        {
            "title": "Glossary Gate",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/glossary-gate/1"},
            ],
        },
    )
    with SessionLocal() as session:
        novel = Novel(slug="glossary-gate", title="Glossary Gate", language="ja", publication_status="ongoing")
        session.add(novel)
        session.flush()
        GlossaryRepository(session).create_glossary_entry(
            novel_id=novel.id,
            canonical_term="Pocott",
            term_type="place",
            status="candidate",
        )
        session.commit()

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="glossary_gate_pending"):
        await orchestrator.translate_chapters("stub", "glossary-gate", "1")


@pytest.mark.asyncio
async def test_translate_chapters_allows_ready_status_and_skip_override(orchestration_env) -> None:
    source = StubSource()
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    for novel_id in ("glossary-ready", "glossary-override"):
        storage.save_metadata(
            novel_id,
            {
                "title": novel_id,
                "source_language": "Japanese",
                "onboarding_status": "ready_for_translation",
                "chapters": [
                    {"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{novel_id}/1"},
                ],
            },
        )
    with SessionLocal() as session:
        session.add(
            Novel(
                slug="glossary-ready",
                title="Glossary Ready",
                language="ja",
                publication_status="ongoing",
                glossary_status="glossary_ready",
            )
        )
        session.add(
            Novel(
                slug="glossary-override",
                title="Glossary Override",
                language="ja",
                publication_status="ongoing",
                glossary_status="glossary_pending",
            )
        )
        session.commit()

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

    await orchestrator.translate_chapters("stub", "glossary-ready", "1")
    await orchestrator.translate_chapters("stub", "glossary-override", "1", skip_glossary_gate=True)

    assert [call["novel_id"] for call in translation.calls] == ["glossary-ready", "glossary-override"]


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
    storage.save_translated_chapter("novel-1", "1", "old translation", provider_key="mock", provider_model="mock-1.0")

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


@pytest.mark.asyncio
async def test_review_glossary_terms_auto_approves_translated_targets(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata("novel-1", {"title": "Original", "chapters": []})
    storage.save_glossary(
        "novel-1",
        [
            {"source": "勇者", "target": "hero", "status": "pending", "locked": True},
            {"source": "魔王", "target": "", "status": "pending", "locked": True},
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

    summary = await orchestrator.review_glossary_terms("novel-1")

    assert summary["approved"] == 1
    assert summary["pending"] == 1
    entries = storage.load_glossary("novel-1")
    by_source = {str(item.get("source")): item for item in entries if isinstance(item, dict)}
    assert by_source["勇者"]["status"] == "approved"
    assert by_source["魔王"]["status"] == "pending"


@pytest.mark.asyncio
async def test_translate_chapters_persists_confidence_metadata(orchestration_env) -> None:
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

    translation = StubTranslationService(final_text="raw text")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "novel-1", "1", confidence_threshold=0.55)

    assert storage.load_translated_chapter("novel-1", "1") is None
    versions = storage.list_translated_chapter_versions("novel-1", "1")
    assert len(versions) == 1
    assert versions[0]["active"] is False
    assert isinstance(versions[0].get("confidence_score"), float)
    assert versions[0].get("polish_needed") is True
    assert isinstance(versions[0].get("confidence_details"), dict)


@pytest.mark.asyncio
async def test_pipeline_phase_two_blocks_when_pending_glossary(orchestration_env) -> None:
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
    storage.save_glossary("novel-1", [{"source": "勇者", "target": "hero", "status": "pending", "locked": True}])

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(final_text="translated"),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.run_phased_translation_pipeline(
        source_key="stub",
        novel_id="novel-1",
        chapters="1",
        phase="2",
    )

    assert summary["status"] == "blocked"
    assert summary["blocked"] is True
